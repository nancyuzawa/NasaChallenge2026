"""Tela de detalhamento mensal ligada ao calendário de atividade."""

import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

from activity_data import AVAILABLE_YEARS, MONTH_NAMES, SENSORS, daily_activity, month_summary
from activity_ui import month_metrics_html
from ui import searchable_selectbox


SENSOR_COLORS = {"MODIS": "#ff3b30", "VIIRS": "#ffd166"}


def open_month(month, year):
    st.session_state.detail_month = month
    st.session_state.detail_year = year
    st.session_state.activity_view = "month"


def back_to_calendar():
    st.session_state.activity_view = "calendar"


def render_month_details(filters, provider=None):
    available = provider.years() if provider else AVAILABLE_YEARS
    get_summary = provider.month_summary if provider else month_summary
    get_daily = provider.daily_activity if provider else daily_activity
    st.html(Path(__file__).with_name("month_details.css"))
    with st.container(key="month-page"):
        st.button("Back", icon=":material/chevron_left:", key="month-back", on_click=back_to_calendar)
        st.markdown('<nav class="month-breadcrumb" aria-label="Breadcrumb">Fire Activity Calendar / <strong>Month Details</strong></nav>', unsafe_allow_html=True)
        st.markdown('''<header class="activity-intro month-intro"><h1>Month Details</h1>
<p>Explore data on fire hotspots for the selected month. </p></header>''', unsafe_allow_html=True)
        with st.container(key="month-panel"):
            with st.container(key="calendar-controls", horizontal=True, gap="small"):
                with st.container(key="sensor-controls", horizontal=True, gap="small", width="content"):
                    sensors = st.pills("Satellite sensors", SENSORS, selection_mode="multi", default=SENSORS, key="activity_sensors",
                                       label_visibility="collapsed", wrap=False, persist_state="session")
                with st.container(key="calendar-period-controls", horizontal=True, gap="small", width="content"):
                    month = searchable_selectbox("Month", list(range(1, 13)), format_func=lambda value: MONTH_NAMES[value - 1],
                                                 key="detail_month", label_visibility="collapsed", required=True)
                    year = searchable_selectbox("Calendar year", available, key="detail_year", label_visibility="collapsed", required=True)
            with st.spinner("Loading monthly activity…", show_time=True):
                summary = get_summary(year, month, filters, sensors)
            with st.container(key="month-content"):
                chart, metrics = st.columns([1.1, 1], gap="medium", vertical_alignment="center")
                with chart:
                    st.markdown('<h2 class="month-chart-title">Evolution of Outbreaks During the Month</h2>', unsafe_allow_html=True)
                    figure = go.Figure()
                    for sensor in SENSORS:
                        if sensor not in sensors:
                            continue
                        counts = get_daily(year, filters, [sensor])
                        figure.add_trace(go.Bar(
                            name=sensor,
                            x=[day.day for day, _ in summary["days"]],
                            y=[counts.get(day) for day, _ in summary["days"]],
                            marker={"color": SENSOR_COLORS[sensor], "line": {"width": 0}},
                            hovertemplate=f"{sensor} · {MONTH_NAMES[month - 1]} %{{x}}, {year}: %{{y:,}} {summary.get('unit', 'hotspots')}<extra></extra>",
                        ))
                    last_day = len(summary["days"])
                    figure.update_layout(
                        paper_bgcolor="#303646", plot_bgcolor="#303646", barmode="stack", showlegend=True,
                        legend={"orientation": "h", "x": 0, "y": 1.15, "itemclick": False, "itemdoubleclick": False},
                        font={"family": "Barlow, Arial", "size": 13, "color": "#d5d8e2"},
                        margin={"l": 40, "r": 8, "t": 16, "b": 32}, bargap=.42,
                        xaxis={"tickmode": "array", "tickvals": [1, 5, 10, 15, 20, 25, last_day],
                               "showgrid": True, "gridcolor": "#424a5a", "fixedrange": True, "range": [.4, last_day + .6]},
                        yaxis={"rangemode": "tozero", "gridcolor": "#495162", "zerolinecolor": "#495162", "fixedrange": True},
                        hoverlabel={"bgcolor": "#09163b"},
                    )
                    st.plotly_chart(figure, key="month-daily-chart", width="stretch", height=360, theme=None, config={"displayModeBar": False})
                with metrics:
                    st.markdown(month_metrics_html(summary), unsafe_allow_html=True)
