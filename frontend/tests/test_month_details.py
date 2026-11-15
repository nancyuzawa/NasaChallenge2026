"""Dados e navegação do detalhamento mensal do calendário."""

from datetime import date
from pathlib import Path
import json
import sys
import unittest

from streamlit.testing.v1 import AppTest

FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND))

from activity_data import annual_series, month_summary


class MonthDetailsTest(unittest.TestCase):
    def test_month_totals_shares_and_year_boundary(self):
        for sensors in ([], ["MODIS"], ["VIIRS"]):
            monthly = annual_series(2025, sensors=sensors)
            summary = month_summary(2025, 9, sensors=sensors)
            self.assertEqual(summary["total"], monthly[8])
            self.assertEqual(sum(n for _, n in summary["days"]), monthly[8])
            self.assertEqual(summary["annual_share"], round(monthly[8] / sum(monthly) * 100, 1))
            self.assertEqual(summary["growth"], round((monthly[8] / monthly[7] - 1) * 100, 1))
            january = month_summary(2025, 1, sensors=sensors)
            december = annual_series(2024, sensors=sensors)[-1]
            self.assertEqual(january["growth"], round((monthly[0] / december - 1) * 100, 1))
        self.assertEqual(len(month_summary(2024, 2)["days"]), 29)
        self.assertIsNone(month_summary(2023, 1)["growth"])
        empty = month_summary(2025, 9, {"country": "Brazil", "city": "Missing city"})
        self.assertEqual(empty["total"], 0)
        self.assertEqual(empty["annual_share"], 0)
        self.assertIsNone(empty["growth"])

    def test_open_change_month_sensor_and_back_preserves_calendar(self):
        app = AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=30).run()
        filters = {"country": "Brazil", "state": "Amazonas", "city": "Manaus",
                   "latitude": -3.119, "longitude": -60.0217,
                   "period": (date(2025, 1, 1), date(2025, 12, 31))}
        app.session_state.filters = filters
        app.switch_page("pages/2_Activity.py").run()
        self.assertNotIn("see-month-details", [button.key for button in app.button])
        self.assertFalse(any((button.key or "").startswith("open-month-") for button in app.button))
        app.get("button_group")[0].set_value(["MODIS"]).run()
        app.selectbox(key="calendar_year").select(2024).run()
        app.selectbox(key="comparison_year").select(2023).run()
        app.selectbox(key="calendar_month").select(9).run()
        self.assertEqual(app.button(key="see-month-details").label, "See more details")
        app.button(key="see-month-details").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.detail_month, 9)
        self.assertEqual(app.session_state.detail_year, 2024)
        self.assertEqual(app.get("button_group")[0].value, ["MODIS"])
        app.selectbox(key="detail_month").select(2).run()
        app.get("button_group")[0].set_value(["VIIRS"]).run()
        self.assertFalse(app.exception)
        chart = json.loads(app.get("plotly_chart")[0].proto.spec)
        self.assertEqual(len(chart["data"][0]["x"]), 29)
        self.assertEqual(sum(chart["data"][0]["y"]), month_summary(2024, 2, filters, ["VIIRS"])["total"])
        app.button(key="month-back").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="calendar_year").value, 2024)
        self.assertEqual(app.selectbox(key="calendar_month").value, 9)
        self.assertEqual(app.selectbox(key="comparison_year").value, 2023)
        self.assertEqual(app.get("button_group")[0].value, ["VIIRS"])
        self.assertEqual(app.session_state.filters, filters)
        app.selectbox(key="calendar_month").select(0).run()
        self.assertNotIn("see-month-details", [button.key for button in app.button])


if __name__ == "__main__":
    unittest.main()
