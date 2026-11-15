"""DuckDB/frontend integration using synthetic Parquets in temporary folders."""
from contextlib import closing
from datetime import date
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.fire_store import grid
from src.firms_analysis import parquet_files, open_parquets, daily_aggregation, harmonize_monthly


class AnalysisTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.parts = []
        for sensor, count in (("MODIS", 1), ("VIIRS", 2)):
            rows = [self.row(sensor, f"2024-{month:02d}-10", i) for month in (1, 2, 3) for i in range(count)]
            self.write(sensor, 2024, rows)
        self.write("VIIRS", 2025, [self.row("VIIRS", "2025-01-10", i) for i in range(4)])
        # Duplicate a MODIS observation in a second part, with different provenance.
        duplicate = self.row("MODIS", "2024-01-10", 0)
        duplicate["source_file"] = "overlapping_source"
        self.write("MODIS", 2024, [duplicate], part=2)
        spec = importlib.util.spec_from_file_location(
            "analysis_frontend_test", Path(__file__).resolve().parents[2] / "frontend/data.py")
        self.data = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.data)
        self.env = patch.dict(os.environ, {"FIREWATCH_DATA": str(self.root)})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.filters = {"bounds": [-23, -48, -22, -46]}
        self.period = date(2025, 1, 1), date(2025, 1, 31)

    def row(self, sensor, day, position):
        lat, lon = -22.9, -47 + position * .02
        x, y = grid(lat, lon)
        return dict(sensor=sensor, satellite="T" if sensor == "MODIS" else "N20",
                    acq_date=day, acq_time="0005", latitude=lat, longitude=lon,
                    confidence="low", frp=1.0, cell_x=x, cell_y=y, source_file="synthetic")

    def write(self, sensor, year, rows, part=1):
        path = self.root / sensor.lower() / str(year) / "brazil" / f"part-{part:03d}.parquet"
        path.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(path, index=False)
        self.parts.append(path)
        return path

    def test_duckdb_deduplicates_before_counting_cells(self):
        with closing(open_parquets(self.root)) as conn:
            daily = daily_aggregation(conn)
        jan = daily[daily.acq_date == "2024-01-10"].set_index("sensor")
        self.assertEqual(int(jan.loc["MODIS", "detections"]), 1)
        self.assertEqual(int(jan.loc["VIIRS", "cells"]), 2)
        self.assertEqual(int(daily.detections.sum()), 13)

    def test_frontend_harmonization_export_and_geographic_filters(self):
        status = self.data.dataset_status()
        self.assertFalse(status["demo"])
        self.assertEqual(status["engine"], "DuckDB")
        monthly, _ = self.data.monthly_analysis(self.period, self.filters)
        self.assertEqual(monthly.attrs["calibration_factor"], .5)
        self.assertEqual(float(monthly.activity.iloc[0]), 2)
        self.assertEqual(self.data.dashboard_metrics(self.period, self.filters)["hotspots"], 4)
        exported = pd.read_csv(io.BytesIO(self.data.export_detections(self.period, self.filters)), dtype={"acq_time": str})
        self.assertEqual(len(exported), 4)
        self.assertEqual(exported.acq_time.iloc[0], "0005")
        for filters in ({"country": "Brazil", "state": "All regions"},
                        {"scope": "radius", "latitude": -22.9, "longitude": -47, "radius_km": 100}):
            self.assertEqual(int(self.data.daily_data(filters).detections.sum()), 13)
        with patch.object(self.data, "EXPORT_LIMIT", 1):
            with self.assertRaises(ValueError):
                self.data.export_detections(self.period, self.filters)

    def test_cache_detects_replacement_and_new_parts(self):
        self.assertEqual(int(self.data.daily_data(self.filters).detections.sum()), 13)
        # Replacing a part with fewer records must invalidate cached aggregates.
        self.write("VIIRS", 2025, [self.row("VIIRS", "2025-01-10", 0)])
        self.assertEqual(int(self.data.daily_data(self.filters).detections.sum()), 10)
        self.write("VIIRS", 2025, [self.row("VIIRS", "2025-01-11", 1)], part=2)
        self.assertEqual(int(self.data.daily_data(self.filters).detections.sum()), 11)

    def test_discovery_ignores_temporary_and_legacy_files(self):
        path = self.root / "modis/2024/brazil/.part-003.parquet.tmp"
        path.write_bytes(b"incomplete")
        legacy = self.root / "modis/year=2024/part-old.parquet"
        legacy.parent.mkdir()
        legacy.write_bytes(b"obsolete")
        self.assertEqual(len(parquet_files(self.root)), 4)
        self.assertEqual(len(parquet_files(self.root, 2025, 2025)), 1)
        self.assertEqual(int(self.data.daily_data(self.filters).detections.sum()), 13)

    def test_missing_period_returns_empty_without_synthetic_records(self):
        exported = pd.read_csv(io.BytesIO(self.data.export_detections(
            (date(2030, 1, 1), date(2030, 12, 31)), self.filters)))
        self.assertTrue(exported.empty)
        self.assertFalse(self.data.dataset_status()["demo"])

    def test_future_data_does_not_enter_calibration_and_viirs_stays_provisional(self):
        self.write("MODIS", 2026, [self.row("MODIS", "2026-01-10", i) for i in range(10)])
        self.write("VIIRS", 2026, [self.row("VIIRS", "2026-01-10", 0)])
        monthly, _ = self.data.monthly_analysis(self.period, self.filters)
        self.assertEqual(monthly.attrs["calibration_factor"], .5)
        daily = pd.DataFrame([dict(acq_date="2025-01-10", sensor="VIIRS", cells=4, detections=4)])
        monthly, _ = harmonize_monthly(daily, self.period)
        self.assertFalse(monthly.calibrated.iloc[0])
        self.assertEqual(float(monthly.activity.iloc[0]), 4)

    def test_no_parquets_returns_empty_without_demo(self):
        with patch.dict(os.environ, {"FIREWATCH_DATA": str(self.root / "missing")}):
            self.assertFalse(self.data.dataset_status()["demo"])
            self.assertFalse(self.data.dataset_status()["available"])
            self.assertEqual(len(self.data.daily_data(self.filters)), 0)


if __name__ == "__main__":
    unittest.main()
