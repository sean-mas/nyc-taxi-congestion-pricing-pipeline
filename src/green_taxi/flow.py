"""Step 5, orchestrate: the same pipeline as a Prefect flow, with retries, logs and reports.

Run once:            uv run python -m green_taxi.flow
Serve on a schedule: uv run python -m green_taxi.flow --serve
Both need the local Prefect server: uv run prefect server start
"""

import logging
from pathlib import Path

import click
import pandas as pd
from prefect import flow, task, unmapped
from prefect.artifacts import create_markdown_artifact, create_table_artifact
from prefect.cache_policies import NO_CACHE
from prefect_dbt import PrefectDbtRunner, PrefectDbtSettings

from .config import DBT_DIR, DEFAULT_MONTHS
from .extract import DownloadResult, download_month
from .load import LoadResult, create_db_engine, load_raw_file
from .months import ReportingPeriod, parse_months, reporting_period
from .report import ReportOutputs, export_outputs
from .transform import dbt_build_args

# Prefect sends the green_taxi log lines to the UI (PREFECT_LOGGING_EXTRA_LOGGERS in
# .env) but doesn't set their level, so INFO lines would be dropped without this.
logging.getLogger("green_taxi").setLevel(logging.INFO)

# Downloads talk to the internet, so they're the step most likely to fail for a
# moment and succeed when tried again.
download_task = task(
    download_month,
    name="download-month",
    task_run_name="download {month}",
    retries=3,
    retry_delay_seconds=10,
)


@task(name="load-raw-file", task_run_name="load {path.name}", cache_policy=NO_CACHE)
def load_task(path: Path) -> LoadResult:
    """Copy one staged file into raw.green_trips."""
    return load_raw_file(path, create_db_engine())


@task(name="export-outputs", cache_policy=NO_CACHE)
def report_task(period: ReportingPeriod) -> ReportOutputs:
    """Reconcile row counts and write CSV, Parquet, charts and quality report."""
    return export_outputs(create_db_engine(), period)


def usd(amount: float) -> str:
    """Format money with the sign in front: -$6,462.61."""
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


def format_measure(measure: str, value: float) -> str:
    """Show a comparison value in its unit: trips, USD or a share of trips."""
    if pd.isna(value):
        return ""
    if measure.endswith("_share"):
        return f"{value:.1%}"
    if "revenue" in measure:
        return usd(value)
    return f"{value:,.1f}"


@task(name="publish-artifacts")
def publish_artifacts(outputs: ReportOutputs) -> None:
    """Show the result and the row counts in the Prefect UI (Artifacts tab)."""
    report = outputs.quality_report
    period = f"{report['first_day']} to {report['last_day']}"
    daily = outputs.daily_revenue.assign(
        service_date=outputs.daily_revenue["service_date"].dt.strftime("%Y-%m-%d")
    )
    create_table_artifact(
        key="green-taxi-daily-revenue",
        table=daily.to_dict(orient="records"),
        description=f"Revenue per pickup day, NYC Green Taxi, {period} (USD)",
    )

    comparison = outputs.congestion_comparison
    create_table_artifact(
        key="green-taxi-congestion-pricing",
        table=[
            {
                "winter": row.winter,
                "day_type": row.day_type,
                "measure": row.measure,
                "before_5_jan": format_measure(row.measure, row.before),
                "after_5_jan": format_measure(row.measure, row.after),
                "change": "" if pd.isna(row.change_pct) else f"{row.change_pct:+.1f}%",
            }
            for row in comparison.itertuples()
        ],
        description=(
            "Congestion pricing (from 5 January 2025): each winter before and after "
            "5 January. Compare the winters' changes to separate the fee from the season."
        ),
    )

    file_rows = "\n".join(
        f"| `{name}` | {rows:,} |" for name, rows in report["rows_per_file"].items()
    )
    create_markdown_artifact(
        key="green-taxi-quality-report",
        description="Row counts at every stage of the pipeline",
        markdown=f"""# Green Taxi pipeline: quality report

| Source file | Rows |
|---|---:|
{file_rows}

| Stage | Rows |
|---|---:|
| Raw table (`raw.green_trips`) | {report["raw_rows"]:,} |
| In period (`staging.stg_green_trips`) | {report["staged_rows"]:,} |
| Dropped: pickup outside the period | {report["dropped_outside_period"]:,} |
| Trips in the daily table | {report["trips"]:,} |
| Refund rows in the daily table | {report["refund_rows"]:,} |

| Result | Value |
|---|---:|
| Period | {period} |
| Days | {report["days"]} |
| Gross revenue | {usd(report["gross_revenue"])} |
| Refunds | {usd(report["refunds"])} |
| **Net revenue** | **{usd(report["net_revenue"])}** |
| Fare revenue (fare + extras + tips) | {usd(report["fare_revenue"])} |
""",
    )


@flow(name="green-taxi-elt", log_prints=True)
def green_taxi_elt(
    months: list[str] | None = None, force_download: bool = False
) -> dict:
    """Download, load, transform with dbt, and report daily Green Taxi revenue."""
    selected_months = months or list(DEFAULT_MONTHS)
    # Fails on gaps between months before anything is downloaded.
    period = reporting_period(selected_months)

    # Extract: the months download in parallel.
    downloads: list[DownloadResult] = download_task.map(
        selected_months, force=unmapped(force_download)
    ).result()

    # Load: one file after another, each in its own transaction.
    for download in downloads:
        load_task(download.path)

    # Transform: run inside the flow, so each dbt model and test is its own task.
    PrefectDbtRunner(
        settings=PrefectDbtSettings(project_dir=DBT_DIR, profiles_dir=DBT_DIR)
    ).invoke(dbt_build_args(period))

    outputs = report_task(period)
    publish_artifacts(outputs)
    return outputs.quality_report


@click.command()
@click.option(
    "--months",
    default=f"{DEFAULT_MONTHS[0]}..{DEFAULT_MONTHS[-1]}",
    show_default=True,
    help="YYYY-MM months: a list (2025-01,2025-02) or a range (2024-10..2025-03).",
)
@click.option(
    "--serve",
    is_flag=True,
    help="Register a monthly schedule and wait for runs instead of running once.",
)
def main(months: str, serve: bool) -> None:
    """Run the Prefect flow once, or serve it as a scheduled deployment."""
    selected_months = parse_months(months)
    if serve:
        # TLC publishes each month's files with a delay; check early each month.
        green_taxi_elt.serve(
            name="monthly",
            cron="0 7 2 * *",
            tags=["green-taxi", "elt"],
            description="Refresh daily revenue and the congestion pricing comparison.",
            parameters={"months": selected_months},
        )
    else:
        green_taxi_elt(months=selected_months)


if __name__ == "__main__":
    main()
