# Ganit Capstone Project — Build Plan
### Currency Exchange Insights Platform (Frankfurter API → FastAPI → Streamlit → Tableau)

---

## 1. Project recap (from the brief)

- Data source: **Frankfurter API** (ECB reference rates, refreshes ~16:00 CET on working days).
- Build a script to fetch and store **1 year of historical exchange rate data**.
- Store locally in a structured format (CSV / SQLite) as a **reusable asset**.
- Do thorough **EDA in Python, Excel, and SQL**.
- Derive **insights**.
- Load data into **Tableau** and build a dashboard.
- Deliver a **git repo** with code, screenshots of outcomes/dashboards, and documentation.

Your additions on top of the brief:
- **Streamlit** frontend to visualize insights.
- **FastAPI** backend serving the data/insights and handling DB calls.
- **Download buttons** for (a) the clean dataset and (b) the derived insights, so the clean CSV can be pulled straight into Tableau.

---

## 1a. Progress so far

| File | Status | What it does |
|---|---|---|
| `data_pipeline/fetch_data.py` | ✅ Built | Pulls 1 year of USD-base rates from the **Frankfurter v2 API** (`/v2/rates`, query-param date range). v2 already returns tidy long-format JSON (`{date, base, quote, rate}`), so no melt/reshape is needed — just a rename + type cast. Saves raw JSON to `data/raw/` and an unprocessed long CSV to `data/processed/exchange_rates_raw_long.csv`. |
| `data_pipeline/check_fetch.py` | ✅ Built | *(not in the original brief — added as a verification step.)* Standalone health-check script: confirms the v2 API is reachable and returns the expected shape, that the raw JSON and processed CSV exist, and that the CSV has the right columns, no nulls, no dupes, a ~1-year span, a recent max date, and positive rates. Exits non-zero on any failure so it doubles as a CI check. |
| `data_pipeline/clean_transform.py` | ✅ Built & tested | Reads the raw long CSV, casts types, drops duplicates, reindexes each currency onto the full calendar range (flagging non-trading days rather than silently dropping them), and adds `daily_pct_change`, `ma_7`, `ma_30`, `volatility_30d`, `day_of_week`, `month`, `is_month_end`. Outputs `data/processed/exchange_rates_clean.csv`. Verified against synthetic data with an injected duplicate and a gap. |
| `data_pipeline/load_to_db.py` | ✅ Built & tested | Loads the clean CSV into `data/currency.db` (SQLite) — the pipeline's "reusable asset." Creates `exchange_rates` and `currencies` tables if missing, upserts via `INSERT OR REPLACE` (confirmed idempotent — re-running doesn't duplicate rows), and populates `currencies` from `/v2/currencies` (non-fatal if that call fails). |
| `analysis/eda_python.ipynb`, `eda_sql_queries.sql`, `eda_excel/` | ⬜ Not started | Phase 2 — EDA in Python/SQL/Excel. |
| `backend/` (FastAPI) | ⬜ Not started | Phase 3. |
| `frontend/` (Streamlit) | ⬜ Not started | Phase 4. |
| `tableau/` | ⬜ Not started | Phase 5. |

Everything above Phase 1 is done: you have a working `fetch → clean → load` pipeline producing a queryable SQLite database. Next up per the build order (§9) is Phase 2 (EDA).

---

## 2. Architecture

```
Frankfurter API → ETL ingestion script → Storage (SQLite + CSV)
                                              ↓
                                       FastAPI backend
                                              ↓
                                     Streamlit frontend
                                              ↓
                              Downloads (CSV / insights) → Tableau
```

- **FastAPI** owns all data access — it reads from SQLite, computes/serves insights, and exposes download endpoints. It's the single source of truth.
- **Streamlit** is a pure client — it only calls FastAPI endpoints (via `requests`/`httpx`), never touches the database directly. This keeps the two services decoupled and mirrors a real production setup.
- **Tableau** connects to the *clean CSV export*, not live to the API — simplest, most portable, and satisfies "reusable asset."

---

## 3. Repository structure

