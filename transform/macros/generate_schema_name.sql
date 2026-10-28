{#
  Without this override dbt names a dataset "<target.schema>_<custom schema>"
  (e.g. "stg_cegid_intermediate"), which Terraform never provisions and no
  service account has a grant on. Here a model's +schema is the WHOLE dataset
  name, matching infra/bigquery.tf.

  Environments: in dev the datasets are the bare names (stg_cegid,
  intermediate, marts), as provisioned. In any other env they are prefixed
  ("prod_marts") so several environments can share one project, as described
  in CLAUDE.md. The env comes from the `env` VAR, not from target.name.
  Keep both sides in sync with infra/bigquery.tf.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- elif var('env', 'dev') == 'dev' -%}
        {{ custom_schema_name | trim }}
    {%- else -%}
        {{ var('env') }}_{{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
