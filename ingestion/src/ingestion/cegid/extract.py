"""
Cegid POS ingestion — Olist dataset → Parquet → GCS.

Olist is a Brazilian e-commerce dataset (Kaggle). We map it to a fictional
French retail POS system (Cegid) by treating sellers as stores and orders
as in-store transactions. The mapping is intentionally simple: one order
line = one transaction line, quantity is always 1 (Olist semantics).

Expected files in --data-dir:
  olist_orders_dataset.csv
  olist_order_items_dataset.csv
  olist_products_dataset.csv
  olist_order_payments_dataset.csv
"""

import argparse
from datetime import date
from pathlib import Path

import pandas as pd
import structlog

from ingestion.shared.determinism import stable_int
from ingestion.shared.publish import publish_frame
from ingestion.shared.schema_registry import CegidTransaction

logger = structlog.get_logger()

BRANDS = ["lumio_maison", "lumio_sport", "lumio_kids"]


def _brand_for_seller(seller_id: str) -> str:
    """Stable deterministic brand assignment — same seller always maps to same brand."""
    return BRANDS[stable_int(seller_id) % len(BRANDS)]


def extract(data_dir: Path, bucket: str, run_date: date, tmp_dir: Path) -> None:
    logger.info("cegid_extract_start", data_dir=str(data_dir), run_date=str(run_date))

    orders = pd.read_csv(
        data_dir / "olist_orders_dataset.csv",
        parse_dates=["order_purchase_timestamp"],
        usecols=["order_id", "order_purchase_timestamp"],
    )
    items = pd.read_csv(
        data_dir / "olist_order_items_dataset.csv",
        usecols=["order_id", "order_item_id", "product_id", "seller_id", "price"],
    )
    products = pd.read_csv(
        data_dir / "olist_products_dataset.csv",
        usecols=["product_id", "product_category_name"],
    )
    # Take the primary payment method per order (lowest payment_sequential)
    payments = (
        pd.read_csv(
            data_dir / "olist_order_payments_dataset.csv",
            usecols=["order_id", "payment_type", "payment_sequential"],
        )
        .sort_values("payment_sequential")
        .groupby("order_id", as_index=False)
        .first()[["order_id", "payment_type"]]
    )

    df = (
        items
        .merge(orders, on="order_id", how="left")
        .merge(products, on="product_id", how="left")
        .merge(payments, on="order_id", how="left")
    )

    df["transaction_id"] = df["order_id"] + "_" + df["order_item_id"].astype(str)
    df["store_id"] = df["seller_id"]
    df["brand_id"] = df["seller_id"].apply(_brand_for_seller)
    df["transaction_date"] = df["order_purchase_timestamp"]
    df["category_id"] = df["product_category_name"]
    df["quantity"] = 1
    df["unit_price"] = df["price"]
    df["total_price"] = df["price"]

    result = df[[
        "transaction_id", "store_id", "brand_id", "transaction_date",
        "product_id", "category_id", "quantity", "unit_price", "total_price", "payment_type",
    ]].copy()

    publish_frame(
        result,
        CegidTransaction,
        source="cegid",
        entity="transactions",
        bucket=bucket,
        run_date=run_date,
        tmp_dir=tmp_dir,
    )
    logger.info("cegid_extract_done", rows=len(result))


def main() -> None:
    parser = argparse.ArgumentParser(description="Cegid (Olist) → GCS ingestion")
    parser.add_argument("--data-dir", required=True, type=Path, help="Directory containing Olist CSV files")
    parser.add_argument("--bucket", required=True, help="GCS bucket name")
    parser.add_argument("--date", default=date.today().isoformat(), help="Run date YYYY-MM-DD")
    parser.add_argument("--tmp-dir", default=Path("/tmp/lumio/cegid"), type=Path)
    args = parser.parse_args()

    extract(
        data_dir=args.data_dir,
        bucket=args.bucket,
        run_date=date.fromisoformat(args.date),
        tmp_dir=args.tmp_dir,
    )


if __name__ == "__main__":
    main()
