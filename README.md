# Clinical Document Intelligence

Clinical Document Intelligence is a source-grounded clinical extraction and
evaluation project. The current implementation focuses on pure domain logic for
parsing notes, validating source evidence, applying deterministic clinical
guardrails, and evaluating extracted clinical items against golden fixtures.

## Disclaimer

This project uses synthetic/demo data only. It does not provide medical advice,
diagnosis, or treatment recommendations. It is not a medical device and must not
be used with real patient data.

## Current Implementation Status

Implemented:

- Repository skeleton and documentation structure.
- Pure domain section parser.
- Source quote/span validation.
- Clinical extraction schema primitives.
- Deterministic normalization helpers.
- Validation status and review primitives.
- Deterministic clinical rule guardrails.
- Evaluation domain harness.
- Golden fixture tests for `note_001`.

Not implemented yet:

- Backend API.
- Frontend UI.
- LLM extraction.
- Kafka/Redpanda workers.
- Database persistence.
- FHIR export.
- CLI golden evaluator.

## Current Domain Modules

- `processor/src/domain/sectioning.py`: parses raw note text into ordered sections with exact source spans.
- `processor/src/domain/source_spans.py`: validates exact source quote grounding against raw text.
- `processor/src/domain/extraction_schema.py`: defines immutable extracted clinical item shape.
- `processor/src/domain/normalization.py`: normalizes clinical names, item types, and statuses.
- `processor/src/domain/validation.py`: defines validation statuses, severities, findings, and decisions.
- `processor/src/domain/clinical_rules.py`: applies deterministic clinical safety guardrails.
- `processor/src/domain/evaluation.py`: evaluates predicted items against golden expected labels.

## Evaluation Status

The domain evaluator is implemented through `evaluate_predictions(...)`.
It currently:

- parses golden expected items;
- parses invalid extraction traps;
- matches expected and predicted items deterministically;
- reports missing expected items;
- reports extra predicted items;
- detects invalid trap hits;
- validates predicted source quote spans;
- returns an inspectable `EvaluationResult`.

Prediction JSON format is defined in `docs/prediction_format.md`. A CLI runner
for evaluating saved prediction files is intentionally not implemented yet.

## Key Documentation

- `docs/domain_contracts.md`: stable domain contracts and invariants.
- `docs/clinical_rules.md`: deterministic clinical rule behavior.
- `docs/evaluation.md`: current evaluation harness behavior.
- `docs/prediction_format.md`: saved prediction JSON contract for future CLI use.
- `docs/architecture.md`: broader target architecture.

## How to Run Tests

```bash
python3 -m unittest processor.tests.test_evaluation processor.tests.test_clinical_rules processor.tests.test_normalization processor.tests.test_extraction_schema processor.tests.test_validation processor.tests.test_source_spans processor.tests.test_sectioning -v
```

## Recommended Next Steps

1. Implement prediction JSON parsing for `docs/prediction_format.md`.
2. Add a lightweight `scripts/eval_golden.py` CLI after the prediction parser is stable.
3. Build manual baseline prediction files for a small subset of golden notes.
4. Expand golden notes with harder clinical ambiguity and noisier source text.
5. Only then integrate extractor or LLM-generated predictions.
