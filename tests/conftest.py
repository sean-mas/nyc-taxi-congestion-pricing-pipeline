"""Shared fixtures: a tiny hand-made trips file and a clean test database."""

from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from green_taxi.config import database_url
from green_taxi.load import create_db_engine

TEST_DATABASE = "green_taxi_test"
PIPELINE_SCHEMAS = ("raw", "staging", "marts")


def make_trips_file(path: Path, trips: list[dict]) -> Path:
    """Write trips with the same column names and types as the real TLC files."""
    frame = pd.DataFrame(trips)
    frame["lpep_pickup_datetime"] = pd.to_datetime(frame["lpep_pickup_datetime"])
    frame["lpep_dropoff_datetime"] = frame["lpep_pickup_datetime"] + pd.Timedelta(
        minutes=15
    )
    frame["VendorID"] = frame.get("VendorID", 2)
    frame = frame.astype(
        {"VendorID": "int32", "payment_type": "Int64", "total_amount": "float64"}
    )
    frame.to_parquet(path, index=False)
    return path


@pytest.fixture
def sample_trips_file(tmp_path: Path) -> Path:
    """Six trips that hit every cleaning rule in the staging model."""
    return make_trips_file(
        tmp_path / "green_tripdata_2025-01.parquet",
        [
            # two normal trips and a refund on Jan 1
            {
                "lpep_pickup_datetime": "2025-01-01 08:00",
                "payment_type": 1,
                "total_amount": 20.0,
            },
            {
                "lpep_pickup_datetime": "2025-01-01 09:30",
                "payment_type": 2,
                "total_amount": 15.5,
            },
            {
                "lpep_pickup_datetime": "2025-01-01 10:00",
                "payment_type": 4,
                "total_amount": -5.0,
            },
            # a trip with no payment type still counts
            {
                "lpep_pickup_datetime": "2025-01-02 14:00",
                "payment_type": None,
                "total_amount": 30.0,
            },
            # a zero-amount trip counts as a trip with no revenue
            {
                "lpep_pickup_datetime": "2025-01-02 15:00",
                "payment_type": 3,
                "total_amount": 0.0,
            },
            # outside the period: dropped
            {
                "lpep_pickup_datetime": "2024-12-31 23:50",
                "payment_type": 1,
                "total_amount": 99.0,
            },
        ],
    )


@pytest.fixture
def test_engine(monkeypatch: pytest.MonkeyPatch) -> Iterator[Engine]:
    """Engine for the test database with empty pipeline schemas; skips if Postgres is down."""
    # dbt reads POSTGRES_DB too, so the whole pipeline points at the test database.
    monkeypatch.setenv("POSTGRES_DB", TEST_DATABASE)
    engine = create_db_engine(database_url(TEST_DATABASE))
    try:
        with engine.begin() as connection:
            for schema in PIPELINE_SCHEMAS:
                connection.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    except OperationalError:
        pytest.skip(
            "Postgres isn't running: start it with 'docker compose up -d --wait'"
        )
    yield engine
    engine.dispose()
