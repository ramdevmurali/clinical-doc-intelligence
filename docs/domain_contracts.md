# Domain Contracts

This document defines the stable domain contracts for Clinical Document Intelligence. These contracts should guide implementation before API routes, workers, storage adapters, or UI components are built.

The goal is to prevent the project from becoming a thin LLM demo. The system should preserve source evidence, explicit lifecycle state, failure semantics, and reviewability at every stage.

## Scope of This Document

These contracts define:

- Core domain objects and their responsibilities.
- Lifecycle states and allowed meanings.
- Source grounding invariants.
- Section parsing expectations.
- Golden-set labeling rules.
- Phase 1 implementation boundaries.
- Testing expectations for non-toy behavior.

These contracts do not define framework-specific implementation details. FastAPI, Postgres, Kafka, React, and worker code should conform to these rules rather than redefine them.

## Core Domain Concepts

### Document

A `Document` is the immutable raw clinical text submitted to the system, plus mutable workflow metadata.

Required fields:

- `id`: stable document identifier.
- `filename`: original or generated filename.
- `source_type`: source category, such as `synthetic_note`, `uploaded_text`, or later `synthea_derived`.
- `raw_text`: exact source text used for parsing and extraction.
- `status`: current document lifecycle status.
- `created_at`: creation timestamp.
- `updated_at`: last state-change timestamp.
- `parser_version`: parser version used once parsing succeeds.
- `error_message`: failure reason when status is `failed`.

Contract rules:

- `raw_text` must not be modified after document creation.
- All downstream offsets refer to `raw_text`.
- A document may fail at any stage, but failure must preserve enough state to diagnose and replay.
- A document must not be exported until its extractable items are accepted or reviewed.

### DocumentSection

A `DocumentSection` is a contiguous span of text within a document.

Required fields:

- `id`: stable section identifier.
- `document_id`: parent document.
- `name`: normalized section name.
- `text`: exact section body text.
- `start_char`: inclusive character offset into `Document.raw_text`.
- `end_char`: exclusive character offset into `Document.raw_text`.
- `page_number`: page number when available, otherwise `null`.
- `created_at`: creation timestamp.

Contract rules:

- `raw_text[start_char:end_char]` must equal the source section span represented by the section.
- `start_char` and `end_char` are zero-based offsets.
- `end_char` must be greater than or equal to `start_char`.
- Section order must follow document order.
- Repeated headings must produce distinct sections, not overwrite earlier sections.

### ExtractedItem

An `ExtractedItem` is a structured clinical fact produced by extraction and later validated/reviewed.

Initial item types:

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

Required common fields:

- `id`: stable item identifier.
- `document_id`: source document.
- `section_id`: source section.
- `item_type`: one of the supported item types.
- `normalized_name`: canonical display name.
- `raw_text`: raw mention text when different from normalized name.
- `status`: clinical status where applicable.
- `confidence`: extractor confidence where available.
- `source_quote`: exact source evidence string.
- `source_start_char`: inclusive character offset into `Document.raw_text`.
- `source_end_char`: exclusive character offset into `Document.raw_text`.
- `extraction_model`: model/provider identifier where applicable.
- `schema_version`: extraction schema version.
- `validation_status`: validation decision.
- `review_status`: human review decision.
- `created_at`: creation timestamp.
- `updated_at`: last mutation timestamp.

Contract rules:

- Every extracted item must be source-grounded.
- No item may be accepted without a valid `source_quote` and source span.
- Negated findings must not be represented as active positive conditions.
- Family-history findings must not be represented as patient diagnoses.
- Orders/referrals must not be represented as completed procedures unless the note states completion.
- Discontinued, stopped, or held medications must not be represented as active medications.

### ValidationFinding

A `ValidationFinding` records a deterministic rule result attached to an extracted item.

Required fields:

- `id`: stable finding identifier.
- `document_id`: source document.
- `item_id`: extracted item reviewed by the rule.
- `rule_id`: stable rule identifier.
- `severity`: `info`, `warning`, or `error`.
- `message`: human-readable explanation.
- `created_at`: creation timestamp.

Contract rules:

- Findings explain validation decisions; they should not silently mutate facts.
- Rule identifiers must be stable enough for tests, metrics, and diagnostics.
- A severe finding should route the item to review or rejection, depending on the rule.

### ReviewAction

A `ReviewAction` records a human decision on an extracted item.

Required fields:

- `id`: stable action identifier.
- `document_id`: source document.
- `item_id`: reviewed item.
- `action`: `approve`, `reject`, `edit`, or `mark_uncertain`.
- `old_value`: previous item value for edits.
- `new_value`: replacement item value for edits.
- `reviewer`: reviewer identifier.
- `created_at`: creation timestamp.

Contract rules:

- Review actions must be append-only audit records.
- Edits must preserve the original extracted item and record the changed fields.
- Export should use the latest approved or edited state, not rejected state.

