"""Real report totals, filters, bounded pagination, export and carousel flow."""
import csv
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd
from streamlit.testing.v1 import AppTest

FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND))
import processed_reports as reports


class ProcessedReportsTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        env = patch.dict(os.environ, {"FIREWATCH_DATA": folder.name})
        env.start()
        self.addCleanup(env.stop)
        self.rows = []
        for year, count in ((2024, 3), (2025, 7)):
            for sensor in ("MODIS", "VIIRS"):
                for i in range(count):
                    self.rows.append(dict(sensor=sensor, satellite="Terra" if sensor == "MODIS" else "N20",
                                          acq_date=f"{year}-01-10", acq_time="0130", latitude=-22.9,
                                          longitude=-47 + i * .01, cell_x=i, cell_y=0,
                                          confidence="90" if sensor == "MODIS" else "n", frp=2.5))
        self.write()

    def write(self):
        frame = pd.DataFrame(self.rows)
        for (sensor, year), group in frame.groupby([frame.sensor, frame.acq_date.str[:4]]):
            path = self.root / sensor.lower() / year / "brazil" / "part-001.parquet"
            path.parent.mkdir(parents=True, exist_ok=True)
            # Both file formats and duplicate observations must not double totals.
            pd.concat([group, group.iloc[:1]]).to_parquet(path, index=False)
            group.to_csv(path.with_suffix(".csv"), index=False)

    def test_totals_fields_export_and_cache_refresh(self):
        area = (2025, "Brazil", "S\u00e3o Paulo")
        summary = reports.historical_summary(*area)
        self.assertEqual(summary["total"], 14)
        self.assertEqual(summary["current"], (14,) + (None,) * 11)
        self.assertEqual(summary["previous_years"], (2024,))
        self.assertEqual(summary["historical_total"], 6)
        self.assertAlmostEqual(summary["deviation"], (14 / 6 - 1) * 100)
        first = reports.record_page(*area, 0)
        last = reports.record_page(*area, 1000)
        self.assertEqual((first["total"], len(first["rows"]), last["page"], last["end"]), (14, 10, 1, 14))
        rows = first["rows"] + last["rows"]
        self.assertTrue(all(row[0] == "2025-01-10 01:30:00" for row in rows))
        self.assertEqual({row[3] for row in rows}, {"Terra", "N20"})
        self.assertEqual({row[5] for row in rows}, {"90", "n"})
        self.assertTrue(all(row[6:] == (2.5, None) for row in rows))
        exported = list(csv.DictReader(io.StringIO(reports.records_csv(*area).decode("utf-8-sig"))))
        self.assertEqual(len(exported), first["total"])
        self.assertEqual({row["Data type"] for row in exported}, {"NASA FIRMS"})
        self.rows = [row for row in self.rows if row["longitude"] == -47]
        self.write()
        self.assertEqual(reports.historical_summary(*area)["total"], 2)
        self.assertEqual(reports.record_page(*area, 0)["total"], 2)

    def test_missing_coverage_empty_period_and_state_polygon(self):
        self.rows.append(dict(self.rows[-1], latitude=-15.8, longitude=-47.9, cell_x=20))
        self.write()
        self.assertEqual(reports.historical_summary(2025, "Brazil", "All regions")["total"], 15)
        self.assertEqual(reports.historical_summary(2025, "Brazil", "S\u00e3o Paulo")["total"], 14)
        self.assertEqual(reports.record_page(2025, "Brazil", "Distrito Federal", 0)["total"], 1)
        self.assertIn("Distrito Federal", reports.regions("Brazil"))
        for year, state in ((2030, "All regions"), (2025, "Unknown province")):
            self.assertEqual(reports.historical_summary(year, "Brazil", state)["total"], 0)
            self.assertEqual(reports.record_page(year, "Brazil", state, 0)["rows"], ())
        self.rows = [row for row in self.rows if not (row["acq_date"].startswith("2025") and row["sensor"] == "MODIS")]
        # Remove the old file to represent genuinely absent sensor coverage.
        (self.root / "modis/2025/brazil/part-001.parquet").unlink()
        self.write()
        summary = reports.historical_summary(2025, "Brazil", "All regions")
        self.assertIsNone(summary["average"])
        self.assertEqual(summary["incidents"], [])

    def test_reports_filters_slides_and_pagination_render(self):
        app = AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=30).run()
        app.switch_page("pages/3_Reports.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="reports_year").value, 2025)
        self.assertEqual(set(app.selectbox(key="reports_year").options), {"2025", "2024"})
        app.button(key="reports-next").click().run()
        self.assertFalse(app.exception)
        chart = json.loads(app.get("plotly_chart")[0].proto.spec)
        self.assertEqual(chart["data"][0]["y"], [14] + [None] * 11)
        self.assertEqual(chart["data"][1]["y"], [6] + [None] * 11)
        app.button(key="reports-next").click().run()
        app.button(key="records-next").click().run()
        self.assertEqual(app.session_state.reports_record_page, 1)
        self.assertTrue(app.button(key="records-next").disabled)
        app.selectbox(key="reports_year").select(2024).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.reports_record_page, 0)
        app.button(key="reports-dot-1").click().run()
        self.assertEqual(len(json.loads(app.get("plotly_chart")[0].proto.spec)["data"]), 1)
        app.selectbox(key="reports_country").select("Antarctica").run()
        app.button(key="reports-dot-2").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(app.button(key="records-next").disabled)
        self.assertTrue(any("No records for this selection" in m.value for m in app.markdown))


if __name__ == "__main__":
    unittest.main()
