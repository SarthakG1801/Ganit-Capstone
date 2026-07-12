import tempfile
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse, FileResponse
import pandas as pd
import io

from ..database import engine
from ..services import insight_engine, report_builder

router = APIRouter(prefix="/download", tags=["downloads"])


@router.get("/clean-csv")
def download_clean_csv(base: str = Query("USD")):
    df = insight_engine.get_rates(engine, base_currency=base)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=exchange_rates_clean.csv"},
    )


@router.get("/wide-csv")
def download_wide_csv(base: str = Query("USD")):
    df = insight_engine.get_rates(engine, base_currency=base)
    wide = df.pivot(index="date", columns="target_currency", values="rate").reset_index()
    buf = io.StringIO()
    wide.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=exchange_rates_wide.csv"},
    )


@router.get("/insights-report")
def download_insights_report(base: str = Query("USD")):
    out_path = str(Path(tempfile.gettempdir()) / "insights_report.pdf")
    report_builder.build_report(engine, base_currency=base, out_path=out_path)
    return FileResponse(
        out_path, media_type="application/pdf", filename="currency_insights_report.pdf"
    )
