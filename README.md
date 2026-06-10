# Clinical Document Intelligence

Clinical Document Intelligence is a production-style platform for extracting, validating, reviewing, and exporting structured healthcare data from synthetic clinical notes.

The project focuses on reliability concerns common in healthcare AI systems:

- Source-grounded extraction from messy clinical text
- Negation, uncertainty, and family-history handling
- Procedure/order/status disambiguation
- Human-in-the-loop review
- FHIR-style JSON exports
- Evaluation against golden clinical notes
- Diagnostics, dead-letter queues, replay paths, and structured observability

## Disclaimer

This project is for engineering demonstration only. It uses synthetic/demo data only. It does not provide medical advice, diagnosis, or treatment recommendations. It is not a medical device and must not be used with real patient data.

## Current Status

This repository currently contains the initial project skeleton only. It defines the intended boundaries for the backend, processor workers, frontend, infrastructure, scripts, documentation, and evaluation assets. Business logic, LLM calls, Kafka consumers, and UI implementation are intentionally not implemented yet.

## Architecture

This system is designed as a document workflow:

1. Upload or generate a synthetic clinical document.
2. Parse the document into sections.
3. Extract clinical entities with source quotes and spans.
4. Validate extractions using deterministic clinical rules.
5. Send uncertain or contradictory items to human review.
6. Export approved structured data as FHIR-style JSON.
7. Evaluate extraction quality against golden expected outputs.

See `docs/architecture.md` for the full architecture outline.

## Planned Services

- `backend`: FastAPI API for documents, jobs, reviews, exports, evaluation, and diagnostics.
- `processor`: parser, extraction, validation, and FHIR mapping workers.
- `frontend`: React clinical review console.
- `infra`: local Postgres and Redpanda/Kafka infrastructure.

## Phase 1 Target

The first implementation phase should prove the document lifecycle:

- FastAPI backend shell
- Postgres schema and migrations path
- Document upload endpoint
- Basic section parser worker
- Document status lifecycle
- Minimal React document list/viewer
- `/health` endpoint

Acceptance goal: upload a synthetic note, store parsed sections, and view them in the UI.
