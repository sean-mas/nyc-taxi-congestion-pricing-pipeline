"""Settings shared by every pipeline stage: months, source URL, paths and database."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Resolve paths from this file so commands work from any current directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

# One .env file configures Docker Compose, this code and dbt. Variables already set
# in the shell win, so tests and CI can point at another database.
load_dotenv(PROJECT_ROOT / ".env")

# The brief asks for the first three months of 2025.
DEFAULT_MONTHS = ("2025-01", "2025-02", "2025-03")

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

DATABASE_ENV_VARS = (
    "POSTGRES_HOST",
    "POSTGRES_PORT",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
)


def database_url(database: str | None = None) -> str:
    """Build the SQLAlchemy URL from the POSTGRES_* variables, failing fast if any is missing."""
    missing = [name for name in DATABASE_ENV_VARS if not os.getenv(name)]
    if missing:
        raise RuntimeError(
            f"Missing {', '.join(missing)}. Copy .env.example to .env and try again."
        )
    user = os.environ["POSTGRES_USER"]
    password = os.environ["POSTGRES_PASSWORD"]
    host = os.environ["POSTGRES_HOST"]
    port = os.environ["POSTGRES_PORT"]
    name = database or os.environ["POSTGRES_DB"]
    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{name}"
