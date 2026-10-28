# The identity GitHub Actions deploys with (.github/workflows/deploy.yml):
# push the dbt runner image, roll the Cloud Run Jobs onto it, and start a run.
# Federated through the pool in iam.tf and bound to this repository only.
#
# Deliberately narrow, nothing project-wide: write on the one registry,
# developer rights on the dbt Jobs only. It cannot read or write BigQuery --
# the Jobs do that, as the dbt SA.

resource "google_service_account" "deploy" {
  account_id   = "lumio-deploy"
  display_name = "Lumio Deploy -- GitHub Actions: push runner image, roll and run the dbt Jobs"
}

resource "google_service_account_iam_member" "wif_deploy" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/slimane-lakehal/bq-entreprise-blueprint"
}

resource "google_artifact_registry_repository_iam_member" "deploy_writer" {
  project    = var.project
  location   = var.region
  repository = google_artifact_registry_repository.lumio.repository_id
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.deploy.email}"
}

# Updating a Job to a new image, and running it. Empty until var.runner_image is
# set (the Jobs do not exist before that, see runner.tf).
resource "google_cloud_run_v2_job_iam_member" "deploy_developer" {
  for_each = local.jobs

  name     = google_cloud_run_v2_job.dbt[each.key].name
  location = var.region
  role     = "roles/run.developer"
  member   = "serviceAccount:${google_service_account.deploy.email}"
}

# Changing a Job that runs as the dbt SA requires actAs on that SA.
resource "google_service_account_iam_member" "deploy_acts_as_dbt" {
  service_account_id = google_service_account.dbt.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}
