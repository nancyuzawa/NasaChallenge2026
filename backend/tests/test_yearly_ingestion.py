"""Regression coverage for annual persistence and interrupted publication."""
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.firms_ingestion import ingest_all
from src.fire_store import insert_frame
from src.parquet_writer import export_source

HEADER = "latitude,longitude,acq_date,acq_time,satellite,confidence,frp\n"


class YearlyIngestionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        # The project directory's year must not filter out valid inputs.
        self.root = Path(self.temp.name) / "NasaChallenge2026"
        self.raw = self.root / "raw"
        self.output = self.root / "processed"
        (self.raw / "modis").mkdir(parents=True)
        (self.raw / "viirs").mkdir()

    def write(self, name, rows):
        path = self.raw / "modis" / name
        path.write_text(HEADER + rows, encoding="utf-8")
        return path

    def run_import(self, **kwargs):
        return ingest_all(self.raw, self.output, chunk_size=1, **kwargs)

    def count(self, table="detections"):
        with closing(sqlite3.connect(self.output / "firewatch.sqlite")) as conn:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_expanding_period_keeps_previous_year_and_exports_low_confidence(self):
        self.write("mixed.csv", "0,0,2020-01-01,5,T,low,1\n1,1,2021-01-01,10,T,0,2\n")
        self.run_import(start_year=2020, end_year=2020)
        self.assertEqual(self.count(), 1)
        self.run_import(start_year=2020, end_year=2021)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.run_import(start_year=2020, end_year=2021), [])
        for year in (2020, 2021):
            folder = self.output / "modis" / str(year) / "unknown"
            parquet = pd.read_parquet(next(folder.glob("*.parquet")))
            csv = pd.read_csv(next(folder.glob("*.csv")), dtype={"acq_time": str})
            self.assertEqual(len(parquet), 1)
            self.assertEqual(csv.iloc[0].acq_time, "0005" if year == 2020 else "0010")
        self.assertEqual(pd.read_parquet(next((self.output / "modis/2020/unknown").glob("*.parquet"))).iloc[0].confidence, "low")

    def test_interrupted_chunk_resumes_without_reinserting_committed_chunk(self):
        self.write("2020.csv", "0,0,2020-01-01,5,T,low,1\n1,1,2020-01-02,10,T,high,2\n")
        calls = []
        def interrupt(conn, frame, **kwargs):
            calls.append(len(frame))
            if len(calls) == 2:
                raise KeyboardInterrupt()
            return insert_frame(conn, frame, **kwargs)
        with patch("src.firms_ingestion.insert_frame", side_effect=interrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_import(start_year=2020, end_year=2020)
        self.assertEqual(self.count("ingestion_staging"), 1)
        self.assertEqual(self.count(), 0)
        with patch("src.firms_ingestion.insert_frame", wraps=insert_frame) as resumed:
            self.run_import(start_year=2020, end_year=2020)
            self.assertEqual(resumed.call_count, 1)
        self.assertEqual(self.count(), 2)
        self.assertEqual(self.count("ingestion_staging"), 0)

    def test_failed_zip_publication_retries_without_rereading_raw(self):
        with ZipFile(self.raw / "viirs/2020.zip", "w") as archive:
            archive.writestr("nested/a.csv", HEADER + "0,0,2020-01-01,5,N20,l,1\n")
            archive.writestr("nested/b.csv", HEADER + "1,1,2020-01-01,5,N20,h,2\n")
        with patch("src.firms_ingestion.export_source", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                self.run_import(start_year=2020, end_year=2020)
        self.assertEqual(self.count(), 2)
        with patch("src.firms_ingestion.iter_csv_files", side_effect=AssertionError("must not reread")):
            self.run_import(start_year=2020, end_year=2020)
        self.assertEqual(len(list(self.output.rglob("*.parquet"))), 1)
        self.assertEqual(sum(len(pd.read_parquet(p)) for p in self.output.rglob("*.parquet")), 2)

    def test_completed_year_survives_next_year_interruption(self):
        self.write("2020.csv", "0,0,2020-01-01,5,T,l,1\n")
        self.write("2021.csv", "bad,header\n")
        # A malformed CSV aborts 2021 after 2020 has been published.
        (self.raw / "modis/2021.csv").write_text("wrong\n1\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_import(start_year=2020, end_year=2021)
        self.assertEqual(self.count(), 1)
        self.assertEqual(len(list((self.output / "modis/2020/unknown").glob("*.parquet"))), 1)

    def test_changed_source_replaces_exports_and_failed_replacement_keeps_old_data(self):
        path = self.write("2020.csv", "0,0,2020-01-01,5,T,l,1\n")
        self.run_import(start_year=2020, end_year=2020)
        path.write_text("wrong\n1\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.run_import(start_year=2020, end_year=2020)
        self.assertEqual(self.count(), 1)
        self.assertEqual(len(pd.read_parquet(next(self.output.rglob("*.parquet")))), 1)
        path.write_text(HEADER, encoding="utf-8")
        self.run_import(start_year=2020, end_year=2020)
        self.assertEqual(self.count(), 0)
        self.assertEqual(list(self.output.rglob("*.parquet")), [])
        self.assertEqual(list(self.output.rglob("*.csv")), [])

    def test_frontend_sees_published_parts_while_wal_writer_stays_open(self):
        import importlib.util
        from src.fire_store import connect
        from src.firms_ingestion import prepare_dataframe
        spec = importlib.util.spec_from_file_location(
            "frontend_yearly_test", Path(__file__).resolve().parents[2] / "frontend/data.py",
        )
        data = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(data)
        database = self.output / "firewatch.sqlite"
        conn = connect(database)
        self.addCleanup(conn.close)
        frame = pd.DataFrame(dict(latitude=[0], longitude=[0], acq_date=["2020-01-01"], acq_time=[5]))
        normalized, _ = prepare_dataframe(frame, "MODIS", "test", 2020, 2020)
        filters = dict(bounds=[-1, -1, 1, 1])
        with patch.dict("os.environ", {"FIREWATCH_DATA": str(self.output)}):
            before = data._signature(filters)
            self.assertTrue(data.daily_data(filters).empty)
            with conn:
                insert_frame(conn, normalized)
            # Staging commits do not expose data before Parquet publication.
            self.assertTrue(data.daily_data(filters).empty)
            self.assertEqual(before, data._signature(filters))
            export_source(conn, self.output, "MODIS", 2020, "test")
            self.assertNotEqual(before, data._signature(filters))
            self.assertEqual(int(data.daily_data(filters).detections.sum()), 1)


if __name__ == "__main__":
    unittest.main()
