
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

import pandas as pd
import requests
from sqlalchemy import text
from sqlalchemy.engine import Engine

FRANKFURTER_RATES_URL = "https://api.frankfurter.dev/v2/rates"
FRANKFURTER_CURRENCIES_URL = "https://api.frankfurter.dev/v2/currencies"

RETENTION_DAYS = 365          # rolling window we keep in the DB
TRAILING_WINDOW_FOR_ROLLING = 40  # trading days of history pulled to seed ma_30 correctly


def _fetch_rates(base_currency: str, start: date, end: date) -> pd.DataFrame:
    resp = requests.get(
        FRANKFURTER_RATES_URL,
        params={"base": base_currency, "from": str(start), "to": str(end)},
        timeout=30,
    )
    resp.raise_for_status()
    records = resp.json()  # flat list of {date, base, quote, rate}
    if not records:
        return pd.DataFrame(columns=["date", "base_currency", "target_currency", "rate"])
    df = pd.DataFrame(records).rename(columns={"base": "base_currency", "quote": "target_currency"})
    df["date"] = pd.to_datetime(df["date"])
    df["rate"] = df["rate"].astype(float)
    return df


def _fetch_currencies() -> dict[str, str]:

    resp = requests.get(FRANKFURTER_CURRENCIES_URL, timeout=30)
    resp.raise_for_status()
    payload = resp.json()

    if isinstance(payload, dict):
        return {code: name for code, name in payload.items()}

    if isinstance(payload, list):
        out = {}
        for entry in payload:
            code = entry.get("iso_code") or entry.get("code")
            name = entry.get("name")
            if code:
                out[code] = name
        return out

    return {}


def _existing_trailing_window(engine: Engine, base_currency: str) -> pd.DataFrame:
    query = text(
        """
        SELECT date, base_currency, target_currency, rate
        FROM exchange_rates
        WHERE base_currency = :base AND is_trading_day = 1
        ORDER BY target_currency, date
        """
    )
    df = pd.read_sql(query, engine, params={"base": base_currency}, parse_dates=["date"])
    if df.empty:
        return df
    return (
        df.groupby("target_currency", group_keys=False)
        .apply(lambda g: g.tail(TRAILING_WINDOW_FOR_ROLLING))
        .reset_index(drop=True)
    )


def _max_existing_date(engine: Engine, base_currency: str) -> date | None:
    query = text("SELECT MAX(date) FROM exchange_rates WHERE base_currency = :base")
    with engine.connect() as conn:
        result = conn.execute(query, {"base": base_currency}).scalar()
    if result is None:
        return None
    if isinstance(result, str):
        return datetime.strptime(result[:10], "%Y-%m-%d").date()
    return result


def _min_max_dates(engine: Engine, base_currency: str) -> tuple[date | None, date | None]:
    query = text(
        "SELECT MIN(date), MAX(date) FROM exchange_rates WHERE base_currency = :base"
    )
    with engine.connect() as conn:
        row = conn.execute(query, {"base": base_currency}).fetchone()

    def _parse(v):
        if v is None:
            return None
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date() if isinstance(v, str) else v

    return _parse(row[0]), _parse(row[1])


def _compute_derived(trading_df: pd.DataFrame) -> pd.DataFrame:
    """Same derived-column logic as clean_transform.py, run on trading days only."""
    trading_df = trading_df.sort_values(["target_currency", "date"]).copy()
    g = trading_df.groupby("target_currency")["rate"]
    trading_df["daily_pct_change"] = g.pct_change()
    trading_df["ma_7"] = g.transform(lambda s: s.rolling(7, min_periods=1).mean())
    trading_df["ma_30"] = g.transform(lambda s: s.rolling(30, min_periods=1).mean())
    trading_df["volatility_30d"] = trading_df.groupby("target_currency")["daily_pct_change"].transform(
        lambda s: s.rolling(30, min_periods=2).std()
    )
    trading_df["day_of_week"] = trading_df["date"].dt.day_name()
    trading_df["month"] = trading_df["date"].dt.month
    trading_df["is_month_end"] = trading_df["date"].dt.is_month_end.astype(int)
    trading_df["is_trading_day"] = 1
    return trading_df


def _build_placeholder_rows(
    all_dates: pd.DatetimeIndex, trading_dates_by_currency: dict[str, set], base_currency: str
) -> pd.DataFrame:
    """Non-trading calendar-gap rows (weekends/holidays) for the new window, per currency."""
    rows = []
    for currency, trading_dates in trading_dates_by_currency.items():
        for d in all_dates:
            if d not in trading_dates:
                rows.append(
                    {
                        "date": d,
                        "base_currency": base_currency,
                        "target_currency": currency,
                        "rate": None,
                        "is_trading_day": 0,
                        "daily_pct_change": None,
                        "ma_7": None,
                        "ma_30": None,
                        "volatility_30d": None,
                        "day_of_week": d.day_name(),
                        "month": d.month,
                        "is_month_end": int(pd.Timestamp(d).is_month_end),
                    }
                )
    return pd.DataFrame(rows)


