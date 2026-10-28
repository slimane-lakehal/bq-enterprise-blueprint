# BigLake external tables over the Parquet landed in GCS by the ingestion jobs.
#
# Layout written by ingestion/shared/publish.py (hive-style so BigQuery can
# prune on `dt`):
#   gs://<bucket>/<source>/raw/dt=YYYY-MM-DD/<entity>.parquet
#   gs://<bucket>/<source>/rejected/dt=YYYY-MM-DD/<entity>.parquet
#
# BigLake (connection-based), not a plain external table: readers need access
# to the dataset only. The connection's service account reads the bucket, so
# dbt's SA never gets storage permissions -- least privilege holds end to end.
#
# One entity per source folder for now (the URI is `<source>/raw/*`). A second
# entity in the same source needs a per-entity prefix in publish.py first.

locals {
  biglake_sources = {
    cegid      = { dataset = google_bigquery_dataset.raw_cegid.dataset_id, entity = "transactions" }
    sap        = { dataset = google_bigquery_dataset.raw_sap.dataset_id, entity = "inventory" }
    salesforce = { dataset = google_bigquery_dataset.raw_salesforce.dataset_id, entity = "customers" }
  }

  # table key -> {dataset, table_id, folder}
  biglake_tables = merge(
    {
      for source, cfg in local.biglake_sources : "${source}_raw" => {
        source   = source
        dataset  = cfg.dataset
        table_id = cfg.entity
        folder   = "raw"
      }
    },
    {
      for source, cfg in local.biglake_sources : "${source}_rejected" => {
        source   = source
        dataset  = cfg.dataset
        table_id = "rejected"
        folder   = "rejected"
      }
    },
  )
}

resource "google_bigquery_connection" "biglake" {
  connection_id = "lumio-biglake"
  location      = var.region
  friendly_name = "BigLake over the raw landing bucket"

  cloud_resource {}

  depends_on = [google_project_service.required]
}

resource "google_storage_bucket_iam_member" "biglake_reads_raw" {
  bucket = google_storage_bucket.raw_data.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_bigquery_connection.biglake.cloud_resource[0].service_account_id}"
}

resource "google_bigquery_table" "biglake" {
  for_each = local.biglake_tables

  dataset_id = each.value.dataset
  table_id   = each.value.table_id

  # Derived from GCS: losing the table definition loses no data.
  deletion_protection = false

  external_data_configuration {
    source_format = "PARQUET"
    connection_id = google_bigquery_connection.biglake.name
    # Types come from the Parquet files. The contract is enforced upstream
    # (Pydantic, ingestion/shared/validation.py); dbt staging still casts
    # defensively.
    autodetect  = true
    source_uris = ["gs://${google_storage_bucket.raw_data.name}/${each.value.source}/${each.value.folder}/*"]

    hive_partitioning_options {
      mode                     = "AUTO"
      source_uri_prefix        = "gs://${google_storage_bucket.raw_data.name}/${each.value.source}/${each.value.folder}/"
      require_partition_filter = true # every query must filter on dt: cost guard
    }
  }

  depends_on = [google_storage_bucket_iam_member.biglake_reads_raw]
}
