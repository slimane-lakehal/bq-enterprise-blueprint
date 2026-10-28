from datetime import date

import pandas as pd
import pytest

from ingestion.shared import publish
from ingestion.shared.publish import ContractBreach, publish_frame, raw_blob, rejected_blob
from ingestion.shared.schema_registry import SapInventoryRecord

RUN_DATE = date(2024, 1, 1)


def _row(i: int, **overrides) -> dict:
    return {
        "inventory_id": f"i{i}",
        "product_id": "p1",
        "brand_id": "lumio_maison",
        "category_id": "tables",
        "store_id": "store_001",
        "quantity_on_hand": 10,
        "quantity_reserved": 2,
        "reorder_point": 20,
        "unit_cost": 12.5,
        "snapshot_date": RUN_DATE,
        **overrides,
    }


@pytest.fixture
def uploads(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(publish, "upload_to_gcs", lambda bucket, path, blob: calls.append(blob))
    return calls


def _publish(df, tmp_path, **kw):
    publish_frame(
        df,
        SapInventoryRecord,
        source="sap",
        entity="inventory",
        bucket="b",
        run_date=RUN_DATE,
        tmp_dir=tmp_path,
        **kw,
    )


def test_blob_layout_is_hive_partitioned():
    assert raw_blob("sap", RUN_DATE, "inventory") == "sap/raw/dt=2024-01-01/inventory.parquet"
    assert rejected_blob("sap", RUN_DATE, "inventory") == "sap/rejected/dt=2024-01-01/inventory.parquet"


def test_clean_batch_publishes_raw_and_an_empty_rejected(uploads, tmp_path):
    _publish(pd.DataFrame([_row(i) for i in range(10)]), tmp_path)
    assert uploads == [
        "sap/rejected/dt=2024-01-01/inventory.parquet",
        "sap/raw/dt=2024-01-01/inventory.parquet",
    ]
    assert pd.read_parquet(tmp_path / "inventory_rejected_2024-01-01.parquet").empty


def test_rerun_is_idempotent(uploads, tmp_path):
    df = pd.DataFrame([_row(i) for i in range(10)])
    _publish(df, tmp_path)
    first = pd.read_parquet(tmp_path / "inventory_2024-01-01.parquet")
    uploads.clear()
    _publish(df, tmp_path)
    assert uploads[1] == "sap/raw/dt=2024-01-01/inventory.parquet"  # same blob, overwritten
    pd.testing.assert_frame_equal(first, pd.read_parquet(tmp_path / "inventory_2024-01-01.parquet"))


def test_few_rejects_are_tolerated_and_kept(uploads, tmp_path):
    rows = [_row(i) for i in range(99)] + [_row(99, quantity_on_hand="bad")]
    _publish(pd.DataFrame(rows), tmp_path)
    assert len(pd.read_parquet(tmp_path / "inventory_2024-01-01.parquet")) == 99
    assert len(pd.read_parquet(tmp_path / "inventory_rejected_2024-01-01.parquet")) == 1


def test_breach_publishes_rejects_but_not_raw(uploads, tmp_path):
    rows = [_row(0)] + [_row(i, quantity_on_hand="bad") for i in range(1, 10)]
    with pytest.raises(ContractBreach):
        _publish(pd.DataFrame(rows), tmp_path)
    assert uploads == ["sap/rejected/dt=2024-01-01/inventory.parquet"]
