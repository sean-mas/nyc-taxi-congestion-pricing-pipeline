"""Unit tests for the database settings: a fresh clone runs without a .env file."""

import pytest

from green_taxi.config import DATABASE_DEFAULTS, database_url


def test_database_url_works_without_any_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in DATABASE_DEFAULTS:
        monkeypatch.delenv(name, raising=False)

    assert (
        database_url()
        == "postgresql+psycopg2://postgres:postgres@localhost:5433/green_taxi"
    )


def test_settings_from_the_environment_win(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("POSTGRES_PORT", "6543")
    monkeypatch.setenv("POSTGRES_DB", "other")

    assert database_url().endswith("@localhost:6543/other")
    assert database_url("green_taxi_test").endswith("/green_taxi_test")
