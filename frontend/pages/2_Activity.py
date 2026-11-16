"""Calendário de atividade e comparação anual do segundo item do menu."""

if __name__ == "__main__":
    from pathlib import Path
    import sys

    frontend_path = str(Path(__file__).resolve().parents[1])
    if frontend_path not in sys.path:
        sys.path.insert(0, frontend_path)
    from bootstrap import launch_if_direct

    launch_if_direct()

from pathlib import Path

import plotly.graph_objects as go
import streamlit as st

from processed_activity import years, MONTH_NAMES, MONTH_LABELS, SERIES_COLORS, SENSORS, annual_summary, calendar_cells, heat_legend
from processed_data import dataset_status
from activity_ui import calendar_html, chart_heading, key_periods_html, legend_html, summary_html
from month_details import open_month, render_month_details
from ui import apply_styles, render_sidebar, searchable_selectbox


st.set_page_config(page_title="Fire Activity Calendar | Firewatch", page_icon="🔥", layout="wide", initial_sidebar_state="expanded")
apply_styles()
st.markdown(f"<style>{(Path(__file__).resolve().parents[1] / 'activity.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
render_sidebar("Activity")
filters = st.session_state.get("filters")
with st.spinner("Loading activity data…", show_time=True):
    AVAILABLE_YEARS = years()
    status = dataset_status()
real = not status["demo"]
st.caption(status["label"] + (" · Cell-days; gray cells indicate missing observations. VIIRS is provisional without three earlier overlap months." if real else " · Demonstration data"))
for key in ("calendar_year", "comparison_year", "detail_year"):
    if key in st.session_state and st.session_state[key] not in AVAILABLE_YEARS:
        st.session_state[key] = AVAILABLE_YEARS[0]
if filters:
    state, country, city = filters.get("state"), filters["country"], filters.get("city")
    area = [city] if city else []
    if state and state not in ("All regions", city):
        area.append(state)
    location = ", ".join([*area, country])
else:
    location = "Campinas, São Paulo, Brazil"


def render_location():
    with st.container(key="activity-location", width="content"):
        st.page_link("pages/1_Dashboard.py", label=location, icon=":material/location_on:", help=location)


if st.session_state.get("activity_view") == "month":
    render_month_details(filters, provider=__import__("processed_activity"))
    render_location()
    st.stop()

with st.container(key="activity-page"):
    st.markdown('''<header class="activity-intro"><h1>Fire Activity Calendar</h1>
<p>Visualize the number of fire hotspots by month and year, identifying periods of peak and low activity.</p></header>''', unsafe_allow_html=True)

    with st.container(key="activity-calendar"):
        with st.container(key="calendar-split"):
            heatmap, legend_column = st.columns([4.8, 1], gap="medium")
            with heatmap:
                with st.container(key="calendar-main"):
                    with st.container(key="calendar-controls", horizontal=True, gap="small"):
                        with st.container(key="sensor-controls", horizontal=True, gap="small", vertical_alignment="center", width="content"):
                            sensors = st.pills("Satellite sensors", SENSORS, selection_mode="multi", default=SENSORS, key="activity_sensors",
                                               label_visibility="collapsed", wrap=False, persist_state="session")
                        with st.container(key="calendar-period-controls", horizontal=True, gap="small", width="content"):
                            month = searchable_selectbox("Month", list(range(13)), format_func=lambda value: "All months" if value == 0 else MONTH_NAMES[value - 1],
                                                         key="calendar_month", label_visibility="collapsed", persist_state="session", icon=None) or 0
                            calendar_year = searchable_selectbox("Calendar year", AVAILABLE_YEARS, key="calendar_year", label_visibility="collapsed", persist_state="session", icon=None) or AVAILABLE_YEARS[0]
                    with st.spinner("Loading activity calendar…", show_time=True):
                        cells = calendar_cells(calendar_year, month, filters, sensors)
                        legend = heat_legend(cell["count"] for cell in cells)
                    with st.container(key="calendar-body"):
                        st.markdown(calendar_html(cells, legend), unsafe_allow_html=True)
                    if month:
                        with st.container(key="calendar-footer", horizontal=True, horizontal_alignment="right"):
                            st.button("See more details", icon=":material/arrow_forward:", key="see-month-details",
                                      on_click=open_month, args=(month, calendar_year))
            with legend_column:
                st.markdown(legend_html(legend, "cell-days" if real else "hotspots"), unsafe_allow_html=True)

    st.markdown('''<header class="activity-section-heading"><h2>Annual analysis</h2>
<p>Compare the burning activity across the years.</p></header>''', unsafe_allow_html=True)

    with st.container(key="activity-annual"):
        with st.container(key="annual-controls", horizontal=True, gap="small"):
            end_year = searchable_selectbox("Comparison year", AVAILABLE_YEARS, key="comparison_year", label_visibility="collapsed", persist_state="session", icon=None) or AVAILABLE_YEARS[0]
            available = [year for year in AVAILABLE_YEARS if year <= end_year]
            if st.session_state.get("comparison_range", 1) > len(available):
                st.session_state.comparison_range = len(available)
            span = searchable_selectbox("Comparison range", list(range(len(available), 0, -1)),
                                        format_func=lambda value: "Last year" if value == 1 else f"Last {value} years",
                                        key="comparison_range", label_visibility="collapsed", persist_state="session", icon=None) or len(available)
        with st.spinner("Preparing annual comparison…", show_time=True):
            summaries = [annual_summary(year, filters, sensors) for year in available[:span]]
        colors = [SERIES_COLORS[i % len(SERIES_COLORS)] for i in range(len(summaries))]
        with st.container(key="annual-comparison"):
            chart, periods = st.columns([4, 1.2], gap="medium")
            with chart:
                with st.container(key="annual-chart"):
                    st.markdown(chart_heading(summaries, colors), unsafe_allow_html=True)
                    figure = go.Figure()
                    for summary, color in zip(summaries, colors):
                        figure.add_trace(go.Scatter(
                            x=MONTH_LABELS, y=summary["series"], name=str(summary["year"]), mode="lines+markers",
                            line={"color": color, "width": 2}, marker={"size": 6, "color": "#303646", "line": {"color": color, "width": 2}},
                            hovertemplate=f"{summary['year']} · %{{x}}: %{{y:,}} {'cell-days' if real else 'hotspots'}<extra></extra>",
                        ))
                    figure.update_layout(
                        autosize=True, paper_bgcolor="#303646", plot_bgcolor="#303646", showlegend=False,
                        font={"family": "Barlow, Arial", "size": 11, "color": "#d5d8e2"},
                        margin={"l": 33, "r": 10, "t": 14, "b": 26},
                        xaxis={"showgrid": True, "gridcolor": "#424a5a", "fixedrange": True},
                        yaxis={"range": [0, max(10, max((n for summary in summaries for n in summary["series"] if n is not None), default=0) * 1.15)], "gridcolor": "#495162", "zerolinecolor": "#495162", "nticks": 5, "fixedrange": True},
                        hovermode="x unified", hoverlabel={"bgcolor": "#09163b"},
                    )
                    st.plotly_chart(figure, key="annual-comparison-chart", width="stretch", height="stretch", theme=None, config={"displayModeBar": False})
            with periods:
                st.markdown(key_periods_html(summaries, colors), unsafe_allow_html=True)
        st.markdown(summary_html(summaries, colors), unsafe_allow_html=True)

render_location()
