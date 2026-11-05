"""Unit tests for the extract step. No real network calls."""

from pathlib import Path
from typing import Self

import pytest
import requests

from green_taxi import extract


class FakeResponse:
    """Stands in for a streamed requests response."""

    def __init__(self, chunks: list[bytes], status_error: Exception | None = None):
        self.chunks = chunks
        self.status_error = status_error

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.status_error:
            raise self.status_error

    def iter_content(self, chunk_size: int) -> list[bytes]:
        return self.chunks


@pytest.mark.parametrize("month", ["2025-01", "2025-02", "2025-03"])
def test_build_url_points_to_the_green_taxi_file(month: str) -> None:
    assert extract.build_url(month) == (
        f"https://d37ci6vzurychx.cloudfront.net/trip-data/green_tripdata_{month}.parquet"
    )


@pytest.mark.parametrize("bad_month", ["2025-13", "2025-1", "25-01", "2025/01", ""])
def test_invalid_months_are_rejected(bad_month: str) -> None:
    with pytest.raises(ValueError, match="YYYY-MM"):
        extract.validate_month(bad_month)


def test_existing_file_is_reused_without_any_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    staged = tmp_path / "green_tripdata_2025-01.parquet"
    staged.write_bytes(b"already here")

    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("no HTTP request expected")

    monkeypatch.setattr(extract.requests, "get", fail_if_called)

    result = extract.download_month("2025-01", tmp_path)

    assert result.downloaded is False
    assert staged.read_bytes() == b"already here"


def test_download_writes_the_file_and_leaves_no_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        extract.requests, "get", lambda *a, **k: FakeResponse([b"PAR1", b"data"])
    )

    result = extract.download_month("2025-02", tmp_path)

    assert result.downloaded is True
    assert result.path.read_bytes() == b"PAR1data"
    assert list(tmp_path.glob("*.part")) == []


def test_failed_download_leaves_nothing_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    error = requests.HTTPError("404 Not Found")
    monkeypatch.setattr(
        extract.requests, "get", lambda *a, **k: FakeResponse([], status_error=error)
    )

    with pytest.raises(requests.HTTPError):
        extract.download_month("2025-03", tmp_path)

    assert list(tmp_path.iterdir()) == []
