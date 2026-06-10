# Processor

The processor package contains the clinical document workflow workers and pure domain logic.

## Workers

- Parser worker: converts uploaded text/PDF content into document sections.
- Extraction worker: calls an LLM provider through an abstraction and emits schema-bound raw extractions.
- Validation worker: applies deterministic clinical rules and creates validation findings.
- FHIR mapper worker: maps accepted or approved internal items into FHIR-style JSON.

## Domain Modules

Domain modules should stay pure where possible:

- `sectioning.py`
- `extraction_schema.py`
- `source_spans.py`
- `clinical_rules.py`
- `validation.py`
- `confidence.py`
- `normalization.py`
- `fhir_mapping.py`

Pure domain logic should be testable without Postgres, Kafka, or network calls.

