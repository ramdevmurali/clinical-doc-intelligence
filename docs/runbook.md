# Runbook

This runbook is a placeholder for operational procedures as the implementation grows.

## Local Development

1. Start infrastructure with `make up`.
2. Apply schema with `make migrate`.
3. Seed demo documents with `make seed`.
4. Run a pipeline probe with `make probe-clinical-path`.

## Recovery Paths

Planned replay commands:

- `make replay-documents-dlq`
- `make replay-extractions-dlq`
- `make replay-validation-dlq`
- `make replay-fhir-dlq`

## Safety

Use synthetic/demo data only. Do not ingest real patient records.

