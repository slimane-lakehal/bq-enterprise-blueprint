# BQ Enterprise Blueprint

> Migrating a fictional French omnichannel retail group from a legacy SQL Server DWH to a modern Google BigQuery data platform — built in public as a portfolio and freelance reference implementation.

---

## Business Context

**Groupe Lumio** operates three retail brands across 60 stores in France plus an e-commerce site, generating roughly €180M in annual revenue. Their data infrastructure hadn't moved in a decade: an on-premises SQL Server data warehouse, SSRS reports that took hours to refresh, and analysts spending their mornings in Excel.

The migration goal is a unified, cloud-native data platform that gives the business:

- A **single source of truth** across POS, ERP, CRM, and web analytics
- **Self-serve analytics** for brand and supply chain teams via Looker Studio
- A **real-time stock visibility** layer across all stores and the warehouse
- An **ML-ready foundation** for demand forecasting and customer segmentation

EU data residency is a hard constraint throughout — all data stays in `europe-west1`.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        SOURCE SYSTEMS                               │
│                                                                     │
│  Cegid POS      SAP ERP       Salesforce CRM    Shopify    GA4     │
│  (transactions) (inventory)   (customers)       (orders)  (events) │
└────────┬───────────┬──────────────┬──────────────┬──────────┬──────┘
         │           │              │              │          │
    batch daily  batch daily   batch daily     BQ public  BQ public
         │           │              │            dataset    dataset
         ▼           ▼              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    RAW LANDING (GCS)                                │
│         gs://lumio-raw-data-dev/{source}/raw/{date}/               │
│                     Parquet, partitioned by date                    │
└─────────────────────────┬───────────────────────────────────────────┘
                          │  dbt
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    BIGQUERY LAYERS                                   │
│                                                                     │
│  raw_*          Typed external tables on top of GCS Parquet         │
│  stg_*          Cleaned, renamed, deduplicated (dbt views)          │
│  intermediate   Joined, business-logic applied (dbt tables)         │
│  mart_*         Aggregated, BI-ready (dbt incremental tables)       │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
         ┌────────────────┼─────────────────┐
         ▼                ▼                 ▼
   Looker Studio     BigQuery ML       Real-time path
   (self-serve BI)  (forecasting,    ┌──────────────┐
                     segmentation)   │  Pub/Sub      │
                                     │  Dataflow     │
                                     │  Bigtable     │
                                     │  (stock feed) │
                                     └──────────────┘
```

---

## Repo Structure

```
bq-enterprise-blueprint/
│
├── infra/                     Terraform — all GCP resources as code
│   ├── main.tf                Provider + remote state backend (GCS)
│   ├── apis.tf                Required GCP APIs
│   ├── bigquery.tf            Datasets (raw, staging, intermediate, marts)
│   ├── biglake.tf             BigLake connection + external tables over GCS
│   ├── gcs.tf                 Raw landing bucket
│   ├── iam.tf / ci.tf         Service accounts, IAM bindings, WIF, deploy SA
│   ├── runner.tf              dbt Cloud Run Jobs + Cloud Scheduler triggers
│   ├── artifact_registry.tf   Runner image repository
│   ├── variables.tf
│   └── output.tf
│
├── ingestion/                 Python batch ingestion (uv workspace package)
│   └── src/ingestion/
│       ├── cegid/             Olist dataset → Cegid POS simulation
│       ├── sap/               Faker → SAP ERP inventory snapshots
│       ├── salesforce/        Faker → Salesforce CRM customers
│       └── shared/            GCS client, Pydantic data contracts
│
├── transform/                 dbt Core project (Phase 2, in progress)
│   └── models/
│       ├── staging/           stg_cegid__, stg_sap__ (stg_salesforce__ next)
│       ├── intermediate/      int_unified_customer, int_stock_positions
│       └── marts/             finance, supply, crm, marketing
│
├── streaming/                 Dataflow jobs — Shopify webhooks, WMS feed (Phase 4)
│
├── .github/workflows/
│   ├── ingestion.yml          Daily batch ingestion (03:00 UTC)
│   ├── ingestion_ci.yml       Ingestion unit tests on PR
│   ├── dbt_ci.yml             dbt parse + selector coverage on PR
│   └── deploy.yml             Build runner image, roll dbt Jobs, run a build
│
└── docs/                      Architecture deep-dives, runbooks
```

---

## Key Technical Decisions

**Infrastructure as Code from day one**
Every GCP resource — datasets, buckets, service accounts, IAM bindings — is declared in Terraform and applied via CI. No click-ops, no undocumented permissions.

**Keyless CI authentication (Workload Identity Federation)**
GitHub Actions authenticates to GCP via OIDC, not a stored JSON key. Short-lived credentials are minted per workflow run. Nothing to rotate, nothing to leak.

**Least-privilege service accounts**
Two dedicated SAs with minimal scope: `lumio-ingestion` (write to GCS + raw datasets) and `lumio-dbt` (read raw, write staging/marts). They cannot touch each other's resources.

**Idempotent pipelines**
Every ingestion script is safe to re-run for the same date — it overwrites the Parquet blob in GCS rather than appending. Every dbt incremental model uses `unique_key`. Running a job twice produces the same result.

**Strict dbt layering**
Staging renames and casts only. Intermediate handles joins and business logic. Marts aggregate. `SELECT *` is banned — every model projects explicit columns. This keeps the DAG understandable as it grows.

**Cost-conscious BigQuery usage**
Every large table is partitioned by date and clustered by its dominant filter key. Queries on partitioned tables must filter on the partition column. Staging models are views; intermediate and mart models are tables or incrementals.

**Simulated sources, real patterns**
The source systems are simulated (Olist dataset for POS, Faker for ERP/CRM, BigQuery public datasets for Shopify/GA4), but the ingestion patterns, data contracts, GCS layout, and dbt models are production-grade. The point is the architecture, not the data.

---

## Status & Roadmap

| Phase | Description | Status |
|---|---|---|
| **0 — Foundation** | Terraform, GCP IAM, GCS, BigQuery datasets, WIF | ✅ Done |
| **1 — Batch Ingestion** | Cegid (Olist), SAP (Faker), Salesforce (Faker) → GCS | ✅ Done  |
| **2 — dbt Core** | Staging, intermediate, tests, source freshness, docs | ⬜ Next |
| **3 — Marts & BI** | 4 business marts, Looker Studio dashboards | ⬜ |
| **4 — Streaming** | Shopify webhooks, WMS Pub/Sub → Bigtable | ⬜ |
| **5 — Advanced** | Iceberg tables, column-level security, BigQuery ML | ⬜ |
| **6 — Docs & Polish** | Runbooks, architecture guides, LinkedIn series wrap-up | ⬜ |

---

## Built By

**Slimane Lakehal** — Analytics Engineer & Data Platform Freelance, based in Occitanie, France.

Core stack: Python · SQL · dbt · BigQuery · FastAPI · GCP  
Instructor at Le Wagon Toulouse (SQL, Python, BigQuery, Power BI)

[LinkedIn](https://www.linkedin.com/in/lakehal-slimane) · [Malt](https://www.malt.fr/profile/slimanelakehal1)
