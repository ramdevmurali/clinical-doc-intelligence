import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import eval_golden


class EvalGoldenScriptTests(unittest.TestCase):
    def test_document_id_note_001_evaluates_manual_baseline_prediction(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = eval_golden.main(["--document-id", "note_001"])

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr.getvalue())
        output = stdout.getvalue()
        self.assertIn("Document: note_001", output)
        self.assertIn("expected_item_count:", output)
        self.assertIn("predicted_item_count: 5", output)
        self.assertIn("matched_item_count: 5", output)
        self.assertIn("source_quote_failure_count: 0", output)
        self.assertIn("Aggregate Summary", output)
        self.assertIn("notes_evaluated: 1", output)

    def test_missing_prediction_file_returns_error(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = eval_golden.main(["--document-id", "missing_note"])

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("missing prediction file", stderr.getvalue())

    def test_missing_note_file_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            expected_dir = root / "expected"
            predictions_dir = root / "predictions"
            notes_dir.mkdir()
            expected_dir.mkdir()
            predictions_dir.mkdir()

            (expected_dir / "note_missing.expected.json").write_text(
                json.dumps({"items": [], "invalid_extractions": []}),
                encoding="utf-8",
            )
            (predictions_dir / "note_missing.predicted.json").write_text(
                json.dumps({"items": []}),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            stderr = io.StringIO()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = eval_golden.main(
                    [
                        "--document-id",
                        "note_missing",
                        "--notes-dir",
                        str(notes_dir),
                        "--expected-dir",
                        str(expected_dir),
                        "--predictions-dir",
                        str(predictions_dir),
                    ]
                )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout.getvalue())
        self.assertIn("missing note file", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
