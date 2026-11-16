"""Country partitions, numbered parts, and layout migration."""
from contextlib import closing
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.fire_store import connect, insert_frame, readonly
from src.firms_ingestion import ingest_all, prepare_dataframe
from src.parquet_writer import country_from_source, export_source, export_existing, source_id

HEADER = "latitude,longitude,acq_date,acq_time,satellite\n"


class PartitionExportTest(unittest.TestCase):
    def test_country_from_firms_compression_folders_and_zip(self):
        examples = {
            "modis/2020/modis_2020_Brazil.csv": "brazil",
            "viirs/2020/viirs-jpss1_2020_Argentina.csv.gz": "argentina",
            "modis/2020/modis_2020_Antigua_and_Barbuda.csv": "antigua_and_barbuda",
            "viirs/archive.zip::nested/viirs_2020_Chile.csv": "chile",
            "modis/2020/brazil/custom.csv": "brazil",
            "modis/modis_2020_Brazil.csv.zip::data.csv": "brazil",
            "modis/data.csv": "unknown",
        }
        for key, country in examples.items():
            with self.subTest(key=key):
                self.assertEqual(country_from_source(key), country)

    def test_same_country_multiple_sources_numbered_parts_and_shrink(self):
        with tempfile.TemporaryDirectory() as directory, closing(connect(":memory:")) as conn:
            keys = ["modis/2020/brazil/a.csv", "modis/2020/brazil/b.csv"]
            for index, key in enumerate(keys):
                frame, _ = prepare_dataframe(pd.DataFrame({
                    "latitude": [index], "longitude": [0],
                    "acq_date": ["2020-01-01"], "acq_time": [5],
                }), "MODIS", key)
                with conn:
                    insert_frame(conn, frame)
                export_source(conn, directory, "MODIS", 2020, key, batch_size=1)
            folder = Path(directory) / "modis/2020/brazil"
            self.assertEqual(sorted(p.name for p in folder.glob("*.parquet")),
                             ["part-001.parquet", "part-002.parquet"])
            self.assertEqual(sum(pq.read_metadata(p).num_rows for p in folder.glob("*.parquet")), 2)
            with conn:
                conn.execute("DELETE FROM detections WHERE source_file = ?", (keys[0],))
            export_source(conn, directory, "MODIS", 2020, keys[0], batch_size=1)
            self.assertEqual(sorted(p.name for p in folder.glob("*.parquet")), ["part-001.parquet"])
            self.assertEqual(pd.read_parquet(folder / "part-001.parquet").iloc[0].source_file, keys[1])
            self.assertFalse((folder / "part-002.csv").exists())

    def test_zip_countries_are_separate_and_cached_layout_migrates_without_raw_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "raw/viirs").mkdir(parents=True)
            with ZipFile(root / "raw/viirs/2020.zip", "w") as archive:
                archive.writestr("viirs_2020_Brazil.csv", HEADER + "0,0,2020-01-01,5,N20\n")
                archive.writestr("viirs_2020_Chile.csv", HEADER + "1,1,2020-01-01,5,N20\n")
            kwargs = dict(start_year=2020, end_year=2020)
            ingest_all(root / "raw", root / "processed", **kwargs)
            output = root / "processed"
            self.assertTrue((output / "viirs/2020/brazil/part-001.parquet").is_file())
            self.assertTrue((output / "viirs/2020/chile/part-001.parquet").is_file())
            legacy = output / "viirs/year=2020"
            legacy.mkdir()
            key = "viirs/2020.zip::viirs_2020_Brazil.csv"
            old = legacy / f"part-{source_id(key)}.parquet"
            old.write_bytes(b"legacy")
            with closing(connect(output / "firewatch.sqlite")) as conn:
                with conn:
                    conn.execute("UPDATE ingestion_years SET layout_version = 0")
            with patch("src.firms_ingestion.iter_csv_files", side_effect=AssertionError("raw read")):
                ingest_all(root / "raw", output, **kwargs)
            self.assertFalse(old.exists())
            self.assertEqual(ingest_all(root / "raw", output, **kwargs), [])

    def test_export_existing_works_with_readonly_database_and_no_registry(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = root / "input.sqlite"
            with closing(connect(database)) as conn:
                frame, _ = prepare_dataframe(pd.DataFrame({
                    "latitude": [0], "longitude": [0], "acq_date": ["2020-01-01"],
                    "acq_time": [5],
                }), "MODIS", "modis/2020/modis_2020_Brazil.csv")
                with conn:
                    insert_frame(conn, frame)
            with closing(readonly(database)) as conn:
                before = conn.execute("PRAGMA journal_mode").fetchone()
                self.assertEqual(export_existing(conn, root / "output", 2020, 2020), 1)
                self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone(), before)
                self.assertIsNone(conn.execute(
                    "SELECT name FROM sqlite_master WHERE name = 'export_sources'"
                ).fetchone())
            self.assertEqual(pq.read_metadata(root / "output/modis/2020/brazil/part-001.parquet").num_rows, 1)

    def test_empty_export_explains_why_no_files_were_generated(self):
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as directory, closing(connect(":memory:")) as conn:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(export_existing(conn, directory, 2020, 2025), 0)
            self.assertIn("Nenhum dado processado", output.getvalue())
            self.assertIn("sem --export-only", output.getvalue())
            self.assertEqual(list(Path(directory).rglob("*.parquet")), [])


if __name__ == "__main__":
    unittest.main()
