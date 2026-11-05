"""Plain entry point: run the pipeline stages from the command line, without Prefect."""

import logging

import click

from .config import DEFAULT_MONTHS
from .extract import download_months
from .load import create_db_engine, load_raw_files, staged_paths
from .report import export_outputs
from .transform import run_dbt_build


def parse_months(raw_months: str) -> list[str]:
    """Turn '2025-01,2025-02' into ['2025-01', '2025-02']."""
    return [month.strip() for month in raw_months.split(",") if month.strip()]


months_option = click.option(
    "--months",
    default=",".join(DEFAULT_MONTHS),
    show_default=True,
    help="Comma-separated list of YYYY-MM months.",
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
def download(months: str, force: bool) -> None:
    """Step 1: download the monthly Parquet files into data/raw/."""
    download_months(parse_months(months), force=force)


@cli.command()
@months_option
def load(months: str) -> None:
    """Step 2: copy the staged files unchanged into Postgres (raw.green_trips)."""
    load_raw_files(staged_paths(parse_months(months)), create_db_engine())


@cli.command()
def transform() -> None:
    """Step 3: build and test the dbt models (staging view, daily revenue table)."""
    run_dbt_build()


@cli.command()
def report() -> None:
    """Step 4: reconcile row counts and write the outputs to data/processed/."""
    export_outputs(create_db_engine())


@cli.command()
@months_option
@click.option("--force", is_flag=True, help="Download again even if already staged.")
def run(months: str, force: bool) -> None:
    """Run every step in order: download, load, transform, report."""
    selected_months = parse_months(months)
    engine = create_db_engine()
    download_months(selected_months, force=force)
    load_raw_files(staged_paths(selected_months), engine)
    run_dbt_build()
    export_outputs(engine)
