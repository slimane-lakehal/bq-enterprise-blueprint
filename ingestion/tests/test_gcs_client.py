from unittest.mock import MagicMock

import pytest

from ingestion.shared import gcs_client


@pytest.fixture
def adc(monkeypatch):
    creds = MagicMock(name="adc")
    monkeypatch.setattr(gcs_client.google.auth, "default", lambda: (creds, "proj"))
    return creds


def test_ci_uses_ambient_credentials_when_no_target_sa(monkeypatch, adc):
    monkeypatch.delenv(gcs_client.INGESTION_SA_ENV, raising=False)
    assert gcs_client.get_credentials() is adc


def test_local_impersonates_the_ingestion_sa(monkeypatch, adc):
    monkeypatch.setenv(gcs_client.INGESTION_SA_ENV, "sa@p.iam.gserviceaccount.com")
    seen = {}

    def fake_impersonated(**kwargs):
        seen.update(kwargs)
        return "impersonated"

    monkeypatch.setattr(gcs_client.impersonated_credentials, "Credentials", fake_impersonated)
    assert gcs_client.get_credentials() == "impersonated"
    assert seen["source_credentials"] is adc
    assert seen["target_principal"] == "sa@p.iam.gserviceaccount.com"
