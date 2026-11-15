import streamlit as st
try:
    import plotly.graph_objects as go
except ModuleNotFoundError:
    go = None

from data import MONTHS, TREND_2025
from ui import apply_styles, render_sidebar

st.set_page_config(page_title="Atividade | Firewatch", page_icon="🔥", layout="wide")
apply_styles()
render_sidebar("Atividade")
st.markdown("<div class='eyebrow'>FIREWATCH · HISTÓRICO</div>", unsafe_allow_html=True)
st.title("Atividade de incêndios")
st.caption("Explore a distribuição mensal dos focos de referência em 2025.")
if go:
    fig = go.Figure(go.Bar(x=MONTHS, y=TREND_2025, marker_color="#4bc2dd", hovertemplate="%{x}: %{y} focos<extra></extra>"))
    fig.update_layout(paper_bgcolor="#303848", plot_bgcolor="#303848", font_color="#f5f7fb", height=430,
                      margin={"l":25,"r":20,"t":25,"b":35}, xaxis={"showgrid":False}, yaxis={"gridcolor":"#424b5d"})
    st.plotly_chart(fig, use_container_width=True)
else:
    st.bar_chart({"Focos": TREND_2025}, height=430)
st.info("Os valores exibidos são demonstrativos. A conexão com os dados processados será adicionada quando a API estiver disponível.", icon="ℹ️")
