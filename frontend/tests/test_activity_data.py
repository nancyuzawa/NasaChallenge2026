"""Calendário diário, agregação mensal e comparação anual demonstrativa."""

from calendar import monthrange
from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from activity_data import annual_series, annual_summary, calendar_cells, daily_activity, heat_legend
from data import dashboard_series


class ActivityDataTest(unittest.TestCase):
    def test_daily_counts_match_monthly_and_annual_totals(self):
        for year in (2023, 2024, 2025):
            daily = daily_activity(year)
            monthly = annual_series(year)
            self.assertEqual(len(daily), 366 if year == 2024 else 365)
            for month in range(1, 13):
                self.assertEqual(sum(count for day, count in daily.items() if day.month == month), monthly[month - 1])
            self.assertEqual(sum(daily.values()), annual_summary(year)["total"])

    def test_reference_year_matches_dashboard(self):
        self.assertEqual(annual_series(2025), dashboard_series((date(2025, 1, 1), date(2025, 12, 31))))
        self.assertIsNone(annual_summary(2023)["growth"])
        self.assertGreater(annual_summary(2025)["growth"], 0)

    def test_calendar_week_alignment_and_leap_day(self):
        cells = calendar_cells(2025)
        self.assertEqual(len({cell["date"] for cell in cells}), 365)
        self.assertEqual(cells[0]["date"], date(2025, 1, 1))
        self.assertEqual(cells[0]["weekday"], 3)
        self.assertEqual(cells[0]["week"], 0)
        self.assertEqual(len(calendar_cells(2024, 2)), 29)
        for month in range(1, 13):
            focused = calendar_cells(2025, month)
            self.assertEqual(len(focused), monthrange(2025, month)[1])
            self.assertTrue(all(cell["date"].month == month for cell in focused))

    def test_sensor_sources_partition_daily_and_monthly_totals(self):
        for year in (2023, 2024, 2025):
            combined = daily_activity(year)
            modis = daily_activity(year, sensors=["MODIS"])
            viirs = daily_activity(year, sensors=["VIIRS"])
            self.assertEqual(combined, {day: modis[day] + viirs[day] for day in combined})
            self.assertEqual({day: 0 for day in combined}, daily_activity(year, sensors=[]))
            self.assertEqual(annual_series(year, sensors=[]), [0] * 12)
            self.assertEqual(annual_summary(year, sensors=[])["total"], 0)
            self.assertTrue(all(cell["count"] == 0 for cell in calendar_cells(year, sensors=[])))
            self.assertEqual(combined, daily_activity(year, sensors=["VIIRS", "MODIS"]))
            self.assertNotEqual(modis, viirs)
            for sensor, counts in (("MODIS", modis), ("VIIRS", viirs)):
                monthly = annual_series(year, sensors=[sensor])
                self.assertEqual(monthly, [sum(n for day, n in counts.items() if day.month == m) for m in range(1, 13)])
                summary = annual_summary(year, sensors=[sensor])
                self.assertEqual(summary["total"], sum(counts.values()))
                february = calendar_cells(year, 2, sensors=[sensor])
                self.assertEqual(sum(cell["count"] for cell in february), monthly[1])
                self.assertTrue(all(n >= 0 for n in counts.values()))

    def test_sensor_filter_respects_location_and_empty_samples(self):
        from locations import selection_filters
        base = {"period": (date(2025, 1, 1), date(2025, 12, 31))}
        manaus = selection_filters({"kind": "city", "id": "BRA:Manaus"}, base)
        combined = annual_series(2025, manaus)
        modis = annual_series(2025, manaus, ["MODIS"])
        viirs = annual_series(2025, manaus, ["VIIRS"])
        self.assertEqual(combined, [a + b for a, b in zip(modis, viirs)])
        self.assertNotEqual(modis, annual_series(2025, sensors=["MODIS"]))
        self.assertEqual(annual_summary(2025, {"country": "Brazil", "city": "Missing city"}, ["VIIRS"])["total"], 0)
        with self.assertRaises(ValueError):
            calendar_cells(2025, sensors=["Unknown"])

    def test_same_location_is_stable_and_other_city_changes_counts(self):
        from locations import selection_filters
        base = {"period": (date(2025, 1, 1), date(2025, 12, 31))}
        campinas = selection_filters({"kind": "city", "id": "BRA:Campinas"}, base)
        manaus = selection_filters({"kind": "city", "id": "BRA:Manaus"}, base)
        self.assertEqual(daily_activity(2025, campinas), daily_activity(2025, campinas))
        self.assertNotEqual(daily_activity(2025, campinas), daily_activity(2025, manaus))

    def test_legend_ranges_cover_all_counts_without_overlap(self):
        counts = daily_activity(2025).values()
        legend = heat_legend(counts)
        for value in counts:
            self.assertEqual(sum(item["low"] <= value <= item["high"] for item in legend), 1)

    def test_missing_samples_and_invalid_controls(self):
        empty = {"country": "Brazil", "city": "Missing city"}
        self.assertEqual(annual_summary(2025, empty)["total"], 0)
        self.assertEqual(annual_summary(2025, empty)["peak_period"], "No activity")
        with self.assertRaises(ValueError):
            annual_series(2022)
        with self.assertRaises(ValueError):
            calendar_cells(2025, 13)


if __name__ == "__main__":
    unittest.main()
