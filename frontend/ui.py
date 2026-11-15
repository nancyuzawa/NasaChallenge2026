"""Estilos e navegação compartilhados entre as telas."""

from base64 import b64encode
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
        "pie": '<path fill="currentColor" stroke="none" d="M10 2a10 10 0 1 0 12 12H10Z"/><path d="M14 2v8h8a8 8 0 0 0-8-8Z" fill="currentColor" stroke="none"/>',
        "filter": '<path d="M4 3h16a1 1 0 0 1 .8 1.6L14 13v7l-4 2v-9L3.2 4.6A1 1 0 0 1 4 3Z"/>',
    }
    return f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{paths[name]}</svg>'


def apply_styles(dashboard=False):
    st.markdown(f"<style>{Path(__file__).with_name('styles.css').read_text(encoding='utf-8-sig')}</style>", unsafe_allow_html=True)
    st.html(Path(__file__).with_name("select_search.html"), unsafe_allow_javascript=True)
    if dashboard:
        st.markdown("<style>.stApp{--dashboard-page:1}.stMainBlockContainer:has(.st-key-dashboard-grid){max-width:none;padding:var(--page-gap)!important}.stMainBlockContainer:has(.st-key-dashboard-grid)>[data-testid='stVerticalBlock']{gap:0}</style>", unsafe_allow_html=True)


def searchable_selectbox(label, options, **kwargs):
    """Campo editável com pesquisa textual diretamente no seletor."""
    kwargs.setdefault("placeholder", "Type to search…")
    kwargs.setdefault("help", "Type in this field to search the available options.")
    kwargs.setdefault("icon", ":material/search:")
    return st.selectbox(label, options, filter_mode="contains", **kwargs)


def render_sidebar(active, show_navigation=True):
    if show_navigation:
        active_page = {"Map": 1, "Activity": 2, "Reports": 3}[active]
        selected = f".st-key-navigation>[data-testid='stElementContainer']:nth-child({active_page}) [data-testid='stPageLink-NavLink']"
        st.markdown(f"<style>{selected}{{background:#fff;color:#000}}{selected} [data-testid='stIconMaterial']{{color:#000!important}}</style>", unsafe_allow_html=True)
    logo_path = Path(__file__).resolve().parent.parent / "midias" / "logo" / "Logo.svg"
    logo = b64encode(logo_path.read_bytes()).decode("ascii")
    with st.sidebar:
        st.markdown(f'<img class="space-apps-logo" src="data:image/svg+xml;base64,{logo}" alt="NASA Space Apps Challenge">', unsafe_allow_html=True)
        if show_navigation:
            with st.container(key="navigation"):
                st.page_link("pages/1_Dashboard.py", label="Map", icon=":material/map:", help="Fire hotspots map")
                st.page_link("pages/2_Activity.py", label="Activity", icon=":material/event:", help="Monthly activity")
                st.page_link("pages/3_Reports.py", label="Reports", icon=":material/description:", help="Reports")
