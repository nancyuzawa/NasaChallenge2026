"""Dashboard Streamlit baseado no protótipo de monitoramento de incêndios."""

from datetime import date
from html import escape

import streamlit as st

try:
    import plotly.graph_objects as go
except ModuleNotFoundError:
    go = None

from data import dashboard_metrics, dashboard_series
from globe import render_globe
from locations import CITIES, REGIONS, STATE_CODES, LOCATION_OPTIONS, LOCATION_LABELS, location_key, selection_filters
from ui import apply_styles, icon, render_sidebar, searchable_selectbox

st.set_page_config(
    page_title="Space Apps | Firewatch",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_styles(dashboard=True)

DEFAULT_FILTERS = {
    "country": "Brazil",
    "state": "São Paulo",
    "city": "Campinas",
    "latitude": -22.9064,
    "longitude": -47.0616,
    "period": (date(2025, 1, 1), date(2025, 12, 31)),
}

if "filters" not in st.session_state:
    st.session_state.filters = DEFAULT_FILTERS.copy()
# Preserva seleções anteriores à atualização da interface.
if st.session_state.filters["country"] == "Brasil":
    st.session_state.filters["country"] = "Brazil"
filters = st.session_state.filters
metrics = dashboard_metrics(filters["period"], filters)
series = dashboard_series(filters["period"], filters)
city = filters.get("city")
location = (
    f"{city} - {STATE_CODES.get(filters['state'], filters['state'])}, {filters['country']}"
    if city else (filters["country"] if filters["state"] == "All regions" else f"{filters['state']}, {filters['country']}")
)
start, end = filters["period"]
ENGLISH_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
period_label = (
    f"{ENGLISH_MONTHS[start.month - 1]} to {ENGLISH_MONTHS[end.month - 1]} {end.year}"
    if start.year == end.year else f"{start:%d/%m/%Y} to {end:%d/%m/%Y}"
)
hotspot_total = f"{metrics['hotspots']:,}".replace(",", ".")


def close_dialog():
    st.session_state.active_dialog = None


@st.dialog("Filter", width="large", on_dismiss=close_dialog)
def filter_dialog():
    st.markdown("#### Area of interest")
    country_col, state_col = st.columns(2)
    countries = list(REGIONS)
    if "filter_country" not in st.session_state:
        st.session_state.filter_country = filters["country"] if filters["country"] in countries else countries[0]
    with country_col:
        chosen_country = searchable_selectbox("Country", countries, index=None, key="filter_country")
    country = chosen_country or filters["country"]
    states = list(REGIONS[country])
    state_key = f"filter_state_{country}"
    if state_key not in st.session_state:
        st.session_state[state_key] = filters["state"] if filters["state"] in states else states[0]
    with state_col:
        chosen_state = searchable_selectbox("State/Province", states, index=None, key=state_key)
    state = chosen_state or (filters["state"] if filters["state"] in states else states[0])
    same_region = country == filters["country"] and state == filters["state"]
    lat, lon = (filters["latitude"], filters["longitude"]) if same_region else REGIONS[country][state]
    with st.form("dashboard_filters", border=False):
        lat_col, lon_col = st.columns(2)
        with lat_col:
            latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=float(lat), format="%.4f", key=f"latitude_{country}_{state}")
        with lon_col:
            longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=float(lon), format="%.4f", key=f"longitude_{country}_{state}")
        st.markdown("#### Interval")
        period = st.date_input("Analysis period", value=filters["period"], format="DD/MM/YYYY", label_visibility="collapsed")
        st.markdown("")
        reset_col, apply_col, _ = st.columns([1, 1, 1.2])
        with reset_col:
            reset = st.form_submit_button("Reset", width="stretch")
        with apply_col:
            apply = st.form_submit_button("Apply", type="primary", width="stretch")
        if reset:
            st.session_state.filters = DEFAULT_FILTERS.copy()
            close_dialog()
            st.rerun()
        if apply:
            if chosen_country is None or chosen_state is None:
                st.error("Select a country and a state/region.")
                return
            if not isinstance(period, tuple) or len(period) != 2:
                st.error("Select a start and end date.")
                return
            keep_city = same_region and latitude == filters["latitude"] and longitude == filters["longitude"]
            st.session_state.filters = {
                "country": country, "state": state, "city": filters.get("city") if keep_city else None,
                "latitude": latitude, "longitude": longitude, "period": period,
            }
            close_dialog()
            st.rerun()


@st.dialog("Search location", on_dismiss=close_dialog)
def search_dialog():
    with st.form("location_search", border=False):
        chosen = searchable_selectbox("City", list(CITIES), index=None, placeholder="Search a city…", help="Type a city name to search, or use Filter to enter coordinates.")
        if st.form_submit_button("Show on map", type="primary", width="stretch"):
            if chosen is None:
                st.error("Select a city to continue.")
                return
            country, state, city, lat, lon = CITIES[chosen]
            st.session_state.filters = {**filters, "country": country, "state": state, "city": city, "latitude": lat, "longitude": lon}
            close_dialog()
            st.rerun()


def change_toolbar_location():
    value = st.session_state.toolbar_location
    if value and value != "current":
        kind, identifier = value.split(":", 1)
        selected = selection_filters({"kind": kind, "id": identifier}, st.session_state.filters)
        if selected is not None:
            st.session_state.filters = selected


