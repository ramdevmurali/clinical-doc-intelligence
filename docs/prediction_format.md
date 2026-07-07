# Prediction Format

This document defines the saved prediction JSON contract used for local evaluation.
Prediction files are extractor outputs that can be evaluated against
`golden_set/expected/*.expected.json` using the domain evaluator.

This format is for local development and evaluation with synthetic/demo data only.
It is not medical advice, diagnosis, treatment guidance, or a medical device.

## File Location

Default prediction files live under:

```text
predictions/
```

Each prediction file should use the source document identifier:

```text
predictions/{document_id}.predicted.json
```

Example:

```text
predictions/note_001.predicted.json
```

The matching golden files are:

```text
golden_set/notes/{document_id}.txt
golden_set/expected/{document_id}.expected.json
```

## Top-Level Shape

Prediction files must be JSON objects.

```json
{
  "schema_version": "prediction-format-v1",
  "document_id": "note_001",
  "extractor": {
    "name": "manual-baseline",
    "version": "0.1.0"
  },
  "items": []
}
```

Required top-level fields for the future CLI:

- `schema_version`
- `document_id`
- `items`

Optional top-level fields:

- `extractor`
- future metadata fields ignored by the first-pass evaluator unless explicitly
  supported later

## Item Shape

Each item in `items` represents one predicted clinical fact. It must map cleanly
to `ExtractedClinicalItem`.

Required item fields:

- `type`
- `name`
- `source_quote`
- `source_start_char`
- `source_end_char`
- `section_id`
- `section_name`

Optional item fields:

- `status`
- `confidence`
- future metadata fields ignored by the first-pass evaluator unless explicitly
  supported later

## Field Semantics

### `type`

Clinical item type. It must map to `ClinicalItemType`.

Supported stable values:

- `condition`
- `procedure`
- `medication`
- `allergy`
- `observation`
- `lab_result`
- `order`
- `care_need`
- `negative_finding`
- `uncertain_mention`
- `family_history`

The evaluator may normalize supported aliases where the domain normalization
module defines them. New producers should prefer stable values instead of
aliases.

### `name`

Ordinary clinical display name, such as `hypertension` or `metformin`.

The evaluator normalizes whitespace and case for matching. Producers should
still emit clear, human-readable names.

### `status`

Optional clinical status, such as `active`, `performed`, `not_performed`, or
`discontinued`.

The evaluator normalizes supported status aliases. If an expected golden item
has no status, status does not block first-pass matching. If an expected item
does have a status, predicted status must match after normalization.

### `confidence`

Optional extractor confidence as a number between `0.0` and `1.0`, inclusive.
The first-pass evaluator preserves schema validity expectations but does not
score calibration.

### `source_quote`

Exact evidence text copied from the raw source document. It must not be
paraphrased or normalized.

### `source_start_char`

Zero-based inclusive character offset into the raw note text.

### `source_end_char`

Zero-based exclusive character offset into the raw note text.

### `section_id`

Stable source section identifier from the section parser, for example:

```text
note_001:section:006
```

### `section_name`

Canonical section name from the section parser, such as `Past Medical History`
or `Medications on Discharge`.

## Source Grounding Contract

Predictions must be exactly source-grounded:

```python
raw_text[source_start_char:source_end_char] == source_quote
```

Rules:

- Source quote matching is exact and case-sensitive.
- Offsets are based on raw source text, not normalized text.
- Do not trim, lowercase, collapse whitespace, or otherwise transform
  `source_quote` after calculating spans.
- If the quote appears elsewhere but the supplied offsets point to different
  text, the evaluator records a source quote failure.
- If the quote cannot be found at the supplied offsets, the evaluator records a
  source quote failure.

## Example Prediction File

Example `predictions/note_001.predicted.json`:

```json
{
  "schema_version": "prediction-format-v1",
  "document_id": "note_001",
  "extractor": {
    "name": "manual-baseline",
    "version": "0.1.0"
  },
  "items": [
    {
      "type": "condition",
      "name": "hypertension",
      "status": "active",
      "confidence": 0.98,
      "source_quote": "Hypertension.",
      "source_start_char": 392,
      "source_end_char": 405,
      "section_id": "note_001:section:003",
      "section_name": "Past Medical History"
    },
    {
      "type": "medication",
      "name": "metformin",
      "status": "active",
      "confidence": 0.96,
      "source_quote": "Metformin 500 mg twice daily.",
      "source_start_char": 612,
      "source_end_char": 641,
      "section_id": "note_001:section:006",
      "section_name": "Medications on Discharge"
    },
    {
      "type": "procedure",
      "name": "circumcision",
      "status": "not_performed",
      "confidence": 0.94,
      "source_quote": "Circumcision was not performed.",
      "source_start_char": 714,
      "source_end_char": 746,
      "section_id": "note_001:section:007",
      "section_name": "Procedures"
    }
  ]
}
```

Offsets above are illustrative. Producers and tests must compute offsets from
the exact raw note text being evaluated.

## Evaluation Behavior

The current domain evaluator:

- parses expected items from golden expected JSON
- parses invalid extraction traps from golden expected JSON
- matches expected items against predicted items
- detects missing expected items
- detects extra predicted items
- detects invalid trap hits
- validates predicted source quote spans
- returns deterministic counts and issue details in `EvaluationResult`

## Current Non-Scope

The prediction format and evaluator currently do not:

- call LLMs
- generate predictions
- run clinical rules automatically
- validate FHIR resources
- infer missing offsets
- repair malformed predictions
- evaluate every golden note by themselves
- provide a CLI runner

The CLI runner will be added later in `scripts/eval_golden.py`.

## Common Failure Examples

### Missing Source Quote

The predicted `source_quote` does not appear in the raw note text at the
provided offsets. The evaluator records `source_quote_failure`.

### Wrong Source Offsets

The quote exists in the note, but `source_start_char` and `source_end_char`
point to different text. The evaluator still records `source_quote_failure`
because grounding is incorrect.

### Invalid Item Type

The item uses a `type` that cannot map to `ClinicalItemType`. Prediction JSON
loading should fail before evaluation.

### Status Mismatch

The expected item has `status: "discontinued"` but the prediction has
`status: "active"`. The item does not match the expected item.

### Invalid Trap Hit

The note says:

```text
Patient denies chest pain and denies shortness of breath.
```

A prediction like this is an invalid trap hit:

```json
{
  "type": "condition",
  "name": "chest pain",
  "status": "active",
  "source_quote": "Patient denies chest pain and denies shortness of breath.",
  "source_start_char": 0,
  "source_end_char": 58,
  "section_id": "note_001:section:002",
  "section_name": "History of Present Illness"
}
```

The correct representation should not turn a denied symptom into an active
patient condition.

## Versioning

Use:

```json
{
  "schema_version": "prediction-format-v1"
}
```

Breaking changes to required fields, field meanings, or source grounding rules
should increment the schema version. Backward-compatible metadata additions can
keep the same schema version if older evaluators safely ignore those fields.
