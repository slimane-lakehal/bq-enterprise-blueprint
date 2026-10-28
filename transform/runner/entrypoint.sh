#!/bin/sh
# Entry point of the dbt runner image: `<dbt command> [options]`, e.g.
#   build --selector marts
#   build --selector quality
#   build --full-refresh --exclude config.full_refresh:false
# The prod target and env var are appended here once, so the Cloud Run Jobs
# (infra/runner.tf) only say WHAT to build.
exec dbt "$@" --target prod --vars '{env: prod}'
