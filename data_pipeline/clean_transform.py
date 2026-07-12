"""
Cleans the raw long-format exchange rate data and engineers the derived
columns used throughout the EDA / API / dashboard (moving averages,
volatility, daily % change, calendar features).

Input:  data/processed/exchange_rates_raw_long.csv   (from fetch_data.py)
Output: data/processed/exchange_rates_clean.csv       (Tableau-ready)

Run:
    python data_pipeline/clean_transform.py
"""

import os

import pandas as pd

INPUT_PATH = "data/processed/exchange_rates_raw_long.csv"
OUTPUT_PATH = "data/processed/exchange_rates_clean.csv"

# Frankfurter (ECB-sourced) doesn't publish on weekends/holidays.
# Choose how to handle those gaps:
#   "flag"     -> reindex to every calendar day, keep gaps as NaN rate,
#                 add is_trading_day so downstream tools can filter/ffill themselves
#   "ffill"    -> reindex to every calendar day, forward-fill the rate itself
#   "none"     -> leave the data exactly as returned (business days only, no reindex)
MISSING_DATE_STRATEGY = "flag"


def load_raw(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    print(f"Loaded {len(df)} raw rows from {path}")
    return df


def cast_types(df: pd.DataFrame) -> pd.DataFrame:
    df["date"] = pd.to_datetime(df["date"])
    df["base_currency"] = df["base_currency"].astype(str)
    df["target_currency"] = df["target_currency"].astype(str)
    df["rate"] = df["rate"].astype(float)
    return df


def drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    before = len(df)
    df = df.drop_duplicates(subset=["date", "base_currency", "target_currency"])
    dropped = before - len(df)
    if dropped:
        print(f"Dropped {dropped} duplicate (date, base, target) rows")
    return df


def handle_missing_dates(df: pd.DataFrame, strategy: str) -> pd.DataFrame:
    """
    Reindexes each currency's series onto a full calendar-day range so that
    weekends/holidays are explicit rather than silently absent, then applies
    the chosen strategy for the resulting gaps.
    """
    if strategy == "none":
        return df

    full_range = pd.date_range(df["date"].min(), df["date"].max(), freq="D")

    reindexed = []
    for (base, target), group in df.groupby(["base_currency", "target_currency"]):
        group = group.set_index("date").reindex(full_range)
        group["base_currency"] = base
        group["target_currency"] = target
        group = group.rename_axis("date").reset_index()
        reindexed.append(group)
    out = pd.concat(reindexed, ignore_index=True)

    out["is_trading_day"] = out["rate"].notna()

    if strategy == "ffill":
        out = out.sort_values(["target_currency", "date"])
        out["rate"] = out.groupby("target_currency")["rate"].ffill()
    elif strategy == "flag":
        pass  # rate stays NaN on non-trading days; is_trading_day marks it
    else:
        raise ValueError(f"Unknown MISSING_DATE_STRATEGY: {strategy!r}")

    n_gaps = (~out["is_trading_day"]).sum()
    print(f"Reindexed to {len(full_range)} calendar days per currency "
          f"({n_gaps} non-trading rows handled via strategy='{strategy}')")
    return out


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes daily_pct_change, moving averages, and volatility.

    Important: daily_pct_change must be computed against the previous
    TRADING day, not the previous CALENDAR day. If the frame has been
    reindexed to include weekend/holiday gap rows (rate = NaN), a naive
    groupby().pct_change() on the full calendar-day series compares Monday
    against Sunday's NaN and silently returns NaN for every single Monday
    — a systematic gap, not random missingness, which would quietly bias
    every volatility/seasonality calculation downstream.

    To avoid that, derived columns are computed on the trading-days-only
    subset (so each row is compared against the actual previous trading
    day), then merged back onto the full frame — non-trading rows keep
    NaN for all derived columns, same as before.
    """
    df = df.sort_values(["target_currency", "date"]).reset_index(drop=True)

    if "is_trading_day" in df.columns:
        trading = df[df["is_trading_day"] == True].copy()  # noqa: E712
    else:
        trading = df.copy()

    trading = trading.sort_values(["target_currency", "date"])
    g = trading.groupby("target_currency")["rate"]
    trading["daily_pct_change"] = g.pct_change()
    trading["ma_7"] = g.transform(lambda s: s.rolling(7, min_periods=1).mean())
    trading["ma_30"] = g.transform(lambda s: s.rolling(30, min_periods=1).mean())
    trading["volatility_30d"] = trading.groupby("target_currency")["daily_pct_change"] \
        .transform(lambda s: s.rolling(30, min_periods=2).std())

    derived_cols = ["daily_pct_change", "ma_7", "ma_30", "volatility_30d"]
    df = df.merge(
        trading[["date", "target_currency"] + derived_cols],
        on=["date", "target_currency"], how="left",
    )

    df["day_of_week"] = df["date"].dt.day_name()
    df["month"] = df["date"].dt.month
    df["is_month_end"] = df["date"].dt.is_month_end

    return df


def save_clean(df: pd.DataFrame, path: str) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False)
    print(f"Clean long-format CSV saved to {path}")
    return path


def main():
    df = load_raw(INPUT_PATH)
    df = cast_types(df)
    df = drop_duplicates(df)
    df = handle_missing_dates(df, MISSING_DATE_STRATEGY)
    df = add_derived_columns(df)

    print("\n--- Sanity check ---")
    print(f"Shape: {df.shape}")
    print(f"Columns: {list(df.columns)}")
    print(f"Date range: {df['date'].min().date()} to {df['date'].max().date()}")
    if "is_trading_day" in df.columns:
        print(f"Trading days: {df['is_trading_day'].sum()} / {len(df)} rows")
    print(f"Null rates: {df['rate'].isnull().sum()}")
    print("\nHead:")
    print(df.head())
    print("\nTail:")
    print(df.tail())

    save_clean(df, OUTPUT_PATH)
    print("\nDone. Next step: load_to_db.py")


if __name__ == "__main__":
    main()