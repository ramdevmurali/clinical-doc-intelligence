# Observability

Observability should be practical and local-friendly.

## Backend Endpoints

- `GET /health`
- `GET /diagnostics/pipeline`

## Runtime Signals

- Document counts by lifecycle status
- Job freshness
- DLQ counts
- Worker success/failure counts
- Schema validation failures
- Validation rule hit counts
- Review action counts
- Stage latency metrics

## Structured Log Fields

- `event_id`
- `document_id`
- `job_id`
- `stage`
- `topic`
- `consumer_group`
- `operation`
- `duration_ms`
- `error`
- `error_type`
- `attempt`
- `model`
- `schema_version`