```
currency-insights-capstone/
├── README.md
├── .env.example
├── .gitignore
├── requirements.txt
├── docker-compose.yml                # optional, runs api + frontend together
│
├── data/
│   ├── raw/                          # untouched daily JSON pulls (audit trail)
│   ├── processed/
│   │   ├── exchange_rates_clean.csv  # long format — ready for Tableau
│   │   ├── exchange_rates_wide.csv   # wide format — one column per currency
│   │   └── insights_summary.xlsx
│   └── currency.db                   # SQLite
│
├── data_pipeline/
│   ├── fetch_data.py                  # ✅ pulls 1 yr from Frankfurter v2 API into a DataFrame
│   ├── check_fetch.py                 # ✅ health-check for fetch_data.py output (not in original brief)
│   ├── clean_transform.py             # ✅ pandas: validation, dedupe, derived columns
│   └── load_to_db.py                  # ✅ upserts clean data into SQLite
│
├── analysis/
│   ├── eda_python.ipynb              # pandas/matplotlib/seaborn EDA
│   ├── eda_sql_queries.sql           # window functions, aggregations
│   └── eda_excel/
│       └── currency_pivot_analysis.xlsx
│
├── backend/
│   ├── main.py                       # FastAPI app entrypoint
│   ├── database.py                   # SQLAlchemy engine/session
│   ├── models.py                     # ORM models
│   ├── schemas.py                    # Pydantic request/response models
│   ├── routers/
│   │   ├── rates.py
│   │   ├── insights.py
│   │   └── downloads.py
│   └── services/
│       ├── insight_engine.py         # volatility, trend, correlation calcs
│       ├── chart_engine.py           # matplotlib figures → PNG bytes
│       └── report_builder.py         # builds downloadable PDF report (charts + insights)
│
├── frontend/
│   ├── app.py                        # Streamlit entrypoint
│   ├── pages/
│   │   ├── 1_Overview.py
│   │   ├── 2_Currency_Explorer.py
│   │   ├── 3_Insights_Dashboard.py
│   │   └── 4_Downloads.py
│   └── utils/api_client.py           # thin wrapper around FastAPI calls
│
├── tableau/
│   └── currency_dashboard.twbx
│
└── docs/
    ├── screenshots/
    └── architecture.png
```

---

## 4. Phase 1 — Data acquisition & cleaning (pandas, no orchestration layer)

No scheduler, no cron, no separate ETL framework — just three small pandas-driven scripts (or one notebook, if you prefer) that you run manually when you need to (re)build the dataset. Keeps things simple and fully reproducible with `python data_pipeline/fetch_data.py`.

