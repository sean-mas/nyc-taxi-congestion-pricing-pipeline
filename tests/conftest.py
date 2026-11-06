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
PIPELINE_SCHEMAS = ("raw", "reference", "staging", "marts")
MONEY_COLUMNS = (
    "total_amount",
    "fare_amount",
    "extra",
    "tip_amount",
    "cbd_congestion_fee",
)


def trip(
    pickup_at: str,
    payment_type: int | None,
    total_amount: float,
    fare_amount: float,
    *,
    extra: float = 0.0,
    tip_amount: float = 0.0,
    cbd_congestion_fee: float = 0.0,
) -> dict:
    """One trip record. total_amount also holds taxes the other amounts leave out."""
    return {
        "lpep_pickup_datetime": pickup_at,
        "payment_type": payment_type,
        "total_amount": total_amount,
        "fare_amount": fare_amount,
        "extra": extra,
        "tip_amount": tip_amount,
        "cbd_congestion_fee": cbd_congestion_fee,
    }


def make_trips_file(path: Path, trips: list[dict]) -> Path:
    """Write trips with the same column names and types as the real TLC files.

    Only the columns the trips set end up in the file, so leaving out
    cbd_congestion_fee gives a file like the ones from before 2025.
    """
    frame = pd.DataFrame(trips)
    frame["lpep_pickup_datetime"] = pd.to_datetime(frame["lpep_pickup_datetime"])
    frame["lpep_dropoff_datetime"] = frame["lpep_pickup_datetime"] + pd.Timedelta(
        minutes=15
    )
    frame["VendorID"] = frame.get("VendorID", 2)
    types = {"VendorID": "int32", "payment_type": "Int64"}
    types |= {name: "float64" for name in frame.columns if name in MONEY_COLUMNS}
    frame.astype(types).to_parquet(path, index=False)
    return path


@pytest.fixture
def sample_trips_file(tmp_path: Path) -> Path:
    """Nine trips that hit every cleaning rule and both sides of 5 January 2025."""
    return make_trips_file(
        tmp_path / "green_tripdata_2025-01.parquet",
        [
            # Wed Jan 1: two normal trips and a refund
            trip("2025-01-01 08:00", 1, 20.0, 15.0, extra=1.0, tip_amount=2.0),
            trip("2025-01-01 09:30", 2, 15.5, 12.0),
            trip("2025-01-01 10:00", 4, -5.0, -4.0),
            # Thu Jan 2: a trip with no payment type still counts
            trip("2025-01-02 14:00", None, 30.0, 25.0, tip_amount=3.0),
            # ... and a zero-amount trip counts as a trip with no revenue
            trip("2025-01-02 15:00", 3, 0.0, 0.0),
            # Sun Jan 5, the first day of congestion pricing: a weekend trip with the fee
            trip(
                "2025-01-05 12:00",
                1,
                10.0,
                8.0,
                tip_amount=1.0,
                cbd_congestion_fee=0.75,
            ),
            # Mon Jan 6: one weekday trip with the fee, one without
            trip(
                "2025-01-06 08:00",
                1,
                25.75,
                18.0,
                extra=1.0,
                tip_amount=3.0,
                cbd_congestion_fee=0.75,
            ),
            trip("2025-01-06 18:00", 2, 14.5, 11.0),
            # outside the period: dropped
            trip("2024-12-31 23:50", 1, 99.0, 80.0, tip_amount=10.0),
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
