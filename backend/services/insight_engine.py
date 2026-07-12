
from __future__ import annotations

import pandas as pd
from sqlalchemy.engine import Engine


def _load_rates(engine: Engine, base_currency: str = "USD") -> pd.DataFrame:
    query = """
        SELECT date, base_currency, target_currency, rate, is_trading_day,
               daily_pct_change, ma_7, ma_30, volatility_30d,
               day_of_week, month, is_month_end
        FROM exchange_rates
        WHERE base_currency = :base AND is_trading_day = 1
        ORDER BY target_currency, date
    """
    df = pd.read_sql(query, engine, params={"base": base_currency}, parse_dates=["date"])
    return df


def get_currencies(engine: Engine) -> pd.DataFrame:
    return pd.read_sql(
        "SELECT code, name FROM currencies WHERE code IS NOT NULL ORDER BY code", engine
    )


def get_available_currencies(engine: Engine, base_currency: str = "USD") -> pd.DataFrame:
    query = """
        SELECT DISTINCT er.target_currency AS code, c.name AS name
        FROM exchange_rates er
        LEFT JOIN currencies c ON c.code = er.target_currency
        WHERE er.base_currency = :base
        ORDER BY er.target_currency
    """
    return pd.read_sql(query, engine, params={"base": base_currency})


def get_rates(
    engine: Engine,
    base_currency: str = "USD",
    target_currency: str | None = None,
    start: str | None = None,
    end: str | None = None,
) -> pd.DataFrame:
    clauses = ["base_currency = :base"]
    params: dict = {"base": base_currency}
    if target_currency:
        clauses.append("target_currency = :target")
        params["target"] = target_currency
    if start:
        clauses.append("date >= :start")
        params["start"] = start
    if end:
        clauses.append("date <= :end")
        params["end"] = end
    where = " AND ".join(clauses)
    query = f"""
        SELECT date, base_currency, target_currency, rate, is_trading_day,
               daily_pct_change, ma_7, ma_30, volatility_30d,
               day_of_week, month, is_month_end
        FROM exchange_rates
        WHERE {where}
        ORDER BY target_currency, date
    """
    return pd.read_sql(query, engine, params=params, parse_dates=["date"])


def get_latest_rates(engine: Engine, base_currency: str = "USD") -> pd.DataFrame:
    query = """
        SELECT er.*
        FROM exchange_rates er
        JOIN (
            SELECT target_currency, MAX(date) AS max_date
            FROM exchange_rates
            WHERE base_currency = :base AND is_trading_day = 1
            GROUP BY target_currency
        ) latest
          ON er.target_currency = latest.target_currency
         AND er.date = latest.max_date
        WHERE er.base_currency = :base
        ORDER BY er.target_currency
    """
    return pd.read_sql(query, engine, params={"base": base_currency}, parse_dates=["date"])


def get_summary(engine: Engine, base_currency: str = "USD") -> dict:
    df = _load_rates(engine, base_currency)
    if df.empty:
        raise ValueError("No data available for summary")

    start_end = (
        df.groupby("target_currency")["rate"]
        .agg(start_rate="first", end_rate="last")
        .reset_index()
    )
    start_end["pct_change"] = (
        (start_end["end_rate"] - start_end["start_rate"]) / start_end["start_rate"] * 100
    )

    best = start_end.loc[start_end["pct_change"].idxmax()]
    worst = start_end.loc[start_end["pct_change"].idxmin()]

    return {
        "base_currency": base_currency,
        "start_date": df["date"].min().date(),
        "end_date": df["date"].max().date(),
        "num_currencies": df["target_currency"].nunique(),
        "best_performer": best["target_currency"],
        "best_performer_pct_change": round(float(best["pct_change"]), 4),
        "worst_performer": worst["target_currency"],
        "worst_performer_pct_change": round(float(worst["pct_change"]), 4),
        "avg_volatility_30d": round(float(df["volatility_30d"].mean()), 6),
    }


def get_volatility_ranking(engine: Engine, base_currency: str = "USD") -> pd.DataFrame:
    df = _load_rates(engine, base_currency)
    latest_date = df["date"].max()
    latest = df[df["date"] == latest_date]
    ranking = (
        latest[["target_currency", "volatility_30d"]]
        .dropna()
        .sort_values("volatility_30d", ascending=False)
        .reset_index(drop=True)
    )
    ranking["rank"] = ranking.index + 1
    ranking.attrs["as_of"] = latest_date.date()
    return ranking


def get_correlation_matrix(
    engine: Engine, base_currency: str = "USD", currencies: list[str] | None = None
) -> pd.DataFrame:
    df = _load_rates(engine, base_currency)
    wide = df.pivot(index="date", columns="target_currency", values="daily_pct_change")
    if currencies:
        wide = wide[[c for c in currencies if c in wide.columns]]
    corr = wide.corr()
    return corr


def get_trend(engine: Engine, target_currency: str, base_currency: str = "USD") -> dict:
    df = get_rates(engine, base_currency=base_currency, target_currency=target_currency)
    df = df[df["is_trading_day"] == 1].sort_values("date")
    if df.empty:
        raise ValueError(f"No data for currency '{target_currency}'")

    latest = df.iloc[-1]
    lookback = df.tail(30)
    pct_change_30d = None
    if len(lookback) >= 2 and lookback["rate"].iloc[0]:
        pct_change_30d = round(
            float((lookback["rate"].iloc[-1] - lookback["rate"].iloc[0]) / lookback["rate"].iloc[0] * 100),
            4,
        )

    if latest["ma_7"] is not None and latest["ma_30"] is not None:
        if latest["ma_7"] > latest["ma_30"]:
            direction = "up"
        elif latest["ma_7"] < latest["ma_30"]:
            direction = "down"
        else:
            direction = "flat"
    else:
        direction = "flat"

    return {
        "target_currency": target_currency,
        "latest_rate": latest["rate"],
        "ma_7": latest["ma_7"],
        "ma_30": latest["ma_30"],
        "trend_direction": direction,
        "pct_change_30d": pct_change_30d,
    }


def get_top_movers(engine: Engine, base_currency: str = "USD", n: int = 5) -> pd.DataFrame:
    df = _load_rates(engine, base_currency)
    start_end = (
        df.groupby("target_currency")["rate"]
        .agg(start_rate="first", end_rate="last")
        .reset_index()
    )
    start_end["pct_change"] = (
        (start_end["end_rate"] - start_end["start_rate"]) / start_end["start_rate"] * 100
    )
    gainers = start_end.sort_values("pct_change", ascending=False).head(n)
    losers = start_end.sort_values("pct_change", ascending=True).head(n)
    gainers["direction"] = "gainer"
    losers["direction"] = "loser"
    return pd.concat([gainers, losers], ignore_index=True)


MAJOR_CURRENCIES = [
    "EUR", "GBP", "JPY", "CHF", "AUD", "CAD",
    "CNY", "INR", "MXN", "BRL", "ZAR", "SGD",
]