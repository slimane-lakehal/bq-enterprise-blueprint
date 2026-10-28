# Scheduled dbt runs: Cloud Run Jobs from one image (transform/Dockerfile).
# Each Job says WHAT to build through its args; transform/runner/entrypoint.sh
# appends the prod target and vars once.
#
#   dbt-marts     marts and everything that feeds them   (selector: marts)
#   dbt-quality   the data_quality marts                 (selector: quality)
#   dbt-refresh   everything from scratch, except append-only history tables
#
# Why Jobs and not a GitHub Actions cron: the run uses the dbt SA's ambient
# identity (no key, no WIF round trip), is retried/timed out by Cloud Run, and
# its logs sit next to the rest of the platform's.

locals {
  jobs = var.runner_image == null ? {} : {
    marts = {
      args        = ["build", "--selector", "marts"]
      timeout     = "1800s"
      max_retries = 1
      cron        = var.marts_cron
    }
    quality = {
      args        = ["build", "--selector", "quality"]
      timeout     = "1800s"
      max_retries = 1
      cron        = var.quality_cron
    }
    refresh = {
      args        = ["build", "--full-refresh", "--exclude", "config.full_refresh:false"]
      timeout     = "7200s"
      max_retries = 0 # a failed refresh is looked at, not retried blindly
      cron        = var.refresh_cron
    }
  }
}

resource "google_cloud_run_v2_job" "dbt" {
  for_each = local.jobs

  name     = "dbt-${each.key}"
  location = var.region

  template {
    template {
      service_account = google_service_account.dbt.email
      timeout         = each.value.timeout
      max_retries     = each.value.max_retries

      containers {
        image = var.runner_image
        args  = each.value.args

        env {
          name  = "BQ_PROJECT"
          value = var.project
        }

        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
      }
    }
  }

  lifecycle {
    # CI rolls the Jobs onto each new image digest: Terraform must not roll
    # them back to whatever var.runner_image was at plan time.
    ignore_changes = [template[0].template[0].containers[0].image]
  }

  depends_on = [google_project_service.required]
}

resource "google_cloud_run_v2_job_iam_member" "scheduler_can_run" {
  for_each = local.jobs

  name     = google_cloud_run_v2_job.dbt[each.key].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "dbt" {
  for_each = local.jobs

  name      = "dbt-${each.key}-trigger"
  region    = var.region
  schedule  = each.value.cron
  time_zone = "UTC"
  paused    = !var.schedules_enabled

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project}/locations/${var.region}/jobs/${google_cloud_run_v2_job.dbt[each.key].name}:run"

    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }

  depends_on = [google_cloud_run_v2_job_iam_member.scheduler_can_run]
}
