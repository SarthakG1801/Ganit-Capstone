
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import rates, insights, downloads, admin

app = FastAPI(
    title="Currency Exchange Insights API",
    description="Serves cleaned Frankfurter exchange-rate data, derived insights, "
    "chart PNGs, and downloadable exports for the Streamlit frontend / Tableau.",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(rates.router)
app.include_router(insights.router)
app.include_router(downloads.router)
app.include_router(admin.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}
