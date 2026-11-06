"""End-to-end test of load -> dbt -> report on nine hand-made trips."""

import json
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import Engine

from green_taxi.load import load_raw_file
from green_taxi.months import reporting_period
from green_taxi.report import export_outputs
from green_taxi.transform import run_dbt_build
from tests.conftest import make_trips_file, trip

pytestmark = pytest.mark.integration


def test_sample_trips_become_daily_revenue(
    sample_trips_file: Path, test_engine: Engine, tmp_path: Path
) -> None:
    january = reporting_period(["2025-01"])
    load_raw_file(sample_trips_file, test_engine)
    run_dbt_build(january)
    outputs = export_outputs(test_engine, january, tmp_path / "processed")

    daily = pd.read_csv(outputs.daily_revenue_csv)
    assert daily.to_dict(orient="records") == [
        # 20.00 + 15.50 charged, one 5.00 refund; fare revenue 18 + 12 - 4
        {
            "service_date": "2025-01-01",
            "trip_count": 2,
            "refund_count": 1,
            "gross_revenue": 35.5,
            "refunds": -5.0,
            "net_revenue": 30.5,
            "fare_revenue": 26.0,
            "cbd_fee_trip_count": 0,
        },
        # the missing payment type and the $0 trip still count as trips
        {
            "service_date": "2025-01-02",
            "trip_count": 2,
            "refund_count": 0,
            "gross_revenue": 30.0,
            "refunds": 0.0,
            "net_revenue": 30.0,
            "fare_revenue": 28.0,
            "cbd_fee_trip_count": 0,
        },
        # congestion pricing starts: the fee counts in net, not in fare revenue
        {
            "service_date": "2025-01-05",
            "trip_count": 1,
            "refund_count": 0,
            "gross_revenue": 10.0,
            "refunds": 0.0,
            "net_revenue": 10.0,
            "fare_revenue": 9.0,
            "cbd_fee_trip_count": 1,
        },
        {
            "service_date": "2025-01-06",
            "trip_count": 2,
            "refund_count": 0,
            "gross_revenue": 40.25,
            "refunds": 0.0,
            "net_revenue": 40.25,
            "fare_revenue": 33.0,
            "cbd_fee_trip_count": 1,
        },
    ]

    report = json.loads(outputs.quality_report_json.read_text())
    assert report["raw_rows"] == 9
    assert report["dropped_outside_period"] == 1  # the 2024-12-31 trip
    assert report["net_revenue"] == 110.75
    assert report["fare_revenue"] == 96.0
    assert outputs.chart_png.stat().st_size > 0


def test_weekdays_are_compared_before_and_after_5_january(
    sample_trips_file: Path, test_engine: Engine, tmp_path: Path
) -> None:
    january = reporting_period(["2025-01"])
    load_raw_file(sample_trips_file, test_engine)
    run_dbt_build(january)
    outputs = export_outputs(test_engine, january, tmp_path / "processed")

    comparison = pd.read_csv(outputs.congestion_comparison_csv)
    weekdays = comparison[comparison["day_type"] == "weekday"].drop(
        columns=["winter", "day_type"]
    )
    # Empty cells as None, so they compare equal (NaN never equals NaN).
    weekdays = weekdays.astype(object).where(weekdays.notna(), None)
    assert weekdays.to_dict(orient="records") == [
        # Jan 1-2: 4 trips over 2 days. Jan 6: 2 trips on 1 day.
        {"measure": "trips_per_day", "before": 2.0, "after": 2.0, "change_pct": 0.0},
        {
            "measure": "net_revenue_per_day",
            "before": 30.25,
            "after": 40.25,
            "change_pct": 33.1,
        },
        {
            "measure": "fare_revenue_per_day",
            "before": 27.0,
            "after": 33.0,
            "change_pct": 22.2,
        },
        {
            "measure": "net_revenue_per_trip",
            "before": 15.13,
            "after": 20.13,
            "change_pct": 33.0,
        },
        {
            "measure": "fare_revenue_per_trip",
            "before": 13.5,
            "after": 16.5,
            "change_pct": 22.2,
        },
        # one of the two Jan 6 trips paid the fee; no change % from a zero base
        {
            "measure": "cbd_fee_trip_share",
            "before": 0.0,
            "after": 0.5,
            "change_pct": None,
        },
    ]
    assert set(comparison["winter"]) == {"2024/25"}
    assert outputs.congestion_chart_png.stat().st_size > 0


def test_only_the_chosen_months_files_count(
    sample_trips_file: Path, test_engine: Engine, tmp_path: Path
) -> None:
    # An earlier run left a December file in the raw table, with one trip
    # dated in January. A January-only run must give the same result as if
    # that file had never been loaded.
    december_file = make_trips_file(
        tmp_path / "green_tripdata_2024-12.parquet",
        [trip("2025-01-02 09:00", 1, 50.0, 40.0)],
    )
    january = reporting_period(["2025-01"])
    load_raw_file(december_file, test_engine)
    load_raw_file(sample_trips_file, test_engine)
    run_dbt_build(january)
    outputs = export_outputs(test_engine, january, tmp_path / "processed")

    report = outputs.quality_report
    assert report["rows_per_file"] == {"green_tripdata_2025-01.parquet": 9}
    assert report["dropped_outside_period"] == 1
    assert report["net_revenue"] == 110.75
