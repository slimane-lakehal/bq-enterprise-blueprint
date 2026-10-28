import json
from datetime import date, datetime

import pandas as pd

from ingestion.shared.schema_registry import SapInventoryRecord
from ingestion.shared.validation import REJECTED_COLUMNS, validate_frame


def _row(**overrides) -> dict:
    base = {
        "inventory_id": "i1",
        "product_id": "p1",
        "brand_id": "lumio_maison",
        "category_id": "tables",
        "store_id": "store_001",
        "quantity_on_hand": 10,
        "quantity_reserved": 2,
        "reorder_point": 20,
        "unit_cost": 12.5,
        "snapshot_date": date(2024, 1, 1),
    }
    return {**base, **overrides}


def _validate(rows: list[dict]):
    return validate_frame(
        pd.DataFrame(rows),
        SapInventoryRecord,
        source="sap",
        entity="inventory",
        run_date="2024-01-01",
    )


def test_splits_valid_and_rejected_without_losing_rows():
    result = _validate([_row(), _row(inventory_id="i2", quantity_on_hand="not-a-number")])
    assert len(result.valid) == 1
    assert len(result.rejected) == 1
    assert result.reject_ratio == 0.5


def test_rejected_row_keeps_payload_and_reason():
    result = _validate([_row(quantity_on_hand="oops")])
    rejected = result.rejected.iloc[0]
    assert json.loads(rejected["row_json"])["quantity_on_hand"] == "oops"
    assert "quantity_on_hand" in rejected["errors_json"]
    assert list(result.rejected.columns) == REJECTED_COLUMNS


def test_missing_required_field_is_rejected():
    result = _validate([_row(product_id=None)])
    assert len(result.valid) == 0 and len(result.rejected) == 1


def test_optional_nan_is_accepted():
    from ingestion.shared.schema_registry import CegidTransaction

    df = pd.DataFrame(
        [
            {
                "transaction_id": "t1",
                "store_id": "s1",
                "brand_id": "b1",
                "transaction_date": datetime(2024, 1, 1),
                "product_id": "p1",
                "category_id": float("nan"),  # Optional[str] arrives as NaN from pandas
                "quantity": 1,
                "unit_price": 9.9,
                "total_price": 9.9,
                "payment_type": None,
            }
        ]
    )
    result = validate_frame(
        df, CegidTransaction, source="cegid", entity="transactions", run_date="2024-01-01"
    )
    assert len(result.valid) == 1 and result.rejected.empty


def test_empty_rejected_keeps_string_schema():
    result = _validate([_row()])
    assert result.rejected.empty
    assert all(str(t) == "string" for t in result.rejected.dtypes)
