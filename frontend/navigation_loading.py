"""Loading overlay for the Welcome to Dashboard transition."""
import streamlit as st


def show_dashboard_loading():
    placeholder=st.empty()
    placeholder.markdown("""
<style>
.dashboard-loading-overlay {
  position:fixed; inset:0; z-index:999990;
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  gap:20px; background:rgba(9,22,59,.96); color:#f1f5f9;
  font:600 20px Barlow,Arial,sans-serif; text-align:center; padding:24px;
}
.dashboard-loading-ring {
  width:56px; height:56px; border:5px solid #53657e;
  border-top-color:#57c9c0; border-radius:50%;
  animation:dashboard-loading-spin .85s linear infinite;
}
.dashboard-loading-overlay p { color:#f1f5f9 !important; margin:0; }
@keyframes dashboard-loading-spin { to { transform:rotate(360deg); } }
@media (prefers-reduced-motion:reduce) { .dashboard-loading-ring { animation:none; } }
</style>
<div class="dashboard-loading-overlay" role="status" aria-live="polite" aria-busy="true">
  <div class="dashboard-loading-ring" aria-hidden="true"></div>
  <p>Preparing your dashboard…</p>
</div>
""",unsafe_allow_html=True)
    return placeholder
