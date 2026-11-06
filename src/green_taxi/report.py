"""Step 4, report: reconcile row counts end to end and export the daily revenue."""

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
from matplotlib.dates import DateFormatter
from matplotlib.figure import Figure
from sqlalchemy import Engine, bindparam, text

from .config import (
    CONGESTION_IMPACT_TABLE,
    DAILY_REVENUE_TABLE,
    LARGE_TRIP_AMOUNT,
    PROCESSED_DIR,
    RAW_SCHEMA,
    RAW_TABLE,
    STAGING_TABLE,
    source_filename,
)
from .months import ReportingPeriod

logger = logging.getLogger(__name__)

# Measures of fct_congestion_pricing_impact, in the order the comparison lists them.
IMPACT_MEASURES = (
    "trips_per_day",
    "net_revenue_per_day",
    "fare_revenue_per_day",
    "net_revenue_per_trip",
    "fare_revenue_per_trip",
    "cbd_fee_trip_share",
)

# Chart colors: the first two slots of a colorblind-checked palette, plus text inks.
CURRENT_WINTER_COLOR = "#2a78d6"  # blue: the winter with congestion pricing
EARLIER_WINTER_COLOR = "#eb6834"  # orange: the winter before, for comparison
TEXT_COLOR = "#0b0b0b"
MUTED_TEXT_COLOR = "#52514e"
GRID_COLOR = "#e4e3df"


@dataclass(frozen=True)
class ReportOutputs:
    """Files written by one run, plus the numbers behind them."""

    daily_revenue_csv: Path
    daily_revenue_parquet: Path
    quality_report_json: Path
    chart_png: Path
    congestion_comparison_csv: Path
    congestion_chart_png: Path
    daily_revenue: pd.DataFrame
    congestion_comparison: pd.DataFrame
    quality_report: dict


def read_daily_revenue(engine: Engine) -> pd.DataFrame:
    """Return the dbt mart as a DataFrame, one row per day."""
    return pd.read_sql(
        f"SELECT * FROM {DAILY_REVENUE_TABLE} ORDER BY service_date",
        engine,
        parse_dates=["service_date"],
    )


def read_congestion_impact(engine: Engine) -> pd.DataFrame:
    """Return the congestion pricing mart: one row per winter, day type and period."""
    return pd.read_sql(
        f"SELECT * FROM {CONGESTION_IMPACT_TABLE} ORDER BY winter, day_type, period DESC",
        engine,
        parse_dates=["splits_on", "first_day", "last_day"],
    )


def compare_periods(impact: pd.DataFrame) -> pd.DataFrame:
    """One row per winter, day type and measure: before, after and the change in %.

    The change is left empty where the before value is zero (the fee's share of
    trips before the fee existed).
    """
    long = impact.melt(
        id_vars=["winter", "day_type", "period"],
        value_vars=list(IMPACT_MEASURES),
        var_name="measure",
    )
    wide = (
        long.pivot(
            index=["winter", "day_type", "measure"], columns="period", values="value"
        )
        .reindex(columns=["before", "after"])
        .reset_index()
    )
    wide.columns.name = None
    wide["change_pct"] = (
        (100 * (wide["after"] / wide["before"] - 1)).where(wide["before"] != 0).round(1)
    )
    order = {measure: position for position, measure in enumerate(IMPACT_MEASURES)}
    return wide.sort_values(
        ["winter", "day_type", "measure"],
        key=lambda column: column.map(order) if column.name == "measure" else column,
        ignore_index=True,
    )


