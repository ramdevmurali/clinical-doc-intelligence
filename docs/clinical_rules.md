# Clinical Rules

Clinical validation rules are deterministic checks around model output. They are the safety-critical center of the project.

## Initial Rule Categories

- Negation rules
- Family-history rules
- Procedure-status rules
- Medication-status rules
- Order-vs-completed-action rules
- Uncertainty rules
- Date sanity rules
- Section boundary rules
- Required-field completeness rules
- Contradiction rules

## Early Acceptance Cases

- `Patient denies chest pain.` should become a negative finding, not an active condition.
- `Family history: mother had breast cancer.` should not become a patient diagnosis.
- `Circumcision was not performed.` should not become a performed procedure.
- `Referred for colonoscopy.` should become an order/referral, not a completed procedure.
- `Warfarin discontinued.` should not become an active medication.

