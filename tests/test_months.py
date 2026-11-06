"""Unit tests for choosing months and the reporting period dbt keeps."""

from datetime import date

import pytest

from green_taxi.months import month_range, parse_months, reporting_period


def test_a_range_covers_every_month_across_the_new_year() -> None:
    assert month_range("2024-11", "2025-02") == [
        "2024-11",
        "2024-12",
        "2025-01",
        "2025-02",
    ]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2025-01,2025-02", ["2025-01", "2025-02"]),
        (" 2025-01 , ", ["2025-01"]),
        ("2024-12..2025-02", ["2024-12", "2025-01", "2025-02"]),
        ("2024-11,2024-12..2025-01", ["2024-11", "2024-12", "2025-01"]),
    ],
)
def test_months_can_be_listed_or_given_as_a_range(
    raw: str, expected: list[str]
) -> None:
    assert parse_months(raw) == expected


@pytest.mark.parametrize("raw", ["2025-13", "2025-03..2025-01", "2025/01"])
def test_bad_months_are_rejected(raw: str) -> None:
    with pytest.raises(ValueError):
        parse_months(raw)


def test_the_period_runs_from_the_first_month_to_the_end_of_the_last() -> None:
    # Order doesn't matter: the earliest and latest month set the period.
    months = ["2025-03", "2024-10", "2024-11", "2025-01", "2024-12", "2025-02"]
    period = reporting_period(months)

    assert (period.start, period.end) == (date(2024, 10, 1), date(2025, 4, 1))
    assert period.dbt_vars() == {
        "period_start": "2024-10-01",
        "period_end": "2025-04-01",
    }


def test_a_december_period_ends_on_the_first_of_january() -> None:
    assert reporting_period(["2024-12"]).end == date(2025, 1, 1)


def test_months_with_a_gap_are_rejected() -> None:
    with pytest.raises(ValueError, match="2024-11, 2024-12"):
        reporting_period(["2024-10", "2025-01"])
