import json
import unittest

from processor.src.domain.ai_extraction_response import (
    AI_EXTRACTION_RESPONSE_SCHEMA_VERSION,
    AiExtractionResponseError,
    parse_ai_extraction_response,
)
from processor.src.domain.extraction_schema import ClinicalItemType


class AiExtractionResponseTests(unittest.TestCase):
    def test_parses_valid_candidate_response_and_normalizes_fields(self) -> None:
        response = {
            "schema_version": AI_EXTRACTION_RESPONSE_SCHEMA_VERSION,
            "document_id": "note_test",
            "items": [
                {
                    "type": "diagnosis",
                    "name": "  Hypertension  ",
                    "status": "Active",
                    "confidence": 0.91,
                    "source_quote": "Hypertension.",
                    "section_id": "note_test:section:001",
                    "section_name": "Past Medical History",
                }
            ],
        }

        items = parse_ai_extraction_response(json.dumps(response), document_id="note_test")

        self.assertEqual(1, len(items))
        self.assertEqual(ClinicalItemType.CONDITION, items[0].item_type)
        self.assertEqual("hypertension", items[0].name)
        self.assertEqual("active", items[0].status)
        self.assertEqual(0.91, items[0].confidence)

    def test_rejects_markdown_fenced_json(self) -> None:
        with self.assertRaisesRegex(AiExtractionResponseError, "markdown"):
            parse_ai_extraction_response(
                '```json\n{"schema_version": "ai-extraction-response-v1"}\n```',
                document_id="note_test",
            )

    def test_rejects_document_mismatch(self) -> None:
        response = {"schema_version": AI_EXTRACTION_RESPONSE_SCHEMA_VERSION, "document_id": "other", "items": []}

        with self.assertRaisesRegex(AiExtractionResponseError, "document_id"):
            parse_ai_extraction_response(json.dumps(response), document_id="note_test")

    def test_rejects_unknown_top_level_and_item_fields(self) -> None:
        top_level = {
            "schema_version": AI_EXTRACTION_RESPONSE_SCHEMA_VERSION,
            "document_id": "note_test",
            "items": [],
            "extra": "nope",
        }
        with self.assertRaisesRegex(AiExtractionResponseError, "unknown fields"):
            parse_ai_extraction_response(json.dumps(top_level), document_id="note_test")

        item_with_offsets = {
            "schema_version": AI_EXTRACTION_RESPONSE_SCHEMA_VERSION,
            "document_id": "note_test",
            "items": [
                {
                    "type": "condition",
                    "name": "hypertension",
                    "source_quote": "Hypertension.",
                    "section_id": "note_test:section:001",
                    "section_name": "Past Medical History",
                    "source_start_char": 22,
                }
            ],
        }
        with self.assertRaisesRegex(AiExtractionResponseError, "source_start_char"):
            parse_ai_extraction_response(json.dumps(item_with_offsets), document_id="note_test")

    def test_rejects_bad_confidence_and_unknown_status(self) -> None:
        bad_confidence = self.response_with_item(confidence=True)
        with self.assertRaisesRegex(AiExtractionResponseError, "confidence"):
            parse_ai_extraction_response(json.dumps(bad_confidence), document_id="note_test")

        bad_status = self.response_with_item(status="definitely")
        with self.assertRaisesRegex(AiExtractionResponseError, "normalization failed"):
            parse_ai_extraction_response(json.dumps(bad_status), document_id="note_test")

    def response_with_item(self, **overrides: object) -> dict:
        item = {
            "type": "condition",
            "name": "hypertension",
            "status": "active",
            "confidence": 0.9,
            "source_quote": "Hypertension.",
            "section_id": "note_test:section:001",
            "section_name": "Past Medical History",
        }
        item.update(overrides)
        return {
            "schema_version": AI_EXTRACTION_RESPONSE_SCHEMA_VERSION,
            "document_id": "note_test",
            "items": [item],
        }


if __name__ == "__main__":
    unittest.main()