def build_quality_report(
    engine: Engine, period: ReportingPeriod, daily_revenue: pd.DataFrame
) -> dict:
    """Count rows at every stage so nothing can disappear unnoticed.

    Only the chosen months' files count, like in the staging view, so files that
    earlier runs left in the raw table don't show up as dropped rows.
    """
    files = [source_filename(month) for month in period.months]
    with engine.connect() as connection:
        rows_per_file = dict(
            connection.execute(
                text(
                    f"SELECT source_file, count(*) FROM {RAW_SCHEMA}.{RAW_TABLE} "
                    "WHERE source_file IN :files "
                    "GROUP BY source_file ORDER BY source_file"
                ).bindparams(bindparam("files", expanding=True)),
                {"files": files},
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
        "first_day": daily_revenue["service_date"].min().date().isoformat(),
        "last_day": daily_revenue["service_date"].max().date().isoformat(),
        "days": len(daily_revenue),
        "trips": int(daily_revenue["trip_count"].sum()),
        "refund_rows": int(daily_revenue["refund_count"].sum()),
        "gross_revenue": round(float(daily_revenue["gross_revenue"].sum()), 2),
        "refunds": round(float(daily_revenue["refunds"].sum()), 2),
        "net_revenue": round(float(daily_revenue["net_revenue"].sum()), 2),
        "fare_revenue": round(float(daily_revenue["fare_revenue"].sum()), 2),
        f"trips_over_{LARGE_TRIP_AMOUNT}_usd": [
            {"pickup_at": pickup_at.isoformat(), "total_amount": float(amount)}
            for pickup_at, amount in large_trips
        ],
    }


def save_chart(daily_revenue: pd.DataFrame, path: Path) -> Path:
    """Plot net revenue per day. Uses Figure directly, so no GUI backend is needed."""
    dates = daily_revenue["service_date"]
    figure = Figure(figsize=(10, 4), layout="constrained")
    axes = figure.subplots()
    axes.plot(dates, daily_revenue["net_revenue"], linewidth=1.5)
    axes.set_title(
        f"NYC Green Taxi: net revenue per day, {dates.min():%b %Y} to {dates.max():%b %Y}"
    )
    axes.set_ylabel("USD")
    axes.yaxis.set_major_formatter("${x:,.0f}")
    axes.grid(alpha=0.3)
    figure.savefig(path, dpi=150)
    return path


def weekly_weekday_means(
    daily_revenue: pd.DataFrame, first_day: pd.Timestamp, last_day: pd.Timestamp
) -> pd.DataFrame:
    """Average trips and fare revenue per weekday, week by week, between two days."""
    dates = daily_revenue["service_date"]
    weekdays = daily_revenue[
        dates.between(first_day, last_day) & (dates.dt.day_of_week < 5)
    ]
    return (
        weekdays.set_index("service_date")[["trip_count", "fare_revenue"]]
        .astype(float)
        .resample("W")  # weeks ending on Sunday
        .mean()
        .dropna()
    )


def save_congestion_chart(
    daily_revenue: pd.DataFrame, impact: pd.DataFrame, path: Path
) -> Path:
    """Weekday trips and fare revenue per day for each winter, lined up on 5 January.

    Earlier winters are shifted onto the latest winter's dates, so a seasonal dip
    shows up in both lines and a change caused by the fee shows up in only one.
    """
    figure = Figure(figsize=(10, 6.5), layout="constrained")
    trips_axes, revenue_axes = figure.subplots(2, 1, sharex=True)
    winters = (
        impact.groupby(["winter", "splits_on", "has_congestion_pricing"])
        .agg(first_day=("first_day", "min"), last_day=("last_day", "max"))
        .reset_index()
        .sort_values("splits_on")
    )
    if winters.empty:
        figure.suptitle("No winter (October to March) in the selected months")
        figure.savefig(path, dpi=150)
        return path

    priced = winters[winters["has_congestion_pricing"]]
    reference_split = (priced if not priced.empty else winters)["splits_on"].max()

    for winter in winters.itertuples():
        weekly = weekly_weekday_means(daily_revenue, winter.first_day, winter.last_day)
        # Plot each week at its middle (Thursday), shifted onto the reference winter.
        x = weekly.index - pd.Timedelta(days=3) + (reference_split - winter.splits_on)
        if winter.has_congestion_pricing:
            color, label = (
                CURRENT_WINTER_COLOR,
                f"{winter.winter}, with congestion pricing",
            )
        else:
            color, label = (
                EARLIER_WINTER_COLOR,
                f"{winter.winter}, no congestion pricing",
            )
        for axes, column in (
            (trips_axes, "trip_count"),
            (revenue_axes, "fare_revenue"),
        ):
            axes.plot(
                x,
                weekly[column],
                color=color,
                linewidth=2,
                label=label,
                solid_joinstyle="round",
                solid_capstyle="round",
            )
            # Direct label at the line's end, in text ink next to the colored line.
            axes.annotate(
                winter.winter,
                (x[-1], weekly[column].iloc[-1]),
                xytext=(6, 0),
                textcoords="offset points",
                va="center",
                color=TEXT_COLOR,
                fontsize=9,
            )

    for axes, title in (
        (trips_axes, "Trips per weekday"),
        (revenue_axes, "Fare revenue per weekday (fare + extras + tips)"),
    ):
        axes.axvline(reference_split, color=MUTED_TEXT_COLOR, linewidth=1)
        axes.set_title(title, loc="left", color=TEXT_COLOR, fontsize=11)
        axes.grid(axis="y", color=GRID_COLOR, linewidth=1)
        axes.set_axisbelow(True)
        axes.spines[["top", "right"]].set_visible(False)
        axes.spines[["left", "bottom"]].set_color(GRID_COLOR)
        axes.tick_params(colors=MUTED_TEXT_COLOR, labelsize=9)
    trips_axes.yaxis.set_major_formatter("{x:,.0f}")
    revenue_axes.yaxis.set_major_formatter("${x:,.0f}")
    revenue_axes.xaxis.set_major_formatter(DateFormatter("%b"))
    trips_axes.annotate(
        f" Congestion pricing starts, {reference_split.day} {reference_split:%b}",
        (reference_split, 1),
        xycoords=("data", "axes fraction"),
        va="top",
        color=MUTED_TEXT_COLOR,
        fontsize=9,
    )
    trips_axes.legend(loc="lower left", frameon=False, fontsize=9)
    figure.suptitle(
        "NYC Green Taxi: did congestion pricing change weekday trips and revenue?",
        x=0.01,
        ha="left",
        color=TEXT_COLOR,
        fontsize=13,
    )
    figure.text(
        0.01,
        -0.02,
        "Weekly average of Monday to Friday. The earlier winter is moved forward a "
        "year so both line up on 5 January.",
        ha="left",
        va="top",
        color=MUTED_TEXT_COLOR,
        fontsize=9,
    )
    figure.savefig(path, dpi=150, bbox_inches="tight")
    return path


def export_outputs(
    engine: Engine, period: ReportingPeriod, output_dir: Path = PROCESSED_DIR
) -> ReportOutputs:
    """Write the daily revenue (CSV, Parquet), the congestion pricing comparison,
    two charts and the quality report for the period dbt built."""
    output_dir.mkdir(parents=True, exist_ok=True)
    daily_revenue = read_daily_revenue(engine)
    quality_report = build_quality_report(engine, period, daily_revenue)
    impact = read_congestion_impact(engine)
    comparison = compare_periods(impact)

    csv_path = output_dir / "daily_revenue.csv"
    parquet_path = output_dir / "daily_revenue.parquet"
    report_path = output_dir / "quality_report.json"
    daily_revenue.to_csv(csv_path, index=False, date_format="%Y-%m-%d")
    daily_revenue.to_parquet(parquet_path, index=False)
    report_path.write_text(
        json.dumps(quality_report, indent=2) + "\n", encoding="utf-8"
    )
    chart_path = save_chart(daily_revenue, output_dir / "daily_revenue.png")
    comparison_path = output_dir / "congestion_pricing_comparison.csv"
    comparison.to_csv(comparison_path, index=False)
    congestion_chart_path = save_congestion_chart(
        daily_revenue, impact, output_dir / "congestion_pricing.png"
    )

    logger.info(
        "rows: %s raw -> %s in period -> %s days; net revenue $%s",
        f"{quality_report['raw_rows']:,}",
        f"{quality_report['staged_rows']:,}",
        quality_report["days"],
        f"{quality_report['net_revenue']:,.2f}",
    )
    return ReportOutputs(
        daily_revenue_csv=csv_path,
        daily_revenue_parquet=parquet_path,
        quality_report_json=report_path,
        chart_png=chart_path,
        congestion_comparison_csv=comparison_path,
        congestion_chart_png=congestion_chart_path,
        daily_revenue=daily_revenue,
        congestion_comparison=comparison,
        quality_report=quality_report,
    )
