# Extraction Schema

Clinical extraction should start with a small, explicit schema rather than free-form model output.

## Initial Entity Types

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

## Required Grounding Fields

Every extracted item must include:

- `document_id`
- `section_id`
- `source_quote`
- `source_start_char`
- `source_end_char`
- `page_number`, when available
- `confidence`

Without source grounding, the project becomes a generic GPT wrapper. With grounding, it becomes auditable clinical document intelligence.

