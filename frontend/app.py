"""Página inicial de escolha de localização do Firewatch."""

if __name__ == "__main__":
    from bootstrap import launch_if_direct

    launch_if_direct()

from datetime import date
from pathlib import Path

import streamlit as st

from locations import COUNTRIES, selection_filters
from navigation_loading import show_dashboard_loading
from ui import apply_styles, render_sidebar, searchable_selectbox


st.set_page_config(
    page_title="Welcome | Firewatch", page_icon="🔥", layout="wide",
    initial_sidebar_state="expanded",
)
apply_styles()
st.markdown(f"<style>{Path(__file__).with_name('welcome.css').read_text(encoding='utf-8')}</style>", unsafe_allow_html=True)
st.html(Path(__file__).with_name("welcome_keyboard.html"), unsafe_allow_javascript=True)
render_sidebar("Home", show_navigation=False)

with st.container(key="welcome", width=520):
    st.markdown('''<div class="welcome-heading">
      <h1>Hi, welcome!</h1>
      <svg class="welcome-sparkles" viewBox="0 0 70 70" aria-hidden="true">
        <path d="M48 3 53 18 66 24 53 30 48 46 43 30 30 24 43 18Z"/>
        <path d="m15 43 3 6 6 3-6 3-3 7-3-7-6-3 6-3Z"/>
      </svg>
    </div><p class="welcome-subtitle">Choose a location to start viewing the data</p>''', unsafe_allow_html=True)
    with st.form("welcome_form", border=False):
        countries = sorted(COUNTRIES, key=lambda code: COUNTRIES[code]["name"])
        country = searchable_selectbox(
            "Country", countries, index=None, key="welcome_country",
            format_func=lambda code: COUNTRIES[code]["name"],
            placeholder="Select a country", label_visibility="collapsed",
        )
        if st.form_submit_button("Confirm", type="primary", width="stretch"):
            if country is None:
                st.error("Select a country to continue.")
            else:
                current = st.session_state.get("filters", {
                    "period": (date(2025, 1, 1), date(2025, 12, 31)),
                })
                st.session_state.filters = selection_filters({"kind": "country", "id": country}, current)
                st.session_state.active_dialog = None
                st.session_state._dashboard_navigation_loading = True
                show_dashboard_loading()
                st.switch_page("pages/1_Dashboard.py")
