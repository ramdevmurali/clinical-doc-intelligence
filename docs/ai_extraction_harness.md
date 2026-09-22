# AI Extraction Harness Technical Spec

Status: implemented through local harness Phase 2; Phase 3 evaluation is next

Owner: Clinical Document Intelligence

Scope: local AI/LLM extraction harness for synthetic clinical notes

This document specifies and tracks the production-grade local AI extraction
harness after the deterministic baseline extractor. It is implementation
context for current and future work. It does not define backend, Kafka, UI,
FHIR export, or real patient data flows.

The current repository is the implementation truth. Attached project specs are
background only.

## Executive Summary

The AI extraction harness must turn one or more synthetic clinical notes into
`prediction-format-v1` JSON files that can be evaluated by the existing golden
set evaluator.

The harness must not be a thin GPT wrapper. The LLM is allowed to propose
candidate clinical facts, but the local code must own:

- section parsing
- schema validation
- item type and status normalization
- exact source quote and span grounding
- deterministic clinical guardrails
- prediction JSON writing
- audit metadata
- golden-set evaluation compatibility

The current implementation proves the harness can call a model through a small
provider abstraction, convert the model response into source-grounded
`ExtractedClinicalItem` objects, write `predictions_llm/*.predicted.json`, and
evaluate those files using the existing `scripts/eval_golden.py` path.

Current implemented status:

- Phase 1 fixture-backed harness is complete.
- Phase 2 Gemini provider adapter is complete for local synthetic-note runs.
- Audit sidecars are always written for successful runs.
- Schema parse failures write audit sidecars and do not write prediction files.
- Prediction serialization is shared between baseline and AI runners.
- Final prediction items are sorted deterministically before writing.
- Baseline-vs-AI comparison tooling exists.
- Full golden-set Gemini evaluation is not complete yet.
- Backend, worker, review UI, and FHIR flows remain out of scope.

## Current Repository Anchors

The harness must build on these existing files and contracts:

- `processor/src/domain/sectioning.py`
  - `parse_sections(raw_text, document_id=...)`
  - `DocumentSection`
  - stable section IDs such as `note_001:section:003`
- `processor/src/domain/source_spans.py`
  - `find_source_span(raw_text, source_quote)`
  - `validate_source_span(raw_text, source_quote, start_char, end_char)`
- `processor/src/domain/extraction_schema.py`
  - `ClinicalItemType`
  - `ExtractedClinicalItem`
- `processor/src/domain/normalization.py`
  - `normalize_item_type`
  - `normalize_name`
  - `normalize_status`
- `processor/src/domain/clinical_rules.py`
  - `validate_clinical_item`
  - rejection and review guardrails
- `processor/src/domain/evaluation.py`
  - `predicted_items_from_json`
  - `evaluate_predictions`
- `scripts/run_baseline_extractor.py`
  - CLI and prediction writer pattern
  - shared prediction formatting is now in `processor/src/domain/prediction_format.py`
- `processor/src/domain/prediction_format.py`
  - `PREDICTION_SCHEMA_VERSION`
  - `prediction_json_for_items`
  - `prediction_item_from_extracted_item`
- `processor/src/domain/ai_extraction_audit.py`
  - successful-run audit sidecars
  - schema-failure audit sidecars
  - prompt and raw response hashes
- `scripts/eval_golden.py`
  - saved prediction evaluation
- `scripts/compare_prediction_runs.py`
  - baseline-vs-AI comparison
- `scripts/eval_extractions.py`
  - placeholder evaluation entrypoint; not the active local evaluation path yet
- `scripts/report_baseline_errors.py`
  - aggregate error reporting pattern
- `docs/prediction_format.md`
  - saved prediction JSON contract
- `golden_set/notes/`
  - synthetic source notes
- `golden_set/expected/`
  - manually controlled expected labels
- `predictions_baseline/`
  - frozen-enough deterministic baseline predictions

The baseline metrics at the time this spec was written:

```text
expected_item_count: 149
predicted_item_count: 117
matched_item_count: 110
missing_item_count: 39
extra_item_count: 7
invalid_trap_hit_count: 0
source_quote_failure_count: 0
medication missing: 0
```

These metrics are a comparison baseline, not an AI harness target for the first
commit.

## Product Goals

The AI extraction harness should prove that the project can safely introduce a
non-deterministic extractor without weakening the existing clinical reliability
core.

Primary goals:

