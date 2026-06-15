# Clinical Rules

Clinical rules are deterministic guardrails around extracted clinical items. They are designed to catch high-risk extraction mistakes before human review or downstream export.

These rules are not medical advice, diagnosis, treatment recommendations, or a medical device. This project phase uses synthetic/demo data only. Real clinical use would require clinical governance, validation, monitoring, and human review.

## Scope

The current rules validate one `ExtractedClinicalItem` at a time. They operate on item type, status, source quote, section name, and confidence.

They do not perform source-span validation, name/status normalization, LLM extraction, human review, or FHIR export. Those responsibilities belong to separate domain modules or later application layers.

## Composition Behavior

Rules are evaluated in this deterministic order:

1. `RULE_NEGATED_CONDITION`
2. `RULE_FAMILY_HISTORY_NOT_PATIENT_CONDITION`
3. `RULE_PROCEDURE_NOT_PERFORMED`
4. `RULE_REFERRAL_NOT_PROCEDURE`
5. `RULE_INACTIVE_MEDICATION_NOT_ACTIVE`
6. `RULE_LOW_CONFIDENCE`

Multiple findings may be returned for a single item. Any `error` severity finding produces a final `rejected` decision. If no rejection rule fires but low confidence fires, the final decision is `needs_review`. If no findings fire, the final decision is `accepted`.

## Implemented Rules

### `RULE_NEGATED_CONDITION`

- **Catches:** Active patient conditions extracted from negated source evidence.
- **Trigger:** `item_type == condition`, `status == active`, and source quote contains one of:
  - `denies`
  - `denied`
  - `no evidence of`
  - `negative for`
  - `no history of`
  - `without`
- **Finding severity:** `error`
- **Final status:** `rejected`
- **Rejected examples:**
  - `Patient denies chest pain.`
  - `No evidence of diabetic ketoacidosis.`
- **Accepted examples:**
  - A `negative_finding` item from `Patient denies chest pain.`
  - A non-active condition from a negated quote.
- **Known limitations:** Phrase-based only. It does not model negation scope, double negatives, temporality, or section-specific clinical context beyond the listed phrases.

### `RULE_FAMILY_HISTORY_NOT_PATIENT_CONDITION`

- **Catches:** Family-history mentions incorrectly extracted as patient conditions.
- **Trigger:** `item_type == condition` and either:
  - `section_name == Family History` case-insensitive, or
  - source quote contains one of: `mother`, `father`, `sister`, `brother`, `family history`
- **Finding severity:** `error`
- **Final status:** `rejected`
- **Rejected examples:**
  - `Mother had breast cancer.`
  - `Father has coronary artery disease.`
- **Accepted examples:**
  - A `family_history` item from `Mother had breast cancer.`
  - A patient condition outside family history with neutral evidence.
- **Known limitations:** Relation detection is intentionally simple and limited to the listed terms. It does not resolve more complex kinship, family pedigrees, or ambiguous statements.

### `RULE_PROCEDURE_NOT_PERFORMED`

- **Catches:** Procedures incorrectly marked as performed when evidence says they were not completed.
- **Trigger:** `item_type == procedure`, `status == performed`, and source quote contains one of:
  - `not performed`
  - `was not performed`
  - `declined`
  - `cancelled`
  - `planned`
- **Finding severity:** `error`
- **Final status:** `rejected`
- **Rejected example:** `Circumcision was not performed.`
- **Accepted examples:**
  - A procedure with `status == not_performed` from `Circumcision was not performed.`
  - A performed procedure with neutral completed-procedure evidence.
- **Known limitations:** Phrase-based only. It does not yet distinguish every planned procedure from every completed procedure without explicit trigger phrases.

### `RULE_REFERRAL_NOT_PROCEDURE`

- **Catches:** Referrals, orders, or outpatient plans incorrectly extracted as completed/performed procedures.
- **Trigger:** `item_type == procedure`, `status == performed`, and source quote contains one of:
  - `referred for`
  - `referral for`
  - `referred to`
  - `outpatient`
  - `ordered`
- **Finding severity:** `error`
- **Final status:** `rejected`
- **Rejected example:** `Patient referred for outpatient colonoscopy.`
- **Accepted examples:**
  - An `order` item with `status == referred` from `Patient referred for outpatient colonoscopy.`
  - A performed procedure with completed-procedure evidence.
- **Known limitations:** Does not model full order lifecycle. It only guards against the current high-risk referral/order-as-completed-procedure trap.

### `RULE_INACTIVE_MEDICATION_NOT_ACTIVE`

- **Catches:** Medications incorrectly marked active when evidence says they are inactive, stopped, held, or avoided.
- **Trigger:** `item_type == medication`, `status == active`, and source quote contains one of:
  - `discontinued`
  - `stopped`
  - `held`
  - `avoid`
  - `was stopped`
- **Finding severity:** `error`
- **Final status:** `rejected`
- **Rejected example:** `Warfarin discontinued due to bleeding risk.`
- **Accepted examples:**
  - A medication with `status == discontinued` from discontinued evidence.
  - A medication with `status == held` from held evidence.
  - An active medication with neutral active-medication evidence.
- **Known limitations:** Phrase-based only. It does not handle dose changes, temporary holds without explicit wording, or medication reconciliation conflicts across multiple sections.

### `RULE_LOW_CONFIDENCE`

- **Catches:** Otherwise-valid extracted items whose confidence is below the review threshold.
- **Trigger:** `confidence is not None` and `confidence < 0.75`
- **Finding severity:** `warning`
- **Final status:** `needs_review` if no error findings are present.
- **Review threshold:** `0.75`
- **Review example:** An otherwise-valid item with `confidence == 0.74`.
- **Accepted examples:**
  - An otherwise-valid item with `confidence == 0.75`.
  - An otherwise-valid item with `confidence == 0.90`.
  - An otherwise-valid item with `confidence is None`.
- **Known limitations:** This is a fixed threshold, not calibrated confidence. It does not estimate model reliability or clinical risk.

## Golden-Set Traps Covered

The current clinical rule tests explicitly cover these golden-set traps:

- Performed circumcision trap.
- Active chest pain trap.
- Active family-history breast cancer trap.
- Performed outpatient colonoscopy referral trap.
- Active stopped apixaban trap.

These tests prove the current deterministic rules catch known invalid extraction patterns in the synthetic golden set.

## Known Limitations

- Rules are phrase-based guardrails only.
- There is no comprehensive negation model yet.
- There is no allergy denial rule yet.
- There is no rule-out or possible-diagnosis rule yet.
- There is no generic imaging-negative condition rule yet.
- Source quote span validation is not handled here; it belongs to `source_spans.py`.
- Name, item-type, and status normalization are not handled here; they belong to `normalization.py`.
- Human review and clinical validation remain required for any real-world use.
