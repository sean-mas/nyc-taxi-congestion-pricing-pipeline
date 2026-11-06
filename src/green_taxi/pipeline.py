"""Plain entry point: run the pipeline stages from the command line, without Prefect."""

import logging

import click

from .config import DEFAULT_MONTHS
from .extract import download_months
from .load import create_db_engine, load_raw_files, staged_paths
from .months import ReportingPeriod, parse_months, reporting_period
from .report import export_outputs
from .transform import run_dbt_build


def months_from_option(
    context: click.Context, parameter: click.Parameter, value: str
) -> list[str]:
    """Parse --months, turning a bad value into a clear usage error."""
    try:
        return parse_months(value)
    except ValueError as error:
        raise click.BadParameter(str(error)) from error


def period_for(months: list[str]) -> ReportingPeriod:
    """The reporting period for --months, or a usage error if the months have gaps."""
    try:
        return reporting_period(months)
    except ValueError as error:
        raise click.BadParameter(str(error), param_hint="'--months'") from error


months_option = click.option(
    "--months",
    default=f"{DEFAULT_MONTHS[0]}..{DEFAULT_MONTHS[-1]}",
    show_default=True,
    callback=months_from_option,
    help="YYYY-MM months: a list (2025-01,2025-02) or a range (2024-10..2025-03).",
)


@click.group()
def cli() -> None:
    """NYC Green Taxi ELT pipeline: download, load, transform, report."""
    # force=True: importing dbt already attaches a WARNING-level handler to the
    # root logger, which would otherwise make basicConfig do nothing.
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


@cli.command()
@months_option
@click.option("--force", is_flag=True, help="Download again even if already staged.")
def download(months: list[str], force: bool) -> None:
    """Step 1: download the monthly Parquet files into data/raw/."""
    download_months(months, force=force)


@cli.command()
@months_option
def load(months: list[str]) -> None:
    """Step 2: copy the staged files unchanged into Postgres (raw.green_trips)."""
    load_raw_files(staged_paths(months), create_db_engine())


@cli.command()
@months_option
def transform(months: list[str]) -> None:
    """Step 3: build and test the dbt models for the period the months cover."""
    run_dbt_build(period_for(months))


@cli.command()
def report() -> None:
    """Step 4: reconcile row counts and write the outputs to data/processed/."""
    export_outputs(create_db_engine())


@cli.command()
@months_option
@click.option("--force", is_flag=True, help="Download again even if already staged.")
def run(months: list[str], force: bool) -> None:
    """Run every step in order: download, load, transform, report."""
    # Check the months before downloading anything.
    period = period_for(months)
    engine = create_db_engine()
    download_months(months, force=force)
    load_raw_files(staged_paths(months), engine)
    run_dbt_build(period)
    export_outputs(engine)
