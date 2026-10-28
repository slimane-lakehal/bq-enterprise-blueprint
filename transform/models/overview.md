{% docs __overview__ %}

# Groupe Lumio -- dbt models

| Layer | Role | BigQuery dataset |
|---|---|---|
| `staging` | Rename, cast, deduplicate. No business logic. | `stg_<source>` |
| `intermediate` | Joins and business logic. No aggregation. | `intermediate` |
| `marts` | Final aggregates, BI-ready. | `marts` |
| `marts/data_quality` | Freshness and coverage metrics, not read by BI. | `marts` |

Dataset names come from `macros/generate_schema_name.sql`; outside `dev` they
are prefixed with the `env` var (`prod_marts`).

{% enddocs %}
