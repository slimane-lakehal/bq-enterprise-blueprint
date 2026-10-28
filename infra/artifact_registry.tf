resource "google_artifact_registry_repository" "lumio" {
  project       = var.project
  location      = var.region
  repository_id = "lumio"
  format        = "DOCKER"
  description   = "Container images for the Lumio data platform (dbt-runner)"

  depends_on = [google_project_service.required]
}