### FHIRExport

A `FHIRExport` is a FHIR-style JSON representation of accepted or approved data.

Required fields:

- `id`: stable export identifier.
- `document_id`: source document.
- `resource_type`: FHIR-style resource type.
- `resource_json`: generated resource body.
- `export_version`: mapper/export schema version.
- `created_at`: creation timestamp.

Contract rules:

- The project implements FHIR-style JSON, not a full FHIR server.
- Exports must preserve evidence where supported, especially source quotes.
- Only accepted or human-approved items should be exported.
- Failed mappings should be diagnosable and replayable.

### EvalRun and EvalResult

An `EvalRun` records one evaluation pass over a dataset. An `EvalResult` records a metric from that run.

`EvalRun` required fields:

- `id`: stable run identifier.
- `dataset_name`: dataset evaluated.
- `started_at`: run start timestamp.
- `finished_at`: run completion timestamp.
- `status`: `running`, `completed`, or `failed`.
- `summary_json`: aggregate metrics and metadata.

`EvalResult` required fields:

- `id`: stable result identifier.
- `eval_run_id`: parent run.
- `document_id`: document evaluated when applicable.
- `metric_name`: metric identifier.
- `metric_value`: numeric metric value when applicable.
- `details_json`: structured metric details.

Contract rules:

- Evaluation must compare extracted output against manually controlled expected labels.
- LLM-generated expected labels are not trusted unless manually reviewed.
- Evaluation should measure both extraction quality and safety behavior.

## Document Lifecycle Statuses

Allowed `document.status` values:

- `uploaded`: document is stored but not parsed.
- `parsed`: sections have been generated and stored.
- `extracted`: raw extraction items have been generated.
- `validated`: extraction items have validation decisions.
- `needs_review`: at least one item requires human review.
- `approved`: all required review actions are complete and accepted for export.
- `exported`: FHIR-style export has been generated.
- `failed`: a stage failed and requires diagnosis or replay.

Contract rules:

- Status transitions should be monotonic for the main success path.
- A failed document must retain stage and error context.
- Reprocessing should create a new job attempt or versioned output rather than silently overwriting prior results.
- Later phases may add explicit job-stage state; document status remains a coarse workflow summary.

## Extraction and Review Statuses

Allowed `item.validation_status` values:

- `accepted`: deterministic checks found no blocking issue.
- `rejected`: item is invalid and should not be exported.
- `uncertain`: item may be valid but needs human judgment.
- `contradiction`: item conflicts with another mention or rule.
- `needs_review`: item must be reviewed before export.

Allowed `item.review_status` values:

- `pending`: item is waiting for review.
- `approved`: reviewer accepted item as-is.
- `rejected`: reviewer rejected item.
- `edited`: reviewer changed one or more fields.

Contract rules:

- Low-confidence items should route to review.
- Items with contradictions should route to review.
- Rejected items must not be exported.
- Edited items must preserve audit history.

## Source Grounding Invariants

Source grounding is mandatory for clinical credibility.

Required invariants:

- Every extracted item must have a `source_quote`.
- `source_quote` must appear verbatim in `Document.raw_text`.
- `source_start_char` and `source_end_char` must map back exactly to `source_quote`.
- `section_id` must identify a known section from the same document.
- The source quote should support the extracted fact, not merely mention related text.
- Page number should be preserved when available, but text notes may use `null`.

Failure behavior:

- Missing source quote should reject the item or send it to extraction DLQ.
- Invalid source span should reject the item or send it to extraction DLQ.
- Unknown section ID should reject the item or send it to validation DLQ.

## Section Parsing Contract

Section parsing converts raw clinical text into ordered `DocumentSection` records.

### Section Names

The parser should recognize common clinical headings, including:

- `Chief Complaint`
- `Reason for Visit`
- `Reason for Referral`
- `Reason for Consult`
- `History of Present Illness`
- `History`
- `Past Medical History`
- `Past Surgical History`
- `Family History`
- `Social History`
- `Allergies`
- `Allergies and Adverse Reactions`
- `Medications`
- `Medication History`
- `Medications on Discharge`
- `Vitals`
- `Physical Exam`
- `Labs`
- `Imaging`
- `Procedures`
- `Orders`
- `Orders and Referrals`
- `Assessment`
- `Assessment and Plan`
- `Discharge Instructions`
- `Pending Orders`

Contract rules:

- Preserve the original heading text where useful, but expose a normalized section name for downstream logic.
- Unknown headings should still create sections rather than discarding text.
- Heading detection must not remove or alter source text needed for offsets.

### Offsets

Contract rules:

- Section offsets must refer to the original raw document text.
- Offsets must be deterministic across runs for the same parser version.
- Section body text should be recoverable from the original document using offsets.
- Tests must verify exact offset reconstruction.

### Repeated Sections

Contract rules:

