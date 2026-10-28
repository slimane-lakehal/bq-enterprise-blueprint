"""
Prints which identity the ingestion code will actually use.

    uv run python scripts/check_auth.py

Run it after `gcloud auth application-default login` and exporting the
variables from `.envrc.example`. If you see the ingestion service account's
email, impersonation works; a permission error here (not on the bucket) means
your user lacks roles/iam.serviceAccountTokenCreator on that account.
"""

import google.auth.transport.requests

from ingestion.shared.gcs_client import get_credentials


def main() -> None:
    credentials = get_credentials()
    credentials.refresh(google.auth.transport.requests.Request())
    print(getattr(credentials, "service_account_email", "ambient credentials (no impersonation)"))


if __name__ == "__main__":
    main()
