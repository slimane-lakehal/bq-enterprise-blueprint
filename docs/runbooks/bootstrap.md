# Bootstrap and first deploy

Order matters: the dbt Jobs need an image, the image needs the registry, the
registry needs Terraform. Each step is safe to re-run.

## 0. Read the plan before every apply

```bash
cd infra && terraform plan
```

- `marts` has `prevent_destroy`: it will hold append-only history tables that
  cannot be recomputed. A plan that wants to replace it is a mistake to find,
  not to approve.
- `intermediate`, staging and the BigLake tables are derived: rebuildable with
  `dbt build --full-refresh` or a re-apply.
- Never hand-edit a Terraform-managed resource in the console. If you did,
  `terraform plan -refresh-only` shows the drift without "fixing" it.

## 1. Foundation (no runner yet)

`runner_image` defaults to `null`, so the Jobs and schedules are not planned:

```bash
terraform apply
terraform output   # wif_provider, deploy_sa_email, runner_image_repo
```

Set these GitHub **repository variables**: `WIF_PROVIDER`, `DEPLOY_SA_EMAIL`,
`GCP_PROJECT`.

## 2. First image

Merge to `main` (or run the *Deploy dbt runner* workflow manually). It builds
and pushes the image, then notices that the Jobs do not exist and skips them.
Note the digest in the workflow log.

## 3. Create the Jobs

```bash
terraform apply -var 'runner_image=<runner_image_repo>@sha256:<digest>'
```

Schedules are created **paused** (`schedules_enabled = false`). From now on the
workflow rolls the Jobs onto each new digest; Terraform ignores image changes.

## 4. Prove it, then switch the schedules on

```bash
gcloud run jobs execute dbt-marts --region europe-west1 --wait
gcloud run jobs execute dbt-quality --region europe-west1 --wait
terraform apply -var 'runner_image=...' -var 'schedules_enabled=true'
```

## When something fails

- **Permission error right after adding a dataset**: a new dataset has zero
  grants. Add the `google_bigquery_dataset_iam_member` in `infra/iam.tf` for the
  dbt SA before suspecting dbt.
- **`dataset not found` with a doubled name** (`stg_cegid_intermediate`):
  `macros/generate_schema_name.sql` is not being picked up.
- **Incremental model not reflecting new logic**: a normal run does not rewrite
  old rows. `dbt build --select <model> --full-refresh`.
