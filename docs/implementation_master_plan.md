# Implementation Master Plan

This document is the implementation source-of-truth for Clinical Document Intelligence. It should be used alongside `docs/domain_contracts.md` when deciding what to build next.

The project should prioritize clinical reliability depth before infrastructure breadth. The goal is not to create a polished demo around an LLM call. The goal is to build a defensible clinical document intelligence pipeline with source grounding, deterministic validation, reviewability, and measurable extraction quality.

## Build Principle

Build the clinical reliability core before the distributed-system shell.

Do not add Kafka, a complex frontend, multiple workers, or FHIR export until the domain logic proves it can handle difficult clinical text. Infrastructure should support real operational needs, not create the appearance of seriousness.

## Current Foundation

Already implemented:

- `golden_set/`: manually controlled synthetic notes and expected extraction labels.
- `docs/domain_contracts.md`: domain contracts, lifecycle states, source grounding invariants, and Phase 1 boundaries.
- `processor/src/domain/sectioning.py`: pure section parser with exact character offsets.
- `processor/src/domain/source_spans.py`: source quote/span validation utilities.
- `processor/src/domain/validation.py`: validation status, review status, severity, findings, and decisions.

Current test coverage:

- Section parsing over all golden notes.
- Exact section span reconstruction.
- Source quote resolution over all golden expected labels.
- Validation decision/status contract behavior.

## Near-Term Direction

The next phase is **Clinical Item Schema + Normalization**.

Before implementing clinical rules, LLM extraction, API routes, workers, or UI, the project needs a stable internal representation of an extracted clinical fact.

Clinical rules should not operate on loose dictionaries. They should operate on typed, validated, source-grounded clinical item objects.

## Phase: Clinical Item Schema + Normalization

### Goal

Define the internal clinical item model and normalization behavior that future extraction and validation stages will use.

This phase should answer:

- What is an extracted clinical item?
- Which item types are supported?
- Which fields are required for source grounding?
- How are names and statuses normalized?
- Which invalid item shapes are rejected before rule evaluation?

### Target Files

Implementation:

- `processor/src/domain/extraction_schema.py`
- `processor/src/domain/normalization.py`

Tests:

- `processor/tests/test_extraction_schema.py`
- `processor/tests/test_normalization.py`

Do not modify backend, DB, Kafka, frontend, infra, or FHIR mapping in this phase.

## Clinical Item Types

Start with these supported item types:

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

These should be represented as a stable enum/string enum, not free-form strings spread across the codebase.

## Extracted Clinical Item Contract

A clinical item should include:

- `item_type`: supported clinical item type.
- `name`: normalized display name or clinical concept name.
- `status`: normalized status where applicable.
- `confidence`: optional model confidence, bounded from `0.0` to `1.0` when present.
- `source_quote`: exact evidence quote from the source document.
- `source_start_char`: inclusive zero-based offset.
- `source_end_char`: exclusive zero-based offset.
- `section_id`: source section identifier.
- `section_name`: normalized source section name.

Optional type-specific attributes can be added later, such as:

- `dose`
- `frequency`
- `route`
- `value`
- `unit`
- `date`
- `reaction`
- `relation`

Do not over-model every clinical detail in the first pass. The first pass should make common facts safe and hard to misuse.

## Required Invariants

The item schema must enforce these invariants:

- `item_type` must be known.
- `name` must be non-empty.
- `source_quote` must be non-empty.
- `section_id` must be non-empty.
- `section_name` must be non-empty.
- `source_start_char` must be non-negative.
- `source_end_char` must be greater than or equal to `source_start_char`.
- `confidence`, when present, must be between `0.0` and `1.0`.

Source quote text should be validated against raw document text by `processor/src/domain/source_spans.py`, not duplicated inside the item schema.

## Normalization Contract

Normalization should be deterministic and conservative.

### Name Normalization

Normalize names by:

- Trimming leading/trailing whitespace.
- Collapsing repeated internal whitespace.
- Lowercasing ordinary clinical names where appropriate.
- Preserving meaningful acronyms where later needed only if there is a clear rule.

Examples:

- `"  Type 2   Diabetes Mellitus "` → `"type 2 diabetes mellitus"`
- `" Chest Pain "` → `"chest pain"`
- `"Warfarin"` → `"warfarin"`

### Item Type Normalization

Normalize known aliases into supported item types only when unambiguous.

Examples:

- `diagnosis` → `condition`
- `problem` → `condition`
- `drug` → `medication`
- `med` → `medication`
- `lab` → `lab_result`
- `referral` → `order`

Unknown item types should be rejected, not silently accepted.

### Status Normalization

Normalize status values into stable internal strings.

Initial statuses:

