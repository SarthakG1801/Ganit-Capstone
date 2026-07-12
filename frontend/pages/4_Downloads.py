"""
Page 4 — Downloads.

Buttons wired to the FastAPI download endpoints. Uses st.download_button
fed by the bytes returned from FastAPI (rather than a plain link) since
that gives a cleaner UX and still works even if the FastAPI server isn't
publicly reachable from wherever the user opens the file.
"""
from datetime import date

import streamlit as st

from utils.api_client import download_bytes
from utils.sidebar import render_sidebar

st.set_page_config(page_title="Downloads", page_icon="⬇️", layout="wide")
render_sidebar()

st.title("⬇️ Downloads")
base = "USD"
today_str = date.today().isoformat()

col1, col2, col3 = st.columns(3)

with col1:
    st.subheader("Clean dataset")
    st.caption("Long format, ready for Tableau's text-file connector.")
    if st.button("Prepare clean CSV", use_container_width=True, key="prep_clean"):
        with st.spinner("Fetching from FastAPI..."):
            try:
                st.session_state["clean_csv"] = download_bytes("/download/clean-csv", base=base)
            except Exception as exc:
                st.error(f"Failed: {exc}")
    if "clean_csv" in st.session_state:
        st.download_button(
            "⬇️ Download clean dataset (CSV)",
            data=st.session_state["clean_csv"],
            file_name=f"exchange_rates_clean_{today_str}.csv",
            mime="text/csv",
            use_container_width=True,
        )

with col2:
    st.subheader("Wide-format dataset")
    st.caption("One column per currency — handy for Excel pivoting.")
    if st.button("Prepare wide CSV", use_container_width=True, key="prep_wide"):
        with st.spinner("Fetching from FastAPI..."):
            try:
                st.session_state["wide_csv"] = download_bytes("/download/wide-csv", base=base)
            except Exception as exc:
                st.error(f"Failed: {exc}")
    if "wide_csv" in st.session_state:
        st.download_button(
            "⬇️ Download wide-format dataset (CSV)",
            data=st.session_state["wide_csv"],
            file_name=f"exchange_rates_wide_{today_str}.csv",
            mime="text/csv",
            use_container_width=True,
        )

with col3:
    st.subheader("Full insights report")
    st.caption("Same charts as the Insights Dashboard, plus a text summary page, bundled as one PDF.")
    if st.button("Generate PDF report", use_container_width=True, key="prep_pdf"):
        with st.spinner("Building report on the backend (this generates fresh charts, may take a moment)..."):
            try:
                st.session_state["pdf_report"] = download_bytes("/download/insights-report", base=base)
            except Exception as exc:
                st.error(f"Failed: {exc}")
    if "pdf_report" in st.session_state:
        st.download_button(
            "⬇️ Download insights report (PDF)",
            data=st.session_state["pdf_report"],
            file_name=f"currency_insights_report_{today_str}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

st.divider()
st.info(
    "📎 To load the clean CSV into **Tableau**: open `tableau/currency_dashboard.twbx`, "
    "or start a new workbook and use the text-file connector to point at the "
    "downloaded `exchange_rates_clean_*.csv`. It's already long-format and "
    "Tableau-ready — no reshaping needed."
)
