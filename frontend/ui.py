"""Estilos e navegação compartilhados entre as telas."""

from pathlib import Path

import streamlit as st


def icon(name, size=32):
    """Ícones vetoriais sem dependências externas."""
    paths = {
        "fire": '<path fill="currentColor" stroke="none" d="M13 1c1 6 7 7 7 13a8 8 0 0 1-6 8c3-5-1-7-2-10-1 3-5 5-3 10A8 8 0 0 1 3 14c0-4 3-8 6-12l3 5z"/>',
        "calendar": '<rect x="3" y="5" width="18" height="17" rx="2"/><path d="M7 2v6M17 2v6M3 11h18M7 15h1m4 0h1m4 0h1M7 18h1m4 0h1m4 0h1"/>',
        "chart": '<path d="m2 13 6-5 5 3L22 2M17 2h5v5M4 17v5m5-9v9m5-7v7m5-11v11"/>',
        "pin": '<path d="M20 10c0 6-8 13-8 13S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
        "trend": '<path d="m2 18 7-7 5 3 8-10M16 4h6v6"/>',
    }
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>'


def apply_styles(dashboard=False):
    st.markdown(f"<style>{Path(__file__).with_name('styles.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
    if dashboard:
        st.markdown("<style>.stMainBlockContainer{max-width:none;padding:18px 14px 12px!important}.stMainBlockContainer>[data-testid='stVerticalBlock']{gap:0}</style>", unsafe_allow_html=True)


def render_sidebar(active):
    active_page = {"Mapa": 1, "Atividade": 2, "Relatórios": 3}[active]
    st.markdown(f"<style>.st-key-navigation>[data-testid='stElementContainer']:nth-child({active_page}) [data-testid='stPageLink-NavLink']{{background:var(--blue)}}</style>", unsafe_allow_html=True)
    with st.sidebar:
        st.markdown('''<div class="space-apps-logo" aria-label="NASA Space Apps Challenge">
          <span class="logo-orbit"></span><small>NASA</small><strong>SPACE APPS</strong><span>CHALLENGE</span>
        </div>''', unsafe_allow_html=True)
        with st.container(key="navigation"):
            st.page_link("app.py", label="Map", icon=":material/map:", help="Mapa de focos de incêndio")
            st.page_link("pages/2_Atividade.py", label="Activity", icon=":material/event:", help="Atividade mensal")
            st.page_link("pages/3_Relatorios.py", label="Reports", icon=":material/description:", help="Relatórios")
