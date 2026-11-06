"""Step 3, transform: build and test the dbt models inside Postgres."""

import logging

from dbt.cli.main import dbtRunner

from .config import DBT_DIR

logger = logging.getLogger(__name__)


def dbt_args(command: str = "build") -> list[str]:
    """Arguments that point dbt at this repo's project and profile."""
    return [command, "--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]


def run_dbt_build() -> None:
    """Run every model and test in order; fail if any of them fails.

    `dbt build` (not `dbt run`) so a failing data test stops the pipeline
    before a wrong number reaches the outputs.
    """
    result = dbtRunner().invoke(dbt_args("build"))
    if not result.success:
        raise RuntimeError("dbt build failed: check the model and test results above")
    logger.info("dbt build passed")
