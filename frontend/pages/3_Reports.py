"""Historical Analysis: indicators, anomalies and paginated detection records."""

if __name__ == "__main__":
    from pathlib import Path
    import sys

    frontend_path = str(Path(__file__).resolve().parents[1])
    if frontend_path not in sys.path:
        sys.path.insert(0, frontend_path)
    from bootstrap import launch_if_direct

    launch_if_direct()

from pathlib import Path
import re

import streamlit as st

from activity_data import AVAILABLE_YEARS
from locations import REGIONS
from reports_data import ANOMALY_THRESHOLD, detection_records, historical_summary, record_page, records_csv
from reports_ui import anomalies_html, comparison_figure, indicators_html, records_html
from ui import apply_styles, render_sidebar, searchable_selectbox


st.set_page_config(page_title="Historical Analysis | Firewatch", page_icon="🔥", layout="wide", initial_sidebar_state="expanded")
apply_styles()
st.markdown(f"<style>{(Path(__file__).resolve().parents[1] / 'reports.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
render_sidebar("Reports")


def change_slide(index):
    st.session_state.reports_slide = index


def change_page(offset):
    st.session_state.reports_record_page += offset


# Inherit the map's administrative area, retaining report selections on reruns.
shared = st.session_state.get("filters", {})
origin = (shared.get("country", "Brazil"), shared.get("state", "São Paulo"))
if st.session_state.get("reports_location_origin") != origin:
    country = origin[0] if origin[0] in REGIONS else "Brazil"
    st.session_state.reports_country = country
    st.session_state.reports_state = origin[1] if origin[1] in REGIONS[country] else "All regions"
    st.session_state.reports_location_origin = origin
st.session_state.setdefault("reports_slide", 0)
st.session_state.setdefault("reports_record_page", 0)

with st.container(key="reports-page"):
    heading, export = st.columns([4, 1], vertical_alignment="center")
    with heading:
        st.markdown('''<header class="historical-intro"><h1>Historical Analysis</h1>
<p>Activity comparison and anomaly identification.</p></header>''', unsafe_allow_html=True)

    with st.container(key="reports-filters"):
        st.markdown('<h2 class="historical-section-title">Area of interest &amp; Period</h2>', unsafe_allow_html=True)
        country_col, state_col, _, year_col = st.columns([2, 2, 2.3, 1.1], vertical_alignment="bottom")
        with country_col:
            country = searchable_selectbox("Country", list(REGIONS), key="reports_country", persist_state="session", icon=None)
        country = country or st.session_state.get("reports_valid_country", origin[0])
        states = list(REGIONS[country])
        if st.session_state.get("reports_state") not in states:
            st.session_state.reports_state = "All regions"
        with state_col:
            state = searchable_selectbox("State/Province", states, key="reports_state", persist_state="session", icon=None)
        state = state or "All regions"
        with year_col:
            year = searchable_selectbox("Period analyzed", AVAILABLE_YEARS, key="reports_year", persist_state="session", icon=None) or 2025
        st.session_state.reports_valid_country = country

    selection = (year, country, state)
    if st.session_state.get("reports_record_selection") != selection:
        st.session_state.reports_record_page = 0
        st.session_state.reports_record_selection = selection
    summary = historical_summary(*selection)
    with export:
        filename = re.sub(r"[^\w-]+", "_", f"firewatch_{country}_{state}_{year}_demo")
        st.download_button("Export all data", data=records_csv(*selection),
                           file_name=f"{filename}.csv", mime="text/csv", icon=":material/download:",
                           key="reports-export", disabled=summary["total"] == 0, on_click="ignore")

    slide = st.session_state.reports_slide
    with st.container(key=f"reports-panel-{slide}"):
        with st.container(key="reports-carousel-body"):
            back, content, forward = st.columns([.18, 10, .18], gap="small", vertical_alignment="center")
            with back:
                if slide > 0:
                    st.button("Previous section", icon=":material/chevron_left:", key="reports-previous", type="tertiary",
                              on_click=change_slide, args=(slide - 1,), help="Previous section")
            with content:
                if slide == 0:
                    st.markdown('<h2 class="historical-section-title">Historical indicators</h2>', unsafe_allow_html=True)
                    st.markdown(indicators_html(summary), unsafe_allow_html=True)
                elif slide == 1:
                    anomalies, chart = st.columns([1, 1.4], gap="large")
                    with anomalies:
                        st.markdown(anomalies_html(summary), unsafe_allow_html=True)
                    with chart:
                        st.markdown('<h2 class="historical-section-title">Current activity vs. historical average</h2>', unsafe_allow_html=True)
                        with st.container(key="reports-chart"):
                            st.caption("Illustrative figures for detected hotspots per month.")
                            st.plotly_chart(comparison_figure(summary), key="reports-comparison", width="stretch",
                                            height=400, theme=None, config={"displayModeBar": False})
                else:
                    st.markdown('<h2 class="historical-section-title">Detection record</h2>', unsafe_allow_html=True)
                    page = record_page(detection_records(*selection), st.session_state.reports_record_page)
                    st.session_state.reports_record_page = page["page"]
                    st.markdown(records_html(page), unsafe_allow_html=True)
                    with st.container(key="reports-pagination", horizontal=True, horizontal_alignment="center"):
                        st.button("Back", icon=":material/arrow_back:", key="records-back", disabled=page["page"] == 0,
                                  on_click=change_page, args=(-1,))
                        st.button("Next", icon=":material/arrow_forward:", key="records-next", disabled=page["page"] + 1 >= page["pages"],
                                  on_click=change_page, args=(1,))
            with forward:
                if slide < 2:
                    st.button("Next section", icon=":material/chevron_right:", key="reports-next", type="tertiary",
                              on_click=change_slide, args=(slide + 1,), help="Next section")

        with st.container(key="reports-dots", horizontal=True, horizontal_alignment="center", gap="small"):
            for index, label in enumerate(("Historical indicators", "Anomaly identification", "Detection record")):
                st.button("●" if slide == index else "○", key=f"reports-dot-{index}", type="tertiary",
                          help=label, on_click=change_slide, args=(index,))

    baseline = ", ".join(str(y) for y in sorted(summary["previous_years"])) or "unavailable"
    st.caption(f"Synthetic demonstration data · Historical baseline: {baseline}. "
               f"Anomalies: monthly deviation ≥ {ANOMALY_THRESHOLD:g}% in either direction, or activity with a zero baseline. "
               "Area totals include catalog cities only. Record times and sensor assignments are simulated; coordinates are city centers. "
               "N/A: satellite, confidence, radiative power and day/night are unavailable.")
