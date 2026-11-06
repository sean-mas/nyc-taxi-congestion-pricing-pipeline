"""Which months to process, and the reporting period dbt keeps from them."""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

MONTH_PATTERN = re.compile(r"\d{4}-(0[1-9]|1[0-2])")


def validate_month(month: str) -> str:
    """Return the month unchanged, or fail early if it isn't in YYYY-MM form."""
    if not MONTH_PATTERN.fullmatch(month):
        raise ValueError(f"Month must look like YYYY-MM, got {month!r}")
    return month


def first_day(month: str) -> date:
    """2025-01 -> 1 January 2025."""
    year, month_number = validate_month(month).split("-")
    return date(int(year), int(month_number), 1)


def next_month(day: date) -> date:
    """First day of the month after the given day's month."""
    return date(day.year + day.month // 12, day.month % 12 + 1, 1)


def month_range(first: str, last: str) -> list[str]:
    """Every month from first to last, both included."""
    current, end = first_day(first), first_day(last)
    if current > end:
        raise ValueError(f"{first} comes after {last}")
    months = []
    while current <= end:
        months.append(current.strftime("%Y-%m"))
        current = next_month(current)
    return months


def parse_months(raw_months: str) -> list[str]:
    """Turn '2025-01,2025-02' or a range like '2024-10..2025-03' into a list of months."""
    months: list[str] = []
    for part in raw_months.split(","):
        part = part.strip()
        if ".." in part:
            first, _, last = part.partition("..")
            months.extend(month_range(first.strip(), last.strip()))
        elif part:
            months.append(validate_month(part))
    return months


@dataclass(frozen=True)
class ReportingPeriod:
    """The days dbt keeps: from start (included) to end (excluded)."""

    start: date
    end: date

    @property
    def months(self) -> list[str]:
        """The months the period covers, as YYYY-MM."""
        last_day = self.end - timedelta(days=1)
        return month_range(f"{self.start:%Y-%m}", f"{last_day:%Y-%m}")

    def dbt_vars(self) -> dict[str, str]:
        """The period as the vars dbt_project.yml expects."""
        return {
            "period_start": self.start.isoformat(),
            "period_end": self.end.isoformat(),
        }


def reporting_period(months: Iterable[str]) -> ReportingPeriod:
    """Return the days the months cover. The months must follow each other.

    A gap (say 2024-10 and 2025-01 only) would leave days without data inside the
    period, so it fails here, before anything is downloaded.
    """
    selected = sorted(set(months))
    if not selected:
        raise ValueError("Pick at least one month")
    expected = month_range(selected[0], selected[-1])
    if selected != expected:
        missing = ", ".join(sorted(set(expected) - set(selected)))
        raise ValueError(f"Months must follow each other without gaps; add {missing}")
    return ReportingPeriod(first_day(selected[0]), next_month(first_day(selected[-1])))
