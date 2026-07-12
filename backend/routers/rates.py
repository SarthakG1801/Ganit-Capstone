from datetime import date

from fastapi import APIRouter, HTTPException, Query

from ..database import engine
from ..services import insight_engine
from ..schemas import RateOut, CurrencyOut

router = APIRouter(tags=["rates"])


@router.get("/currencies", response_model=list[CurrencyOut])
def list_currencies():
    df = insight_engine.get_currencies(engine)
    return df.to_dict(orient="records")


@router.get("/currencies/available", response_model=list[CurrencyOut])
def list_available_currencies(base: str = Query("USD")):
    df = insight_engine.get_available_currencies(engine, base_currency=base)
    return df.to_dict(orient="records")


@router.get("/rates", response_model=list[RateOut])
def get_rates(
    base: str = Query("USD"),
    target: str | None = Query(None),
    start: date | None = Query(None),
    end: date | None = Query(None),
):
    df = insight_engine.get_rates(
        engine,
        base_currency=base,
        target_currency=target,
        start=str(start) if start else None,
        end=str(end) if end else None,
    )
    if df.empty:
        raise HTTPException(status_code=404, detail="No rates found for the given filters")
    return df.to_dict(orient="records")


@router.get("/rates/latest", response_model=list[RateOut])
def get_latest_rates(base: str = Query("USD")):
    df = insight_engine.get_latest_rates(engine, base_currency=base)
    if df.empty:
        raise HTTPException(status_code=404, detail="No rates available")
    return df.to_dict(orient="records")