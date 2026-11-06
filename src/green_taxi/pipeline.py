"""Plain entry point: run the pipeline stages from the command line, without Prefect."""

import logging

import click

from .config import DEFAULT_MONTHS
from .extract import download_months


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
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )


@cli.command()
@months_option
@click.option("--force", is_flag=True, help="Download again even if already staged.")
def download(months: str, force: bool) -> None:
    """Step 1: download the monthly Parquet files into data/raw/."""
    download_months(parse_months(months), force=force)
