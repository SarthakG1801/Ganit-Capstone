
import tempfile
from datetime import datetime, date
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

from . import insight_engine
from .chart_engine import plot_trend, plot_volatility, plot_correlation, plot_top_movers


def _summary_text(summary: dict) -> str:
    lines = [
        f"Base currency: {summary['base_currency']}",
        f"Period covered: {summary['start_date']} to {summary['end_date']}",
        f"Currencies tracked: {summary['num_currencies']}",
        "",
        f"Best performer: {summary['best_performer']} "
        f"({summary['best_performer_pct_change']:+.2f}%)",
        f"Worst performer: {summary['worst_performer']} "
        f"({summary['worst_performer_pct_change']:+.2f}%)",
        f"Average 30-day volatility across all currencies: "
        f"{summary['avg_volatility_30d']:.4f}",
        "",
        f"Report generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
    ]
    return "\n".join(lines)


def build_report(engine, base_currency: str = "USD", out_path: str | None = None) -> str:
    if out_path is None:
        out_path = str(Path(tempfile.gettempdir()) / "insights_report.pdf")

    summary = insight_engine.get_summary(engine, base_currency=base_currency)
    rates_df = insight_engine.get_rates(engine, base_currency=base_currency)
    rates_df = rates_df[rates_df["is_trading_day"] == 1]
    volatility_df = insight_engine.get_volatility_ranking(engine, base_currency=base_currency)
    corr_df = insight_engine.get_correlation_matrix(
        engine, base_currency=base_currency, currencies=insight_engine.MAJOR_CURRENCIES
    )
    movers_df = insight_engine.get_top_movers(engine, base_currency=base_currency, n=5)

    with PdfPages(out_path) as pdf:
        # Page 1 -- text summary
        fig, ax = plt.subplots(figsize=(8.5, 11))
        ax.axis("off")
        ax.text(0, 1, "Currency Insights Report", fontsize=18, weight="bold", va="top")
        ax.text(0, 0.9, _summary_text(summary), fontsize=11, va="top", wrap=True)
        pdf.savefig(fig)
        plt.close(fig)


        top_currencies = list(
            movers_df["target_currency"].drop_duplicates().head(5)
        ) or insight_engine.MAJOR_CURRENCIES[:5]
        for currency in top_currencies:
            fig, ax = plt.subplots(figsize=(8.5, 5))
            plot_trend(ax, rates_df, currency)
            pdf.savefig(fig)
            plt.close(fig)


        fig, ax = plt.subplots(figsize=(8.5, 6))
        plot_volatility(ax, volatility_df, top_n=20)
        pdf.savefig(fig)
        plt.close(fig)


        fig, ax = plt.subplots(figsize=(8.5, 7))
        plot_correlation(ax, corr_df)
        pdf.savefig(fig)
        plt.close(fig)


        fig, ax = plt.subplots(figsize=(8.5, 6))
        plot_top_movers(ax, movers_df)
        pdf.savefig(fig)
        plt.close(fig)

    return out_path