render_sidebar("Mapa")
with st.container(key="dashboard-grid"):
    map_col, insight_col = st.columns([1, 1], gap="small", vertical_alignment="top")
with map_col:
    with st.container(key="map-panel"):
        with st.container(key="map-toolbar", horizontal=True, vertical_alignment="center", gap="small"):
            if st.button("", icon=":material/search:", key="search", help="Search location", width="content"):
                st.session_state.active_dialog = "search"
            if st.button("Filter", icon=":material/filter_alt:", key="filter", width="content"):
                st.session_state.active_dialog = "filter"
                st.session_state.filter_country = filters["country"]
                states = list(REGIONS[filters["country"]])
                st.session_state[f"filter_state_{filters['country']}"] = filters["state"] if filters["state"] in states else states[0]
            current_location = location_key(filters)
            location_options = LOCATION_OPTIONS if current_location != "current" else ["current", *LOCATION_OPTIONS]
            filter_signature = tuple(filters.get(key) for key in ("country", "state", "city", "latitude", "longitude"))
            if "toolbar_location" not in st.session_state or st.session_state.get("toolbar_filter_signature") != filter_signature:
                st.session_state.toolbar_location = current_location
                st.session_state.toolbar_filter_signature = filter_signature
            searchable_selectbox(
                "Location", location_options, key="toolbar_location", index=None,
                format_func=lambda value: location if value == "current" else LOCATION_LABELS[value],
                label_visibility="collapsed", placeholder="Search a country or city…",
                on_change=change_toolbar_location, help="Type a country or city name to search.",
            )
        map_event = render_globe(filters)
        if isinstance(map_event, dict) and map_event.get("event_id") != st.session_state.get("last_map_event"):
            st.session_state.last_map_event = map_event.get("event_id")
            selected = selection_filters(map_event, filters)
            if selected is not None:
                st.session_state.filters = selected
                st.rerun()

with insight_col:
    with st.container(key="insights"):
        st.markdown(f"""<div class="metrics-row">
<section class="metric-card" aria-label="Detected hotspots">
  <div class="metric-label">{icon('fire', 38)}<span>Detected hotspots</span></div>
  <div class="metric-value">{hotspot_total}</div>
  <div class="metric-note"><span class="growth-icon">{icon('trend', 24)}</span><strong>{metrics['growth']}%</strong> compared to the same period in<br>{start.year - 1}</div>
  <div class="muted-note">{'Demo data' if metrics['hotspots'] else 'No demo data for this selection'} · {escape(period_label)}</div>
</section>
<section class="metric-card" aria-label="Period of Peak Activity">
  <div class="metric-label">{icon('calendar', 38)}<span>Period of Peak Activity</span></div>
  <div class="metric-value">{metrics['peak_month']}</div>
  <div class="metric-subvalue">{metrics['peak_count']} Hotspots</div>
  <div class="metric-note">Highest monthly amount in selected period</div>
</section>
</div>""", unsafe_allow_html=True)
        st.markdown(f"""<section class="comparison-card" aria-label="Historical Comparison">
  <div class="comparison-main">
    <div class="metric-label">{icon('chart', 38)}<span>Historical Comparison</span></div>
    <div class="metric-value">+{metrics['historical_growth']}%</div>
    <span class="status-chip">{'Above the historical average' if metrics['hotspots'] else 'No demonstration data'}</span>
  </div>
  <div class="comparison-stat"><span>Current period</span><strong>{metrics['current_period']}</strong><span>Detected hotspots</span></div>
  <div class="comparison-dot" aria-hidden="true">•</div>
  <div class="comparison-stat"><span>Historical average</span><strong>{metrics['historical_average']}</strong><span>Expected focal points</span></div>
</section>""", unsafe_allow_html=True)
        with st.container(key="trend-panel"):
            st.markdown(f"<div class='chart-title'>Monthly trend in fire outbreaks</div><div class='chart-subtitle'>{escape(location)} · {escape(period_label)}</div>", unsafe_allow_html=True)
            if go:
                trend = go.Figure(go.Scatter(
                    x=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                    y=series, mode="lines+markers",
                    line={"color": "#fdfbfd", "width": 2},
                    marker={"size": 8, "color": "#fdfbfd", "line": {"width": 2, "color": "#a9aeb8"}},
                    hovertemplate="%{x}: %{y} hotspots<extra></extra>",
                ))
                trend.update_layout(
                    paper_bgcolor="#303646", plot_bgcolor="#303646",
                    font={"color": "#fdfbfd", "family": "Barlow Condensed, Arial", "size": 12},
                    autosize=True, margin={"l": 30, "r": 8, "t": 20, "b": 28},
                    xaxis={"showgrid": False, "zeroline": False, "tickfont": {"color": "#dedee5"}, "fixedrange": True},
                    yaxis={"gridcolor": "#444957", "gridwidth": 1, "zeroline": True, "zerolinecolor": "#444957", "range": [0, max(470, max(series) * 1.15)], "nticks": 4, "fixedrange": True},
                    showlegend=False, hoverlabel={"bgcolor": "#09163b"},
                )
                st.plotly_chart(trend, width="stretch", height="stretch", config={"displayModeBar": False}, theme=None)
            else:
                st.line_chart({"Hotspots": series}, height="stretch")

if st.session_state.get("active_dialog") == "filter":
    filter_dialog()
elif st.session_state.get("active_dialog") == "search":
    search_dialog()
