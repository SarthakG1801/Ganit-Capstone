
import streamlit as st

from utils.api_client import refresh_data


def render_sidebar() -> None:
    with st.sidebar:
        st.header("Data refresh")
        st.write(
            "Pulls only the new dates since the last row in the database, "
            "recomputes moving averages / volatility for those new rows, "
            "and purges anything older than 1 year so the dataset stays a "
            "rolling 365-day window."
        )
        admin_key = st.text_input(
            "Admin API key (if configured)", type="password", key="admin_api_key"
        )

        if st.button("🔄 Refresh data", use_container_width=True, key="refresh_button"):
            with st.spinner("Fetching new rates and purging stale data..."):
                try:
                    result = refresh_data(api_key=admin_key or None)
                except Exception as exc:
                    st.error(f"Refresh failed: {exc}")
                else:
                    st.success(
                        f"Done in {result['duration_seconds']}s — "
                        f"{result['rows_fetched']} new rows fetched, "
                        f"{result['rows_upserted']} rows upserted, "
                        f"{result['rows_purged']} stale rows purged."
                    )
                    st.caption(
                        f"Window now covers {result['date_range_after'][0]} → "
                        f"{result['date_range_after'][1]} "
                        f"(purge cutoff: {result['purge_cutoff_date']})"
                    )
                    for note in result.get("notes", []):
                        st.caption(f"ℹ️ {note}")
                    st.rerun()
