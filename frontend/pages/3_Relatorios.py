import streamlit as st
from datetime import date

from data import dashboard_metrics
from ui import apply_styles, render_sidebar

st.set_page_config(page_title="Reports | Firewatch", page_icon="🔥", layout="wide")
apply_styles()
render_sidebar("Reports")
st.markdown("<div class='eyebrow'>FIREWATCH · SUMMARIES</div>", unsafe_allow_html=True)
st.title("Reports")
st.caption("Summary of the reference scenario shown in the prototype.")
filters = st.session_state.get("filters", {})
period = filters.get("period", (date(2025, 1, 1), date(2025, 12, 31)))
metrics = dashboard_metrics(period, filters or None)
left, middle, right = st.columns(3)
left.metric("Detected hotspots", f"{metrics['hotspots']:,}")
middle.metric("Year-over-year change", f"+{metrics['growth']}%")
right.metric("Historical average", f"{metrics['historical_average']:,}")
st.markdown("### Overview")
st.write(
    f"From {metrics['period_label']}, the selected area records "
    f"{metrics['hotspots']:,} demonstration hotspots. The monthly peak in 2025 "
    f"was {metrics['peak_month']}, with {metrics['peak_count']:,} hotspots."
)
st.info("This summary uses demonstration data from the prototype. Actual results will be available once the API is connected.", icon="ℹ️")