**Frankfurter API basics — v2** (verify exact params when you build, since APIs evolve):
- `GET https://api.frankfurter.dev/v2/rates?base=USD&from={start_date}&to={end_date}` returns a time series of rates for a date range. Note v2 takes the date range as **query params** (`from`/`to`), not baked into the URL path like v1's `/{start}..{end}`.
- The response is a **flat JSON array** of tidy records — `[{"date": "...", "base": "USD", "quote": "EUR", "rate": 0.87}, ...]` — already long-format, so no `melt`/reshape step is needed (v1's nested `{"rates": {date: {currency: rate}}}` dict required one).
- Filter target currencies with `quotes=EUR,GBP` (this was `symbols=` in v1).
- Optionally pin a single official source with `providers=ECB` instead of the default blended-across-providers rate — worth using if reproducibility/auditability matters, since a pinned provider follows its own fixed publishing schedule.
- `GET https://api.frankfurter.dev/v2/currencies` returns the supported currency list, now with richer provider-coverage details (not just a flat `{code: name}` dict like v1).
- v2 also exposes the same data as CSV directly — `GET https://api.frankfurter.dev/v2/rates.csv?base=USD&from=...&to=...` returns `date,base,quote,rate` columns, loadable straight into pandas with `pd.read_csv(url)` if you want to skip the JSON step entirely.
- No API key required. Since this is a single 1-year pull (not a scheduled job), one `requests.get()` call per base currency is enough — no need for batching/retry infrastructure, though a basic `try/except` around the request is still good practice.

**`data_pipeline/fetch_data.py`**
```python
import requests
import pandas as pd
from datetime import date, timedelta

end = date.today()
start = end - timedelta(days=365)
base = "USD"

resp = requests.get(
    "https://api.frankfurter.dev/v2/rates",
    params={"base": base, "from": str(start), "to": str(end)},
)
resp.raise_for_status()
records = resp.json()          # already a flat list of {date, base, quote, rate} dicts

# v2 is already tidy long-format — just load it straight into a DataFrame,
# no pivot/melt needed (v1's nested {date: {currency: rate}} response required one)
df = pd.DataFrame(records).rename(columns={"base": "base_currency", "quote": "target_currency"})
df["date"] = pd.to_datetime(df["date"])

df.to_csv("data/raw/exchange_rates_raw.csv", index=False)
```
That's the entire fetch step — v2's response needs no reshaping at all, just a rename and a `to_datetime` cast.

**`data_pipeline/clean_transform.py`** ✅ *built & tested* — pandas cleaning + feature engineering
- Type casting (`pd.to_datetime`, `astype(float)`).
- Handle missing dates (ECB doesn't publish on weekends/holidays): reindexes every `(base, target)` pair onto the **full calendar-day range** via `groupby` + `reindex`, adds an `is_trading_day` flag, and defaults to leaving gaps as `NaN` (`MISSING_DATE_STRATEGY = "flag"`) rather than forward-filling — configurable to `"ffill"` or `"none"` at the top of the script.
- Drop duplicates: `df.drop_duplicates(subset=["date", "base_currency", "target_currency"])`.
- Derived columns, all via pandas `groupby("target_currency")` + `.transform()` / `.rolling()`:
  - `daily_pct_change` → `df.groupby("target_currency")["rate"].pct_change()`
  - `ma_7`, `ma_30` → `.rolling(7, min_periods=1).mean()`, `.rolling(30, min_periods=1).mean()`
  - `volatility_30d` → `.rolling(30, min_periods=2).std()` on `daily_pct_change`
  - `day_of_week`, `month`, `is_month_end` → `df["date"].dt.*` accessors
- Save the result to `data/processed/exchange_rates_clean.csv` (long format, Tableau-ready).
- Verified against a synthetic input with an injected duplicate row and a 2-day gap: the duplicate was correctly dropped, the gap was correctly reindexed and flagged, and all 8 derived columns populated as expected.

**`data_pipeline/load_to_db.py`** ✅ *built & tested*
- Creates `exchange_rates` and `currencies` tables if they don't already exist (see schema below), then loads the clean CSV into a staging table and **upserts** into `exchange_rates` via `INSERT OR REPLACE` keyed on `(date, base_currency, target_currency)` — re-running the pipeline updates rows instead of duplicating them (confirmed: running it twice back-to-back left the row count unchanged).
- Also populates the `currencies` lookup table from the `/v2/currencies` endpoint; this step is wrapped in a try/except so a network hiccup there doesn't break the core exchange-rate load.
- This becomes your "reusable asset" — a single SQLite file that the EDA notebook, FastAPI backend, and any future re-run can all point to, without needing to re-hit the API.

**SQLite schema** (as implemented in `load_to_db.py` — extended slightly from the original brief to also store the calendar/trading-day columns `clean_transform.py` produces, so nothing gets dropped on the way into the DB):
```sql
CREATE TABLE exchange_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    base_currency TEXT NOT NULL,
    target_currency TEXT NOT NULL,
    rate REAL,
    is_trading_day INTEGER,        -- 0/1, from clean_transform.py's calendar reindex
    daily_pct_change REAL,
    ma_7 REAL,
    ma_30 REAL,
    volatility_30d REAL,
    day_of_week TEXT,
    month INTEGER,
    is_month_end INTEGER,          -- 0/1
    UNIQUE(date, base_currency, target_currency)
);

CREATE TABLE currencies (
    code TEXT PRIMARY KEY,
    name TEXT
);
```
`load_to_db.py` creates these tables if they don't exist, then upserts via `INSERT OR REPLACE` keyed on `(date, base_currency, target_currency)` — so re-running the whole pipeline updates existing rows instead of piling up duplicates.

---

## 5. Phase 2 — EDA (Python, SQL, Excel)

**Python (`analysis/eda_python.ipynb`)**
- Time series line plots per currency pair.
- Distribution of daily returns (histogram + boxplot) — spot outliers/extreme moves.
- Correlation heatmap across currency pairs.
- Rolling volatility comparison — which currencies were most stable/volatile over the year.
- Seasonality check — any day-of-week or month-end patterns.
- Top gainers/losers over the year (start vs end rate, % change).

**SQL (`analysis/eda_sql_queries.sql`)** — demonstrate SQL chops with window functions:
```sql
-- 30-day moving average via window function
SELECT date, target_currency, rate,
       AVG(rate) OVER (PARTITION BY target_currency ORDER BY date
                        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS ma_30
FROM exchange_rates;

-- Month-over-month % change
SELECT target_currency, strftime('%Y-%m', date) AS month,
       FIRST_VALUE(rate) OVER w AS month_open,
       LAST_VALUE(rate) OVER w AS month_close
FROM exchange_rates
WINDOW w AS (PARTITION BY target_currency, strftime('%Y-%m', date)
             ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING);

-- Most volatile currency (highest stddev of daily returns)
SELECT target_currency, ROUND(AVG(daily_pct_change),4) AS avg_change,
       ROUND(STDDEV(daily_pct_change),4) AS volatility  -- use a SQLite stdev extension or compute in pandas if unsupported
FROM exchange_rates
GROUP BY target_currency
ORDER BY volatility DESC;
```

**Excel (`analysis/eda_excel/currency_pivot_analysis.xlsx`)**
- Pivot table: average rate by currency by month.
- Conditional formatting heatmap on daily % change.
- A couple of quick charts (line, sparkline) — this demonstrates the "Excel" leg of the brief and gives non-technical reviewers something to skim.

---

## 6. Phase 3 — FastAPI backend

**Endpoints**

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | liveness check |
| GET | `/currencies` | list available currencies |
| GET | `/rates?base=USD&target=INR&start=&end=` | raw/filtered time series |
| GET | `/rates/latest` | most recent day's rates |
| GET | `/insights/summary` | headline stats: best/worst performer, avg volatility, date range covered |
| GET | `/insights/volatility` | per-currency volatility ranking |
| GET | `/insights/correlation` | correlation matrix (JSON, ready for a heatmap) |
| GET | `/insights/trend/{currency}` | moving averages + trend direction |
| GET | `/insights/charts/{chart_name}` | matplotlib-generated chart as PNG (`trend`, `volatility`, `correlation`, `top_movers`) |
| GET | `/download/clean-csv` | streams `exchange_rates_clean.csv` (long format, Tableau-ready) |
| GET | `/download/wide-csv` | wide-format CSV (one column per currency) |
| GET | `/download/insights-report` | full PDF report — summary stats + every chart, generated on demand |
| POST | `/admin/refresh` | triggers `fetch_data.py` to pull the newest data (optional, protect with a simple API key) |

**`backend/services/chart_engine.py`** — one function per chart, each returns PNG bytes:
```python
import io
import matplotlib
matplotlib.use("Agg")          # headless backend, safe inside FastAPI
import matplotlib.pyplot as plt
import pandas as pd

def fig_to_png_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()

def trend_chart(df: pd.DataFrame, currency: str) -> bytes:
    sub = df[df["target_currency"] == currency]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(sub["date"], sub["rate"], label="rate")
    ax.plot(sub["date"], sub["ma_30"], label="30-day MA", linestyle="--")
    ax.set_title(f"{currency} exchange rate — trailing 12 months")
    ax.legend()
    return fig_to_png_bytes(fig)

def volatility_chart(summary_df: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 4))
    summary_df.sort_values("volatility_30d").plot.barh(
        x="target_currency", y="volatility_30d", ax=ax, legend=False)
    ax.set_title("30-day rolling volatility by currency")
    return fig_to_png_bytes(fig)

def correlation_heatmap(corr_df: pd.DataFrame) -> bytes:
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(corr_df.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr_df.columns))); ax.set_xticklabels(corr_df.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr_df.index))); ax.set_yticklabels(corr_df.index)
    fig.colorbar(im)
    ax.set_title("Currency correlation matrix")
    return fig_to_png_bytes(fig)
```
The `/insights/charts/{chart_name}` route calls the matching function and returns it with `media_type="image/png"` (via `StreamingResponse` or `Response(content=png_bytes, media_type="image/png")`).

**`backend/services/report_builder.py`** — reuses the exact same chart functions so the on-screen charts and the downloaded report are guaranteed to match, using matplotlib's own multi-page PDF writer (no extra PDF library needed):
```python
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt

def build_report(df, summary_df, corr_df, path="insights_report.pdf"):
    with PdfPages(path) as pdf:
        # Page 1 — text summary
        fig, ax = plt.subplots(figsize=(8.5, 11)); ax.axis("off")
        ax.text(0, 1, "Currency Insights Report", fontsize=18, weight="bold", va="top")
        ax.text(0, 0.9, summary_text(summary_df), fontsize=11, va="top", wrap=True)
        pdf.savefig(fig); plt.close(fig)

        # Page 2+ — one chart per page
        for currency in summary_df["target_currency"].head(5):
            fig, ax = plt.subplots(figsize=(8.5, 5))
            # (re-plot trend for this currency directly onto ax)
            pdf.savefig(fig); plt.close(fig)

        fig, ax = plt.subplots(figsize=(8.5, 6))
        # (re-plot volatility bar chart onto ax)
        pdf.savefig(fig); plt.close(fig)

        fig, ax = plt.subplots(figsize=(8.5, 7))
        # (re-plot correlation heatmap onto ax)
        pdf.savefig(fig); plt.close(fig)
    return path
```
`/download/insights-report` calls `build_report(...)` and streams the resulting PDF back with `FileResponse`. Since it's generated fresh from the current SQLite data each time, it's always in sync with what's shown on the Streamlit dashboard.

**Implementation notes**
- SQLAlchemy models mirror the SQLite schema above; use a `Session` dependency (`Depends(get_db)`).
- Pydantic response schemas per endpoint (e.g. `RateOut`, `VolatilitySummary`, `CorrelationMatrix`).
- `insight_engine.py` centralizes the pandas computations (reads from DB via `pd.read_sql`, computes, returns dict/DataFrame) so both the API and any notebook can reuse the same logic — avoids duplicating "insight" definitions in two places.
- `report_builder.py` uses matplotlib's `PdfPages` to assemble the full downloadable report — no separate PDF/Excel library needed, and it reuses the exact same chart functions as the live `/insights/charts/*` endpoints so nothing drifts between what's shown on screen and what's downloaded.
- Enable CORS for `http://localhost:8501` (Streamlit's default port).
- `pip install fastapi uvicorn sqlalchemy pandas matplotlib python-multipart`

---

## 7. Phase 4 — Streamlit frontend

**Pages**

1. **Overview** — headline cards (date range covered, number of currencies, best/worst performer of the year), sourced from `/insights/summary`.
2. **Currency Explorer** — dropdown to pick a base/target pair, date range picker, line chart of the rate with moving averages overlaid (Plotly), table of the raw data underneath.
3. **Insights Dashboard** — the "insights drawn from the data" the brief asks for. Pulls each matplotlib-generated PNG straight from FastAPI and displays it with `st.image`:
   - Trend chart with 30-day moving average, per currency (dropdown to switch).
   - Volatility ranking bar chart.
   - Correlation heatmap.
   - A short bullet list of auto-generated insight text underneath each chart (e.g. "INR was the most volatile currency this year, with 30-day rolling volatility peaking in March.") — built by formatting the numbers `insight_engine.py` already computed, not a separate write-up.
4. **Downloads** — buttons wired to the FastAPI download endpoints:
   - "Download clean dataset (CSV)" → `/download/clean-csv`
   - "Download wide-format dataset (CSV)" → `/download/wide-csv`
   - "Download full insights report (PDF)" → `/download/insights-report` — the same charts seen on the Insights Dashboard plus a text summary page, bundled into one PDF
   - A short note pointing users to `tableau/currency_dashboard.twbx` in the repo, and instructions to point Tableau's text-file connector at the downloaded clean CSV.

**Displaying backend-generated charts in Streamlit**
```python
import streamlit as st
import requests

resp = requests.get(f"{API_URL}/insights/charts/trend", params={"currency": selected_currency})
st.image(resp.content, caption=f"{selected_currency} trend", use_container_width=True)
```
Since the PNGs are generated server-side by `chart_engine.py`, the exact same image bytes end up both on the dashboard and inside the downloadable PDF — one chart definition, two places it shows up.

**Implementation notes**
- `frontend/utils/api_client.py` wraps every call (`requests.get(f"{API_URL}/...")`), with `API_URL` read from an env var so the same code works locally and containerized.
- Use `st.download_button` fed by the bytes returned from the FastAPI download endpoints (don't just link — Streamlit's download button gives a cleaner UX and works even if the FastAPI server isn't publicly reachable).
- Cache read-heavy calls with `st.cache_data(ttl=...)` so the dashboard doesn't re-hit the API on every widget interaction.
- `pip install streamlit plotly requests`

---

## 8. Phase 5 — Tableau dashboard

- Source: the downloaded `exchange_rates_clean.csv` (long format) — reconnect/refresh whenever a new export is pulled.
- Suggested sheets:
  1. **Trend line** — rate over time, filterable by currency (parameter or filter action).
  2. **Volatility ranking** — bar chart of 30-day rolling volatility by currency.
  3. **Correlation heatmap** — currency vs currency.
  4. **Best/worst performers** — a KPI/BAN view of % change over the year.
  5. **Calendar heatmap** — daily % change, useful for spotting big single-day moves.
- Combine into one dashboard with a currency filter that drives all sheets.
- Export a `.twbx` (packaged workbook, so the extract travels with it) into `tableau/` and take screenshots for `docs/screenshots/`.

---

## 9. Suggested build order / timeline

| Step | Task | Output | Status |
|---|---|---|---|
| 1 | Set up repo skeleton, venv, `requirements.txt` | Empty scaffolding, runs `git init` | ⬜ |
| 2 | `fetch_data.py` + `clean_transform.py` + `load_to_db.py` (all pandas) | 1-year clean dataset committed | ✅ Done |
| 3 | EDA: Python notebook + SQL queries + Excel pivot | `analysis/` folder complete, key findings noted | ⬜ |
| 4 | FastAPI: DB layer, rates + insights endpoints | Swagger UI (`/docs`) fully working | ⬜ |
| 5 | FastAPI: download endpoints + report builder | CSV/Excel downloads work via curl/Postman | ⬜ |
| 6 | Streamlit: Overview + Currency Explorer pages | Talks to FastAPI, renders charts | ⬜ |
| 7 | Streamlit: Insights Dashboard + Downloads page | Download buttons functional end-to-end | ⬜ |
| 8 | Tableau dashboard build | `.twbx` + screenshots | ⬜ |
| 9 | README, architecture diagram, screenshots, cleanup | Repo ready to share | ⬜ |
| 10 | (Optional) `docker-compose.yml` for one-command run | `docker compose up` runs both services | ⬜ |

---

## 10. README / documentation checklist (per the brief's submission requirements)

- Project overview + architecture diagram.
- Setup instructions (`pip install -r requirements.txt`, env vars, how to run ETL, FastAPI, Streamlit).
- Screenshots: FastAPI Swagger docs, Streamlit pages, Tableau dashboard.
- A short "Key Insights" section summarizing 4–5 findings from the EDA in plain language.
- Notes on design decisions (why SQLite, why long-format CSV for Tableau, how missing non-trading days were handled).

---

## 11. Stretch goals (only if time allows)

- Dockerize both services with `docker-compose.yml` (`api` + `frontend`), one command to spin up the whole stack.
- Scheduled refresh via GitHub Actions (cron) that re-runs `fetch_data.py` for the latest date range and commits the updated CSV — only worth adding once the core pandas workflow is solid.
- Add a simple caching/rate-limit layer in FastAPI if the API sees repeated identical requests.
- Currency conversion calculator page in Streamlit (amount in currency A → currency B, using historical or latest rate).
