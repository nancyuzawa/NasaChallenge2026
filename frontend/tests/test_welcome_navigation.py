"""Fluxo de entrada e sincronização do seletor de localização do dashboard."""

from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

FRONTEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FRONTEND))


class WelcomeNavigationTest(unittest.TestCase):
    def test_welcome_country_indicator_and_return_home(self):
        app = AppTest.from_file(str(FRONTEND / "app.py"), default_timeout=30).run()
        self.assertFalse(app.exception)
        self.assertIsNone(app.selectbox(key="welcome_country").value)

        next(b for b in app.button if b.label == "Confirm").click().run()
        self.assertEqual(len(app.error), 1)

        app.selectbox(key="welcome_country").select("BRA")
        next(b for b in app.button if b.label == "Confirm").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.filters["country"], "Brazil")
        self.assertIsNone(app.session_state.filters["city"])
        self.assertEqual(app.session_state.filters["period"], (date(2025, 1, 1), date(2025, 12, 31)))
        self.assertEqual(len(app.get("plotly_chart")), 1)
        with self.assertRaises(KeyError):
            app.session_state["_dashboard_navigation_loading"]
        self.assertFalse(any('class="dashboard-loading-overlay"' in m.value for m in app.markdown))

        self.assertNotIn("toolbar_location", [select.key for select in app.selectbox])
        self.assertNotIn("search", [button.key for button in app.button])
        self.assertTrue(any('aria-label="Selected country"' in m.value and 'Brazil' in m.value for m in app.markdown))

        with patch("globe.render_globe", return_value={"kind": "city", "id": "BRA:Manaus", "event_id": "test-city"}):
            app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.filters["city"], "Manaus")
        self.assertTrue(any('aria-label="Selected country"' in m.value and 'Brazil' in m.value for m in app.markdown))

        app.button(key="filter").click().run()
        next(s for s in app.selectbox if s.label == "Country").set_value(None).run()
        self.assertFalse(app.exception)
        next(b for b in app.button if b.label == "Apply").click().run()
        self.assertEqual(len(app.error), 1)
        next(s for s in app.selectbox if s.label == "Country").select("Argentina").run()
        next(b for b in app.button if b.label == "Apply").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.filters["country"], "Argentina")
        self.assertTrue(any('aria-label="Selected country"' in m.value and 'Argentina' in m.value for m in app.markdown))

        app.switch_page("pages/2_Activity.py").run()
        self.assertFalse(app.exception)
        app.switch_page("pages/3_Reports.py").run()
        self.assertFalse(app.exception)
        app.switch_page("app.py").run()
        self.assertFalse(app.exception)
        self.assertIsNone(app.selectbox(key="welcome_country").value)

        # Retornar ao mesmo país deve restaurar o indicador no dashboard.
        app.selectbox(key="welcome_country").select("ARG")
        next(b for b in app.button if b.label == "Confirm").click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('aria-label="Selected country"' in m.value and 'Argentina' in m.value for m in app.markdown))


if __name__ == "__main__":
    unittest.main()