- Extract clinical facts from synthetic clinical notes using an LLM or AI model.
- Preserve exact source evidence for every accepted item.
- Convert AI output into existing `ExtractedClinicalItem` objects.
- Write prediction files compatible with `scripts/eval_golden.py`.
- Keep deterministic validation and evaluation in local code.
- Make model failures inspectable instead of hiding them.
- Enable baseline-vs-AI comparison without changing the golden set.

Engineering goals:

- Keep domain logic pure where possible.
- Isolate network/provider code outside `processor/src/domain/`.
- Make the harness testable with fake providers and fixture responses.
- Avoid adding backend, Kafka, database, or UI dependencies.
- Make output deterministic for a fixed provider response.
- Fail closed on malformed, ungrounded, or unsafe extraction output.

## Non-Goals

This milestone must not build:

- backend API integration
- Kafka/Redpanda workers
- database persistence
- human review UI
- FHIR export
- real patient data ingestion
- diagnosis or treatment recommendations
- a chatbot
- automated golden label generation
- a broad clinical ontology normalization system
- automatic medical coding
- full document OCR or PDF parsing

The harness is a local extraction and evaluation bridge. Its job is to connect
AI extraction to the existing safety/eval spine.

## Safety Stance

This project uses synthetic/demo data only.

It does not provide medical advice, diagnosis, treatment recommendations, or
patient-specific clinical decision support. It is not a medical device and must
not be used with real patient data.

Safety requirements:

- Scripts must assume all source notes are synthetic/demo data.
- Prompts must instruct the model not to provide medical advice.
- The model must extract only facts stated in the supplied document.
- The model must not infer diagnoses, treatment plans, medication changes, or
missing facts beyond the source text.
- The harness must reject ungrounded items.
- The harness must keep clinical guardrails deterministic and local.

## Architecture Overview

The AI harness has six stages:

```text
golden_set/notes/{document_id}.txt
        |
        v
parse_sections(raw_text, document_id)
        |
        v
build AI extraction prompt from raw text + sections
        |
        v
LLM provider returns strict JSON candidate items
        |
        v
parse, normalize, ground, and validate candidates locally
        |
        v
write predictions_llm/{document_id}.predicted.json
        |
        v
scripts/eval_golden.py --predictions-dir predictions_llm
```

The LLM is not trusted to produce final prediction files. It only produces
candidate item JSON. Local deterministic code converts candidates into final
prediction JSON.

## Implemented Files

Current implementation:

```text
processor/src/domain/ai_extraction_prompt.py
processor/src/domain/ai_extraction_response.py
processor/src/domain/ai_extraction_grounding.py
processor/src/domain/ai_extraction_audit.py
processor/src/domain/prediction_format.py
processor/src/services/llm_provider.py
scripts/run_ai_extractor.py
scripts/compare_prediction_runs.py
processor/tests/test_ai_extraction_prompt.py
processor/tests/test_ai_extraction_response.py
processor/tests/test_ai_extraction_grounding.py
processor/tests/test_ai_extraction_audit.py
processor/tests/test_prediction_format.py
processor/tests/test_llm_provider.py
processor/tests/test_run_ai_extractor_script.py
processor/tests/test_compare_prediction_runs_script.py
predictions_llm/
```

Potential follow-up files:

```text
scripts/report_ai_errors.py
processor/src/domain/extractor_comparison.py
docs/extractor_comparison.md
```

### File Responsibilities

`processor/src/domain/ai_extraction_prompt.py`

- Pure prompt construction.
- Input: document ID, raw text, parsed sections, schema version.
- Output: prompt messages or a provider-neutral prompt object.
- Must not read files, call providers, or inspect golden expected labels.

`processor/src/domain/ai_extraction_response.py`

- Pure parsing of raw model JSON into candidate item objects.
- Rejects malformed JSON, unknown item types, unknown statuses, bad confidence
  values, missing source quotes, and unknown fields.
- Does not call the provider.
- Does not infer source offsets.

`processor/src/domain/ai_extraction_grounding.py`

- Converts parsed candidate items into `ExtractedClinicalItem` values.
- Resolves exact source quote spans from raw text and parsed sections.
- Applies normalization through `normalization.py`.
- Applies source span validation through `source_spans.py`.
- Applies clinical rules through `clinical_rules.py`.
- Returns accepted, review-required, rejected, and failed-grounding buckets.

`processor/src/services/llm_provider.py`