- Repeated section headings are valid.
- Each repeated section must receive a distinct section ID.
- Downstream extraction should use section ID and order, not only section name.

### Unknown Headings

Contract rules:

- Unknown headings should be retained as sections with normalized name `unknown` or a sanitized heading-derived name.
- Unknown sections should remain available to extraction and review.
- Unknown headings should be visible in diagnostics or parser metrics.

### Missing Headings

Contract rules:

- Documents without detectable headings should produce one fallback section named `Unsectioned`.
- The fallback section should cover the full document text.
- Empty documents should fail parsing rather than producing an empty section.

## Golden Set Contract

The golden set is the manually controlled evaluation benchmark.

Directory layout:

```text
golden_set/
  notes/
    note_001.txt
  expected/
    note_001.expected.json
```

Expected JSON fields:

- `document_id`: note identifier matching the note filename.
- `title`: short description of the note purpose.
- `data_policy`: must indicate synthetic/demo data.
- `items`: facts that should be extracted.
- `should_not_extract`: traps the extractor must avoid.

`items` contract:

- Must be a non-empty list.
- Every item must include `type`.
- Every item must include `source_quote`.
- Every `source_quote` must appear verbatim in the matching note.
- Items may include type-specific fields such as `dose`, `frequency`, `route`, `value`, `unit`, `relation`, `reaction`, or `status`.

`should_not_extract` contract:

- Must describe facts that unsafe extraction might incorrectly produce.
- Should include a `reason` explaining why extraction would be wrong.
- Does not require `source_quote`, because traps may describe invalid interpretations rather than desired facts.

Data policy:

- The golden set must use synthetic/demo data only.
- Real patient records must not be added.
- Synthea-derived data is allowed later only if it remains synthetic and labels are manually reviewed.

## Phase 1 Scope

Phase 1 proves the document lifecycle foundation.

Included:

- Parse synthetic text notes into sections.
- Preserve exact source spans for sections.
- Define deterministic parser behavior over the golden notes.
- Store or prepare to store document and section state.
- Expose document and sections through backend endpoints later in Phase 1.
- Add tests that validate section names, ordering, and offsets.

Acceptance criteria:

- All current golden notes parse successfully.
- Each parsed section has `name`, `text`, `start_char`, and `end_char`.
- `Document.raw_text[start_char:end_char]` reconstructs the section text according to the parser contract.
- Repeated, unknown, and missing headings have defined behavior.
- Empty documents fail with an explicit error.

## Phase 1 Non-Scope

Phase 1 should not implement:

- LLM extraction.
- Kafka or Redpanda workers.
- Clinical validation rules.
- Human review UI.
- FHIR export.
- Full evaluation metrics.
- Auth, multi-tenancy, or real patient ingestion.
- PDF OCR or scanned document handling.

These are later phases. Adding them early would blur the system boundaries and increase rewrite risk.

## Failure Handling Principles

Failures should be explicit, diagnosable, and replayable.

General principles:

- Do not silently drop text, sections, or extracted items.
- Preserve the original document even if parsing fails.
- Attach stage-specific error messages.
- Prefer deterministic failures over partial ambiguous success.
- Make retry/replay behavior explicit once job orchestration exists.

Phase 1 parser failures:

- Empty text: fail parsing.
- Whitespace-only text: fail parsing.
- Invalid encoding: fail ingestion before parsing.
- No headings: create `Unsectioned` section if text is non-empty.

Later-stage failures:

- Invalid extraction JSON: retry, then DLQ.
- Missing source quote: reject or DLQ.
- Invalid source span: reject or DLQ.
- Unknown item type: validation DLQ.
- Impossible FHIR mapping: FHIR DLQ.

## Testing Expectations

Tests should protect contracts rather than incidental implementation details.

Phase 1 tests:

- Parse every note in `golden_set/notes`.
- Verify non-empty section output for every non-empty note.
- Verify section ordering follows document order.
- Verify section offsets map back to the original document.
- Verify fallback behavior for missing headings.
- Verify empty document failure.
- Verify repeated headings produce separate sections.

Golden-set tests:

- Validate every expected JSON file is valid JSON.
- Verify every expected file has a matching note file.
- Verify every item has `type` and `source_quote`.
- Verify every `source_quote` appears verbatim in the note.
- Verify `should_not_extract` is present and non-empty for each expected file.

Later tests:

- Source span validation for extracted items.
- Clinical rule tests for negation, family history, procedures, referrals, and medication status.
- FHIR mapping tests for accepted/approved items only.
- Evaluation harness tests for precision, recall, hallucination rate, and source quote coverage.

## Contract Change Policy

These contracts may evolve, but changes should be deliberate.

Rules for changing contracts:

- Update this document before or alongside implementation changes.
- Update tests when invariants change.
- Prefer versioned schema changes over silent breaking changes.
- Keep golden labels manually reviewable.
- Do not weaken source grounding requirements to accommodate model limitations.
