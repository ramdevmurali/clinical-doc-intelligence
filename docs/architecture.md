# Architecture

Clinical Document Intelligence is a document workflow and clinical extraction system. It is intentionally not a diagnosis chatbot, treatment recommender, full EHR clone, or complete FHIR server.

## High-Level Flow

```text
Synthetic document
  -> FastAPI backend
  -> Postgres document/job state
  -> Kafka/Redpanda workflow topics
  -> parser worker
  -> extraction worker
  -> validation worker
  -> review queue
  -> FHIR mapper
  -> evaluation and diagnostics
```

## Core Boundaries

- Backend owns API state, document lifecycle, review actions, exports, and diagnostics.
- Processor workers own parsing, extraction, validation, and FHIR mapping.
- Domain modules hold pure logic that can be unit-tested without Kafka, Postgres, or LLM calls.
- Frontend displays documents, extracted items, review actions, diagnostics, FHIR previews, and evaluation results.
- Infrastructure supports local development with Postgres and Redpanda/Kafka.

## Workflow Topics

Planned topics:

- `documents.submitted`
- `documents.parsed`
- `extractions.requested`
- `extractions.raw`
- `extractions.validated`
- `reviews.required`
- `reviews.completed`
- `fhir.exported`
- `documents.deadletter`
- `extractions.deadletter`
- `validation.deadletter`
- `fhir.deadletter`
