"""
Validate a DataFrame against its contract and publish it to the raw zone.

Layout (hive-style `dt=` so BigQuery can prune partitions, see infra/biglake.tf):
  {source}/raw/dt={date}/{entity}.parquet        conforming rows
  {source}/rejected/dt={date}/{entity}.parquet   rows that broke the contract

Idempotent: both blobs are rewritten on every run, the rejected one even when
empty, so re-running a date that now passes clears its stale rejects.

Circuit breaker: if more than `max_reject_ratio` of the rows break the
contract, the batch is NOT published to raw. A near-empty "successful" load is
worse than a failed one -- nothing downstream would notice.
"""

from datetime import date
from pathlib import Path

import pandas as pd
import structlog
from pydantic import BaseModel

from ingestion.shared.gcs_client import upload_to_gcs
from ingestion.shared.validation import validate_frame

logger = structlog.get_logger()

DEFAULT_MAX_REJECT_RATIO = 0.05


class ContractBreach(RuntimeError):
    """Too many rows broke the contract: the batch was not published to raw."""


def raw_blob(source: str, run_date: date, entity: str) -> str:
    return f"{source}/raw/dt={run_date.isoformat()}/{entity}.parquet"


def rejected_blob(source: str, run_date: date, entity: str) -> str:
    return f"{source}/rejected/dt={run_date.isoformat()}/{entity}.parquet"


def publish_frame(
    df: pd.DataFrame,
    model: type[BaseModel],
    *,
    source: str,
    entity: str,
    bucket: str,
    run_date: date,
    tmp_dir: Path,
    max_reject_ratio: float = DEFAULT_MAX_REJECT_RATIO,
) -> None:
    result = validate_frame(
        df, model, source=source, entity=entity, run_date=run_date.isoformat()
    )
    tmp_dir.mkdir(parents=True, exist_ok=True)

    rejected_path = tmp_dir / f"{entity}_rejected_{run_date}.parquet"
    result.rejected.to_parquet(rejected_path, index=False, engine="pyarrow")
    upload_to_gcs(bucket, rejected_path, rejected_blob(source, run_date, entity))

    log = logger.bind(source=source, entity=entity, run_date=str(run_date))
    log.info(
        "contract_checked",
        valid=len(result.valid),
        rejected=len(result.rejected),
        reject_ratio=round(result.reject_ratio, 4),
    )

    if result.reject_ratio > max_reject_ratio:
        log.error("contract_breach", max_reject_ratio=max_reject_ratio)
        raise ContractBreach(
            f"{source}/{entity} {run_date}: {result.reject_ratio:.1%} of rows broke the "
            f"contract (max {max_reject_ratio:.0%}); raw not updated, see rejected/"
        )

    raw_path = tmp_dir / f"{entity}_{run_date}.parquet"
    result.valid.to_parquet(raw_path, index=False, engine="pyarrow")
    upload_to_gcs(bucket, raw_path, raw_blob(source, run_date, entity))
    log.info("raw_published", rows=len(result.valid))
