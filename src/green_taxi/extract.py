"""Step 1, extract: download monthly Green Taxi Parquet files into the staging folder."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import requests

from .config import (
    DOWNLOAD_CHUNK_BYTES,
    DOWNLOAD_TIMEOUT_SECONDS,
    RAW_DIR,
    SOURCE_BASE_URL,
    source_filename,
)
from .months import validate_month

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DownloadResult:
    """What happened to one requested month."""

    month: str
    path: Path
    downloaded: bool  # False when the file was already staged and reused


def build_url(month: str, base_url: str = SOURCE_BASE_URL) -> str:
    """Return the public download link for one month."""
    return f"{base_url.rstrip('/')}/{source_filename(validate_month(month))}"


def download_month(
    month: str, raw_dir: Path = RAW_DIR, *, force: bool = False
) -> DownloadResult:
    """Download one month into raw_dir, or reuse the file if it's already there."""
    destination = raw_dir / source_filename(validate_month(month))
    if destination.exists() and not force:
        logger.info("reused %s", destination.name)
        return DownloadResult(month, destination, downloaded=False)

    raw_dir.mkdir(parents=True, exist_ok=True)
    # Write to a temporary name first, so a broken download never looks finished
    # and gets reused on the next run.
    partial = destination.with_name(destination.name + ".part")
    try:
        with requests.get(
            build_url(month), stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS
        ) as response:
            response.raise_for_status()
            with partial.open("wb") as output_file:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
                    output_file.write(chunk)
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)

    size_mb = destination.stat().st_size / 1_000_000
    logger.info("downloaded %s (%.1f MB)", destination.name, size_mb)
    return DownloadResult(month, destination, downloaded=True)


def download_months(
    months: Iterable[str], raw_dir: Path = RAW_DIR, *, force: bool = False
) -> list[DownloadResult]:
    """Download every requested month and return one result per month."""
    return [download_month(month, raw_dir, force=force) for month in months]
