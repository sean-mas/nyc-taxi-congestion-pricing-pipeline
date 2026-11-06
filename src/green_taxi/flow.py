"""Step 5, orchestrate: the same pipeline as a Prefect flow, with retries, logs and reports.

Run once:            uv run python -m green_taxi.flow
Serve on a schedule: uv run python -m green_taxi.flow --serve
Both need the local Prefect server: uv run prefect server start
"""

import logging
from pathlib import Path

import click
from prefect import flow, task, unmapped
from prefect.artifacts import create_markdown_artifact, create_table_artifact
from prefect.cache_policies import NO_CACHE
from prefect_dbt import PrefectDbtRunner, PrefectDbtSettings

from .config import DBT_DIR, DEFAULT_MONTHS
from .extract import DownloadResult, download_month
from .load import LoadResult, create_db_engine, load_raw_file
from .report import ReportOutputs, export_outputs

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
def report_task() -> ReportOutputs:
    """Reconcile row counts and write CSV, Parquet, chart and quality report."""
    return export_outputs(create_db_engine())


def usd(amount: float) -> str:
    """Format money with the sign in front: -$6,462.61."""
    sign = "-" if amount < 0 else ""
    return f"{sign}${abs(amount):,.2f}"


@task(name="publish-artifacts")
def publish_artifacts(outputs: ReportOutputs) -> None:
    """Show the result and the row counts in the Prefect UI (Artifacts tab)."""
    daily = outputs.daily_revenue.assign(
        service_date=outputs.daily_revenue["service_date"].dt.strftime("%Y-%m-%d")
    )
    create_table_artifact(
        key="green-taxi-daily-revenue",
        table=daily.to_dict(orient="records"),
        description="Revenue per pickup day, NYC Green Taxi, Q1 2025 (USD)",
    )

    report = outputs.quality_report
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
| Days | {report["days"]} |
| Gross revenue | {usd(report["gross_revenue"])} |
| Refunds | {usd(report["refunds"])} |
| **Net revenue** | **{usd(report["net_revenue"])}** |
""",
    )


@flow(name="green-taxi-elt", log_prints=True)
def green_taxi_elt(
    months: list[str] | None = None, force_download: bool = False
) -> dict:
    """Download, load, transform with dbt, and report daily Green Taxi revenue."""
    selected_months = months or list(DEFAULT_MONTHS)

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
    ).invoke(["build"])

    outputs = report_task()
    publish_artifacts(outputs)
    return outputs.quality_report


@click.command()
@click.option(
    "--serve",
    is_flag=True,
    help="Register a monthly schedule and wait for runs instead of running once.",
)
def main(serve: bool) -> None:
    """Run the Prefect flow once, or serve it as a scheduled deployment."""
    if serve:
        # TLC publishes each month's files with a delay; check early each month.
        green_taxi_elt.serve(
            name="monthly",
            cron="0 7 2 * *",
            tags=["green-taxi", "elt"],
            description="Refresh Q1 2025 Green Taxi daily revenue.",
        )
    else:
        green_taxi_elt()


if __name__ == "__main__":
    main()
