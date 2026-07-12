-- ============================================================================
-- Currency Exchange Insights — SQL EDA
-- Demonstrates window functions (PARTITION BY, ROWS BETWEEN, FIRST_VALUE/
-- LAST_VALUE, LAG, RANK) against data/currency.db.
--
-- All queries tested against SQLite 3.45.1. Every query filters
-- `is_trading_day = 1` to exclude the weekend/holiday placeholder rows
-- that clean_transform.py's calendar reindex adds (rate = NULL on those
-- rows) — forgetting this filter is the most common mistake querying this
-- table directly.
--
-- Run: sqlite3 data/currency.db < analysis/eda_sql_queries.sql
--   or load into any SQLite GUI / pandas (pd.read_sql) one query at a time.
-- ============================================================================


-- ----------------------------------------------------------------------------
-- 1. 30-day moving average via window function
-- (Recomputes what's already stored in ma_30, as a demonstration of the
--  ROWS BETWEEN frame — useful if you want a different window size ad hoc.)
-- ----------------------------------------------------------------------------
SELECT
    date,
    target_currency,
    rate,
    AVG(rate) OVER (
        PARTITION BY target_currency
        ORDER BY date
        ROWS BETWEEN 29 PRECEDING AND CURRENT ROW
    ) AS ma_30_recomputed
FROM exchange_rates
WHERE is_trading_day = 1
ORDER BY target_currency, date;


-- ----------------------------------------------------------------------------
-- 2. Month-over-month open/close via FIRST_VALUE / LAST_VALUE
-- Needs the full ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
-- frame — without it, LAST_VALUE would only see up to the current row and
-- just return the current row's own rate.
-- ----------------------------------------------------------------------------
SELECT DISTINCT
    target_currency,
    strftime('%Y-%m', date) AS month,
    FIRST_VALUE(rate) OVER w AS month_open,
    LAST_VALUE(rate) OVER w AS month_close,
    ROUND(
        (LAST_VALUE(rate) OVER w / FIRST_VALUE(rate) OVER w - 1) * 100, 2
    ) AS month_pct_change
FROM exchange_rates
WHERE is_trading_day = 1
WINDOW w AS (
    PARTITION BY target_currency, strftime('%Y-%m', date)
    ORDER BY date
    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
)
ORDER BY target_currency, month;


-- ----------------------------------------------------------------------------
-- 3. Most volatile currency (full-period)
-- SQLite has no built-in STDDEV, so it's computed manually via the
-- population-variance identity: Var(X) = E[X^2] - E[X]^2
-- ----------------------------------------------------------------------------
SELECT
    target_currency,
    ROUND(AVG(daily_pct_change), 5) AS avg_daily_change,
    ROUND(
        SQRT(AVG(daily_pct_change * daily_pct_change) - AVG(daily_pct_change) * AVG(daily_pct_change)),
        5
    ) AS volatility
FROM exchange_rates
WHERE is_trading_day = 1 AND daily_pct_change IS NOT NULL
GROUP BY target_currency
ORDER BY volatility DESC;


-- ----------------------------------------------------------------------------
-- 4. Biggest single-day moves via LAG
-- ----------------------------------------------------------------------------
SELECT
    target_currency,
    date,
    rate,
    LAG(rate) OVER (PARTITION BY target_currency ORDER BY date) AS prev_rate,
    ROUND(rate - LAG(rate) OVER (PARTITION BY target_currency ORDER BY date), 5) AS abs_change
FROM exchange_rates
WHERE is_trading_day = 1
ORDER BY ABS(rate - LAG(rate) OVER (PARTITION BY target_currency ORDER BY date)) DESC
LIMIT 10;


-- ----------------------------------------------------------------------------
-- 5. Monthly volatility ranking via RANK
-- Which currency was the most volatile EACH month, not just over the full
-- year — a currency can be calm most months and spike in one.
-- ----------------------------------------------------------------------------
WITH monthly_vol AS (
    SELECT
        target_currency,
        strftime('%Y-%m', date) AS month,
        SQRT(
            AVG(daily_pct_change * daily_pct_change) - AVG(daily_pct_change) * AVG(daily_pct_change)
        ) AS monthly_volatility
    FROM exchange_rates
    WHERE is_trading_day = 1 AND daily_pct_change IS NOT NULL
    GROUP BY target_currency, month
)
SELECT
    month,
    target_currency,
    ROUND(monthly_volatility, 5) AS monthly_volatility,
    RANK() OVER (PARTITION BY month ORDER BY monthly_volatility DESC) AS volatility_rank
FROM monthly_vol
ORDER BY month, volatility_rank;


-- ----------------------------------------------------------------------------
-- 6. Cumulative return since start of period
-- Running % change from day 1, per currency — good for a "growth of $1"
-- style line chart in Tableau.
-- ----------------------------------------------------------------------------
SELECT
    target_currency,
    date,
    rate,
    ROUND(
        (rate / FIRST_VALUE(rate) OVER (
            PARTITION BY target_currency ORDER BY date
        ) - 1) * 100, 3
    ) AS cumulative_pct_change
FROM exchange_rates
WHERE is_trading_day = 1
ORDER BY target_currency, date;


-- ----------------------------------------------------------------------------
-- 7. Top gainers / losers over the full period
-- Cross-check against Python's start_end table in eda_python.ipynb —
-- both should agree exactly since they're doing the same start/end math.
-- ----------------------------------------------------------------------------
WITH bounds AS (
    SELECT
        target_currency,
        FIRST_VALUE(rate) OVER (
            PARTITION BY target_currency ORDER BY date
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS start_rate,
        LAST_VALUE(rate) OVER (
            PARTITION BY target_currency ORDER BY date
            ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
        ) AS end_rate
    FROM exchange_rates
    WHERE is_trading_day = 1
)
SELECT DISTINCT
    target_currency,
    start_rate,
    end_rate,
    ROUND((end_rate / start_rate - 1) * 100, 2) AS pct_change_ytd
FROM bounds
ORDER BY pct_change_ytd DESC;


-- ----------------------------------------------------------------------------
-- 8. Seasonality check — average daily change by day of week
-- Note: on a full calendar-reindexed table, computing daily_pct_change
-- naively (current rate vs. previous CALENDAR day) makes every Monday's
-- change compare against Sunday's NULL rate and come out NULL — silently
-- dropping ~1/5 of all trading days from this exact query. clean_transform.py
-- avoids this by computing daily_pct_change against the previous TRADING
-- day before merging back onto the calendar-reindexed frame, so all five
-- weekdays are correctly represented below.
-- ----------------------------------------------------------------------------
SELECT
    day_of_week,
    ROUND(AVG(daily_pct_change), 5) AS avg_daily_change,
    COUNT(*) AS n
FROM exchange_rates
WHERE is_trading_day = 1 AND daily_pct_change IS NOT NULL
GROUP BY day_of_week
ORDER BY avg_daily_change DESC;
