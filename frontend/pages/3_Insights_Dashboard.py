
import streamlit as st

from utils.api_client import get_chart_png, get_available_currencies, get_summary, get_volatility, get_trend
from utils.sidebar import render_sidebar

st.set_page_config(page_title="Insights Dashboard", page_icon="📊", layout="wide")
render_sidebar()

st.title("📊 Insights Dashboard")

base = "USD"

try:
    currency_codes = sorted(get_available_currencies()["code"].dropna().unique().tolist())
except Exception:
    currency_codes = []

if not currency_codes:
    st.warning("Couldn't load the currency list from the backend. Is FastAPI running?")
    st.stop()


st.subheader("Trend")
default_target = "EUR" if "EUR" in currency_codes else currency_codes[0]
trend_currency = st.selectbox(
    "Currency", currency_codes, index=currency_codes.index(default_target), key="trend_currency"
)

col_chart, col_text = st.columns([2, 1])
with col_chart:
    try:
        png = get_chart_png("trend", currency=trend_currency, base=base)
        st.image(png, use_container_width=True)
    except Exception as exc:
        st.error(f"Couldn't load trend chart: {exc}")

with col_text:
    try:
        trend = get_trend(trend_currency, base=base)
        direction_word = {"up": "trending up", "down": "trending down", "flat": "flat"}[trend["trend_direction"]]
        st.markdown(f"**{trend_currency} is currently {direction_word}** (7d MA vs 30d MA).")
        if trend["pct_change_30d"] is not None:
            st.markdown(f"Moved **{trend['pct_change_30d']:+.2f}%** over the last 30 trading days.")
        st.markdown(f"Latest rate: **{trend['latest_rate']:.4f}**")
    except Exception:
        pass

st.divider()


st.subheader("Volatility ranking")
try:
    vol_png = get_chart_png("volatility", base=base)
    st.image(vol_png, use_container_width=True)
    vol_data = get_volatility(base=base)
    if vol_data["rankings"]:
        top = vol_data["rankings"][0]
        st.markdown(
            f"📌 **{top['target_currency']}** was the most volatile currency as of "
            f"{vol_data['as_of']}, with 30-day rolling volatility of **{top['volatility_30d']:.4f}**."
        )
except Exception as exc:
    st.error(f"Couldn't load volatility chart: {exc}")

st.divider()


st.subheader("Correlation matrix")
st.caption("Scoped to major/liquid currencies for readability — the full dataset tracks 166.")
try:
    corr_png = get_chart_png("correlation", base=base)
    st.image(corr_png, use_container_width=True)
except Exception as exc:
    st.error(f"Couldn't load correlation heatmap: {exc}")

st.divider()


st.subheader("Top gainers / losers")
try:
    movers_png = get_chart_png("top_movers", base=base)
    st.image(movers_png, use_container_width=True)
    summary = get_summary(base=base)
    st.markdown(
        f"📌 Over **{summary['start_date']} → {summary['end_date']}**, "
        f"**{summary['best_performer']}** gained the most against {base} "
        f"({summary['best_performer_pct_change']:+.2f}%), while "
        f"**{summary['worst_performer']}** lost the most "
        f"({summary['worst_performer_pct_change']:+.2f}%)."
    )
except Exception as exc:
    st.error(f"Couldn't load top movers chart: {exc}")