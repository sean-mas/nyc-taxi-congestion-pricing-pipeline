"""Settings shared by every pipeline stage: months, source URL, paths and database."""

import os
from pathlib import Path

from dotenv import load_dotenv

from .months import month_range

# Resolve paths from this file so commands work from any current directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
DBT_DIR = PROJECT_ROOT / "dbt"

# An optional .env file overrides the defaults below for Docker Compose, this code and
# dbt. Variables already set in the shell win, so tests and CI can point elsewhere.
load_dotenv(PROJECT_ROOT / ".env")

# Two winters, to answer whether congestion pricing (from 5 January 2025) changed
# Green Taxi trips and revenue. October 2024 to March 2025 holds the start of the
# fee; October 2023 to March 2024 is the same season a year earlier, without it, to
# tell the fee apart from the normal winter dip. The months between them keep the
# period free of gaps. (The course brief only asked for January to March 2025.)
DEFAULT_MONTHS = tuple(month_range("2023-10", "2025-03"))

# Public NYC TLC trip record files, one Parquet file per taxi type and month.
SOURCE_BASE_URL = "https://d37ci6vzurychx.cloudfront.net/trip-data"
TAXI_TYPE = "green"
DOWNLOAD_TIMEOUT_SECONDS = 60
DOWNLOAD_CHUNK_BYTES = 1024 * 1024


def source_filename(month: str) -> str:
    """Return the TLC file name for one month, e.g. green_tripdata_2025-01.parquet."""
    return f"{TAXI_TYPE}_tripdata_{month}.parquet"


# Raw layer: an unchanged copy of the staged files, plus where each row came from.
RAW_SCHEMA = "raw"
RAW_TABLE = "green_trips"
LOAD_BATCH_ROWS = 100_000

# Defaults match docker-compose.yaml and dbt/profiles.yml, so a fresh clone runs
# without any configuration file. They're local-only credentials for the Docker
# database on this laptop, not secrets.
DATABASE_DEFAULTS = {
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5433",
    "POSTGRES_DB": "green_taxi",
    "POSTGRES_USER": "postgres",
    "POSTGRES_PASSWORD": "postgres",
}


def database_setting(name: str) -> str:
    """Return a POSTGRES_* setting from the environment or .env, else its default."""
    return os.getenv(name) or DATABASE_DEFAULTS[name]


def database_url(database: str | None = None) -> str:
    """Build the SQLAlchemy URL for the project database (or another one on it)."""
    user = database_setting("POSTGRES_USER")
    password = database_setting("POSTGRES_PASSWORD")
    host = database_setting("POSTGRES_HOST")
    port = database_setting("POSTGRES_PORT")
    name = database or database_setting("POSTGRES_DB")
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"


# Tables built by dbt (see dbt/models/).
STAGING_TABLE = "staging.stg_green_trips"
DAILY_REVENUE_TABLE = "marts.fct_daily_revenue"
CONGESTION_IMPACT_TABLE = "marts.fct_congestion_pricing_impact"
# Trips above this amount are listed in the quality report for a human to check.
LARGE_TRIP_AMOUNT = 500
