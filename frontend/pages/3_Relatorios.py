import streamlit as st
from datetime import date

from data import dashboard_metrics
from ui import apply_styles, render_sidebar

st.set_page_config(page_title="Relatórios | Firewatch", page_icon="🔥", layout="wide")
apply_styles()
render_sidebar("Relatórios")
st.markdown("<div class='eyebrow'>FIREWATCH · RESUMOS</div>", unsafe_allow_html=True)
st.title("Relatórios")
st.caption("Resumo do cenário de referência apresentado no protótipo.")
filters = st.session_state.get("filters", {})
period = filters.get("period", (date(2025, 1, 1), date(2025, 12, 31)))
metrics = dashboard_metrics(period)
left, middle, right = st.columns(3)
left.metric("Focos detectados", f"{metrics['hotspots']:,}")
middle.metric("Variação anual", f"+{metrics['growth']}%")
right.metric("Média histórica", f"{metrics['historical_average']}")
st.markdown("### Síntese")
st.write(
    f"No período de {metrics['period_label']}, a área selecionada registra "
    f"{metrics['hotspots']:,} focos de referência. O pico mensal observado em 2025 "
    f"foi {metrics['peak_month']}, com {metrics['peak_count']} ocorrências."
)
st.info("Este resumo usa dados demonstrativos do protótipo; resultados reais serão ligados à API quando ela estiver implementada.", icon="ℹ️")
