"""Step 3, transform: build and test the dbt models inside Postgres."""

import json
import logging

from dbt.cli.main import dbtRunner

from .config import DBT_DIR
from .months import ReportingPeriod

logger = logging.getLogger(__name__)


def dbt_build_args(period: ReportingPeriod) -> list[str]:
    """`dbt build` for the given period. The months chosen on the command line
    set the period, so dbt never keeps days that weren't asked for."""
    return ["build", "--vars", json.dumps(period.dbt_vars())]


def run_dbt_build(period: ReportingPeriod) -> None:
    """Run every model and test in order; fail if any of them fails.

    `dbt build` (not `dbt run`) so a failing data test stops the pipeline
    before a wrong number reaches the outputs.
    """
    args = dbt_build_args(period)
    args += ["--project-dir", str(DBT_DIR), "--profiles-dir", str(DBT_DIR)]
    result = dbtRunner().invoke(args)
    if not result.success:
        raise RuntimeError("dbt build failed: check the model and test results above")
    logger.info("dbt build passed for %s to %s", period.start, period.end)