- Defines a small provider protocol.
- Owns provider-specific network calls and credentials.
- Provides a fake/fixture provider for tests.
- Provides the Gemini generateContent adapter for local synthetic-note runs.
- Must not contain clinical parsing logic.

`scripts/run_ai_extractor.py`

- Local CLI runner analogous to `scripts/run_baseline_extractor.py`.
- Reads note files.
- Calls the provider through the abstraction.
- Writes prediction JSON files.
- Writes audit sidecars.
- Does not read `golden_set/expected/`.

`processor/src/domain/prediction_format.py`

- Owns `prediction-format-v1` serialization.
- Converts `ExtractedClinicalItem` values to prediction JSON items.
- Sorts final prediction items by
  `(source_start_char, source_end_char, type, name, status)`.
- Is shared by baseline and AI runners.

`processor/src/domain/ai_extraction_audit.py`

- Owns audit sidecar shape.
- Records provider/model/prompt metadata.
- Hashes prompt messages and raw provider responses.
- Records grounding and clinical-rule failures.
- Records schema parse failures without producing prediction files.

## Input Contracts

The CLI should accept:

```text
python3 scripts/run_ai_extractor.py \
  --document-id note_001 \
  --notes-dir golden_set/notes \
  --output-dir predictions_llm \
  --provider fixture \
  --model fixture-model \
  --overwrite
```

Arguments:

- `--document-id`
  - Optional single document ID.
  - If absent, process all `*.txt` notes in sorted order.
- `--notes-dir`
  - Defaults to `golden_set/notes`.
- `--output-dir`
  - Defaults to `predictions_llm`.
- `--provider`
  - Required or defaulted explicitly.
  - Current values: `fixture`, `gemini`.
- `--model`
  - Provider-specific model identifier.
- `--overwrite`
  - Required to replace existing prediction files.
- `--dry-run`
  - Builds prompt and parses sections without calling a real provider.
  - Not implemented yet.
- `--save-audit`
  - Writes audit sidecars. This should default to enabled for local work.
  - Not implemented as a flag; audit sidecars are currently always written.

The extractor must not read expected labels. Tests should explicitly protect
that boundary, as `test_run_baseline_extractor_script.py` does for the baseline.

## Output Contracts

Primary output:

```text
predictions_llm/{document_id}.predicted.json
```

The file must match `docs/prediction_format.md` and parse through
`predicted_items_from_json`.

Top-level shape:

```json
{
  "schema_version": "prediction-format-v1",
  "document_id": "note_001",
  "extractor": {
    "name": "llm-harness",
    "version": "ai-extractor-v1",
    "provider": "fixture",
    "model": "fixture-model",
    "prompt_version": "ai-extraction-prompt-v1"
  },
  "items": []
}
```

The existing evaluator ignores extra extractor metadata. The required fields
remain `schema_version`, `document_id`, and `items`.

Optional audit sidecar:

```text
predictions_llm/{document_id}.audit.json
```

Audit sidecar shape:

```json
{
  "document_id": "note_001",
  "extractor": {
    "name": "llm-harness",
    "version": "ai-extractor-v1",
    "provider": "fixture",
    "model": "fixture-model",
    "prompt_version": "ai-extraction-prompt-v1"
  },
  "counts": {
    "candidate_count": 0,
    "accepted_count": 0,
    "needs_review_count": 0,
    "rejected_by_schema_count": 0,
    "rejected_by_grounding_count": 0,
    "rejected_by_rules_count": 0
  },
  "failures": [],
  "validation_findings": [],
  "prompt_sha256": "...",
  "raw_response_sha256": "...",
  "latency_ms": 0
}
```

Audit files must not be required by `scripts/eval_golden.py`.

## Raw AI Response Contract

The model should not emit final prediction files. It should emit candidate JSON
that is easier to validate safely.

Raw response shape:

```json
{
  "schema_version": "ai-extraction-response-v1",
  "document_id": "note_001",
  "items": [
    {
      "type": "condition",
      "name": "hypertension",
      "status": "active",
      "confidence": 0.92,
      "source_quote": "Hypertension.",
      "section_id": "note_001:section:003",
      "section_name": "Past Medical History"
    }
  ]
}
```

Required top-level fields:

- `schema_version`
- `document_id`
- `items`

Required item fields:

- `type`
- `name`
- `source_quote`
- `section_id`
- `section_name`

Optional item fields:

- `status`
- `confidence`

