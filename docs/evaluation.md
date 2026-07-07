# Evaluation

The evaluation harness compares predicted clinical items against manually
controlled golden expected outputs. The current implementation is pure domain
logic in `processor/src/domain/evaluation.py`; it does not perform file I/O,
call LLMs, run clinical rules, or evaluate a dataset by itself.

Prediction file structure for future CLI use is defined in
`docs/prediction_format.md`.

## Dataset Layout

Golden fixtures are stored as:

```text
golden_set/
  notes/
    {document_id}.txt
  expected/
    {document_id}.expected.json
```

Future saved predictions should follow `docs/prediction_format.md`.

## Current Evaluator Responsibilities

`evaluate_predictions(raw_text, expected_json, predicted_items)` currently:

- parses expected items from golden expected JSON;
- parses invalid extraction traps from golden expected JSON;
- normalizes match keys for expected and predicted items;
- matches expected items against predicted items;
- computes missing expected indexes;
- computes extra predicted indexes;
- detects invalid extraction trap hits;
- validates predicted source quote spans;
- returns a deterministic `EvaluationResult`.

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

## Implemented Counts vs Future Metrics

Implemented now:

- expected item count
- predicted item count
- matched item count
- missing item count
- extra item count
- invalid trap hit count
- source quote failure count

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

These future metrics should be added only after saved prediction files and a
dataset-level runner exist.

## Current Non-Scope

The evaluator currently does not:

- load files from disk;
- provide a CLI runner;
- call LLMs or extraction models;
- run deterministic clinical rules automatically;
- validate FHIR resources;
- aggregate over all golden notes;
- repair malformed predictions;
- infer missing source offsets.

Clinical rule behavior is documented separately in `docs/clinical_rules.md`.

## Related Documents

- `docs/prediction_format.md`: saved prediction JSON contract.
- `docs/clinical_rules.md`: deterministic clinical validation guardrails.
- `docs/domain_contracts.md`: source grounding and domain invariants.
