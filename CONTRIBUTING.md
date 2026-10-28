# Contributing

This is a portfolio project, but it's built with the same rigor as a
production data platform. This doc covers environment setup and how to
run each piece locally. For engineering principles, naming conventions,
and dbt patterns, see [CLAUDE.md](./CLAUDE.md) — this file is the "how do
I run it," that one is the "how do I write it."

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) for the Python workspace
- [Terraform](https://developer.hashicorp.com/terraform) 1.x, provider pinned to `google ~> 6.8.0`
- `gcloud` CLI, authenticated against a GCP project you have access to
- A GCP project with billing enabled if you're testing infra changes for real (dev-only sandbox recommended, not the portfolio's own project)

## Repository setup

```bash
git clone <repo-url>
cd bq-entreprise-blueprint
uv sync --package ingestion
```

`uv sync` creates `.venv/` and installs the `ingestion` workspace package
plus `dbt-bigquery` from the root `pyproject.toml`. There's a single `uv`
workspace — `ingestion/` is a member package, not a separate repo.

## GCP authentication for local runs

Ingestion scripts do not run with your own permissions. When
`GCP_SA_INGESTION` is set, `gcs_client.py` impersonates the `lumio-ingestion`
service account (`google.auth.impersonated_credentials`), so a laptop run has
exactly the job's permissions. In CI that variable is unset: Workload Identity
Federation already yields the ingestion service account, so the same code uses
the ambient credentials. One code path, two ways to obtain credentials.

To run anything locally you need:

1. Application Default Credentials on your machine:
   ```bash
   gcloud auth application-default login
   ```
2. Your GCP identity granted `roles/iam.serviceAccountTokenCreator` on the
   `lumio-ingestion` service account (ask whoever holds the project to grant
   this — it is not self-service by design, least-privilege applies to
   contributors too).
3. Environment variables — copy `.envrc.example` to `.envrc` (git-ignored),
   fill it in and load it with [direnv](https://direnv.net/) (`direnv allow`),
   or export the variables by hand.
4. Check which identity you are really using:
   ```bash
   uv run python scripts/check_auth.py
   ```

Without step 2, uploads will fail with a permissions error on impersonation,
not on the bucket itself — that's the first place to look if `upload_to_gcs`
fails.

## Running ingestion jobs

Each source is a separate console script, not a single unified CLI:

```bash
uv run ingest-cegid --data-dir <path-to-olist-csvs> --bucket lumio-raw-data-dev --date 2026-07-29
uv run ingest-sap --bucket lumio-raw-data-dev --date 2026-07-29
uv run ingest-salesforce --bucket lumio-raw-data-dev --date 2026-07-29
```

Notes:

- `--date` defaults to today if omitted. Re-running the same date overwrites
  the existing GCS blobs rather than appending — every ingestion job is
  idempotent by design. Output goes to `<source>/raw/dt=<date>/` (conforming
  rows) and `<source>/rejected/dt=<date>/` (rows that broke the Pydantic
  contract, with the reason). If more than 5% of rows are rejected the batch
  is not published to raw and the job fails.
- `ingest-cegid` requires the four Olist CSVs
  (`olist_orders_dataset.csv`, `olist_order_items_dataset.csv`,
  `olist_products_dataset.csv`, `olist_order_payments_dataset.csv`) in
  `--data-dir`. Download them from the
  [Olist Kaggle dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
  — they are not checked into the repo. Cegid is a one-time historical
  load, not a scheduled job (see `.github/workflows/ingestion.yml`).
- `ingest-sap` and `ingest-salesforce` are fully synthetic (Faker) and need
  no input data — they generate a fresh, deterministic snapshot per run date.
  `ingest-salesforce` also takes `--n-customers` (default 50,000) and
  `--seed` (default 42, for reproducibility).
- `--tmp-dir` controls where the local Parquet is staged before upload
  (defaults to `/tmp/lumio/<source>/`).

## Infrastructure changes (Terraform)

```bash
cd infra
terraform init
terraform plan
```

`variables.tf` declares `project` with no default — you must supply your
own dev project ID. Create `infra/terraform.tfvars` (git-ignored, never
commit it):

```hcl
project = "<your-dev-project-id>"
```

State is remote (`gs://lumio-terraform-state`), so `terraform init` needs
read/write access to that bucket. If you're working in your own sandbox
project rather than the shared one, point the backend at your own state
bucket instead of applying against someone else's state.

Run `terraform fmt` before committing — this is enforced by convention,
not currently by CI (see below).

## Transformation layer (dbt)

```bash
cd transform
export GCP_PROJECT=... GCP_SA_DBT=...        # see .envrc.example
uv run dbt deps --profiles-dir profiles
uv run dbt parse --profiles-dir profiles     # no warehouse access needed
uv run dbt build --profiles-dir profiles     # needs the infra applied
```

- Profiles have three targets (`dev`, `ci`, `prod`) that differ only in how
  they authenticate. Which datasets get written is decided by the `env` var,
  see `macros/generate_schema_name.sql`.
- Staging reads the BigLake tables in `raw_*`, which require a `dt` partition
  filter: models apply `dt >= var('raw_start_date')`.
- Scheduled runs are Cloud Run Jobs, not a laptop or a GitHub cron:
  first-time setup is in `docs/runbooks/bootstrap.md`.

## Tests

```bash
uv run --package ingestion --group dev pytest ingestion/tests
```

## Continuous Integration

| Workflow | Trigger | What it does |
|---|---|---|
| `ingestion.yml` | daily 03:00 UTC, manual | SAP + Salesforce ingestion via WIF |
| `ingestion_ci.yml` | PR touching `ingestion/` | unit tests |
| `dbt_ci.yml` | PR touching `transform/` | `dbt parse` (dev + prod env), selector coverage warning |
| `deploy.yml` | push to `main` touching `transform/` | build runner image, roll dbt Jobs, run a build |

Not implemented yet: `terraform.yml` (drift detection) and a build-based dbt
slim CI (`state:modified+ --defer`), which needs prod artifacts to defer to.
Do not assume they run against your PR.

## What a complete contribution looks like

A new data source is not "done" when the extractor runs. Per CLAUDE.md,
it's a full stack slice:

1. `ingestion/src/ingestion/<source>/extract.py` — the Python extractor
2. `infra/biglake.tf` — the BigLake external table over the landed GCS data
3. `transform/models/staging/<source>/` — the dbt staging model plus its
   `schema.yml` (tests + column docs)
4. `.github/workflows/ingestion.yml` — updated to schedule the new job

If a PR only has piece 1, it's a partial contribution — flag it as such
rather than merging it as a finished source.
