output "raw_bucket_url" {
  value = google_storage_bucket.raw_data.url
}

output "wif_provider" {
  description = "Workload Identity Provider resource name — set as WIF_PROVIDER GitHub variable"
  value       = google_iam_workload_identity_pool_provider.github.name
}

output "ingestion_sa_email" {
  description = "Ingestion service account email — set as INGESTION_SA_EMAIL GitHub variable"
  value       = google_service_account.ingestion.email
}

output "dbt_sa_email" {
  description = "dbt service account email"
  value       = google_service_account.dbt.email
}

output "deploy_sa_email" {
  description = "Deploy service account email -- set as DEPLOY_SA_EMAIL GitHub variable"
  value       = google_service_account.deploy.email
}

output "runner_image_repo" {
  description = "Artifact Registry path for the dbt runner image"
  value       = "${var.region}-docker.pkg.dev/${var.project}/${google_artifact_registry_repository.lumio.repository_id}/dbt-runner"
}