Disallowed item fields in the raw AI response:

- `source_start_char`
- `source_end_char`
- `validation_status`
- `review_status`
- `diagnosis_advice`
- `treatment_recommendation`
- any unrecognized field

Reason: the model must not be trusted to compute offsets or make workflow
decisions. Local code owns those fields.

## LLM Provider Abstraction

Provider code should be small and boring.

Suggested protocol:

```python
class LlmProvider(Protocol):
    name: str

    def complete_json(
        self,
        *,
        model: str,
        messages: tuple[PromptMessage, ...],
        timeout_seconds: float,
    ) -> LlmResponse:
        ...
```

Suggested response:

```python
@dataclass(frozen=True)
class LlmResponse:
    provider: str
    model: str
    content: str
    latency_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    request_id: str | None = None
```

Provider requirements:

- No provider imports in `processor/src/domain/`.
- No clinical interpretation in provider classes.
- Credentials are read only by provider classes or config helpers.
- Credentials are never logged.
- Provider calls should use explicit timeouts.
- Tests use fixture providers, not network calls.

The first implementation may include only a fixture provider plus one real
provider adapter if credentials are available. Missing credentials must produce
a clear CLI error and must not break unit tests.

## Prompt Construction Strategy

The prompt must be schema-first, extraction-only, and evidence-constrained.

Inputs to the prompt:

- safety disclaimer
- supported item types
- supported statuses
- raw document ID
- section inventory with `section_id`, `section_name`, and exact section text
- output JSON schema
- extraction rules and negative examples

The prompt must not include:

- golden expected labels
- baseline predictions
- evaluation outcomes
- hidden answers from `golden_set/expected`
- any instruction to infer missing diagnoses or treatments

Prompt rules:

- Extract only facts explicitly stated in the note.
- Every item must include an exact `source_quote` copied verbatim.
- If a fact cannot be supported by one exact quote, omit it.
- Do not emit offsets.
- Do not paraphrase source quotes.
- Do not include explanatory markdown.
- Do not include medical advice.
- Represent negated symptoms as `negative_finding`, not active conditions.
- Represent family history as `family_history`, not patient condition.
- Represent planned/referred procedures as `order` unless completed.
- Represent stopped, discontinued, or held medications with inactive statuses.
- Represent uncertain/rule-out/possible findings as `uncertain_mention`.

The prompt should prefer recall over clever summarization, but the local
guardrails are allowed to reject unsafe candidates.

### Prompt Versioning

Use a stable prompt version constant:

```text
AI_EXTRACTION_PROMPT_VERSION = "ai-extraction-prompt-v1"
```

Any prompt change that can alter output semantics should update the version.
Prediction and audit metadata must include the prompt version.

## Strict Schema Requirements

`ai_extraction_response.py` should parse model output into a strict domain
candidate, for example:

```python
@dataclass(frozen=True)
class AiCandidateItem:
    item_type: ClinicalItemType
    name: str
    status: str | None
    confidence: float | None
    source_quote: str
    section_id: str
    section_name: str
```

Parser behavior:

- Response must be a JSON object.
- JSON must not be embedded in markdown fences.
- `schema_version` must equal `ai-extraction-response-v1`.
- `document_id` must match the requested document.
- `items` must be a list.
- Each item must be an object.
- Item type must normalize to `ClinicalItemType`.
- Status must normalize through `normalize_status` when provided.
- Name must normalize through `normalize_name`.
- Confidence must be numeric between `0.0` and `1.0` when provided.
- Source quote must be non-empty.
- Section ID and section name must be non-empty.
- Unknown fields must raise an error in the first implementation.
- Duplicate candidate items should be deduplicated after grounding by
  `(type, name, status, source_start_char, source_end_char)`.

Fail closed. A malformed response should create a clear runner error or audit
failure. It should not produce a partially trusted prediction file unless the
CLI explicitly supports partial outputs.

## Source Quote and Span Grounding Strategy

The model supplies only an exact quote and section identity. Local code computes
spans.

Grounding algorithm:

1. Parse sections with `parse_sections(raw_text, document_id=document_id)`.
2. Build a lookup by `section_id`.
3. For each candidate:
   - verify `section_id` exists;
   - verify candidate `section_name` matches the parsed section name;
   - search for `source_quote` exactly inside that section text;
   - if found exactly once inside the section, compute raw offsets as
     `section.start_char + local_start` and `section.start_char + local_end`;
   - validate with `validate_source_span`;
   - create `ExtractedClinicalItem`.
