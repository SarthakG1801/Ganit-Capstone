"""
Streamlit entrypoint. This is a starter scaffold for Phase 4 -- a full
Overview / Currency Explorer / Insights Dashboard / Downloads multi-page
build comes later per the build plan. For now this wires up the one thing
that was explicitly needed alongside the backend: a working "Refresh data"
button that calls FastAPI's POST /admin/refresh, shows what changed, and
clears Streamlit's cached reads so the rest of the app reflects the new
(purged-to-1-year) data immediately.

Run with:  streamlit run frontend/app.py
"""
import streamlit as st

from utils.api_client import get_summary, API_URL
from utils.sidebar import render_sidebar

st.set_page_config(page_title="Currency Exchange Insights", page_icon="💱", layout="wide")

st.title("💱 Currency Exchange Insights")
st.caption(f"Talking to FastAPI at `{API_URL}`")

render_sidebar()

# ------------------------------------------------------------- overview ----
st.subheader("Overview")
try:
    summary = get_summary()
except Exception as exc:
    st.warning(f"Couldn't reach the backend at {API_URL}: {exc}")
else:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Currencies tracked", summary["num_currencies"])
    c2.metric(
        f"Best performer — {summary['best_performer']}",
        f"{summary['best_performer_pct_change']:+.2f}%",
    )
    c3.metric(
        f"Worst performer — {summary['worst_performer']}",
        f"{summary['worst_performer_pct_change']:+.2f}%",
    )
    c4.metric("Avg 30d volatility", f"{summary['avg_volatility_30d']:.4f}")
    st.caption(f"Data window: {summary['start_date']} → {summary['end_date']} (base {summary['base_currency']})")

st.divider()
st.markdown(
    "Use the pages in the sidebar to explore individual currencies, view the "
    "insights dashboard (charts + auto-generated commentary), or download the "
    "clean dataset / report."
)