"""Regras de seleção e agregação compartilhadas pelo globo e pelo formulário."""

from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from data import dashboard_metrics, dashboard_series
from locations import CITY_RECORDS, selection_filters


class LocationFiltersTest(unittest.TestCase):
    def setUp(self):
        self.period = (date(2025, 1, 1), date(2025, 12, 31))
        self.filters = {"country": "Brazil", "state": "São Paulo", "city": "Campinas",
                        "latitude": -22.9064, "longitude": -47.0616, "period": self.period}

    def test_country_selection_replaces_city_and_preserves_period(self):
        selected = selection_filters({"kind": "country", "id": "ARG"}, self.filters)
        self.assertEqual(selected["country"], "Argentina")
        self.assertIsNone(selected["city"])
        self.assertEqual(selected["state"], "All regions")
        self.assertEqual(selected["period"], self.period)

    def test_city_selection_uses_catalog_coordinates(self):
        selected = selection_filters({"kind": "city", "id": "BRA:Manaus", "latitude": 1000}, self.filters)
        self.assertEqual(selected["city"], "Manaus")
        self.assertEqual(selected["latitude"], -3.1190)
        self.assertEqual(selected["period"], self.period)

    def test_unknown_selections_are_rejected(self):
        for event in (None, {}, {"kind": "country", "id": "unknown"}, {"kind": "city", "id": "unknown"}):
            self.assertIsNone(selection_filters(event, self.filters))

    def test_country_series_aggregates_available_city_samples(self):
        country = selection_filters({"kind": "country", "id": "BRA"}, self.filters)
        expected = [0] * 12
        for city in CITY_RECORDS:
            if city["country"] == "Brazil":
                selected = selection_filters({"kind": "city", "id": city["id"]}, self.filters)
                expected = [a + b for a, b in zip(expected, dashboard_series(self.period, selected))]
        self.assertEqual(dashboard_series(self.period, country), expected)

    def test_location_changes_values_and_metrics_match_chart(self):
        other = selection_filters({"kind": "city", "id": "BRA:Manaus"}, self.filters)
        series = dashboard_series(self.period, self.filters)
        self.assertNotEqual(series, dashboard_series(self.period, other))
        metrics = dashboard_metrics(self.period, self.filters)
        self.assertEqual(metrics["hotspots"], 1284)
        self.assertEqual(metrics["hotspots"], sum(series))
        self.assertEqual(metrics["peak_count"], max(series))

    def test_interval_limits_data_and_outside_reference_year_is_empty(self):
        january = dashboard_series((date(2025, 1, 1), date(2025, 1, 31)), self.filters)
        self.assertGreater(january[0], 0)
        self.assertEqual(sum(january[1:]), 0)
        self.assertEqual(dashboard_series((date(2026, 1, 1), date(2026, 12, 31)), self.filters), [0] * 12)


if __name__ == "__main__":
    unittest.main()
