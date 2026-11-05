"""Step 2, load: copy staged Parquet files unchanged into Postgres (raw.green_trips)."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sqlalchemy import Engine, create_engine, inspect, text

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


def load_raw_file(path: Path, engine: Engine) -> LoadResult:
    """Replace this file's rows in raw.green_trips, so loading twice gives the same table."""
    parquet_file = pq.ParquetFile(path)
    rows_in_file = parquet_file.metadata.num_rows
    loaded_at = datetime.now(UTC)
    qualified_table = f"{RAW_SCHEMA}.{RAW_TABLE}"

    # One transaction: if any batch fails, the old rows for this file come back.
    with engine.begin() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {RAW_SCHEMA}"))
        if inspect(connection).has_table(RAW_TABLE, schema=RAW_SCHEMA):
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
