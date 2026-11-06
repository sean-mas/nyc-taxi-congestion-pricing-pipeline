"""Settings shared by every pipeline stage: months, source URL and paths."""

from pathlib import Path

# Resolve paths from this file so commands work from any current directory.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"

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
