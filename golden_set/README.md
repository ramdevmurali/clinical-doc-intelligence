# Golden Set

This directory contains the initial manually controlled synthetic evaluation set for Clinical Document Intelligence.

The notes are synthetic and intentionally compact, but each one resembles a realistic clinical document type. The expected JSON files are the benchmark labels for extraction evaluation. They should be reviewed and edited by humans, not trusted if generated blindly by an LLM.

## Coverage

| Note | Document Type | Primary Coverage |
| --- | --- | --- |
| `note_001` | Discharge summary | active conditions, negation, family history, discontinued medication, not-performed procedure |
| `note_002` | Emergency note | rule-out diagnosis, orders, vitals, labs, administered medication |
| `note_003` | Inpatient progress note | heart failure, held/stopped medication, negative imaging, family history |
| `note_004` | Medication reconciliation | active/stopped/held meds, allergies, adverse reactions, denied allergy |
| `note_005` | Referral/procedure note | performed procedure vs not-performed procedure vs referral order |
| `note_006` | Outpatient lab follow-up | abnormal labs, vitals, negative imaging, medication change |
| `note_007` | Allergy clinic note | active allergy, incorrect chart allergy, denied allergy, prescribed medication |
| `note_008` | Pulmonary consult | uncertain mentions, differential diagnosis, negative imaging, planned follow-up |
| `note_009` | Primary care annual visit | social history, screening orders, chronic disease management, family-history traps |
| `note_010` | Post-operative discharge | performed surgery, denied complications, discharge care needs, pending pathology |

## Labeling Conventions

- `items` contains facts that should be extracted.
- `should_not_extract` contains traps that a safe extractor should avoid.
- Every extractable item includes a `source_quote` that appears verbatim in the note.
- These files use synthetic/demo data only and must not be mixed with real patient records.
