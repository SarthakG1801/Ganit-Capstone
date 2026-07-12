
from sqlalchemy import Column, Integer, String, Float, Date, UniqueConstraint

from .database import Base


class ExchangeRate(Base):
    __tablename__ = "exchange_rates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    base_currency = Column(String, nullable=False, index=True)
    target_currency = Column(String, nullable=False, index=True)
    rate = Column(Float)
    is_trading_day = Column(Integer)  # 0/1
    daily_pct_change = Column(Float)
    ma_7 = Column(Float)
    ma_30 = Column(Float)
    volatility_30d = Column(Float)
    day_of_week = Column(String)
    month = Column(Integer)
    is_month_end = Column(Integer)  # 0/1

    __table_args__ = (
        UniqueConstraint(
            "date", "base_currency", "target_currency", name="uq_rate_row"
        ),
    )


class Currency(Base):
    __tablename__ = "currencies"

    code = Column(String, primary_key=True)
    name = Column(String)
