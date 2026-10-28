import os
import subprocess
import sys

from ingestion.shared.determinism import stable_int


def _brand_in_fresh_process(seed: str) -> str:
    """builtin hash() differs per PYTHONHASHSEED; the brand must not."""
    code = (
        "from ingestion.cegid.extract import _brand_for_seller;"
        "print(_brand_for_seller('seller-42'))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "PYTHONHASHSEED": seed},
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout.strip()


def test_stable_int_is_fixed():
    assert stable_int("2024-01-01") == stable_int("2024-01-01")
    assert stable_int("a") != stable_int("b")


def test_brand_assignment_is_stable_across_processes():
    assert len({_brand_in_fresh_process(s) for s in ("1", "2", "3")}) == 1


def test_salesforce_customers_are_reproducible():
    from datetime import date

    from faker import Faker

    from ingestion.salesforce.extract import _generate_customers

    run_date = date(2024, 6, 1)
    Faker.seed(7)
    first = _generate_customers(20, run_date, seed=7)
    Faker.seed(7)
    second = _generate_customers(20, run_date, seed=7)
    assert first == second
    assert len({c["customer_id"] for c in first}) == 20