4. If a quote is not found inside the declared section, reject the candidate.
5. If a quote appears multiple times inside the declared section, reject it as
   ambiguous unless a future version adds deterministic disambiguation.
6. If the model omits or invents a section, reject the candidate.

Do not globally search and silently accept a quote from a different section.
Section mismatch is an extraction error, not a harmless formatting issue.

Source quote requirements:

- Exact raw text, including punctuation and whitespace.
- Prefer one sentence or one clinically meaningful line.
- Must support the extracted type, name, and status.
- Must not be a broad section chunk unless the fact cannot be represented more
  narrowly.

## Clinical Validation and Rule Integration

After grounding, every item must pass through:

```python
validate_clinical_item(item)
```

Decision handling:

- `accepted`
  - Include in prediction JSON.
- `needs_review`
  - Include in prediction JSON for local evaluation.
  - Record review-required metadata in the audit sidecar.
- `rejected`
  - Exclude from prediction JSON.
  - Record the rejected candidate and findings in the audit sidecar.
- future `uncertain` or `contradiction`
  - Include only if the item itself is valid and source-grounded.
  - Record review-required metadata.

This separation matters:

- Prediction JSON represents the harness output after deterministic guardrails.
- Audit JSON records what the model attempted and what the guardrails rejected.

Evaluation should be able to measure both:

- final extractor quality through `predictions_llm/*.predicted.json`;
- model failure patterns through audit sidecars and comparison reports.

## Confidence and Review Routing

LLM self-confidence is not calibrated. Treat it as a weak triage signal, not a
truth probability.

First-pass rules:

- Model responses should include `confidence`.
- Parser should reject non-numeric confidence values.
- Confidence must be between `0.0` and `1.0`.
- `validate_clinical_item` routes confidence below `0.75` to review.
- Missing confidence should be allowed only if the provider cannot produce it;
  in that case, audit metadata should count `missing_confidence_count`.

Future calibration work:

- Compare confidence buckets against golden-set correctness.
- Report calibration curves only after enough synthetic examples exist.
- Do not claim medical-grade confidence calibration.

## JSON Parsing, Repair, and Rejection Policy

First implementation:

- Strict `json.loads`.
- No markdown fence stripping.
- No best-effort regex extraction.
- No automatic type coercion beyond existing normalization helpers.
- No automatic repair call.
- Clear errors for malformed JSON and schema drift.

Later implementation may add one explicit repair pass:

- The repair prompt receives only the invalid JSON and schema errors.
- It must not receive golden expected labels.
- Repaired output must pass the same strict parser.
- Raw and repaired responses must both be captured in audit metadata.
- Repair must be configurable and disabled in deterministic tests.

The default posture is reject, not repair.

## Error Handling and Failure Modes

Expected failure categories:

- missing note file
- missing credentials
- provider timeout
- provider rate limit
- provider invalid response
- malformed JSON
- schema version mismatch
- unknown item type
- unknown status
- bad confidence
- source quote not found
- source quote ambiguous
- section ID mismatch
- clinical rule rejection
- output file exists without `--overwrite`
- output write failure

CLI behavior:

- Return exit code `1` for unrecoverable run errors.
- Print concise errors to stderr.
- Print per-document summaries to stdout.
- If processing all notes, one document failure should be configurable:
  - default first implementation: fail the run;
  - future `--continue-on-error`: write audit failures and continue.

## Idempotency and Reproducibility

For a fixed provider response, the harness output must be deterministic.

Requirements:

- Process notes in sorted order.
- Sort final items by `(source_start_char, source_end_char, type, name, status)`.
- Use stable JSON indentation.
- Refuse to overwrite existing prediction files unless `--overwrite` is set.
- Include extractor version, prompt version, provider, and model in metadata.
- Include prompt and raw response hashes in audit sidecars.
- Set provider temperature or equivalent sampling controls to deterministic
  values where supported.

Do not promise bit-for-bit reproducibility for live LLM calls. Instead, make
each run auditable enough to explain.

## Evaluation Flow

Primary local evaluation:

```bash
python3 scripts/run_ai_extractor.py --overwrite
python3 scripts/eval_golden.py --predictions-dir predictions_llm
python3 scripts/report_ai_errors.py
```

If `report_ai_errors.py` is not implemented yet, use:

```bash
python3 scripts/eval_golden.py --predictions-dir predictions_llm
```

