"""Step 4, report: reconcile row counts end to end and export the daily revenue."""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from matplotlib.figure import Figure
from sqlalchemy import Engine, text

from .config import (
    DAILY_REVENUE_TABLE,
    LARGE_TRIP_AMOUNT,
    PROCESSED_DIR,
    RAW_SCHEMA,
    RAW_TABLE,
    STAGING_TABLE,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReportOutputs:
    """Files written by one run, plus the numbers behind them."""

    daily_revenue_csv: Path
    daily_revenue_parquet: Path
    quality_report_json: Path
    chart_png: Path
    daily_revenue: pd.DataFrame
    quality_report: dict


def read_daily_revenue(engine: Engine) -> pd.DataFrame:
    """Return the dbt mart as a DataFrame, one row per day."""
    return pd.read_sql(
        f"SELECT * FROM {DAILY_REVENUE_TABLE} ORDER BY service_date",
        engine,
        parse_dates=["service_date"],
    )


def build_quality_report(engine: Engine, daily_revenue: pd.DataFrame) -> dict:
    """Count rows at every stage so nothing can disappear unnoticed."""
    with engine.connect() as connection:
        rows_per_file = dict(
            connection.execute(
                text(
                    f"SELECT source_file, count(*) FROM {RAW_SCHEMA}.{RAW_TABLE} "
                    "GROUP BY source_file ORDER BY source_file"
                )
            ).all()
        )
        staged_rows = connection.execute(
            text(f"SELECT count(*) FROM {STAGING_TABLE}")
        ).scalar_one()
        large_trips = connection.execute(
            text(
                f"SELECT pickup_at, total_amount FROM {STAGING_TABLE} "
                "WHERE total_amount > :limit ORDER BY total_amount DESC"
            ),
            {"limit": LARGE_TRIP_AMOUNT},
        ).all()

    raw_rows = sum(rows_per_file.values())
    return {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rows_per_file": rows_per_file,
        "raw_rows": raw_rows,
        "staged_rows": staged_rows,
        "dropped_outside_period": raw_rows - staged_rows,
        "days": len(daily_revenue),
        "trips": int(daily_revenue["trip_count"].sum()),
        "refund_rows": int(daily_revenue["refund_count"].sum()),
        "gross_revenue": round(float(daily_revenue["gross_revenue"].sum()), 2),
        "refunds": round(float(daily_revenue["refunds"].sum()), 2),
        "net_revenue": round(float(daily_revenue["net_revenue"].sum()), 2),
        f"trips_over_{LARGE_TRIP_AMOUNT}_usd": [
            {"pickup_at": pickup_at.isoformat(), "total_amount": float(amount)}
            for pickup_at, amount in large_trips
        ],
    }


def save_chart(daily_revenue: pd.DataFrame, path: Path) -> Path:
    """Plot net revenue per day. Uses Figure directly, so no GUI backend is needed."""
    figure = Figure(figsize=(10, 4), layout="constrained")
    axes = figure.subplots()
    axes.plot(
        daily_revenue["service_date"], daily_revenue["net_revenue"], linewidth=1.5
    )
    axes.set_title("NYC Green Taxi: net revenue per day, Q1 2025")
    axes.set_ylabel("USD")
    axes.yaxis.set_major_formatter("${x:,.0f}")
    axes.grid(alpha=0.3)
    figure.savefig(path, dpi=150)
    return path


def export_outputs(engine: Engine, output_dir: Path = PROCESSED_DIR) -> ReportOutputs:
    """Write the daily revenue (CSV, Parquet), a chart and the quality report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    daily_revenue = read_daily_revenue(engine)
    quality_report = build_quality_report(engine, daily_revenue)

    csv_path = output_dir / "daily_revenue.csv"
    parquet_path = output_dir / "daily_revenue.parquet"
    report_path = output_dir / "quality_report.json"
    daily_revenue.to_csv(csv_path, index=False, date_format="%Y-%m-%d")
    daily_revenue.to_parquet(parquet_path, index=False)
    report_path.write_text(
        json.dumps(quality_report, indent=2) + "\n", encoding="utf-8"
    )
    chart_path = save_chart(daily_revenue, output_dir / "daily_revenue.png")

    logger.info(
        "rows: %s raw -> %s in period -> %s days; net revenue $%s",
        f"{quality_report['raw_rows']:,}",
        f"{quality_report['staged_rows']:,}",
        quality_report["days"],
        f"{quality_report['net_revenue']:,.2f}",
    )
    return ReportOutputs(
        csv_path, parquet_path, report_path, chart_path, daily_revenue, quality_report
    )
