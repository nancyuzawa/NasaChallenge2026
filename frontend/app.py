"""Dashboard Streamlit baseado no protótipo de monitoramento de incêndios."""

if __name__ == "__main__":
    from bootstrap import launch_if_direct

    launch_if_direct()

from datetime import date
from html import escape

import streamlit as st

try:
    import plotly.graph_objects as go
except ModuleNotFoundError:
    go = None

from data import TREND_2025, dashboard_metrics
from globe import globe_html
from ui import apply_styles, icon, render_sidebar

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
REGIONS = {
    "Brazil": {
        "São Paulo": (-23.5505, -46.6333), "Amazonas": (-3.1190, -60.0217),
        "Mato Grosso": (-15.6014, -56.0979), "Pará": (-1.4558, -48.4902),
        "Rondônia": (-8.7619, -63.9039), "Rio de Janeiro": (-22.9068, -43.1729),
    },
    "Argentina": {"Buenos Aires": (-34.6037, -58.3816), "Córdoba": (-31.4201, -64.1888)},
    "Bolivia": {"La Paz": (-16.4897, -68.1193), "Santa Cruz": (-17.7833, -63.1821)},
    "Chile": {"Santiago": (-33.4489, -70.6693), "Valparaíso": (-33.0472, -71.6127)},
    "Colombia": {"Bogotá": (4.7110, -74.0721), "Antioquia": (6.2442, -75.5812)},
    "Paraguay": {"Asunción": (-25.2637, -57.5759)},
    "Peru": {"Lima": (-12.0464, -77.0428), "Cusco": (-13.5319, -71.9675)},
}
CITIES = {
    "Campinas - SP, Brazil": ("Brazil", "São Paulo", "Campinas", -22.9064, -47.0616),
    "São Paulo - SP, Brazil": ("Brazil", "São Paulo", "São Paulo", -23.5505, -46.6333),
    "Manaus - AM, Brazil": ("Brazil", "Amazonas", "Manaus", -3.1190, -60.0217),
    "Cuiabá - MT, Brazil": ("Brazil", "Mato Grosso", "Cuiabá", -15.6014, -56.0979),
    "Belém - PA, Brazil": ("Brazil", "Pará", "Belém", -1.4558, -48.4902),
    "Rio de Janeiro - RJ, Brazil": ("Brazil", "Rio de Janeiro", "Rio de Janeiro", -22.9068, -43.1729),
}
STATE_CODES = {"São Paulo": "SP", "Amazonas": "AM", "Mato Grosso": "MT", "Pará": "PA", "Rondônia": "RO", "Rio de Janeiro": "RJ"}

if "filters" not in st.session_state:
    st.session_state.filters = DEFAULT_FILTERS.copy()
# Preserva seleções anteriores à atualização da interface.
if st.session_state.filters["country"] == "Brasil":
    st.session_state.filters["country"] = "Brazil"
