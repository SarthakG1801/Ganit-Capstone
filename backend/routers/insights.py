from fastapi import APIRouter, HTTPException, Query, Response

from ..database import engine
from ..services import insight_engine, chart_engine
from ..schemas import SummaryOut, VolatilitySummary, VolatilityEntry, CorrelationMatrix, TrendOut

router = APIRouter(prefix="/insights", tags=["insights"])


@router.get("/summary", response_model=SummaryOut)
def summary(base: str = Query("USD")):
    try:
        return insight_engine.get_summary(engine, base_currency=base)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/volatility", response_model=VolatilitySummary)
def volatility(base: str = Query("USD")):
    df = insight_engine.get_volatility_ranking(engine, base_currency=base)
    if df.empty:
        raise HTTPException(status_code=404, detail="No volatility data available")
    entries = [VolatilityEntry(**row) for row in df.to_dict(orient="records")]
    return VolatilitySummary(as_of=df.attrs["as_of"], rankings=entries)


@router.get("/correlation", response_model=CorrelationMatrix)
def correlation(base: str = Query("USD"), major_only: bool = Query(True)):
    currencies = insight_engine.MAJOR_CURRENCIES if major_only else None
    corr = insight_engine.get_correlation_matrix(engine, base_currency=base, currencies=currencies)
    matrix = corr.round(4).where(corr.notnull(), None).values.tolist()
    return CorrelationMatrix(currencies=list(corr.columns), matrix=matrix)


@router.get("/trend/{currency}", response_model=TrendOut)
def trend(currency: str, base: str = Query("USD")):
    try:
        return insight_engine.get_trend(engine, target_currency=currency, base_currency=base)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/charts/{chart_name}")
def chart(chart_name: str, currency: str = Query("EUR"), base: str = Query("USD")):
    fn = chart_engine.CHART_FUNCTIONS.get(chart_name)
    if fn is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown chart '{chart_name}'. Valid options: {list(chart_engine.CHART_FUNCTIONS)}",
        )
    try:
        if chart_name == "trend":
            png_bytes = fn(engine, currency=currency, base_currency=base)
        else:
            png_bytes = fn(engine, base_currency=base)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return Response(content=png_bytes, media_type="image/png")
