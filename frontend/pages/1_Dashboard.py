"""Dashboard Streamlit baseado no protótipo de monitoramento de incêndios."""

if __name__ == "__main__":
    from pathlib import Path
    import sys

    frontend_path = str(Path(__file__).resolve().parents[1])
    if frontend_path not in sys.path:
        sys.path.insert(0, frontend_path)
    from bootstrap import launch_if_direct

    launch_if_direct()

from datetime import date
from html import escape

import streamlit as st

try:
    import plotly.graph_objects as go
except ModuleNotFoundError:
    go = None

from processed_data import available_years
from dashboard_data import load_dashboard, load_hotspots, available_regions
from globe import render_globe
from navigation_loading import show_dashboard_loading
from locations import REGIONS, STATE_CODES, selection_filters
from ui import apply_styles, icon, render_sidebar, searchable_selectbox

st.set_page_config(
    page_title="Space Apps | Firewatch",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_styles(dashboard=True)
transition_loading = show_dashboard_loading() if st.session_state.get("_dashboard_navigation_loading") else None

years = available_years()
latest_year = years[0] if years else 2025
default_period = (date(latest_year, 1, 1), date(latest_year, 12, 31))

DEFAULT_FILTERS = {
    "country": "Brazil",
    "state": "São Paulo",
    "city": "Campinas",
    "latitude": -22.9064,
    "longitude": -47.0616,
    "period": default_period,
}

if "filters" not in st.session_state:
    st.session_state.filters = DEFAULT_FILTERS.copy()
# Welcome may already have created filters using its demonstration year.
# Initialize on the first Dashboard visit and follow new years only while the
# automatic period remains selected; preserve subsequent manual selections.
previous_default = st.session_state.get("_dashboard_default_period")
if previous_default is None or (not st.session_state.get("_dashboard_period_manual", False) and st.session_state.filters.get("period") == previous_default):
    st.session_state.filters["period"] = default_period
st.session_state._dashboard_default_period = default_period
# Preserva seleções anteriores à atualização da interface.
if st.session_state.filters["country"] == "Brasil":
    st.session_state.filters["country"] = "Brazil"
filters = st.session_state.filters
try:
    with st.spinner("Loading fire activity…", show_time=True):
        metrics, series, status = load_dashboard(filters["period"], filters)
        hotspots = load_hotspots(filters["period"], filters) if not status["demo"] else None
except Exception:
    if transition_loading is not None:
        transition_loading.empty()
        st.session_state.pop("_dashboard_navigation_loading",None)
    raise

real = not status["demo"]
unit = "Hotspots"
selected_state = filters.get("state")
selected_area = filters["country"] + (f" · {selected_state}" if selected_state not in (None,"","All regions") else "")
if hotspots is not None and not hotspots.get("boundary_available",True):
    st.warning("Administrative boundary unavailable for this state/province. Choose another region; no country-wide points are substituted.")
def display(value):
    return "N/A" if value is None else f"{value:,.1f}".rstrip("0").rstrip(".")
change = "N/A" if metrics["growth"] is None else f"{metrics['growth']:g}%"
historical_change = "N/A" if metrics["historical_growth"] is None else f"{metrics['historical_growth']:+g}%"
historical_value = metrics["historical_growth"]
comparison_label = ("Insufficient historical data" if historical_value is None else
                    "Above the historical average" if historical_value > 0 else
                    "Below the historical average" if historical_value < 0 else "At the historical average")
city = filters.get("city")
location = (
    f"{city} - {STATE_CODES.get(filters['state'], filters['state'])}, {filters['country']}"
    if city else (filters["country"] if filters["state"] == "All regions" else f"{filters['state']}, {filters['country']}")
)
start, end = filters["period"]
ENGLISH_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
period_label = f"{start:%d/%m/%Y} to {end:%d/%m/%Y}"

hotspot_total = f"{metrics['hotspots']:,}"


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
    draft_period = st.session_state.get("dashboard_filter_period",filters["period"])
    options_period = tuple(draft_period) if isinstance(draft_period,(tuple,list)) and len(draft_period)==2 else filters["period"]
    if real:
        with st.spinner("Finding regions with hotspots in this period…",show_time=True):
            centers = {"All regions": REGIONS[country]["All regions"], **available_regions(country,options_period)}
    else:
        centers = REGIONS[country]
    states = list(centers)
    state_key = f"filter_state_{country}"
    if state_key not in st.session_state or (st.session_state[state_key] is not None and st.session_state[state_key] not in states):
        st.session_state[state_key] = filters["state"] if filters["state"] in states else states[0]
    with state_col:
        chosen_state = searchable_selectbox("State/Province", states, index=None, key=state_key)
    state = chosen_state or (filters["state"] if filters["state"] in states else states[0])
    same_region = country == filters["country"] and state == filters["state"]
    lat, lon = (filters["latitude"], filters["longitude"]) if same_region else centers[state]
    st.markdown("#### Interval")
    first_year = min([*years, filters["period"][0].year])
    last_year = max([*years, filters["period"][1].year])
    period = st.date_input(
        "Analysis period", value=filters["period"],
        key="dashboard_filter_period",
        min_value=date(first_year, 1, 1), max_value=date(last_year, 12, 31),
        format="DD/MM/YYYY", label_visibility="collapsed",
        help="Select the start and end dates, then click Apply.",
    )
    if real:
        st.caption("Available states/provinces have MODIS or VIIRS observations in the selected interval.")
        if len(states)==1:
            st.info("No state/province observations found for this country and interval.")
    with st.form("dashboard_filters", border=False):
        lat_col, lon_col = st.columns(2)
        with lat_col:
            latitude = st.number_input("Latitude", min_value=-90.0, max_value=90.0, value=float(lat), format="%.4f", key=f"latitude_{country}_{state}")
        with lon_col:
            longitude = st.number_input("Longitude", min_value=-180.0, max_value=180.0, value=float(lon), format="%.4f", key=f"longitude_{country}_{state}")
        st.markdown("")
        reset_col, apply_col, _ = st.columns([1, 1, 1.2])
        with reset_col:
            reset = st.form_submit_button("Reset", width="stretch")
        with apply_col:
            apply = st.form_submit_button("Apply", type="primary", width="stretch")
        if reset:
            st.session_state._dashboard_period_manual = False
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
            if period[0] > period[1]:
                st.error("The start date must precede the end date.")
                return
            st.session_state._dashboard_period_manual = True
            keep_city = same_region and latitude == filters["latitude"] and longitude == filters["longitude"]
            st.session_state.filters = {
                "country": country, "state": state, "city": filters.get("city") if keep_city else None,
                "latitude": latitude, "longitude": longitude, "period": period,
            }
            close_dialog()
            st.rerun()


render_sidebar("Map")
with st.container(key="dashboard-grid"):
    map_col, insight_col = st.columns([1, 1], gap="small", vertical_alignment="top")
with map_col:
    with st.container(key="map-panel"):
        with st.container(key="map-toolbar", horizontal=True, vertical_alignment="center", gap="small"):
            if st.button("Filter", icon=":material/filter_alt:", key="filter", width="content"):
                st.session_state.active_dialog = "filter"
                st.session_state.pop("dashboard_filter_period", None)
                st.session_state.filter_country = filters["country"]
                states = list(REGIONS[filters["country"]])
                st.session_state[f"filter_state_{filters['country']}"] = filters["state"] if filters["state"] in states else states[0]
            st.markdown(f'<div class="location-pill" role="status" aria-label="Selected country">{icon("pin")}<span>{escape(selected_area)}</span></div>', unsafe_allow_html=True)
        map_event = render_globe(filters, hotspots=hotspots)
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
  <div class="metric-note"><span class="growth-icon">{icon('trend', 24)}</span><strong>{change}</strong> compared to the same period in<br>{start.year - 1}</div>
  <div class="muted-note">{escape(status['label'])} · {escape(period_label)}</div>
</section>
<section class="metric-card" aria-label="Period of Peak Activity">
  <div class="metric-label">{icon('calendar', 38)}<span>Period of Peak Activity</span></div>
  <div class="metric-value">{metrics['peak_month']}</div>
  <div class="metric-subvalue">{display(metrics['peak_count'])} {unit}</div>
  <div class="metric-note">Highest monthly amount in selected period</div>
</section>
</div>""", unsafe_allow_html=True)
        st.markdown(f"""<section class="comparison-card" aria-label="Historical Comparison">
  <div class="comparison-main">
    <div class="metric-label">{icon('chart', 38)}<span>Historical Comparison</span></div>
    <div class="metric-value">{historical_change}</div>
    <span class="status-chip">{comparison_label}</span>
  </div>
  <div class="comparison-stat"><span>Current period</span><strong>{display(metrics['current_period'])}</strong><span>Detected hotspots</span></div>
  <div class="comparison-dot" aria-hidden="true">•</div>
  <div class="comparison-stat"><span>Historical average</span><strong>{display(metrics['historical_average'])}</strong><span>Expected focal points</span></div>
</section>""", unsafe_allow_html=True)
        with st.container(key="trend-panel"):
            st.markdown(f"<div class='chart-title'>Monthly trend in fire outbreaks</div><div class='chart-subtitle'>{escape(location)} · {escape(period_label)}</div>", unsafe_allow_html=True)
            if go:
                trend = go.Figure(go.Scatter(
                    x=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                    y=series, mode="lines+markers",
                    line={"color": "#fdfbfd", "width": 2},
                    marker={"size": 8, "color": "#fdfbfd", "line": {"width": 2, "color": "#a9aeb8"}},
                    hovertemplate="%{x}: %{y} " + unit + "<extra></extra>",
                ))
                trend.update_layout(
                    paper_bgcolor="#303646", plot_bgcolor="#303646",
                    font={"color": "#fdfbfd", "family": "Barlow Condensed, Arial", "size": 12},
                    autosize=True, margin={"l": 30, "r": 8, "t": 20, "b": 28},
                    xaxis={"showgrid": False, "zeroline": False, "tickfont": {"color": "#dedee5"}, "fixedrange": True},
                    yaxis={"gridcolor": "#444957", "gridwidth": 1, "zeroline": True, "zerolinecolor": "#444957", "range": [0, max(470, max((v for v in series if v is not None), default=0) * 1.15)], "nticks": 4, "fixedrange": True},
                    showlegend=False, hoverlabel={"bgcolor": "#09163b"},
                )
                st.plotly_chart(trend, width="stretch", height="stretch", config={"displayModeBar": False}, theme=None)
            else:
                st.line_chart({"Hotspots": series}, height="stretch")

if st.session_state.get("active_dialog") == "filter":
    filter_dialog()


if transition_loading is not None:
    transition_loading.empty()
    st.session_state.pop("_dashboard_navigation_loading",None)