- `active`
- `historical`
- `resolved`
- `in_remission`
- `performed`
- `not_performed`
- `planned`
- `ordered`
- `referred`
- `pending`
- `administered`
- `started`
- `stopped`
- `discontinued`
- `held`
- `prescribed`
- `none_known`
- `possible`
- `rule_out`
- `unlikely_not_excluded`
- `planned_change`

Unknown statuses should either become `unknown` or raise a clear domain error. Prefer raising in early development so schema drift is visible.

## Hard Cases This Phase Must Support

Use these examples as implementation targets:

### Negation

Source:

```text
Patient denies chest pain.
```

Valid item shape:

```text
item_type = negative_finding
name = chest pain
source_quote = Patient denies chest pain.
```

Do not represent this as an active `condition`.

### Family History

Source:

```text
Mother had breast cancer.
```

Valid item shape:

```text
item_type = family_history
name = breast cancer
status = historical or family_history-specific status if needed later
relation = mother
```

Do not represent this as a patient `condition`.

### Procedure Not Performed

Source:

```text
Circumcision was not performed.
```

Valid item shape:

```text
item_type = procedure
name = circumcision
status = not_performed
```

Do not represent this as `performed`.

### Referral vs Completed Procedure

Source:

```text
Patient referred for outpatient colonoscopy.
```

Valid item shape:

```text
item_type = order
name = outpatient colonoscopy
status = referred
```

Do not represent this as a performed `procedure`.

### Medication Status

Source:

```text
Warfarin discontinued due to bleeding risk.
```

Valid item shape:

```text
item_type = medication
name = warfarin
status = discontinued
```

Do not represent this as an active medication.

## Tests Required For This Phase

### Extraction Schema Tests

Test that:

- Every supported item type has the expected string value.
- Valid clinical item construction succeeds.
- Empty `name` is rejected.
- Empty `source_quote` is rejected.
- Empty `section_id` is rejected.
- Empty `section_name` is rejected.
- Negative source offsets are rejected.
- `source_end_char < source_start_char` is rejected.
- Confidence below `0.0` or above `1.0` is rejected.
- Confidence may be omitted.

### Normalization Tests

Test that:

- Name normalization trims and collapses whitespace.
- Name normalization lowercases ordinary names.
- Item type aliases normalize to supported item types.
- Unknown item types are rejected.
- Status aliases normalize to stable statuses.
- Unknown statuses are rejected.
- Hard-case statuses normalize correctly:
  - `not performed` → `not_performed`
  - `referred` → `referred`
  - `discontinued` → `discontinued`
  - `held` → `held`
  - `rule out` → `rule_out`

## Non-Scope For This Phase

Do not implement:

- LLM extraction.
- Clinical validation rules.
- Review routing logic.
- FastAPI endpoints.
- Database persistence.
- Kafka/Redpanda topics or consumers.
- FHIR export.
- Full evaluation metrics.

This phase defines the shape and normalization of clinical facts. It does not decide whether facts are clinically valid. That comes in the clinical rules phase.

## Acceptance Criteria

This phase is complete when:

- `extraction_schema.py` defines typed clinical item primitives.
- `normalization.py` defines deterministic name/type/status normalization.
- Tests cover schema invariants and normalization behavior.
- All existing domain tests still pass.
- The implementation remains pure Python with no new dependencies.

Recommended validation command:

```bash
python3 -m unittest processor.tests.test_extraction_schema processor.tests.test_normalization processor.tests.test_validation processor.tests.test_source_spans processor.tests.test_sectioning -v
```

## Next Phase After This

After clinical item schema and normalization are stable, implement the first deterministic clinical rules in `processor/src/domain/clinical_rules.py`.

Start with only the high-value safety rules:

- Negated finding is not active condition.
- Family history is not patient diagnosis.
- Procedure not performed is not performed procedure.
- Referral/order is not completed procedure.
- Discontinued or held medication is not active medication.

These rules should return `ValidationDecision` objects from `processor/src/domain/validation.py`.

## Architecture Guardrails

Until the domain logic is strong, avoid adding infrastructure-heavy components.

Defer:

- Kafka/Redpanda orchestration.
- Separate parser/extraction/validation worker services.
- React review UI.
- FHIR export.

Add those only when there is a concrete reason:

- independent retries,
- replayability,
- stage-specific failures,
- review workflow latency,
- operational diagnostics,
- validated end-to-end domain behavior.

## Quality Bar

This project is serious if the code makes clinical extraction safer and more auditable.

The strongest proof points should be:

- difficult notes,
- exact source spans,
- stable item schema,
- conservative normalization,
- deterministic clinical rules,
- reviewable uncertain items,
- honest evaluation and error analysis.

Do not optimize for broad architecture diagrams before these are real.
