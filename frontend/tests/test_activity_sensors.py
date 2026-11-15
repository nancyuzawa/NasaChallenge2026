"""Verify that source selection updates the rendered calendar and yearly summaries."""

from pathlib import Path
import re
import sys
import unittest

from streamlit.testing.v1 import AppTest

FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND))

from activity_data import annual_summary, calendar_cells


class ActivitySensorsTest(unittest.TestCase):
    def test_source_selection_and_month_keep_calendar_and_summary_consistent(self):
        app = AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=30).run()
        app.switch_page("pages/2_Atividade.py").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.get("button_group")[0].value, [])
        for sources in (["MODIS"], ["VIIRS"], ["MODIS", "VIIRS"], []):
            app.get("button_group")[0].set_value(sources).run()
            self.assertFalse(app.exception)
            calendar = next(m.value for m in app.markdown if 'class="activity-heatmap"' in m.value)
            counts = [int(n.replace(",", "")) for n in re.findall(r'title="\d{2}/\d{2}/\d{4}: ([\d,]+) hotspots"', calendar)]
            self.assertEqual(counts, [cell["count"] for cell in sorted(calendar_cells(2025, sensors=sources), key=lambda c: (c["weekday"], c["date"]))])
            summary = next(m.value for m in app.markdown if 'class="annual-summary"' in m.value)
            self.assertIn("Yearly summary", summary)
            self.assertIn(f'{annual_summary(2025, sensors=sources)["total"]:,}', summary)
        app.get("button_group")[0].set_value(["VIIRS"]).run()
        app.selectbox(key="calendar_year").select(2024).run()
        app.selectbox(key="calendar_month").select(2).run()
        calendar = next(m.value for m in app.markdown if 'class="activity-heatmap"' in m.value)
        self.assertEqual(calendar.count('class="calendar-day"'), 29)
        self.assertIn('data-date="2024-02-29"', calendar)
        self.assertEqual(app.get("button_group")[0].value, ["VIIRS"])


if __name__ == "__main__":
    unittest.main()
