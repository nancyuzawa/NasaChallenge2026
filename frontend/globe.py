"""Componente Streamlit bidirecional para seleção no globo WebGL."""

from pathlib import Path

import streamlit.components.v1 as components

from locations import COUNTRIES


_component = components.declare_component(
    "firewatch_globe", path=str(Path(__file__).with_name("components") / "globe")
)


def render_globe(filters):
    country_iso = next((code for code, country in COUNTRIES.items() if country["name"] == filters["country"]), None)
    return _component(
        selection={"country_iso": country_iso, "city": filters.get("city"),
                   "latitude": filters["latitude"], "longitude": filters["longitude"]},
        default=None, key="globe-map",
    )