Single-note development loop:

```bash
python3 scripts/run_ai_extractor.py --document-id note_001 --overwrite
python3 scripts/eval_golden.py --predictions-dir predictions_llm --document-id note_001
```

The extractor must not inspect `golden_set/expected`. Only evaluation scripts
read expected labels.

## Baseline vs AI Comparison Plan

Use the existing comparison script after AI predictions are written:

```text
scripts/compare_prediction_runs.py
```

Suggested command:

```bash
python3 scripts/compare_prediction_runs.py \
  --left-name baseline \
  --left-dir predictions_baseline \
  --right-name llm \
  --right-dir predictions_llm
```

Comparison output:

- aggregate counts for both runs
- deltas for matched, missing, extra, invalid traps, and source failures
- precision and recall derived from current counts
- per-document deltas
- missing-by-type deltas
- extra-by-type deltas
- source-grounding failure deltas
- clinical-rule rejection counts from AI audit sidecars

Do not modify `scripts/eval_golden.py` just to support comparison. Prefer
reusing `evaluate_prediction_files`.

## Metrics to Report

Existing evaluator metrics:

- `notes_evaluated`
- `expected_item_count`
- `predicted_item_count`
- `matched_item_count`
- `missing_item_count`
- `extra_item_count`
- `invalid_trap_hit_count`
- `source_quote_failure_count`

Derived evaluation metrics:

- precision: `matched_item_count / predicted_item_count`
- recall: `matched_item_count / expected_item_count`
- F1 when both precision and recall are defined
- valid source span rate:
  `(predicted_item_count - source_quote_failure_count) / predicted_item_count`
- invalid trap rate:
  `invalid_trap_hit_count / predicted_item_count`

AI harness operational metrics:

- provider latency per document
- candidate count
- accepted count
- needs-review count
- rejected-by-schema count
- rejected-by-grounding count
- rejected-by-rules count
- malformed-response count
- provider-error count
- token counts when provider supplies them

AI harness safety metrics:

- rejected negated active conditions
- rejected family-history patient conditions
- rejected performed procedures that were not performed
- rejected referral-as-procedure items
- rejected active medications that were stopped/discontinued/held
- low-confidence review route count

## Security and Privacy Assumptions

This milestone is for synthetic/demo data only.

Security requirements:

- Do not send real patient data to any provider.
- Do not log credentials.
- Do not print full prompts by default.
- Raw prompts and raw responses may contain note text. Store them only in local
  audit files when explicitly enabled or hash them by default.
- Do not commit provider credentials.
- Keep `.env`-style files untracked.
- Treat provider request IDs as diagnostic metadata, not secrets.

Privacy posture:

- The first implementation may call an external provider only for synthetic
  notes.
- Any future real-data use would require a separate privacy, compliance, and
  deployment review. That is outside this project scope.

## Observability and Local Logging

CLI stdout should be concise and script-friendly:

```text
document_id: note_001, candidate_count: 18, accepted_count: 14, needs_review_count: 2, rejected_count: 2, output_path: /.../predictions_llm/note_001.predicted.json
documents_processed: 1
total_candidates: 18
total_items: 16
total_rejected: 2
```

CLI stderr should contain errors only.

Audit sidecars should hold structured detail:

- provider and model
- prompt version
- parser version
- extraction version
- prompt hash
- response hash
- counts
- rule findings
- rejected candidates
- failure reasons
- latency
- token counts when available

The runner should avoid noisy logs that make tests brittle.

## Testing Plan

### Unit Tests

`processor/tests/test_ai_extraction_prompt.py`

- prompt includes supported item types and statuses
- prompt includes section IDs and section names
- prompt includes raw section text
- prompt does not include golden expected labels
- prompt instructs no medical advice and source-only extraction
- prompt forbids model-generated offsets

`processor/tests/test_ai_extraction_response.py`

- parses valid response JSON
- rejects markdown-fenced JSON
- rejects unknown schema version
- rejects document ID mismatch
- rejects non-list `items`
- rejects unknown item type
- rejects unknown status
- rejects missing source quote
- rejects model-provided offsets
- rejects confidence outside `0.0` to `1.0`
- normalizes names, item types, and statuses

`processor/tests/test_ai_extraction_grounding.py`