filters = st.session_state.filters
metrics = dashboard_metrics(filters["period"])
city = filters.get("city")
location = (
    f"{city} - {STATE_CODES.get(filters['state'], filters['state'])}, {filters['country']}"
    if city else f"{filters['state']}, {filters['country']}"
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
    with country_col:
        country = st.selectbox("Country", countries, index=countries.index(filters["country"]) if filters["country"] in countries else 0)
    states = list(REGIONS[country])
    with state_col:
        state = st.selectbox("State/Province", states, index=states.index(filters["state"]) if filters["state"] in states else 0)
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
        chosen = st.selectbox("City", list(CITIES), help="Select a reference city or use Filter to enter coordinates.")
        if st.form_submit_button("Show on map", type="primary", width="stretch"):
            country, state, city, lat, lon = CITIES[chosen]
            st.session_state.filters = {**filters, "country": country, "state": state, "city": city, "latitude": lat, "longitude": lon}
            close_dialog()
            st.rerun()


render_sidebar("Mapa")
with st.container(key="dashboard-grid"):
    map_col, insight_col = st.columns([1, 1], gap="small", vertical_alignment="top")
with map_col:
    with st.container(key="map-panel"):
        with st.container(key="map-toolbar", horizontal=True, vertical_alignment="center", gap="small"):
            if st.button("", icon=":material/search:", key="search", help="Search location", width=50):
                st.session_state.active_dialog = "search"
            if st.button("Filter", icon=":material/filter_alt:", key="filter", width=100):
                st.session_state.active_dialog = "filter"
            st.markdown(f"<div class='location-pill'>{icon('pin', 38)}<span>{escape(location)}</span></div>", unsafe_allow_html=True)
        st.iframe(globe_html(filters["latitude"], filters["longitude"], location), height=900, alt="Illustrated globe showing the selected location, with zoom and full screen controls")

with insight_col:
    with st.container(key="insights"):
        st.markdown(f"""<div class="metrics-row">
<section class="metric-card" aria-label="Detected hotspots">
  <div class="metric-label">{icon('fire', 38)}<span>Detected hotspots</span></div>
  <div class="metric-value">{hotspot_total}</div>
  <div class="metric-note"><span class="growth-icon">{icon('trend', 24)}</span><strong>{metrics['growth']}%</strong> compared to the same period in<br>{start.year - 1}</div>
  <div class="muted-note">Selected region · {escape(period_label)}</div>
</section>
<section class="metric-card" aria-label="Period of Peak Activity">
  <div class="metric-label">{icon('calendar', 38)}<span>Period of Peak Activity</span></div>
  <div class="metric-value">{metrics['peak_month']}</div>
  <div class="metric-subvalue">{metrics['peak_count']} Hotspots</div>
  <div class="metric-note">Highest monthly amount in {end.year}</div>
</section>
</div>""", unsafe_allow_html=True)
        st.markdown(f"""<section class="comparison-card" aria-label="Historical Comparison">
  <div class="comparison-main">
    <div class="metric-label">{icon('chart', 38)}<span>Historical Comparison</span></div>
    <div class="metric-value">+{metrics['historical_growth']}%</div>
    <span class="status-chip">Above the historical average</span>
  </div>
  <div class="comparison-stat"><span>Current period</span><strong>{metrics['current_period']}</strong><span>Detected hotspots</span></div>
  <div class="comparison-dot" aria-hidden="true">•</div>
  <div class="comparison-stat"><span>Historical average</span><strong>{metrics['historical_average']}</strong><span>Expected focal points</span></div>
</section>""", unsafe_allow_html=True)
        with st.container(key="trend-panel"):
            st.markdown(f"<div class='chart-title'>Monthly trend in fire outbreaks</div><div class='chart-subtitle'>{escape(location)} · January to December 2025</div>", unsafe_allow_html=True)
            if go:
                trend = go.Figure(go.Scatter(
                    x=["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
                    y=TREND_2025, mode="lines+markers",
                    line={"color": "#fdfbfd", "width": 3},
                    marker={"size": 16, "color": "#fdfbfd", "line": {"width": 3, "color": "#a9aeb8"}},
                    hovertemplate="%{x}: %{y} hotspots<extra></extra>",
                ))
                trend.update_layout(
                    paper_bgcolor="#303646", plot_bgcolor="#303646",
                    font={"color": "#fdfbfd", "family": "Barlow Condensed, Arial", "size": 18},
                    height=470, margin={"l": 42, "r": 12, "t": 45, "b": 38},
                    xaxis={"showgrid": False, "zeroline": False, "tickfont": {"color": "#dedee5"}, "fixedrange": True},
                    yaxis={"gridcolor": "#444957", "gridwidth": 1, "zeroline": True, "zerolinecolor": "#444957", "range": [0, 470], "tickvals": [0, 150, 300, 450], "fixedrange": True},
                    showlegend=False, hoverlabel={"bgcolor": "#09163b"},
                )
                st.plotly_chart(trend, width="stretch", config={"displayModeBar": False}, theme=None)
            else:
                st.line_chart({"Hotspots": TREND_2025}, height=430)

if st.session_state.get("active_dialog") == "filter":
    filter_dialog()
elif st.session_state.get("active_dialog") == "search":
    search_dialog()
