"""
SAP ERP inventory ingestion — Faker → Parquet → GCS.

Generates a daily inventory snapshot: 60 stores × 600 SKUs (200 per brand).
The seed is date-derived so each day produces different stock levels
but the same date is always reproducible (idempotent re-runs).
"""

import argparse
import uuid
from datetime import date
from pathlib import Path
from random import Random

import pandas as pd
import structlog

from ingestion.shared.determinism import stable_int
from ingestion.shared.publish import publish_frame
from ingestion.shared.schema_registry import SapInventoryRecord

logger = structlog.get_logger()

STORES = [f"store_{i:03d}" for i in range(1, 61)]
BRANDS = ["lumio_maison", "lumio_sport", "lumio_kids"]
CATEGORIES = {
    "lumio_maison": ["canapés", "tables", "luminaires", "literie", "rangement"],
    "lumio_sport":  ["running", "vélo", "natation", "fitness", "outdoor"],
    "lumio_kids":   ["jouets", "vêtements", "mobilier", "livres", "jeux"],
}
PRODUCTS_PER_BRAND = 200


def _build_product_catalog(rng: Random) -> list[dict]:
    products = []
    for brand in BRANDS:
        for i in range(PRODUCTS_PER_BRAND):
            category = rng.choice(CATEGORIES[brand])
            products.append({
                "product_id": f"{brand}_{category}_{i:04d}",
                "brand_id": brand,
                "category_id": category,
                "unit_cost": round(rng.uniform(5.0, 500.0), 2),
            })
    return products


def extract(bucket: str, run_date: date, tmp_dir: Path) -> None:
    logger.info("sap_extract_start", run_date=str(run_date))

    # Date-seeded RNG — same date = same output (idempotent), different dates = different levels
    rng = Random(stable_int(run_date.isoformat()))
    products = _build_product_catalog(rng)

    records = []
    for store_id in STORES:
        for product in products:
            qty_on_hand = rng.randint(0, 200)
            qty_reserved = rng.randint(0, min(qty_on_hand, 50))
            records.append({
                "inventory_id": str(uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"{store_id}_{product['product_id']}_{run_date}",
                )),
                "product_id": product["product_id"],
                "brand_id": product["brand_id"],
                "category_id": product["category_id"],
                "store_id": store_id,
                "quantity_on_hand": qty_on_hand,
                "quantity_reserved": qty_reserved,
                "reorder_point": 20,
                "unit_cost": product["unit_cost"],
                "snapshot_date": run_date.isoformat(),
            })

    df = pd.DataFrame(records)

    publish_frame(
        df,
        SapInventoryRecord,
        source="sap",
        entity="inventory",
        bucket=bucket,
        run_date=run_date,
        tmp_dir=tmp_dir,
    )
    logger.info("sap_extract_done", rows=len(df))


def main() -> None:
    parser = argparse.ArgumentParser(description="SAP inventory snapshot (Faker) → GCS")
    parser.add_argument("--bucket", required=True, help="GCS bucket name")
    parser.add_argument("--date", default=date.today().isoformat(), help="Snapshot date YYYY-MM-DD")
    parser.add_argument("--tmp-dir", default=Path("/tmp/lumio/sap"), type=Path)
    args = parser.parse_args()

    extract(
        bucket=args.bucket,
        run_date=date.fromisoformat(args.date),
        tmp_dir=args.tmp_dir,
    )


if __name__ == "__main__":
    main()
