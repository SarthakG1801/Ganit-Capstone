
from datetime import date as date_type
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CurrencyOut(BaseModel):
    code: str
    name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class RateOut(BaseModel):
    date: date_type
    base_currency: str
    target_currency: str
    rate: Optional[float] = None
    is_trading_day: Optional[int] = None
    daily_pct_change: Optional[float] = None
    ma_7: Optional[float] = None
    ma_30: Optional[float] = None
    volatility_30d: Optional[float] = None
    day_of_week: Optional[str] = None
    month: Optional[int] = None
    is_month_end: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class SummaryOut(BaseModel):
    base_currency: str
    start_date: date_type
    end_date: date_type
    num_currencies: int
    best_performer: str
    best_performer_pct_change: float
    worst_performer: str
    worst_performer_pct_change: float
    avg_volatility_30d: float


class VolatilityEntry(BaseModel):
    target_currency: str
    volatility_30d: float
    rank: int


class VolatilitySummary(BaseModel):
    as_of: date_type
    rankings: list[VolatilityEntry]


class CorrelationMatrix(BaseModel):
    currencies: list[str]
    matrix: list[list[Optional[float]]]


class TrendOut(BaseModel):
    target_currency: str
    latest_rate: Optional[float] = None
    ma_7: Optional[float] = None
    ma_30: Optional[float] = None
    trend_direction: str  # "up" | "down" | "flat"
    pct_change_30d: Optional[float] = None


class RefreshResult(BaseModel):
    started_at: str
    finished_at: str
    duration_seconds: float
    base_currency: str
    rows_fetched: int
    rows_upserted: int
    rows_purged: int
    purge_cutoff_date: date_type
    date_range_before: Optional[list[Optional[date_type]]] = None
    date_range_after: list[Optional[date_type]]
    currencies_refreshed: int
    notes: list[str] = []
