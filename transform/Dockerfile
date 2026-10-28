# Runs dbt against prod as a Cloud Run Job (infra/runner.tf). Build with this
# directory as the context:  docker build -t dbt-runner transform
FROM python:3.12-slim

# Same dbt minor as local development (root pyproject.toml).
RUN pip install --no-cache-dir "dbt-bigquery>=1.11,<1.12"

WORKDIR /app
COPY . .

# Packages are installed at build time: nothing is downloaded when a Job runs.
RUN dbt deps --profiles-dir profiles

# oauth = ambient credentials of the Job's service account, no key file.
RUN mkdir -p /root/.dbt && cp profiles/profiles.yml /root/.dbt/profiles.yml
ENV BQ_PROJECT=""

# Compile now: a file missing from the build context (macro, selector) fails
# this build instead of the first Job run. parse reads no warehouse.
RUN BQ_PROJECT=build dbt parse --target prod --vars '{env: prod}'

ENTRYPOINT ["/app/runner/entrypoint.sh"]
CMD ["build", "--selector", "marts"]
