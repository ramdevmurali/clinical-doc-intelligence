import unittest

from processor.src.domain.ai_extraction_prompt import (
    AI_EXTRACTION_PROMPT_VERSION,
    AiExtractionPromptError,
    build_ai_extraction_messages,
)
from processor.src.domain.sectioning import parse_sections


class AiExtractionPromptTests(unittest.TestCase):
    def test_builds_schema_first_messages_from_sections(self) -> None:
        raw_text = "Past Medical History:\nHypertension.\n"
        sections = parse_sections(raw_text, document_id="note_test")

        messages = build_ai_extraction_messages(
            document_id="note_test",
            raw_text=raw_text,
            sections=sections,
        )

        self.assertEqual(AI_EXTRACTION_PROMPT_VERSION, "ai-extraction-prompt-v1")
        self.assertEqual(("system", "user"), tuple(message.role for message in messages))
        joined = "\n".join(message.content for message in messages)
        self.assertIn("synthetic/demo clinical notes", joined)
        self.assertIn("not medical advice", joined)
        self.assertIn("Document ID: note_test", joined)
        self.assertIn("note_test:section:001", joined)
        self.assertIn("Past Medical History", joined)
        self.assertIn("Hypertension.", joined)
        self.assertIn("ai-extraction-response-v1", joined)

    def test_prompt_forbids_model_offsets_and_medical_advice(self) -> None:
        raw_text = "Assessment:\nPossible pneumonia.\n"
        sections = parse_sections(raw_text, document_id="note_test")

        messages = build_ai_extraction_messages(
            document_id="note_test",
            raw_text=raw_text,
            sections=sections,
        )

        joined = "\n".join(message.content for message in messages)
        self.assertIn("Do not emit source_start_char or source_end_char", joined)
        self.assertIn("Do not include validation status", joined)
        self.assertIn("Do not infer missing diagnoses", joined)

    def test_rejects_empty_inputs(self) -> None:
        with self.assertRaises(AiExtractionPromptError):
            build_ai_extraction_messages(document_id="", raw_text="text", sections=[])
        with self.assertRaises(AiExtractionPromptError):
            build_ai_extraction_messages(document_id="note", raw_text=" ", sections=[])


if __name__ == "__main__":
    unittest.main()
