"""Integration tests for the load step against the test database."""

from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, text

from green_taxi.load import load_raw_file
from tests.conftest import make_trips_file

pytestmark = pytest.mark.integration


def count_rows(engine: Engine) -> int:
    with engine.connect() as connection:
        return connection.execute(
            text("SELECT count(*) FROM raw.green_trips")
        ).scalar_one()


def test_loading_the_same_file_twice_keeps_one_copy(
    sample_trips_file: Path, test_engine: Engine
) -> None:
    load_raw_file(sample_trips_file, test_engine)
    result = load_raw_file(sample_trips_file, test_engine)

    assert result.rows_in_file == result.rows_in_table == 6
    assert count_rows(test_engine) == 6


def test_loading_a_second_month_keeps_the_first(
    sample_trips_file: Path, test_engine: Engine, tmp_path: Path
) -> None:
    february_file = make_trips_file(
        tmp_path / "green_tripdata_2025-02.parquet",
        [
            {
                "lpep_pickup_datetime": "2025-02-01 08:00",
                "payment_type": 1,
                "total_amount": 12.0,
            }
        ],
    )

    load_raw_file(sample_trips_file, test_engine)
    load_raw_file(february_file, test_engine)

    assert count_rows(test_engine) == 7


def test_columns_are_lowercased_and_traceable(
    sample_trips_file: Path, test_engine: Engine
) -> None:
    load_raw_file(sample_trips_file, test_engine)

    columns = {
        column["name"]: str(column["type"])
        for column in inspect(test_engine).get_columns("green_trips", schema="raw")
    }

    assert "vendorid" in columns
    assert {"source_file", "loaded_at"} <= columns.keys()
    assert columns["payment_type"] == "BIGINT"
