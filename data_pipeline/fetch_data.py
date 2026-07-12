"""
Fetches 1 year of historical exchange rate data from the Frankfurter API (v2)
and stores it as a tidy long-format pandas DataFrame.

v2 returns data already in long format (a flat JSON array of
{date, base, quote, rate} records), so no melt/reshape step is needed —
that's the main simplification vs. the v1 version of this script.

Run:
    python data_pipeline/fetch_data.py
"""

import json
import os
from datetime import date, timedelta

import pandas as pd
import requests

BASE_URL = "https://api.frankfurter.dev/v2"
BASE_CURRENCY = "USD"

TARGET_CURRENCIES = None

PROVIDER = None

RAW_DIR = "data/raw"
PROCESSED_DIR = "data/processed"


def fetch_year_of_rates(base: str, targets: list | None, provider: str | None = None) -> list[dict]:
    end = date.today()
    start = end - timedelta(days=365)

    params = {"base": base, "from": str(start), "to": str(end)}
    if targets:
        params["quotes"] = ",".join(targets)
    if provider:
        params["providers"] = provider

    url = f"{BASE_URL}/rates"
    print(f"Requesting: {url}  params={params}")

    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    records = resp.json()

    dates = {r["date"] for r in records}
    print(f"Received {len(records)} rate rows across {len(dates)} days "
          f"({min(dates)} to {max(dates)})")
    return records


def save_raw(records: list[dict]) -> str:
    os.makedirs(RAW_DIR, exist_ok=True)
    path = os.path.join(RAW_DIR, f"exchange_rates_raw_{date.today()}.json")
    with open(path, "w") as f:
        json.dump(records, f, indent=2)
    print(f"Raw JSON saved to {path}")
    return path


def to_long_df(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    df = df.rename(columns={"base": "base_currency", "quote": "target_currency"})
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["target_currency", "date"]).reset_index(drop=True)
    return df[["date", "base_currency", "target_currency", "rate"]]


def save_processed(df: pd.DataFrame) -> str:
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    path = os.path.join(PROCESSED_DIR, "exchange_rates_raw_long.csv")
    df.to_csv(path, index=False)
    print(f"Long-format CSV saved to {path}")
    return path


def main():
    records = fetch_year_of_rates(BASE_CURRENCY, TARGET_CURRENCIES, PROVIDER)
    save_raw(records)

    df = to_long_df(records)

    print("\n--- Sanity check ---")
    print(f"Shape: {df.shape}")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Currencies: {sorted(df['target_currency'].unique())}")
    print(f"Any nulls? \n{df.isnull().sum()[df.isnull().sum() > 0]}")
    print("\nHead:")
    print(df.head())
    print("\nTail:")
    print(df.tail())

    save_processed(df)
    print("\nDone. Next step: clean_transform.py")


if __name__ == "__main__":
    main()