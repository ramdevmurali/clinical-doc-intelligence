# Evaluation

The evaluation harness compares predicted clinical items against manually
controlled golden expected outputs. It is the reliability spine of the project:
extractors may change, but their outputs must be source-grounded, schema-valid,
and measurable against the same golden set.

This project uses synthetic/demo data only. It does not provide medical advice,
diagnosis, or treatment recommendations. It is not a medical device.

## Dataset Layout

Golden fixtures are stored as:

```text
golden_set/
  notes/
    {document_id}.txt
  expected/
    {document_id}.expected.json
```

Saved predictions use:

```text
{predictions_dir}/{document_id}.predicted.json
```

Current prediction directories:

- `predictions/`: manual fixture predictions.
- `predictions_baseline/`: deterministic baseline predictions.
- `predictions_llm/`: planned AI/LLM harness predictions.

Prediction file structure is defined in `docs/prediction_format.md`.

## Domain Evaluator

Pure evaluation logic lives in `processor/src/domain/evaluation.py`.

`evaluate_predictions(raw_text, expected_json, predicted_items)`:

- parses expected items from golden expected JSON;
- parses invalid extraction traps from golden expected JSON;
- normalizes match keys for expected and predicted items;
- matches expected items against predicted items;
- computes missing expected indexes;
- computes extra predicted indexes;
- detects invalid extraction trap hits;
- validates predicted source quote spans;
- returns a deterministic `EvaluationResult`.

The domain evaluator does not:

- read files from disk;
- call LLMs or extraction models;
- run deterministic clinical rules automatically;
- validate FHIR resources;
- repair malformed predictions;
- infer missing source offsets.

File I/O and dataset traversal belong to scripts.

## Evaluation CLI

Saved prediction files are evaluated with:

```bash
python3 scripts/eval_golden.py --predictions-dir predictions_baseline
```

Single-document evaluation:

```bash
python3 scripts/eval_golden.py \
  --predictions-dir predictions_baseline \
  --document-id note_001
```

The CLI:

- loads notes from `golden_set/notes/` by default;
- loads expected labels from `golden_set/expected/` by default;
- loads prediction files from the requested `--predictions-dir`;
- parses predictions through `predicted_items_from_json`;
- calls `evaluate_predictions`;
- prints per-document counts and aggregate counts;
- exits non-zero for missing files, malformed JSON, or evaluation input errors.

The extractor runners must not read expected labels. Only evaluation scripts
should inspect `golden_set/expected/`.

## Baseline Error Report

The deterministic baseline has a focused report script:

```bash
python3 scripts/report_baseline_errors.py
```

It reuses `scripts/eval_golden.py` internals and reports:

- aggregate counts;
- missing expected items by type;
- extra predicted items by type;
- worst documents by total failures;
- source grounding failures;
- invalid trap hits.

An AI-specific report can follow the same pattern after `predictions_llm/`
exists.

## EvaluationResult Fields

The evaluator returns `EvaluationResult` with these count fields:

- `expected_item_count`: number of expected items parsed from golden labels.
- `predicted_item_count`: number of predicted items supplied.
- `matched_item_count`: number of one-to-one expected/predicted matches.
- `missing_item_count`: number of expected items not matched.
- `extra_item_count`: number of predicted items not matched.
- `invalid_trap_hit_count`: number of predicted items matching invalid traps.
- `source_quote_failure_count`: number of predicted items with bad source grounding.

It also returns inspectable detail fields:

- `matches`: tuple of `ItemMatch(expected_index, predicted_index)`.
- `missing_expected_indexes`: expected item indexes with no match.
- `extra_predicted_indexes`: predicted item indexes with no match.
- `invalid_trap_hits`: `EvaluationIssue` entries for invalid trap matches.
- `source_quote_failures`: `EvaluationIssue` entries for source grounding failures.

## Matching Rules

Matching is deterministic and conservative:

- Item type is normalized.
- Name is normalized.
- If an expected item has `status`, predicted status must match after normalization.
- If an expected item omits `status`, predicted status does not block the match.
- If an expected item has `source_quote`, predicted source quote must match exactly.
- If an expected item omits `source_quote`, predicted source quote does not block the match.
- One expected item can match at most one predicted item.
- One predicted item can match at most one expected item.
- Expected items are processed in order.
- For each expected item, the first compatible unmatched prediction is selected.

## Invalid Trap Behavior

Invalid extraction traps come from `invalid_extractions` in golden expected JSON.
They catch known forbidden predictions, such as representing a denied symptom as
an active condition.

Trap matching rules:

- Trap item type and predicted item type are normalized.
- Trap name and predicted item name are normalized.
- If `forbidden_status` is present, predicted status must match after normalization.
- If `forbidden_status` is absent, type and name are enough to count as a hit.
- Hits are emitted in deterministic order: trap order first, predicted item order second.

## Source Grounding Behavior

Predicted items must be exactly source-grounded:

```python
raw_text[source_start_char:source_end_char] == source_quote
```

Rules:

- Source quote validation is exact and case-sensitive.
- Offsets refer to raw note text, not normalized text.
- Wrong offsets fail even if the quote appears elsewhere in the document.
- Failures are returned as `EvaluationIssue(issue_type="source_quote_failure")`.

## Current Baseline Metrics

After the deterministic medication baseline improvement:

```text
notes_evaluated: 10
expected_item_count: 149
predicted_item_count: 117
matched_item_count: 110
missing_item_count: 39
extra_item_count: 7
invalid_trap_hit_count: 0
source_quote_failure_count: 0
```

## Implemented Counts vs Future Metrics

Implemented now:

- expected item count
- predicted item count
- matched item count
- missing item count
- extra item count
- invalid trap hit count
- source quote failure count
- missing by type through `scripts/report_baseline_errors.py`
- extra by type through `scripts/report_baseline_errors.py`

Planned future metrics:

- precision and recall
- entity-level F1
- field accuracy
- negation accuracy
- status accuracy
- hallucination rate
- source quote coverage
- valid source span rate
- schema valid rate
- review-routing rate
- latency and failure-rate metrics

Future metrics should be added through script/report layers first, not by
making the pure domain evaluator responsible for file I/O or provider behavior.

## Current Non-Scope

The current evaluator and CLI do not:

- generate predictions;
- call LLMs or extraction models;
- run clinical rules automatically before evaluation;
- validate FHIR resources;
- repair malformed predictions;
- infer missing source offsets;
- compare two prediction directories directly.

The AI extraction harness is specified separately in
`docs/ai_extraction_harness.md`.

## Related Documents

- `docs/prediction_format.md`: saved prediction JSON contract.
- `docs/clinical_rules.md`: deterministic clinical validation guardrails.
- `docs/domain_contracts.md`: source grounding and domain invariants.
- `docs/ai_extraction_harness.md`: planned AI/LLM extraction harness.
