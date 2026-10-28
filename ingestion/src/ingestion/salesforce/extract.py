"""
Salesforce CRM ingestion — Faker (fr_FR) → Parquet → GCS.

Generates a full customer snapshot per run. In a real Salesforce integration
this would be a delta export via simple-salesforce; for this portfolio build
Faker stands in as the source system.
"""

import argparse
import uuid
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import structlog
from faker import Faker

from ingestion.shared.publish import publish_frame
from ingestion.shared.schema_registry import SalesforceCustomer

logger = structlog.get_logger()

fake = Faker("fr_FR")

LOYALTY_TIERS = ["bronze", "silver", "gold", "platinum"]
CHANNELS = ["magasin", "web", "application", "catalogue", "parrainage"]
BRANDS = ["lumio_maison", "lumio_sport", "lumio_kids"]
FRENCH_REGIONS = [
    "Auvergne-Rhône-Alpes",
    "Bourgogne-Franche-Comté",
    "Bretagne",
    "Centre-Val de Loire",
    "Corse",
    "Grand Est",
    "Hauts-de-France",
    "Île-de-France",
    "Normandie",
    "Nouvelle-Aquitaine",
    "Occitanie",
    "Pays de la Loire",
    "Provence-Alpes-Côte d'Azur",
]


def _generate_customers(n: int, run_date: date, seed: int) -> list[dict]:
    customers = []
    window_start = run_date - timedelta(days=5 * 365)
    for i in range(n):
        created = fake.date_time_between(start_date=window_start, end_date=run_date)
        has_purchase = fake.boolean(chance_of_getting_true=80)
        last_purchase = (
            fake.date_between(start_date=created.date(), end_date=run_date)
            if has_purchase
            else None
        )
        customers.append(
            {
                # uuid5 on (seed, index): same run => same ids (uuid4 changed on every re-run)
                "customer_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"salesforce_{seed}_{i}")),
                "email": fake.email(),
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "phone": fake.phone_number()
                if fake.boolean(chance_of_getting_true=70)
                else None,
                "city": fake.city(),
                "region": fake.random_element(FRENCH_REGIONS),
                "postal_code": fake.postcode(),
                "country": "FR",
                "loyalty_tier": fake.random_element(LOYALTY_TIERS),
                "acquisition_channel": fake.random_element(CHANNELS),
                "preferred_brand": fake.random_element(BRANDS),
                "created_at": created.isoformat(),
                "last_purchase_date": last_purchase.isoformat()
                if last_purchase
                else None,
                "lifetime_value": round(
                    fake.pyfloat(min_value=0, max_value=5000, right_digits=2), 2
                ),
            }
        )
    return customers


def extract(
    bucket: str, run_date: date, n_customers: int, tmp_dir: Path, seed: int = 42
) -> None:
    logger.info(
        "salesforce_extract_start", run_date=str(run_date), n_customers=n_customers
    )
    Faker.seed(seed)

    customers = _generate_customers(n_customers, run_date, seed)
    df = pd.DataFrame(customers)

    publish_frame(
        df,
        SalesforceCustomer,
        source="salesforce",
        entity="customers",
        bucket=bucket,
        run_date=run_date,
        tmp_dir=tmp_dir,
    )
    logger.info("salesforce_extract_done", rows=len(df))


def main() -> None:
    parser = argparse.ArgumentParser(description="Salesforce CRM (Faker) → GCS")
    parser.add_argument("--bucket", required=True, help="GCS bucket name")
    parser.add_argument(
        "--date", default=date.today().isoformat(), help="Run date YYYY-MM-DD"
    )
    parser.add_argument(
        "--n-customers",
        default=50_000,
        type=int,
        help="Number of customer records to generate",
    )
    parser.add_argument("--tmp-dir", default=Path("/tmp/lumio/salesforce"), type=Path)
    parser.add_argument(
        "--seed", default=42, type=int, help="Faker seed for reproducibility"
    )
    args = parser.parse_args()

    extract(
        bucket=args.bucket,
        run_date=date.fromisoformat(args.date),
        n_customers=args.n_customers,
        tmp_dir=args.tmp_dir,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
