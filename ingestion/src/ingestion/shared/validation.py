"""
Row-level contract validation, at the ingestion boundary.

Upstream data is assumed dirty. Each row is checked against its Pydantic
contract (schema_registry.py): conforming rows continue to raw, the others are
kept -- never dropped -- with the reason, so they can be triaged and fixed at
the source.

Pure functions, no I/O: publish.py decides what to do with the result.
"""

import json
from dataclasses import dataclass

import pandas as pd
from pydantic import BaseModel, ValidationError

REJECTED_COLUMNS = ["source", "entity", "run_date", "row_json", "errors_json"]


@dataclass(frozen=True)
class ValidationResult:
    valid: pd.DataFrame
    rejected: pd.DataFrame  # REJECTED_COLUMNS, all strings

    @property
    def reject_ratio(self) -> float:
        total = len(self.valid) + len(self.rejected)
        return len(self.rejected) / total if total else 0.0


def validate_frame(
    df: pd.DataFrame,
    model: type[BaseModel],
    *,
    source: str,
    entity: str,
    run_date: str,
) -> ValidationResult:
    """Split df into rows that satisfy `model` and rows that do not."""
    # pandas NaN/NaT would fail Optional[...] fields: normalise to None first.
    records = df.astype(object).where(df.notna(), None).to_dict("records")

    valid_idx: list[int] = []
    rejected: list[dict[str, str]] = []
    for idx, record in zip(df.index, records, strict=True):
        try:
            model.model_validate(record)
        except ValidationError as exc:
            rejected.append(
                {
                    "source": source,
                    "entity": entity,
                    "run_date": run_date,
                    "row_json": json.dumps(record, default=str, sort_keys=True),
                    "errors_json": json.dumps(
                        exc.errors(
                            include_url=False, include_context=False, include_input=False
                        ),
                        default=str,
                    ),
                }
            )
        else:
            valid_idx.append(idx)

    return ValidationResult(
        valid=df.loc[valid_idx],
        rejected=pd.DataFrame(rejected, columns=REJECTED_COLUMNS).astype("string"),
    )
