# Clinical Document Intelligence

Clinical Document Intelligence is a source-grounded clinical extraction and
evaluation project. The current implementation focuses on pure domain logic for
parsing synthetic clinical notes, validating source evidence, applying
deterministic clinical guardrails, running a conservative baseline extractor,
and evaluating predictions against manually controlled golden fixtures.

## Disclaimer

This project uses synthetic/demo data only. It does not provide medical advice,
diagnosis, or treatment recommendations. It is not a medical device and must not
be used with real patient data.

## Current Implementation Status

Implemented:

- Repository skeleton and documentation structure.
- Pure domain section parser with exact section offsets.
- Source quote/span validation utilities.
- Clinical extraction schema primitives.
- Deterministic normalization helpers.
- Validation status and review primitives.
- Deterministic clinical rule guardrails.
- Golden-set evaluation domain logic.
- Saved prediction JSON parsing.
- Golden-set evaluator CLI: `scripts/eval_golden.py`.
- Deterministic baseline extractor: `processor/src/domain/baseline_extractor.py`.
- Baseline extractor runner: `scripts/run_baseline_extractor.py`.
- Baseline error reporter: `scripts/report_baseline_errors.py`.
- Golden fixture set with 10 synthetic notes.
- Baseline prediction files in `predictions_baseline/`.

Not implemented yet:

- AI/LLM extraction harness.
- Backend API.
- Frontend UI.
- Kafka/Redpanda workers.
- Database persistence.
- FHIR export.
- Human review UI/workflow.

## Current Domain Modules

- `processor/src/domain/sectioning.py`: parses raw note text into ordered sections with exact source spans.
- `processor/src/domain/source_spans.py`: validates exact source quote grounding against raw text.
- `processor/src/domain/extraction_schema.py`: defines immutable extracted clinical item shape.
- `processor/src/domain/normalization.py`: normalizes clinical names, item types, and statuses.
- `processor/src/domain/validation.py`: defines validation statuses, severities, findings, and decisions.
- `processor/src/domain/clinical_rules.py`: applies deterministic clinical safety guardrails.
- `processor/src/domain/evaluation.py`: evaluates predicted items against golden expected labels.
- `processor/src/domain/baseline_extractor.py`: produces conservative deterministic baseline predictions.

## Golden Set and Predictions

Golden fixtures:

```text
golden_set/notes/{document_id}.txt
golden_set/expected/{document_id}.expected.json
```

Saved baseline predictions:

```text
predictions_baseline/{document_id}.predicted.json
```

Prediction JSON format is defined in `docs/prediction_format.md`.

## Evaluation and Baseline Commands

Run the deterministic baseline extractor:

```bash
python3 scripts/run_baseline_extractor.py --overwrite
```

Evaluate saved predictions:

```bash
python3 scripts/eval_golden.py --predictions-dir predictions_baseline
```

Summarize baseline errors:

```bash
python3 scripts/report_baseline_errors.py
```

Current deterministic baseline metrics:

```text
expected_item_count: 149
predicted_item_count: 117
matched_item_count: 110
missing_item_count: 39
extra_item_count: 7
invalid_trap_hit_count: 0
source_quote_failure_count: 0
```

## Key Documentation

- `docs/domain_contracts.md`: stable domain contracts and invariants.
- `docs/clinical_rules.md`: deterministic clinical rule behavior.
- `docs/evaluation.md`: evaluation domain and CLI behavior.
- `docs/prediction_format.md`: saved prediction JSON contract.
- `docs/ai_extraction_harness.md`: next milestone technical spec for AI/LLM extraction.
- `docs/architecture.md`: broader target architecture.

## How to Run Tests

Focused domain and script suite:

```bash
python3 -m unittest processor.tests.test_report_baseline_errors_script processor.tests.test_run_baseline_extractor_script processor.tests.test_eval_golden_script processor.tests.test_evaluation processor.tests.test_baseline_extractor processor.tests.test_clinical_rules processor.tests.test_normalization processor.tests.test_extraction_schema processor.tests.test_validation processor.tests.test_source_spans processor.tests.test_sectioning -v
```

## Recommended Next Step

Stop expanding the deterministic baseline unless a specific regression demands
it. The next milestone is the AI/LLM extraction harness described in
`docs/ai_extraction_harness.md`.

The first AI harness implementation should use a fixture provider, strict JSON
parsing, exact local source grounding, clinical rule integration, and
`predictions_llm/*.predicted.json` outputs compatible with `scripts/eval_golden.py`.
