
import os

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")


def _get(path: str, params: dict | None = None) -> requests.Response:
    resp = requests.get(f"{API_URL}{path}", params=params, timeout=30)
    resp.raise_for_status()
    return resp


@st.cache_data(ttl=300)
def get_summary(base: str = "USD") -> dict:
    return _get("/insights/summary", {"base": base}).json()


@st.cache_data(ttl=300)
def get_currencies(base: str = "USD") -> pd.DataFrame:
    return pd.DataFrame(_get("/currencies").json())


@st.cache_data(ttl=300)
def get_available_currencies(base: str = "USD") -> pd.DataFrame:
    """Currencies that actually have rate data -- safe source for dropdowns."""
    return pd.DataFrame(_get("/currencies/available", {"base": base}).json())


@st.cache_data(ttl=300)
def get_rates(
    base: str = "USD",
    target: str | None = None,
    start=None,
    end=None,
) -> pd.DataFrame:
    params = {"base": base}
    if target:
        params["target"] = target
    if start:
        params["start"] = str(start)
    if end:
        params["end"] = str(end)
    return pd.DataFrame(_get("/rates", params).json())


@st.cache_data(ttl=300)
def get_volatility(base: str = "USD") -> dict:
    return _get("/insights/volatility", {"base": base}).json()


@st.cache_data(ttl=300)
def get_correlation(base: str = "USD", major_only: bool = True) -> dict:
    return _get("/insights/correlation", {"base": base, "major_only": major_only}).json()


@st.cache_data(ttl=300)
def get_trend(currency: str, base: str = "USD") -> dict:
    return _get(f"/insights/trend/{currency}", {"base": base}).json()


@st.cache_data(ttl=300)
def get_chart_png(chart_name: str, currency: str = "EUR", base: str = "USD") -> bytes:
    return _get(f"/insights/charts/{chart_name}", {"currency": currency, "base": base}).content


def download_bytes(path: str, base: str = "USD") -> bytes:
    return _get(path, {"base": base}).content


def refresh_data(base: str = "USD", api_key: str | None = None) -> dict:

    headers = {"X-API-Key": api_key} if api_key else {}
    resp = requests.post(f"{API_URL}/admin/refresh", params={"base": base}, headers=headers, timeout=120)
    resp.raise_for_status()
    st.cache_data.clear()
    return resp.json()