"""End-to-end test of load -> dbt -> report on six hand-made trips."""

import json
from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import Engine

from green_taxi.load import load_raw_file
from green_taxi.report import export_outputs
from green_taxi.transform import run_dbt_build

pytestmark = pytest.mark.integration


def test_sample_trips_become_daily_revenue(
    sample_trips_file: Path, test_engine: Engine, tmp_path: Path
) -> None:
    load_raw_file(sample_trips_file, test_engine)
    run_dbt_build()
    outputs = export_outputs(test_engine, tmp_path / "processed")

    daily = pd.read_csv(outputs.daily_revenue_csv)
    assert daily.to_dict(orient="records") == [
        # 20.00 + 15.50 charged, one 5.00 refund
        {
            "service_date": "2025-01-01",
            "trip_count": 2,
            "refund_count": 1,
            "gross_revenue": 35.5,
            "refunds": -5.0,
            "net_revenue": 30.5,
        },
        # the missing payment type and the $0 trip still count as trips
        {
            "service_date": "2025-01-02",
            "trip_count": 2,
            "refund_count": 0,
            "gross_revenue": 30.0,
            "refunds": 0.0,
            "net_revenue": 30.0,
        },
    ]

    report = json.loads(outputs.quality_report_json.read_text())
    assert report["raw_rows"] == 6
    assert report["dropped_outside_period"] == 1  # the 2024-12-31 trip
    assert report["net_revenue"] == 60.5
    assert outputs.chart_png.stat().st_size > 0
