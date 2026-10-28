import os
from pathlib import Path

import google.auth
import structlog
from google.auth import impersonated_credentials
from google.auth.credentials import Credentials
from google.cloud import storage

logger = structlog.get_logger()

INGESTION_SA_ENV = "GCP_SA_INGESTION"


def get_credentials() -> Credentials:
    """
    Locally: impersonate the ingestion service account on top of the developer's
    ADC, so a laptop run has exactly the permissions of the real job.

    In CI (Workload Identity Federation) GCP_SA_INGESTION is unset: the ambient
    credentials ARE the ingestion service account already, and impersonating
    yourself would need a tokenCreator grant that least-privilege withholds.
    """
    source_credentials, _ = google.auth.default()
    target = os.environ.get(INGESTION_SA_ENV)
    if not target:
        return source_credentials
    return impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=target,
        target_scopes=["https://www.googleapis.com/auth/cloud-platform"],
        lifetime=3600,
    )


def upload_to_gcs(bucket_name: str, source_path: Path, destination_blob: str) -> None:
    """Idempotent upload — overwrites existing blob if present."""
    client = storage.Client(
        credentials=get_credentials(),
        project=os.environ.get("GCP_PROJECT"),
    )
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob)
    blob.upload_from_filename(source_path)
    logger.info(
        "gcs_upload_complete",
        bucket=bucket_name,
        blob=destination_blob,
        size_bytes=source_path.stat().st_size,
    )
