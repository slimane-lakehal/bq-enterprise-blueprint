variable "project" {

}

variable "region" {
  default = "europe-west1"
}

# ── dbt runner (runner.tf) ───────────────────────────────────────────────────

variable "runner_image" {
  description = "dbt runner image. CI pushes it; Terraform ignores later image changes (see runner.tf)."
  type        = string
  default     = null
}

variable "schedules_enabled" {
  description = "false creates the Cloud Scheduler triggers paused. Flip once a manual run of each Job has succeeded."
  type        = bool
  default     = false
}

# Offsets keep runs from overlapping: they write the same tables.
variable "marts_cron" {
  description = "Marts build (UTC). After the 03:00 batch ingestion."
  type        = string
  default     = "30 4 * * *"
}

variable "quality_cron" {
  description = "Data-quality marts build (UTC)."
  type        = string
  default     = "0 6 * * *"
}

variable "refresh_cron" {
  description = "Full refresh, Sundays (UTC). Excludes models with full_refresh=false."
  type        = string
  default     = "0 2 * * 0"
}
