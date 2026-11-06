"""Step 2, load: copy staged Parquet files unchanged into Postgres (raw.green_trips)."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import Connection, Engine, create_engine, text

from .config import (
    LOAD_BATCH_ROWS,
    RAW_DIR,
    RAW_SCHEMA,
    RAW_TABLE,
    database_url,
    source_filename,
)

logger = logging.getLogger(__name__)

# Keep integer columns as integers even when they contain nulls
# (plain pandas would turn payment_type into a float column).
NULLABLE_INTEGERS = {pa.int32(): pd.Int32Dtype(), pa.int64(): pd.Int64Dtype()}

# The raw table gets this fixed list of columns instead of copying whichever file
# loads first. Files before 2025 have no cbd_congestion_fee, so a table copied from
# one of them would reject the 2025 files. Types match the TLC files (checked for
# October 2023 to March 2025); a file without a column loads NULL into it.
RAW_COLUMNS = {
    "vendorid": "integer",
    "lpep_pickup_datetime": "timestamp",
    "lpep_dropoff_datetime": "timestamp",
    "store_and_fwd_flag": "text",
    "ratecodeid": "bigint",
    "pulocationid": "integer",
    "dolocationid": "integer",
    "passenger_count": "bigint",
    "trip_distance": "double precision",
    "fare_amount": "double precision",
    "extra": "double precision",
    "mta_tax": "double precision",
    "tip_amount": "double precision",
    "tolls_amount": "double precision",
    "ehail_fee": "double precision",
    "improvement_surcharge": "double precision",
    "total_amount": "double precision",
    "payment_type": "bigint",
    "trip_type": "bigint",
    "congestion_surcharge": "double precision",
    # $0.75 congestion pricing fee, in the files from January 2025 on.
    "cbd_congestion_fee": "double precision",
}
# Added by the loader, so every row can be traced back to its file.
TRACKING_COLUMNS = {
    "source_file": "text not null",
    "loaded_at": "timestamp with time zone not null",
}


@dataclass(frozen=True)
class LoadResult:
    """Row counts for one loaded file, used to prove nothing was lost."""

    source_file: str
    rows_in_file: int
    rows_in_table: int


def create_db_engine(url: str | None = None) -> Engine:
    """Return a SQLAlchemy engine for the project database (or the given URL)."""
    return create_engine(url or database_url())


def staged_paths(months: Iterable[str], raw_dir: Path = RAW_DIR) -> list[Path]:
    """Return the staged file for each month, failing early if one is missing."""
    paths = [raw_dir / source_filename(month) for month in months]
    missing = [path.name for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(
            f"Not staged yet: {', '.join(missing)}. Run 'green-taxi download' first."
        )
    return paths


def create_raw_table(connection: Connection) -> None:
    """Create raw.green_trips from RAW_COLUMNS if it doesn't exist yet."""
    columns = ",\n    ".join(
        f"{name} {sql_type}"
        for name, sql_type in (RAW_COLUMNS | TRACKING_COLUMNS).items()
    )
    connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA}"))
    connection.execute(
        text(f"CREATE TABLE IF NOT EXISTS {RAW_SCHEMA}.{RAW_TABLE} (\n    {columns}\n)")
    )


def check_columns(parquet_file: pq.ParquetFile, file_name: str) -> None:
    """Fail on columns the raw table doesn't know; log the ones the file lacks."""
    file_columns = {name.lower() for name in parquet_file.schema_arrow.names}
    unknown = sorted(file_columns - RAW_COLUMNS.keys())
    if unknown:
        # Fail instead of dropping data: a new TLC column needs a decision.
        raise ValueError(
            f"{file_name} has columns the raw table doesn't have: "
            f"{', '.join(unknown)}. Add them to RAW_COLUMNS in load.py."
        )
    missing = sorted(RAW_COLUMNS.keys() - file_columns)
    if missing:
        logger.info("%s has no %s; loading NULL", file_name, ", ".join(missing))


def load_raw_file(path: Path, engine: Engine) -> LoadResult:
    """Replace this file's rows in raw.green_trips, so loading twice gives the same table."""
    parquet_file = pq.ParquetFile(path)
    check_columns(parquet_file, path.name)
    rows_in_file = parquet_file.metadata.num_rows
    loaded_at = datetime.now(UTC)
    qualified_table = f"{RAW_SCHEMA}.{RAW_TABLE}"

    # One transaction: if any batch fails, the old rows for this file come back.
    with engine.begin() as connection:
        create_raw_table(connection)
        connection.execute(
            text(f"DELETE FROM {qualified_table} WHERE source_file = :source_file"),
            {"source_file": path.name},
        )
        for batch in parquet_file.iter_batches(batch_size=LOAD_BATCH_ROWS):
            frame = batch.to_pandas(types_mapper=NULLABLE_INTEGERS.get)
            # Lowercase names so SQL can use vendorid instead of "VendorID".
            frame.columns = [column.lower() for column in frame.columns]
            frame["source_file"] = path.name
            frame["loaded_at"] = loaded_at
            frame.to_sql(
                RAW_TABLE,
                connection,
                schema=RAW_SCHEMA,
                if_exists="append",
                index=False,
            )
        rows_in_table = connection.execute(
            text(
                f"SELECT count(*) FROM {qualified_table} WHERE source_file = :source_file"
            ),
            {"source_file": path.name},
        ).scalar_one()

    if rows_in_table != rows_in_file:
        raise ValueError(
            f"{path.name}: {rows_in_file} rows in the file but {rows_in_table} in the table"
        )
    logger.info("loaded %s: %s rows", path.name, f"{rows_in_table:,}")
    return LoadResult(path.name, rows_in_file, rows_in_table)


def load_raw_files(paths: Iterable[Path], engine: Engine) -> list[LoadResult]:
    """Load the files one after another and return their row counts."""
    return [load_raw_file(path, engine) for path in paths]
