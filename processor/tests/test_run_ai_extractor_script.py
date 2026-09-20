import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from processor.src.domain.evaluation import predicted_items_from_json
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


if __name__ == "__main__":
    unittest.main()
