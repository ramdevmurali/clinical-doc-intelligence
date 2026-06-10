# Frontend

The frontend is a clinical review console, not a charts-first dashboard.

## Pages

- `/documents`: uploaded/generated document list.
- `/documents/:id`: document viewer with sections and extracted fields.
- `/review`: review queue for uncertain, contradictory, or low-confidence items.
- `/evals`: evaluation runs and metrics.
- `/diagnostics`: pipeline health, DLQ counts, and recent failures.
- `/fhir/:document_id`: FHIR-style export viewer.

## Core Components

- `DocumentList`
- `DocumentViewer`
- `SectionNavigator`
- `ExtractionPanel`
- `SourceQuoteHighlighter`
- `ValidationFindings`
- `ReviewActionBar`
- `FHIRPreview`
- `EvalMetricsTable`
- `DiagnosticsPanel`
- `FailedJobsRail`

The key UI behavior is source quote highlighting when a user selects an extracted item.

