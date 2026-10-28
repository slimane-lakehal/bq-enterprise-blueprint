# APIs the platform depends on, kept under Terraform so a fresh project can be
# bootstrapped from this repo alone. A missing API shows up as a 403
# SERVICE_DISABLED halfway through an apply, which is a bad way to find out.

locals {
  required_apis = [
    "bigquery.googleapis.com",
    "bigquerystorage.googleapis.com", # Storage Write API (streaming path, phase 4)
    "storage.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com", # SA impersonation + Workload Identity Federation
    "sts.googleapis.com",            # token exchange for GitHub OIDC
    "cloudresourcemanager.googleapis.com",
    "run.googleapis.com",              # dbt runner Jobs
    "cloudscheduler.googleapis.com",   # triggers the Jobs
    "artifactregistry.googleapis.com", # runner image
    "secretmanager.googleapis.com",
  ]
}

resource "google_project_service" "required" {
  for_each = toset(local.required_apis)

  project = var.project
  service = each.value

  # Destroying a resource must not switch off an API other resources still use.
  disable_on_destroy = false
}
