"""The command line checks --months before it downloads anything."""

import pytest
from click.testing import CliRunner

from green_taxi import pipeline


def test_months_with_a_gap_stop_the_run_before_any_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_if_called(*args: object, **kwargs: object) -> None:
        raise AssertionError("nothing should be downloaded")

    monkeypatch.setattr(pipeline, "download_months", fail_if_called)

    result = CliRunner().invoke(pipeline.cli, ["run", "--months", "2024-10,2025-01"])

    assert result.exit_code == 2  # click's usage error
    assert "without gaps" in result.output
