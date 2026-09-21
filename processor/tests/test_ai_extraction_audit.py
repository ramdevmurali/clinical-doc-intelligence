import json
import unittest

from processor.src.domain.ai_extraction_audit import (
    audit_json_for_run,
    audit_json_for_schema_failure,
    extractor_metadata,
)
from processor.src.domain.ai_extraction_grounding import ground_ai_candidates
from processor.src.domain.ai_extraction_prompt import PromptMessage
from processor.src.domain.ai_extraction_response import (
    AI_EXTRACTION_RESPONSE_SCHEMA_VERSION,
    AiCandidateItem,
)
from processor.src.domain.extraction_schema import ClinicalItemType
from processor.src.domain.sectioning import parse_sections


class AiExtractionAuditTests(unittest.TestCase):
    def test_audit_json_preserves_rejected_candidates_and_findings(self) -> None:
        raw_text = "Assessment:\nHypertension.\nStable. Stable.\n\nMedications:\nMetformin was discontinued.\n"
        sections = tuple(parse_sections(raw_text, document_id="note_test"))
        candidates = (
            AiCandidateItem(
                item_type=ClinicalItemType.CONDITION,
                name="stable",
                status="present",
                confidence=0.95,
                source_quote="Stable.",
                section_id="note_test:section:001",
                section_name="Assessment",
            ),
            AiCandidateItem(
                item_type=ClinicalItemType.MEDICATION,
                name="metformin",
                status="active",
                confidence=0.95,
                source_quote="Metformin was discontinued.",
                section_id="note_test:section:002",
                section_name="Medications",
            ),
        )
        grounding_result = ground_ai_candidates(
            raw_text=raw_text,
            sections=sections,
            candidates=candidates,
        )
        response_content = json.dumps(
            {
                "schema_version": AI_EXTRACTION_RESPONSE_SCHEMA_VERSION,
                "document_id": "note_test",
                "items": [],
            }
        )
        extractor = extractor_metadata(
            provider_name="fixture",
            model="fixture-model",
            extractor_name="llm-harness",
            extractor_version="ai-extractor-v1",
            prompt_version="ai-extraction-prompt-v1",
        )

        audit = audit_json_for_run(
            document_id="note_test",
            extractor=extractor,
            messages=(PromptMessage(role="user", content="Document ID: note_test"),),
            raw_response_content=response_content,
            latency_ms=12,
            input_tokens=10,
            output_tokens=5,
            request_id="fixture:note_test",
            candidates=candidates,
            grounding_result=grounding_result,
        )

        self.assertEqual(extractor, audit["extractor"])
        self.assertEqual(2, audit["counts"]["candidate_count"])
        self.assertEqual(1, audit["counts"]["rejected_by_grounding_count"])
        self.assertEqual(1, audit["counts"]["rejected_by_rules_count"])
        self.assertEqual("Stable.", audit["failures"][0]["candidate"]["source_quote"])
        self.assertEqual("Metformin was discontinued.", audit["failures"][1]["candidate"]["source_quote"])
        self.assertEqual("RULE_INACTIVE_MEDICATION_NOT_ACTIVE", audit["validation_findings"][0]["rule_id"])
        self.assertEqual("error", audit["validation_findings"][0]["severity"])
        self.assertEqual(64, len(audit["prompt_sha256"]))
        self.assertEqual(64, len(audit["raw_response_sha256"]))
        self.assertEqual("fixture:note_test", audit["request_id"])
        self.assertEqual(10, audit["input_tokens"])
        self.assertEqual(5, audit["output_tokens"])

    def test_schema_failure_audit_records_failed_parse_without_candidates(self) -> None:
        extractor = extractor_metadata(
            provider_name="fixture",
            model="fixture-model",
            extractor_name="llm-harness",
            extractor_version="ai-extractor-v1",
            prompt_version="ai-extraction-prompt-v1",
        )

        audit = audit_json_for_schema_failure(
            document_id="note_test",
            extractor=extractor,
            messages=(PromptMessage(role="user", content="Document ID: note_test"),),
            raw_response_content="{not json",
            latency_ms=7,
            input_tokens=4,
            output_tokens=3,
            request_id="fixture:note_test",
            reason="response is not valid JSON",
        )

        self.assertEqual(0, audit["counts"]["candidate_count"])
        self.assertEqual(1, audit["counts"]["rejected_by_schema_count"])
        self.assertEqual(0, audit["counts"]["rejected_by_grounding_count"])
        self.assertEqual(0, audit["counts"]["rejected_by_rules_count"])
        self.assertEqual("schema_parse", audit["failures"][0]["stage"])
        self.assertIsNone(audit["failures"][0]["candidate_index"])
        self.assertEqual("response is not valid JSON", audit["failures"][0]["reason"])
        self.assertEqual([], audit["validation_findings"])
        self.assertEqual(64, len(audit["prompt_sha256"]))
        self.assertEqual(64, len(audit["raw_response_sha256"]))


if __name__ == "__main__":
    unittest.main()