def _upsert(engine: Engine, df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    records = df.where(pd.notnull(df), None).to_dict(orient="records")
    for r in records:
        if isinstance(r.get("date"), (pd.Timestamp, datetime)):
            r["date"] = r["date"].strftime("%Y-%m-%d")
    stmt = text(
        """
        INSERT OR REPLACE INTO exchange_rates
            (date, base_currency, target_currency, rate, is_trading_day,
             daily_pct_change, ma_7, ma_30, volatility_30d,
             day_of_week, month, is_month_end)
        VALUES
            (:date, :base_currency, :target_currency, :rate, :is_trading_day,
             :daily_pct_change, :ma_7, :ma_30, :volatility_30d,
             :day_of_week, :month, :is_month_end)
        """
    )
    with engine.begin() as conn:
        conn.execute(stmt, records)
    return len(records)


def _upsert_currencies(engine: Engine, currencies: dict[str, str]) -> int:
    if not currencies:
        return 0
    records = [{"code": code, "name": name} for code, name in currencies.items()]
    stmt = text("INSERT OR REPLACE INTO currencies (code, name) VALUES (:code, :name)")
    with engine.begin() as conn:
        conn.execute(stmt, records)
    return len(records)


def _purge_old_rows(engine: Engine, cutoff: date) -> int:
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM exchange_rates WHERE date < :cutoff"),
            {"cutoff": str(cutoff)},
        )
    return result.rowcount if result.rowcount is not None else 0


def refresh_data(engine: Engine, base_currency: str = "USD") -> dict:

    started = datetime.now()
    t0 = time.monotonic()
    notes: list[str] = []

    today = date.today()
    cutoff = today - timedelta(days=RETENTION_DAYS)

    date_before = _min_max_dates(engine, base_currency)
    last_date = date_before[1]

    if last_date is None:
        # empty table: bootstrap with the full 1-year window
        fetch_start = today - timedelta(days=RETENTION_DAYS)
        notes.append("No existing data found -- performing a full 1-year bootstrap fetch.")
    else:
        fetch_start = last_date + timedelta(days=1)

    rows_fetched = 0
    rows_upserted = 0

    if fetch_start > today:
        notes.append("Database already up to date -- no new dates to fetch.")
    else:
        new_raw = _fetch_rates(base_currency, fetch_start, today)
        rows_fetched = len(new_raw)

        if new_raw.empty:
            notes.append(f"API returned no new rows for {fetch_start}..{today}.")
        else:
            trailing = _existing_trailing_window(engine, base_currency)
            combined = pd.concat([trailing, new_raw], ignore_index=True) if not trailing.empty else new_raw
            combined = combined.drop_duplicates(subset=["date", "base_currency", "target_currency"])

            derived = _compute_derived(combined)
            new_dates = set(new_raw["date"])
            new_rows = derived[derived["date"].isin(new_dates)].copy()

            all_calendar_dates = pd.date_range(fetch_start, today, freq="D")
            trading_by_currency = {
                cur: set(g["date"])
                for cur, g in new_raw.groupby("target_currency")
            }
            placeholders = _build_placeholder_rows(all_calendar_dates, trading_by_currency, base_currency)

            to_upsert = pd.concat([new_rows, placeholders], ignore_index=True)
            rows_upserted = _upsert(engine, to_upsert)

    try:
        currencies = _fetch_currencies()
        currencies_refreshed = _upsert_currencies(engine, currencies)
    except Exception as exc:  # non-fatal, mirrors load_to_db.py's try/except
        currencies_refreshed = 0
        notes.append(f"Currency lookup refresh failed (non-fatal): {exc}")

    rows_purged = _purge_old_rows(engine, cutoff)
    date_after = _min_max_dates(engine, base_currency)

    finished = datetime.now()
    return {
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": finished.isoformat(timespec="seconds"),
        "duration_seconds": round(time.monotonic() - t0, 2),
        "base_currency": base_currency,
        "rows_fetched": rows_fetched,
        "rows_upserted": rows_upserted,
        "rows_purged": rows_purged,
        "purge_cutoff_date": cutoff,
        "date_range_before": list(date_before),
        "date_range_after": list(date_after),
        "currencies_refreshed": currencies_refreshed,
        "notes": notes,
    }


def export_clean_csv(engine: Engine, out_path: str, base_currency: str = "USD") -> str:

    df = pd.read_sql(
        text(
            """
            SELECT date, base_currency, target_currency, rate, is_trading_day,
                   daily_pct_change, ma_7, ma_30, volatility_30d,
                   day_of_week, month, is_month_end
            FROM exchange_rates
            WHERE base_currency = :base
            ORDER BY target_currency, date
            """
        ),
        engine,
        params={"base": base_currency},
    )
    df.to_csv(out_path, index=False)
    return out_path