- grounds a candidate to exact raw offsets inside the declared section
- rejects source quote not found
- rejects source quote found in a different section
- rejects ambiguous duplicate quote in the same section
- validates resulting `ExtractedClinicalItem`
- excludes clinical-rule rejected items from final predictions
- preserves needs-review items while marking audit metadata
- sorts final items deterministically

`processor/tests/test_run_ai_extractor_script.py`

- fixture provider writes prediction JSON for one temp note
- output top-level fields match `prediction-format-v1`
- output parses through `predicted_items_from_json`
- generated source spans are exact
- runner does not read expected JSON
- existing output requires `--overwrite`
- missing note returns clear error
- provider failure returns clear error
- real provider tests are skipped unless configured

`processor/tests/test_ai_extraction_audit.py`

- successful-run audit records rejected candidates and rule findings
- schema-failure audit records `rejected_by_schema_count`
- audit hashes prompt and raw response content

`processor/tests/test_prediction_format.py`

- prediction JSON preserves the shared `prediction-format-v1` contract
- optional status and confidence fields are omitted when absent
- final prediction items are sorted deterministically

`processor/tests/test_llm_provider.py`

- fixture provider returns deterministic candidate JSON
- Gemini provider builds requests and parses output text
- Gemini credential failures are explicit and testable

### Regression Tests

Use a fixture provider with static responses for:

- negated symptom
- family history
- stopped medication
- not-performed procedure
- referral/order
- uncertain mention
- malformed JSON
- ungrounded quote

Regression tests should not depend on live LLM output.

### Evaluation Acceptance

For the first implementation commit:

```bash
python3 -m unittest \
  processor.tests.test_ai_extraction_prompt \
  processor.tests.test_ai_extraction_response \
  processor.tests.test_ai_extraction_grounding \
  processor.tests.test_run_ai_extractor_script \
  processor.tests.test_eval_golden_script \
  processor.tests.test_evaluation \
  processor.tests.test_clinical_rules \
  processor.tests.test_source_spans \
  processor.tests.test_sectioning \
  processor.tests.test_ai_extraction_audit \
  processor.tests.test_prediction_format \
  processor.tests.test_llm_provider \
  processor.tests.test_compare_prediction_runs_script \
  -v
```

Then:

```bash
python3 scripts/run_ai_extractor.py --provider fixture --document-id note_001 --overwrite
python3 scripts/eval_golden.py --predictions-dir predictions_llm --document-id note_001
```

If a real provider adapter is included:

```bash
python3 scripts/run_ai_extractor.py --provider gemini --document-id note_001 --overwrite
python3 scripts/eval_golden.py --predictions-dir predictions_llm --document-id note_001
```

The real-provider command may be skipped in CI/local tests when credentials are
not configured.

## Rollout Phases

### Phase 0: Spec - Complete

- Add this document.
- No code.

### Phase 1: Harness Skeleton with Fixture Provider - Complete

- Prompt builder.
- Strict response parser.
- Section-aware source grounding.
- Clinical-rule integration.
- Fixture provider.
- CLI runner.
- Tests.
- One-note fixture extraction path.
- Shared prediction serialization.
- Audit sidecar serialization.
- Schema-failure audit behavior.
- Deterministic prediction sorting.

Acceptance:

- No network required.
- Prediction output is compatible with `eval_golden.py`.
- Source quote failures are zero for fixture output.
- The extractor does not read expected labels.

### Phase 2: Real Provider Adapter - Complete

- Add Gemini provider adapter behind `LlmProvider`.
- Add credential/config error handling.
- Add timeout handling.
- Add raw response hash and provider metadata.
- Keep tests fixture-based.

Acceptance:

- Single-note run works when credentials are configured.
- Missing credentials fail clearly.
- No provider-specific code enters `processor/src/domain/`.

### Phase 3: Golden Set Run and Baseline Comparison - Next

- Run all 10 golden notes into `predictions_llm/`.
- Evaluate with `scripts/eval_golden.py`.
- Use `scripts/compare_prediction_runs.py`.
- Report baseline vs AI deltas.
- Inspect audit sidecars for schema, grounding, and rule failures.

Acceptance:

- The AI run produces diagnostically useful output even if it does not beat the
  baseline.
- Source quote failures remain visible and must not be hidden.
- Invalid trap hits remain visible and must not be hidden.

### Phase 4: Review-Oriented Output

- Preserve review-required items in audit metadata.
- Prepare future review queue data shape.
- Do not build the UI yet.

Note: basic `needs_review` audit recording exists. The future work is a
review-oriented data shape that can feed an end-to-end UI or backend.

