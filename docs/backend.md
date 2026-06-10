# Backend

The backend is a thin FastAPI service. It should not directly call the LLM or own extraction logic.

## Responsibilities

- Serve API requests from the frontend.
- Persist document, section, extraction, review, export, and evaluation state.
- Publish workflow events.
- Provide health and diagnostics endpoints.
- Enforce API contracts around review and export actions.

## Initial Routes

- `GET /health`
- `GET /diagnostics/pipeline`
- `POST /documents/upload`
- `GET /documents`
- `GET /documents/{document_id}`
- `GET /documents/{document_id}/sections`
- `GET /documents/{document_id}/extractions`
- `GET /documents/{document_id}/review`
- `POST /reviews/{item_id}/approve`
- `POST /reviews/{item_id}/reject`
- `POST /reviews/{item_id}/edit`
- `GET /documents/{document_id}/fhir`
- `POST /eval/run`
- `GET /eval/runs/{run_id}`

