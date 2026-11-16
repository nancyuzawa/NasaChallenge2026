"""Small temporary sources exercise ingestion without the large raw files."""
from pathlib import Path
from contextlib import closing
import csv
import gzip
import sqlite3
import sys
import tempfile
import unittest
from zipfile import ZipFile

import pandas as pd

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.firms_ingestion import ingest_all, prepare_dataframe


class PipelineTest(unittest.TestCase):
    def test_invalid_hours_coordinates_and_dates(self):
        data = pd.DataFrame({"lat":[0,91,0,0,0],"lon":[0]*5,
                             "date":["2025-01-01"]*4+["bad"],"time":[5,500,2460,1261,1200]})
        valid,report = prepare_dataframe(data,"MODIS","test")
        self.assertEqual(len(valid),1)
        self.assertEqual(valid.iloc[0].acq_time,"0005")
        self.assertEqual(report["rows_invalid"],4)

    def test_chunking_compression_duplicate_provenance_and_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = root/"raw"
            (raw/"modis").mkdir(parents=True)
            (raw/"viirs").mkdir()
            content = "latitude,longitude,acq_date,acq_time,satellite\n-22.9,-47.0,2025-01-10,1200,T\n"
            (raw/"modis/a.csv").write_text(content,encoding="utf-8")
            with gzip.open(raw/"modis/b.csv.gz","wt") as stream:
                stream.write(content)
            with ZipFile(raw/"viirs/c.zip","w") as archive:
                archive.writestr("nested/c.csv",content.replace(",T",",N20"))
            output = root/"processed"
            ingest_all(raw,output,chunk_size=1)
            self.assertEqual(ingest_all(raw,output,chunk_size=1),[])
            # Replacing one duplicate source must retain the other source's detection.
            (raw/"modis/a.csv").write_text(content.replace("2025-01-10","2025-02-10"),encoding="utf-8")
            ingest_all(raw,output,chunk_size=1)
            with closing(sqlite3.connect(output/"firewatch.sqlite")) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM (SELECT DISTINCT sensor,satellite,acq_date,acq_time,latitude,longitude FROM detections)").fetchone()[0],3)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],3)
            # Failed replacement leaves prior complete source intact.
            (raw/"modis/a.csv").write_text("wrong\n1\n",encoding="utf-8")
            with self.assertRaises(ValueError):
                ingest_all(raw,output,chunk_size=1)
            with closing(sqlite3.connect(output/"firewatch.sqlite")) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0],3)


if __name__ == "__main__":
    unittest.main()
