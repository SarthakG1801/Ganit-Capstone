
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.api_client import get_available_currencies, get_rates
from utils.sidebar import render_sidebar

st.set_page_config(page_title="Currency Explorer", page_icon="🔎", layout="wide")
render_sidebar()

st.title("🔎 Currency Explorer")

try:
    currencies_df = get_available_currencies()
    currency_codes = sorted(currencies_df["code"].dropna().unique().tolist())
except Exception:
    currency_codes = []

if not currency_codes:
    st.warning("Couldn't load the currency list from the backend. Is FastAPI running?")
    st.stop()

col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    base = st.selectbox("Base currency", ["USD"], index=0, help="Pipeline currently tracks USD as base.")
with col2:
    default_target = "EUR" if "EUR" in currency_codes else currency_codes[0]
    target = st.selectbox(
        "Target currency", currency_codes, index=currency_codes.index(default_target)
    )
with col3:
    today = date.today()
    start_default = today - timedelta(days=180)
    date_range = st.date_input(
        "Date range", value=(start_default, today), min_value=today - timedelta(days=365), max_value=today
    )

start, end = (date_range if isinstance(date_range, tuple) and len(date_range) == 2 else (start_default, today))

df = get_rates(base=base, target=target, start=start, end=end)

if df.empty:
    st.info("No data for this selection yet.")
    st.stop()

df["date"] = pd.to_datetime(df["date"])
df = df[df["is_trading_day"] == 1].sort_values("date")

fig = go.Figure()
fig.add_trace(go.Scatter(x=df["date"], y=df["rate"], name="Rate", line=dict(width=1.5)))
fig.add_trace(go.Scatter(x=df["date"], y=df["ma_7"], name="7-day MA", line=dict(width=1, dash="dot")))
fig.add_trace(go.Scatter(x=df["date"], y=df["ma_30"], name="30-day MA", line=dict(width=1.5, dash="dash")))
fig.update_layout(
    title=f"{base} → {target}",
    xaxis_title="Date",
    yaxis_title="Rate",
    height=450,
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
)
st.plotly_chart(fig, use_container_width=True)

c1, c2, c3 = st.columns(3)
c1.metric("Latest rate", f"{df['rate'].iloc[-1]:.4f}")
c2.metric("Period change", f"{(df['rate'].iloc[-1] / df['rate'].iloc[0] - 1) * 100:+.2f}%")
c3.metric("Avg 30d volatility (period)", f"{df['volatility_30d'].mean():.4f}")

st.subheader("Raw data")
st.dataframe(
    df[
        [
            "date", "rate", "daily_pct_change", "ma_7", "ma_30",
            "volatility_30d", "day_of_week", "is_month_end",
        ]
    ],
    use_container_width=True,
    hide_index=True,
)