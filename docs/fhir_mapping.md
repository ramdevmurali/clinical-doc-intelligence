# FHIR-Style Mapping

Clinical Document Intelligence should implement FHIR-style exports, not a full FHIR server.

## Initial Resource Types

- `Patient`
- `Condition`
- `Procedure`
- `MedicationStatement`
- `AllergyIntolerance`
- `Observation`
- `DocumentReference`

## Mapping Rule

Only accepted or human-approved extraction items should be exported.

Each exported resource should preserve evidence where possible, especially the source quote that supports the extracted fact.