### Phase 5: Backend Worker Integration

- Only after the local harness is credible.
- Move provider execution into worker/service boundaries.
- Preserve the same domain parser, grounding, validation, and eval contracts.

## Acceptance Criteria for the First Implementation Commit

Status: satisfied by the current local harness implementation.

The first implementation commit should be named something like:

```text
extractor: add ai harness skeleton
```

It is accepted when:

- `docs/ai_extraction_harness.md` exists and remains consistent with code.
- `scripts/run_ai_extractor.py` exists.
- The runner supports `--document-id`, `--notes-dir`, `--output-dir`,
  `--provider`, and `--overwrite`.
- A fixture provider can produce deterministic candidate JSON.
- The harness writes `predictions_llm/{document_id}.predicted.json`.
- The prediction file uses `prediction-format-v1`.
- The prediction file parses through `predicted_items_from_json`.
- Source spans are locally computed and exact.
- Model-generated offsets are rejected.
- Clinical-rule rejected items are excluded from final predictions and recorded
  in audit metadata.
- The runner does not read `golden_set/expected`.
- Focused unit tests pass.
- Existing evaluation, clinical rules, source spans, and sectioning tests still
  pass.

Do not require the first implementation commit to beat the deterministic
baseline. The first commit proves architecture, safety, and evaluability.

## Risks and Mitigations

### Risk: The project becomes a GPT wrapper

Mitigation:

- Keep schema parsing, grounding, validation, and evaluation local.
- Do not trust model offsets.
- Do not accept ungrounded items.

### Risk: Golden-set leakage

Mitigation:

- The extraction runner must never read `golden_set/expected`.
- Prompt tests should assert expected-label content is absent.
- Only evaluation scripts read expected labels.

### Risk: Model paraphrases source quotes

Mitigation:

- Reject candidates whose quote does not match raw section text exactly.
- Record rejection in audit metadata.
- Improve prompt only after measuring failure patterns.

### Risk: Model extracts unsafe positive findings

Mitigation:

- Run deterministic clinical rules after grounding.
- Exclude hard-rejected items from final predictions.
- Keep rejected model attempts in audit sidecars.

### Risk: Live LLM output makes tests flaky

Mitigation:

- Unit tests use fixture providers only.
- Real provider smoke tests are opt-in.
- Prediction outputs from live models are not committed unless explicitly
  reviewed.

### Risk: Too much abstraction too early

Mitigation:

- Keep provider protocol minimal.
- Avoid backend, database, worker, and UI work in this milestone.
- Add comparison reporting only after first prediction files exist.

### Risk: Source quote duplicate ambiguity

Mitigation:

- Require section ID in model output.
- Reject duplicate exact quotes inside the same section in the first version.
- Add deterministic disambiguation only if the golden set shows it is needed.

### Risk: Confidence is misleading

Mitigation:

- Treat confidence as review triage only.
- Do not claim calibration.
- Measure confidence behavior later against golden correctness.

## Resolved Decisions

- The first real provider adapter is Gemini and belongs to Phase 2.
- Malformed JSON is a hard-fail in the current implementation. The runner writes
  a schema-failure audit sidecar and does not write a prediction file.
- Audit sidecars store hashes by default, not raw prompt or raw response text.
- Baseline-vs-AI comparison metrics live in `scripts/compare_prediction_runs.py`.

## Open Decisions

- Should a later version add an optional repair call after malformed JSON, or
  keep hard-fail behavior permanently?
- Should `needs_review` items be included in prediction files or separated once
  a review queue exists?
- Should `predictions_llm/` be committed, or should only selected fixture
  outputs be committed?
- Should AI candidate parsing preserve type-specific fields such as dose,
  frequency, unit, relation, and date in a later schema version?
- Should `--dry-run`, `--save-audit`, and `--continue-on-error` be added before
  end-to-end product work, or deferred until the local UI/backend path exists?

## Recommended Next Prompt

For the next local harness pass, use:

```text
Run Phase 3 of docs/ai_extraction_harness.md.

Use the existing Gemini provider and local eval scripts to run a controlled
3-note, then 10-note, AI extraction evaluation against synthetic golden notes.
Do not modify golden_set expected labels. Do not tune prompts until the report
identifies whether failures are schema, grounding, clinical rules, missing
items, or extra items. Produce a concise baseline-vs-AI comparison summary and
recommend the next implementation slice.
```
