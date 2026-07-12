
import os
import sqlite3

import pandas as pd
import requests

CLEAN_CSV_PATH = "data/processed/exchange_rates_clean.csv"
DB_PATH = "data/currency.db"
CURRENCIES_URL = "https://api.frankfurter.dev/v2/currencies"


CREATE_EXCHANGE_RATES_SQL = """
CREATE TABLE IF NOT EXISTS exchange_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    base_currency TEXT NOT NULL,
    target_currency TEXT NOT NULL,
    rate REAL,
    is_trading_day INTEGER,
    daily_pct_change REAL,
    ma_7 REAL,
    ma_30 REAL,
    volatility_30d REAL,
    day_of_week TEXT,
    month INTEGER,
    is_month_end INTEGER,
    UNIQUE(date, base_currency, target_currency)
);
"""

CREATE_CURRENCIES_SQL = """
CREATE TABLE IF NOT EXISTS currencies (
    code TEXT PRIMARY KEY,
    name TEXT
);
"""


def load_clean_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=["date"])
    for col in ["is_trading_day", "is_month_end"]:
        if col in df.columns:
            df[col] = df[col].astype(bool).astype(int)
    print(f"Loaded {len(df)} clean rows from {path}")
    return df


def create_tables(conn: sqlite3.Connection) -> None:
    conn.execute(CREATE_EXCHANGE_RATES_SQL)
    conn.execute(CREATE_CURRENCIES_SQL)
    conn.commit()
    print("Ensured exchange_rates and currencies tables exist")


def upsert_exchange_rates(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    df.to_sql("exchange_rates_staging", conn, if_exists="replace", index=False)

    cols = [c for c in df.columns]
    col_list = ", ".join(cols)
    conn.execute(f"""
        INSERT OR REPLACE INTO exchange_rates ({col_list})
        SELECT {col_list} FROM exchange_rates_staging
    """)
    conn.execute("DROP TABLE exchange_rates_staging")
    conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM exchange_rates").fetchone()[0]
    print(f"exchange_rates table now has {count} rows")


def load_currencies(conn: sqlite3.Connection) -> None:

    try:
        resp = requests.get(CURRENCIES_URL, timeout=15)
        resp.raise_for_status()
        payload = resp.json()


        if isinstance(payload, dict):
            rows = [(code, info.get("name", code) if isinstance(info, dict) else info)
                    for code, info in payload.items()]
        elif isinstance(payload, list):
            rows = [(item.get("code"), item.get("name", item.get("code")))
                    for item in payload]
        else:
            raise ValueError(f"Unexpected /currencies response shape: {type(payload)}")

        conn.executemany(
            "INSERT OR REPLACE INTO currencies (code, name) VALUES (?, ?)", rows
        )
        conn.commit()
        print(f"Loaded {len(rows)} currencies into currencies table")
    except (requests.exceptions.RequestException, ValueError) as e:
        print(f"WARNING: could not populate currencies table ({e}). Skipping — "
              f"exchange_rates data is unaffected.")


def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    df = load_clean_csv(CLEAN_CSV_PATH)

    conn = sqlite3.connect(DB_PATH)
    try:
        create_tables(conn)
        upsert_exchange_rates(conn, df)
        load_currencies(conn)

        print("\n--- Sanity check ---")
        sample = pd.read_sql("SELECT * FROM exchange_rates LIMIT 5", conn)
        print(sample)
        n_currencies = conn.execute(
            "SELECT COUNT(DISTINCT target_currency) FROM exchange_rates"
        ).fetchone()[0]
        date_min, date_max = conn.execute(
            "SELECT MIN(date), MAX(date) FROM exchange_rates"
        ).fetchone()
        print(f"\n{n_currencies} distinct target currencies, "
              f"date range {date_min} to {date_max}")
    finally:
        conn.close()

    print(f"\nDone. Database ready at {DB_PATH}. Next step: EDA / FastAPI backend.")


if __name__ == "__main__":
    main()