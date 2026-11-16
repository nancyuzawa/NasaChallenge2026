"""Historical baseline, anomaly classification, record consistency and report flow."""

from collections import Counter
from datetime import date
from pathlib import Path
import csv
import io
import json
import sys
import unittest
import os
import tempfile
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND))

from activity_data import annual_series, daily_activity
from reports_data import (area_cities, area_series, detection_records, historical_summary,
                          monthly_comparison, record_page, records_csv)


class ReportsDataTest(unittest.TestCase):
    def test_baseline_uses_only_earlier_years_and_matches_area_totals(self):
        country, state = "Brazil", "São Paulo"
        summary = historical_summary(2025, country, state)
        self.assertEqual(summary["previous_years"], (2024, 2023))
        for month in range(12):
            expected = sum(annual_series(2025, city)[month] for city in area_cities(country, state))
            self.assertEqual(summary["current"][month], expected)
            self.assertEqual(summary["average"][month],
                             (area_series(2024, country, state)[month] + area_series(2023, country, state)[month]) / 2)
        self.assertEqual(summary["total"], sum(summary["current"]))
        self.assertAlmostEqual(summary["deviation"], (summary["total"] / summary["historical_total"] - 1) * 100)
        earliest = historical_summary(2023, country, state)
        self.assertIsNone(earliest["historical_total"])
        self.assertIsNone(earliest["largest_deviation"])
        self.assertEqual(earliest["incidents"], [])
        empty = historical_summary(2025, "No country", "All regions")
        self.assertEqual(empty["total"], 0)
        self.assertIsNone(empty["deviation"])
        self.assertEqual(empty["incidents"], [])
        with self.assertRaises(ValueError):
            area_series(2026, country, state)

    def test_anomalies_in_both_directions_zero_and_missing_baselines(self):
        rows = monthly_comparison([142, 65, 110, 10, 0], [100, 100, 100, 0, 0])
        self.assertEqual([row["incident"] for row in rows], [True, True, False, True, False])
        self.assertAlmostEqual(rows[0]["deviation"], 42)
        self.assertAlmostEqual(rows[1]["deviation"], -35)
        self.assertTrue(rows[3]["new_activity"])
        self.assertIsNone(rows[3]["deviation"])
        self.assertFalse(any(row["incident"] for row in monthly_comparison([100], None)))

    def test_records_preserve_daily_monthly_source_and_export_totals(self):
        for year in (2024, 2025):
            with self.subTest(year=year):
                records = detection_records(year, "Brazil", "São Paulo")
                self.assertEqual(len(records), historical_summary(year, "Brazil", "São Paulo")["total"])
                monthly = Counter(int(row[0][5:7]) for row in records)
                self.assertEqual([monthly[month] for month in range(1, 13)], list(area_series(year, "Brazil", "São Paulo")))
                for sensor in ("MODIS", "VIIRS"):
                    expected = Counter()
                    for city in area_cities("Brazil", "São Paulo"):
                        expected.update({str(day): count for day, count in daily_activity(year, city, [sensor]).items()})
                    actual = Counter(row[0][:10] for row in records if row[4] == sensor)
                    self.assertEqual(+expected, actual)
                self.assertEqual([row[0] for row in records], sorted((row[0] for row in records), reverse=True))
                self.assertTrue(all(row[3] is None and row[5:] == (None, None, None) for row in records))
                exported = list(csv.DictReader(io.StringIO(records_csv(year, "Brazil", "São Paulo").decode("utf-8-sig"))))
                self.assertEqual(len(exported), len(records))
                self.assertTrue(all(row["Data type"] == "Synthetic demonstration" for row in exported))
                pages = [record_page(records, page) for page in range(record_page(records, 0)["pages"])]
                self.assertEqual(tuple(row for page in pages for row in page["rows"]), records)
                self.assertEqual(pages[-1]["end"], len(records))
                self.assertEqual(record_page(records, 10**6)["page"], pages[-1]["page"])
        empty = record_page((), 100)
        self.assertEqual((empty["start"], empty["end"], empty["page"], empty["pages"]), (0, 0, 0, 1))


class ReportsNavigationTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        env = patch.dict(os.environ, {"FIREWATCH_DATA": folder.name})
        env.start()
        self.addCleanup(env.stop)

    def test_slides_filters_pagination_and_map_reentry(self):
        app = AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=30).run()
        app.switch_page("pages/3_Reports.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="reports_state").value, "São Paulo")
        self.assertNotIn("reports-previous", [button.key for button in app.button])
        app.button(key="reports-next").click().run()
        self.assertFalse(app.exception)
        chart = json.loads(app.get("plotly_chart")[0].proto.spec)
        summary = historical_summary(2025, "Brazil", "São Paulo")
        self.assertEqual(chart["data"][0]["y"], list(summary["current"]))
        self.assertEqual(chart["data"][1]["y"], list(summary["average"]))
        app.button(key="reports-next").click().run()
        self.assertTrue(app.button(key="records-back").disabled)
        table = next(m.value for m in app.markdown if 'class="detection-table"' in m.value)
        app.button(key="records-next").click().run()
        self.assertEqual(app.session_state.reports_record_page, 1)
        self.assertNotEqual(next(m.value for m in app.markdown if 'class="detection-table"' in m.value), table)
        app.button(key="reports-dot-0").click().run()
        app.button(key="reports-dot-2").click().run()
        self.assertEqual(app.session_state.reports_record_page, 1)
        app.selectbox(key="reports_year").select(2023).run()
        self.assertEqual(app.session_state.reports_record_page, 0)
        app.button(key="reports-dot-1").click().run()
        self.assertEqual(len(json.loads(app.get("plotly_chart")[0].proto.spec)["data"]), 1)
        self.assertTrue(any("No comparable earlier years" in m.value for m in app.markdown))
        app.selectbox(key="reports_country").select("Antarctica").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="reports_state").value, "All regions")
        app.button(key="reports-dot-2").click().run()
        self.assertTrue(app.button(key="records-back").disabled)
        self.assertTrue(app.button(key="records-next").disabled)
        self.assertTrue(any("No records" in m.value for m in app.markdown))
        app.session_state.filters = {"country": "Brazil", "state": "Amazonas", "city": "Manaus",
                                     "latitude": -3.119, "longitude": -60.0217,
                                     "period": (date(2025, 1, 1), date(2025, 12, 31))}
        app.switch_page("pages/2_Activity.py").run()
        app.switch_page("pages/3_Reports.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="reports_country").value, "Brazil")
        self.assertEqual(app.selectbox(key="reports_state").value, "Amazonas")


if __name__ == "__main__":
    unittest.main()
