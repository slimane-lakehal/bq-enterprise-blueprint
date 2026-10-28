# ── Service Accounts ─────────────────────────────────────────────────────────

resource "google_service_account" "ingestion" {
  account_id   = "lumio-ingestion"
  display_name = "Lumio Ingestion — batch Python jobs (Cegid, SAP, Salesforce → GCS)"
}

resource "google_service_account" "dbt" {
  account_id   = "lumio-dbt"
  display_name = "Lumio dbt — transformation jobs (raw → staging → marts)"
}

# ── Ingestion SA: least-privilege bindings ───────────────────────────────────

resource "google_storage_bucket_iam_member" "ingestion_gcs" {
  bucket = google_storage_bucket.raw_data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_bigquery_dataset_iam_member" "ingestion_raw_cegid" {
  dataset_id = google_bigquery_dataset.raw_cegid.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_bigquery_dataset_iam_member" "ingestion_raw_sap" {
  dataset_id = google_bigquery_dataset.raw_sap.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_bigquery_dataset_iam_member" "ingestion_raw_salesforce" {
  dataset_id = google_bigquery_dataset.raw_salesforce.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.ingestion.email}"
}

resource "google_project_iam_member" "ingestion_job_user" {
  project = var.project
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.ingestion.email}"
}

# ── dbt SA: least-privilege bindings ─────────────────────────────────────────

resource "google_bigquery_dataset_iam_member" "dbt_read_cegid" {
  dataset_id = google_bigquery_dataset.raw_cegid.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "dbt_read_sap" {
  dataset_id = google_bigquery_dataset.raw_sap.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "dbt_read_salesforce" {
  dataset_id = google_bigquery_dataset.raw_salesforce.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "dbt_write_stg_cegid" {
  dataset_id = google_bigquery_dataset.stg_cegid.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "dbt_write_stg_sap" {
  dataset_id = google_bigquery_dataset.stg_sap.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "dbt_write_stg_salesforce" {
  dataset_id = google_bigquery_dataset.stg_salesforce.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_project_iam_member" "dbt_job_user" {
  project = var.project
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dbt.email}"
}

# ── Workload Identity Federation — keyless GitHub Actions auth ────────────────
#
# How it works:
#   GitHub mints a short-lived OIDC token per workflow run.
#   GCP validates it against this pool/provider and issues temporary credentials
#   for lumio-ingestion. No long-lived key is ever created or stored.

data "google_project" "this" {}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  display_name                       = "GitHub OIDC"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
  }

  # Restrict to this repo — any other repo's token is rejected
  attribute_condition = "attribute.repository == 'slimane-lakehal/bq-entreprise-blueprint'"
}

resource "google_service_account_iam_member" "wif_ingestion" {
  service_account_id = google_service_account.ingestion.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/slimane-lakehal/bq-entreprise-blueprint"
}

# ── dbt SA: downstream layers ────────────────────────────────────────────────

resource "google_bigquery_dataset_iam_member" "dbt_write_intermediate" {
  dataset_id = google_bigquery_dataset.intermediate.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_bigquery_dataset_iam_member" "dbt_write_marts" {
  dataset_id = google_bigquery_dataset.marts.dataset_id
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

# ── Scheduler SA ─────────────────────────────────────────────────────────────
# Dedicated identity for Cloud Scheduler -> Cloud Run Job. It may start a job
# (run.invoker, granted per job in runner.tf) and nothing else: no BigQuery.

resource "google_service_account" "scheduler" {
  account_id   = "lumio-scheduler"
  display_name = "Lumio Scheduler -- only triggers the dbt runner Jobs"
}
