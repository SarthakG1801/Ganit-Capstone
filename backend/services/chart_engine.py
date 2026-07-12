
import io

import matplotlib
matplotlib.use("Agg") 
import matplotlib.pyplot as plt
import pandas as pd

from . import insight_engine


def fig_to_png_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()



def plot_trend(ax, df: pd.DataFrame, currency: str) -> None:
    sub = df[df["target_currency"] == currency].sort_values("date")
    ax.plot(sub["date"], sub["rate"], label="rate", linewidth=1.2)
    ax.plot(sub["date"], sub["ma_30"], label="30-day MA", linestyle="--")
    ax.set_title(f"{currency} exchange rate — trailing 12 months")
    ax.set_xlabel("Date")
    ax.set_ylabel("Rate")
    ax.legend()
    ax.tick_params(axis="x", rotation=45)


def trend_chart(engine, currency: str, base_currency: str = "USD") -> bytes:
    df = insight_engine.get_rates(engine, base_currency=base_currency, target_currency=currency)
    df = df[df["is_trading_day"] == 1]
    fig, ax = plt.subplots(figsize=(8, 4))
    plot_trend(ax, df, currency)
    return fig_to_png_bytes(fig)



def plot_volatility(ax, ranking_df: pd.DataFrame, top_n: int = 20) -> None:
    top = ranking_df.head(top_n).sort_values("volatility_30d")
    ax.barh(top["target_currency"], top["volatility_30d"])
    ax.set_title(f"30-day rolling volatility — top {top_n} currencies")
    ax.set_xlabel("Volatility (std of daily % change)")


def volatility_chart(engine, base_currency: str = "USD", top_n: int = 20) -> bytes:
    ranking = insight_engine.get_volatility_ranking(engine, base_currency=base_currency)
    fig, ax = plt.subplots(figsize=(8, max(4, top_n * 0.3)))
    plot_volatility(ax, ranking, top_n=top_n)
    return fig_to_png_bytes(fig)



def plot_correlation(ax, corr_df: pd.DataFrame) -> None:
    im = ax.imshow(corr_df.values, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr_df.columns)))
    ax.set_xticklabels(corr_df.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr_df.index)))
    ax.set_yticklabels(corr_df.index)
    ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    ax.set_title("Currency correlation matrix (daily % change)")


def correlation_heatmap(engine, base_currency: str = "USD", currencies: list[str] | None = None) -> bytes:
    currencies = currencies or insight_engine.MAJOR_CURRENCIES
    corr = insight_engine.get_correlation_matrix(engine, base_currency=base_currency, currencies=currencies)
    fig, ax = plt.subplots(figsize=(6, 5))
    plot_correlation(ax, corr)
    return fig_to_png_bytes(fig)



def plot_top_movers(ax, movers_df: pd.DataFrame) -> None:
    movers_df = movers_df.sort_values("pct_change")
    colors = ["#d62728" if v == "loser" else "#2ca02c" for v in movers_df["direction"]]
    ax.barh(movers_df["target_currency"], movers_df["pct_change"], color=colors)
    ax.set_title("Top gainers / losers — full period % change")
    ax.set_xlabel("% change")
    ax.axvline(0, color="black", linewidth=0.8)


def top_movers_chart(engine, base_currency: str = "USD", n: int = 5) -> bytes:
    movers = insight_engine.get_top_movers(engine, base_currency=base_currency, n=n)
    fig, ax = plt.subplots(figsize=(8, 5))
    plot_top_movers(ax, movers)
    return fig_to_png_bytes(fig)


CHART_FUNCTIONS = {
    "trend": trend_chart,
    "volatility": volatility_chart,
    "correlation": correlation_heatmap,
    "top_movers": top_movers_chart,
}
