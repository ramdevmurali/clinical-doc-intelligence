import unittest

from processor.src.domain.ai_extraction_grounding import (
    AiExtractionGroundingError,
    ground_ai_candidates,
)
from processor.src.domain.ai_extraction_response import AiCandidateItem
from processor.src.domain.extraction_schema import ClinicalItemType
from processor.src.domain.sectioning import parse_sections


class AiExtractionGroundingTests(unittest.TestCase):
    def test_grounding_computes_exact_offsets_inside_declared_section(self) -> None:
        raw_text = "Past Medical History:\nHypertension.\n"
        sections = tuple(parse_sections(raw_text, document_id="note_test"))
        candidate = self.candidate(source_quote="Hypertension.")

        result = ground_ai_candidates(raw_text=raw_text, sections=sections, candidates=(candidate,))

        self.assertEqual(1, len(result.accepted))
        self.assertEqual((), result.rejected_by_grounding)
        item = result.prediction_items[0]
        self.assertEqual(22, item.source_start_char)
        self.assertEqual(35, item.source_end_char)
        self.assertEqual("Hypertension.", raw_text[item.source_start_char : item.source_end_char])
        self.assertEqual("note_test:section:001", item.section_id)

    def test_rejects_quote_outside_declared_section(self) -> None:
        raw_text = "Past Medical History:\nHypertension.\n\nAssessment:\nStable.\n"
        sections = tuple(parse_sections(raw_text, document_id="note_test"))
        candidate = self.candidate(
            source_quote="Stable.",
            section_id="note_test:section:001",
            section_name="Past Medical History",
        )

        result = ground_ai_candidates(raw_text=raw_text, sections=sections, candidates=(candidate,))

        self.assertEqual((), result.prediction_items)
        self.assertEqual(1, len(result.rejected_by_grounding))
        self.assertIn("not found", result.rejected_by_grounding[0].reason)

    def test_rejects_ambiguous_quote_inside_declared_section(self) -> None:
        raw_text = "Assessment:\nStable. Stable.\n"
        sections = tuple(parse_sections(raw_text, document_id="note_test"))
        candidate = self.candidate(
            source_quote="Stable.",
            section_id="note_test:section:001",
            section_name="Assessment",
        )

        result = ground_ai_candidates(raw_text=raw_text, sections=sections, candidates=(candidate,))

        self.assertEqual((), result.prediction_items)
        self.assertEqual(1, len(result.rejected_by_grounding))
        self.assertIn("ambiguous", result.rejected_by_grounding[0].reason)

    def test_rejects_section_name_mismatch(self) -> None:
        raw_text = "Assessment:\nHypertension.\n"
        sections = tuple(parse_sections(raw_text, document_id="note_test"))
        candidate = self.candidate(
            source_quote="Hypertension.",
            section_id="note_test:section:001",
            section_name="Past Medical History",
        )

        result = ground_ai_candidates(raw_text=raw_text, sections=sections, candidates=(candidate,))

        self.assertEqual((), result.prediction_items)
        self.assertIn("section_name mismatch", result.rejected_by_grounding[0].reason)

    def test_low_confidence_items_are_routed_to_review_but_written_to_predictions(self) -> None:
        raw_text = "Past Medical History:\nHypertension.\n"
        sections = tuple(parse_sections(raw_text, document_id="note_test"))
        candidate = self.candidate(source_quote="Hypertension.", confidence=0.5)

        result = ground_ai_candidates(raw_text=raw_text, sections=sections, candidates=(candidate,))

        self.assertEqual(0, len(result.accepted))
        self.assertEqual(1, len(result.needs_review))
        self.assertEqual(1, len(result.prediction_items))

    def test_rule_rejected_items_are_not_written_to_predictions(self) -> None:
        raw_text = "Medications:\nMetformin was discontinued.\n"
        sections = tuple(parse_sections(raw_text, document_id="note_test"))
        candidate = self.candidate(
            item_type=ClinicalItemType.MEDICATION,
            name="metformin",
            status="active",
            source_quote="Metformin was discontinued.",
            section_id="note_test:section:001",
            section_name="Medications",
        )

        result = ground_ai_candidates(raw_text=raw_text, sections=sections, candidates=(candidate,))

        self.assertEqual((), result.prediction_items)
        self.assertEqual(1, len(result.rejected_by_rules))
        self.assertIn("Discontinued", result.rejected_by_rules[0].reason)

    def test_requires_raw_text_and_sections(self) -> None:
        with self.assertRaises(AiExtractionGroundingError):
            ground_ai_candidates(raw_text="", sections=[], candidates=[])

    def candidate(
        self,
        *,
        item_type: ClinicalItemType = ClinicalItemType.CONDITION,
        name: str = "hypertension",
        status: str | None = "active",
        confidence: float | None = 0.9,
        source_quote: str = "Hypertension.",
        section_id: str = "note_test:section:001",
        section_name: str = "Past Medical History",
    ) -> AiCandidateItem:
        return AiCandidateItem(
            item_type=item_type,
            name=name,
            status=status,
            confidence=confidence,
            source_quote=source_quote,
            section_id=section_id,
            section_name=section_name,
        )


if __name__ == "__main__":
    unittest.main()
