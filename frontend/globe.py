"""Componente Streamlit bidirecional para seleção no globo WebGL."""

from pathlib import Path

import streamlit.components.v1 as components

from locations import COUNTRIES
from state_boundaries import geometry, selected


_component = components.declare_component(
    "firewatch_globe", path=str(Path(__file__).with_name("components") / "globe")
)


def render_globe(filters, hotspots=None):
    country_iso = next((code for code, country in COUNTRIES.items() if country["name"] == filters["country"]), None)
    shape = geometry(filters['country'],filters['state']) if selected(filters) else None
    boundary = dict(type="Feature", properties=dict(kind="selected-state",name=filters.get('state')),
                    geometry=shape) if shape is not None else None
    return _component(
        selection={"country_iso": country_iso, "city": filters.get("city"), "state": filters.get("state"), "boundary": boundary,
                   "latitude": filters["latitude"], "longitude": filters["longitude"]},
        hotspots=hotspots or {"points": [], "total": 0, "shown": 0},
        default=None, key="globe-map",
    )
