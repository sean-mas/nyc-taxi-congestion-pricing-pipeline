"""Integration tests for the load step against the test database."""

from pathlib import Path

import pytest
from sqlalchemy import Engine, inspect, text

from green_taxi.load import load_raw_file
from tests.conftest import make_trips_file, trip

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

    assert result.rows_in_file == result.rows_in_table == 9
    assert count_rows(test_engine) == 9


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

    assert count_rows(test_engine) == 10


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


def test_a_file_from_before_2025_can_load_first(
    sample_trips_file: Path, test_engine: Engine, tmp_path: Path
) -> None:
    # Files before 2025 have no cbd_congestion_fee column. Loading one first must
    # not leave the table without it, or the 2025 files would fail.
    december_file = make_trips_file(
        tmp_path / "green_tripdata_2024-12.parquet",
        [
            {
                "lpep_pickup_datetime": "2024-12-02 08:00",
                "payment_type": 1,
                "total_amount": 12.0,
            }
        ],
    )

    load_raw_file(december_file, test_engine)
    load_raw_file(sample_trips_file, test_engine)

    with test_engine.connect() as connection:
        fees = dict(
            connection.execute(
                text(
                    "SELECT source_file, max(cbd_congestion_fee) FROM raw.green_trips "
                    "GROUP BY source_file"
                )
            ).all()
        )
    assert fees == {
        "green_tripdata_2024-12.parquet": None,
        "green_tripdata_2025-01.parquet": 0.75,
    }


def test_a_file_with_an_unknown_column_is_rejected(
    test_engine: Engine, tmp_path: Path
) -> None:
    surprise_file = make_trips_file(
        tmp_path / "green_tripdata_2025-04.parquet",
        [trip("2025-04-01 08:00", 1, 12.0, 10.0) | {"airport_fee": 1.75}],
    )

    with pytest.raises(ValueError, match="airport_fee"):
        load_raw_file(surprise_file, test_engine)
