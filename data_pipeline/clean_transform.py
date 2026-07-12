
import os

import pandas as pd

INPUT_PATH = "data/processed/exchange_rates_raw_long.csv"
OUTPUT_PATH = "data/processed/exchange_rates_clean.csv"

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
        pass  
    else:
        raise ValueError(f"Unknown MISSING_DATE_STRATEGY: {strategy!r}")

    n_gaps = (~out["is_trading_day"]).sum()
    print(f"Reindexed to {len(full_range)} calendar days per currency "
          f"({n_gaps} non-trading rows handled via strategy='{strategy}')")
    return out


def add_derived_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["target_currency", "date"]).reset_index(drop=True)

    g = df.groupby("target_currency")["rate"]
    df["daily_pct_change"] = g.pct_change()
    df["ma_7"] = g.transform(lambda s: s.rolling(7, min_periods=7).mean())
    df["ma_30"] = g.transform(lambda s: s.rolling(30, min_periods=30).mean())
    df["volatility_30d"] = df.groupby("target_currency")["daily_pct_change"] \
        .transform(lambda s: s.rolling(30, min_periods=30).std())

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