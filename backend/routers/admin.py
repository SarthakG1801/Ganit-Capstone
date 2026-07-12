import os

from fastapi import APIRouter, Header, HTTPException

from ..database import engine
from ..services import refresh_service
from ..schemas import RefreshResult

router = APIRouter(prefix="/admin", tags=["admin"])


ADMIN_API_KEY = os.getenv("ADMIN_API_KEY")


def _check_api_key(x_api_key: str | None) -> None:
    if ADMIN_API_KEY and x_api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key header")


@router.post("/refresh", response_model=RefreshResult)
def refresh(base: str = "USD", x_api_key: str | None = Header(default=None)):

    _check_api_key(x_api_key)
    try:
        result = refresh_service.refresh_data(engine, base_currency=base)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Refresh failed: {exc}")
    return result
