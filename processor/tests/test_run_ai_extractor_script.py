import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from processor.src.domain.ai_extraction_grounding import ground_ai_candidates
from processor.src.domain.ai_extraction_prompt import PromptMessage
from processor.src.domain.ai_extraction_response import (
    AI_EXTRACTION_RESPONSE_SCHEMA_VERSION,
    AiCandidateItem,
)
from processor.src.domain.evaluation import predicted_items_from_json
from processor.src.domain.extraction_schema import ClinicalItemType
from processor.src.domain.sectioning import parse_sections
from processor.src.services.llm_provider import LlmResponse
from scripts import run_ai_extractor


class RunAiExtractorScriptTests(unittest.TestCase):
    def test_fixture_provider_writes_prediction_format_json(self) -> None:
        stdout, stderr, exit_code, root = self.run_temp_fixture()

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("document_id: note_test", stdout)
        self.assertIn("item_count: 0", stdout)
        self.assertIn("documents_processed: 1", stdout)

        prediction = self.read_prediction(root, "note_test")
        self.assertEqual("prediction-format-v1", prediction["schema_version"])
        self.assertEqual("note_test", prediction["document_id"])
        self.assertEqual("llm-harness", prediction["extractor"]["name"])
        self.assertEqual("ai-extractor-v1", prediction["extractor"]["version"])
        self.assertEqual("fixture", prediction["extractor"]["provider"])
        self.assertEqual("fixture-model", prediction["extractor"]["model"])
        self.assertEqual("ai-extraction-prompt-v1", prediction["extractor"]["prompt_version"])
        self.assertEqual((), predicted_items_from_json(prediction))

        audit = self.read_audit(root, "note_test")
        self.assertEqual("note_test", audit["document_id"])
        self.assertEqual("llm-harness", audit["extractor"]["name"])
        self.assertEqual("fixture", audit["extractor"]["provider"])
        self.assertEqual("fixture-model", audit["extractor"]["model"])
        self.assertEqual(
            {
                "candidate_count": 0,
                "accepted_count": 0,
                "needs_review_count": 0,
                "rejected_by_schema_count": 0,
                "rejected_by_grounding_count": 0,
                "rejected_by_rules_count": 0,
            },
            audit["counts"],
        )
        self.assertEqual([], audit["failures"])
        self.assertEqual([], audit["validation_findings"])
        self.assertEqual(64, len(audit["prompt_sha256"]))
        self.assertEqual(64, len(audit["raw_response_sha256"]))
        self.assertEqual(0, audit["latency_ms"])

    def test_does_not_read_expected_json(self) -> None:
        stdout, stderr, exit_code, root = self.run_temp_fixture(create_expected_dir=False)

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("documents_processed: 1", stdout)
        self.assertTrue((root / "predictions_llm" / "note_test.predicted.json").exists())

    def test_existing_output_without_overwrite_returns_error(self) -> None:
        stdout, stderr, exit_code, _ = self.run_temp_fixture(existing_output=True)

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("prediction file already exists", stderr)

    def test_existing_audit_without_overwrite_returns_error(self) -> None:
        stdout, stderr, exit_code, _ = self.run_temp_fixture(existing_audit=True)

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("audit file already exists", stderr)

    def test_existing_output_with_overwrite_succeeds(self) -> None:
        stdout, stderr, exit_code, root = self.run_temp_fixture(existing_output=True, overwrite=True)

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("documents_processed: 1", stdout)
        self.assertTrue((root / "predictions_llm" / "note_test.predicted.json").exists())

    def test_unsupported_provider_returns_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            output_dir = root / "predictions_llm"
            notes_dir.mkdir()
            (notes_dir / "note_test.txt").write_text("Assessment:\nStable.\n", encoding="utf-8")

            stdout, stderr, exit_code = self.run_main(
                [
                    "--document-id",
                    "note_test",
                    "--notes-dir",
                    str(notes_dir),
                    "--output-dir",
                    str(output_dir),
                    "--provider",
                    "real-but-not-yet",
                ]
            )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("unsupported provider", stderr)

    def test_gemini_provider_without_api_key_returns_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_env_file = Path(temp_dir) / ".env.local"
            with patch.dict("os.environ", {}, clear=True):
                stdout, stderr, exit_code = self.run_main(
                    [
                        "--document-id",
                        "note_test",
                        "--provider",
                        "gemini",
                        "--env-file",
                        str(missing_env_file),
                    ]
                )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("GEMINI_API_KEY or GOOGLE_API_KEY is required", stderr)

    def test_load_env_file_sets_missing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env.local"
            env_file.write_text(
                "\n".join(
                    (
                        "# local credentials",
                        "GEMINI_API_KEY='test-key'",
                        'GEMINI_API_ENDPOINT="https://example.test"',
                        "export GOOGLE_API_KEY=fallback-key",
                    )
                ),
                encoding="utf-8",
            )

            with patch.dict("os.environ", {}, clear=True):
                run_ai_extractor.load_env_file(env_file)

                self.assertEqual("test-key", run_ai_extractor.os.environ["GEMINI_API_KEY"])
                self.assertEqual("https://example.test", run_ai_extractor.os.environ["GEMINI_API_ENDPOINT"])
                self.assertEqual("fallback-key", run_ai_extractor.os.environ["GOOGLE_API_KEY"])

    def test_load_env_file_does_not_override_existing_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env.local"
            env_file.write_text("GEMINI_API_KEY=file-key\n", encoding="utf-8")

            with patch.dict("os.environ", {"GEMINI_API_KEY": "existing-key"}, clear=True):
                run_ai_extractor.load_env_file(env_file)

                self.assertEqual("existing-key", run_ai_extractor.os.environ["GEMINI_API_KEY"])

    def test_load_env_file_rejects_invalid_line(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_file = Path(temp_dir) / ".env.local"
            env_file.write_text("not valid\n", encoding="utf-8")

            with self.assertRaisesRegex(run_ai_extractor.AiExtractorRunnerError, "expected KEY=VALUE"):
                run_ai_extractor.load_env_file(env_file)

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

        audit = run_ai_extractor.audit_json_for_run(
            document_id="note_test",
            provider_name="fixture",
            model="fixture-model",
            messages=(PromptMessage(role="user", content="Document ID: note_test"),),
            response=LlmResponse(
                provider="fixture",
                model="fixture-model",
                content=response_content,
                latency_ms=12,
                input_tokens=10,
                output_tokens=5,
                request_id="fixture:note_test",
            ),
            candidates=candidates,
            grounding_result=grounding_result,
        )

        self.assertEqual(2, audit["counts"]["candidate_count"])
        self.assertEqual(1, audit["counts"]["rejected_by_grounding_count"])
        self.assertEqual(1, audit["counts"]["rejected_by_rules_count"])
        self.assertEqual("Stable.", audit["failures"][0]["candidate"]["source_quote"])
        self.assertEqual("Metformin was discontinued.", audit["failures"][1]["candidate"]["source_quote"])
        self.assertEqual("RULE_INACTIVE_MEDICATION_NOT_ACTIVE", audit["validation_findings"][0]["rule_id"])
        self.assertEqual("error", audit["validation_findings"][0]["severity"])
        self.assertEqual("fixture:note_test", audit["request_id"])
        self.assertEqual(10, audit["input_tokens"])
        self.assertEqual(5, audit["output_tokens"])

    def test_processes_real_note_001_with_fixture_provider(self) -> None:
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "predictions_llm"

            stdout, stderr, exit_code = self.run_main(
                [
                    "--document-id",
                    "note_001",
                    "--notes-dir",
                    str(root / "golden_set" / "notes"),
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(0, exit_code)
            self.assertEqual("", stderr)
            self.assertIn("document_id: note_001", stdout)
            prediction = json.loads((output_dir / "note_001.predicted.json").read_text(encoding="utf-8"))
            self.assertEqual("note_001", prediction["document_id"])
            self.assertEqual((), predicted_items_from_json(prediction))

    def run_temp_fixture(
        self,
        *,
        existing_output: bool = False,
        existing_audit: bool = False,
        overwrite: bool = False,
        create_expected_dir: bool = True,
    ) -> tuple[str, str, int, Path]:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        notes_dir = root / "notes"
        output_dir = root / "predictions_llm"
        notes_dir.mkdir()
        output_dir.mkdir()
        if create_expected_dir:
            (root / "expected").mkdir()
            (root / "expected" / "note_test.expected.json").write_text("not json", encoding="utf-8")

        (notes_dir / "note_test.txt").write_text("Past Medical History:\nHypertension.\n", encoding="utf-8")
        output_path = output_dir / "note_test.predicted.json"
        if existing_output:
            output_path.write_text("{}", encoding="utf-8")
        audit_path = output_dir / "note_test.audit.json"
        if existing_audit:
            audit_path.write_text("{}", encoding="utf-8")

        argv = [
            "--document-id",
            "note_test",
            "--notes-dir",
            str(notes_dir),
            "--output-dir",
            str(output_dir),
        ]
        if overwrite:
            argv.append("--overwrite")

        stdout, stderr, exit_code = self.run_main(argv)
        return stdout, stderr, exit_code, root

    def run_main(self, argv: list[str]) -> tuple[str, str, int]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = run_ai_extractor.main(argv)
        return stdout.getvalue(), stderr.getvalue(), exit_code

    def read_prediction(self, root: Path, document_id: str) -> dict:
        prediction_path = root / "predictions_llm" / f"{document_id}.predicted.json"
        return json.loads(prediction_path.read_text(encoding="utf-8"))

    def read_audit(self, root: Path, document_id: str) -> dict:
        audit_path = root / "predictions_llm" / f"{document_id}.audit.json"
        return json.loads(audit_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
