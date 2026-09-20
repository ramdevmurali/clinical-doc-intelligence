import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import compare_prediction_runs


class ComparePredictionRunsScriptTests(unittest.TestCase):
    def test_compares_aggregate_counts_and_deltas(self) -> None:
        stdout, stderr, exit_code = self.run_temp_fixture(
            documents=[
                self.document_fixture(
                    document_id="note_a",
                    raw_text="Hypertension. Metformin.",
                    expected_items=[
                        self.expected_item(
                            item_type="condition",
                            name="hypertension",
                            source_quote="Hypertension.",
                        ),
                        self.expected_item(
                            item_type="medication",
                            name="metformin",
                            source_quote="Metformin.",
                        ),
                    ],
                    left_items=[
                        self.prediction_item(
                            item_type="condition",
                            name="hypertension",
                            source_quote="Hypertension.",
                            source_start_char=0,
                        )
                    ],
                    right_items=[
                        self.prediction_item(
                            item_type="condition",
                            name="hypertension",
                            source_quote="Hypertension.",
                            source_start_char=0,
                        ),
                        self.prediction_item(
                            item_type="medication",
                            name="metformin",
                            source_quote="Metformin.",
                            source_start_char=len("Hypertension. "),
                        ),
                    ],
                )
            ]
        )

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("Prediction Run Comparison", stdout)
        self.assertIn("matched_item_count: 1 -> 2 (delta +1)", stdout)
        self.assertIn("missing_item_count: 1 -> 0 (delta -1)", stdout)
        self.assertIn("predicted_item_count: 1 -> 2 (delta +1)", stdout)

    def test_prints_derived_metrics(self) -> None:
        stdout, _, exit_code = self.run_temp_fixture(
            documents=[
                self.document_fixture(
                    document_id="note_a",
                    raw_text="Hypertension. Metformin.",
                    expected_items=[
                        self.expected_item(item_type="condition", name="hypertension"),
                        self.expected_item(item_type="medication", name="metformin"),
                    ],
                    left_items=[
                        self.prediction_item(item_type="condition", name="hypertension"),
                    ],
                    right_items=[
                        self.prediction_item(item_type="condition", name="hypertension"),
                        self.prediction_item(item_type="procedure", name="appendectomy"),
                    ],
                )
            ]
        )

        self.assertEqual(0, exit_code)
        self.assertIn("Derived Metrics:", stdout)
        self.assertIn("precision: 1.0000 -> 0.5000 (delta -0.5000)", stdout)
        self.assertIn("recall: 0.5000 -> 0.5000 (delta +0.0000)", stdout)
        self.assertIn("f1: 0.6667 -> 0.5000 (delta -0.1667)", stdout)

    def test_prints_per_document_and_type_deltas(self) -> None:
        stdout, _, exit_code = self.run_temp_fixture(
            documents=[
                self.document_fixture(
                    document_id="note_a",
                    raw_text="Hypertension. Metformin. Appendectomy.",
                    expected_items=[
                        self.expected_item(item_type="condition", name="hypertension"),
                        self.expected_item(item_type="medication", name="metformin"),
                    ],
                    left_items=[
                        self.prediction_item(item_type="condition", name="hypertension"),
                    ],
                    right_items=[
                        self.prediction_item(item_type="condition", name="hypertension"),
                        self.prediction_item(item_type="procedure", name="appendectomy"),
                    ],
                )
            ]
        )

        self.assertEqual(0, exit_code)
        self.assertIn("Per-Document Deltas:", stdout)
        self.assertIn(
            "note_a: matched=+0, missing=+0, extra=+1, invalid_trap_hits=+0, source_quote_failures=+0",
            stdout,
        )
        self.assertIn("Missing By Type Delta:", stdout)
        self.assertIn("  medication: left=1, right=1, delta=+0", stdout)
        self.assertIn("Extra By Type Delta:", stdout)
        self.assertIn("  procedure: left=0, right=1, delta=+1", stdout)

    def test_document_id_limits_comparison_to_one_note(self) -> None:
        stdout, _, exit_code = self.run_temp_fixture(
            document_id="note_b",
            documents=[
                self.document_fixture(
                    document_id="note_a",
                    raw_text="Hypertension.",
                    expected_items=[self.expected_item(item_type="condition", name="hypertension")],
                    left_items=[],
                    right_items=[],
                ),
                self.document_fixture(
                    document_id="note_b",
                    raw_text="Metformin.",
                    expected_items=[self.expected_item(item_type="medication", name="metformin")],
                    left_items=[],
                    right_items=[],
                ),
            ],
        )

        self.assertEqual(0, exit_code)
        self.assertIn("notes_evaluated: 1 -> 1", stdout)
        self.assertIn("note_b:", stdout)
        self.assertNotIn("note_a:", stdout)

    def test_mismatched_prediction_sets_return_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            expected_dir = root / "expected"
            left_dir = root / "left"
            right_dir = root / "right"
            notes_dir.mkdir()
            expected_dir.mkdir()
            left_dir.mkdir()
            right_dir.mkdir()
            self.write_prediction(left_dir, "note_a", [])

            stdout, stderr, exit_code = self.run_main(
                [
                    "--notes-dir",
                    str(notes_dir),
                    "--expected-dir",
                    str(expected_dir),
                    "--left-dir",
                    str(left_dir),
                    "--right-dir",
                    str(right_dir),
                ]
            )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("no prediction files found", stderr)

    def test_missing_right_counterpart_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            expected_dir = root / "expected"
            left_dir = root / "left"
            right_dir = root / "right"
            notes_dir.mkdir()
            expected_dir.mkdir()
            left_dir.mkdir()
            right_dir.mkdir()
            self.write_prediction(left_dir, "note_a", [])
            self.write_prediction(right_dir, "note_b", [])

            stdout, stderr, exit_code = self.run_main(
                [
                    "--notes-dir",
                    str(notes_dir),
                    "--expected-dir",
                    str(expected_dir),
                    "--left-dir",
                    str(left_dir),
                    "--right-dir",
                    str(right_dir),
                ]
            )

        self.assertEqual(1, exit_code)
        self.assertEqual("", stdout)
        self.assertIn("missing right predictions for: note_a", stderr)
        self.assertIn("right predictions without left match: note_b", stderr)

    def test_real_baseline_and_llm_note_001_compare_if_present(self) -> None:
        root = Path(__file__).resolve().parents[2]
        if not (root / "predictions_baseline" / "note_001.predicted.json").exists():
            self.skipTest("baseline note_001 prediction is not present")
        if not (root / "predictions_llm" / "note_001.predicted.json").exists():
            self.skipTest("llm note_001 prediction is not present")

        stdout, stderr, exit_code = self.run_main(["--document-id", "note_001"])

        self.assertEqual(0, exit_code)
        self.assertEqual("", stderr)
        self.assertIn("Prediction Run Comparison", stdout)
        self.assertIn("note_001:", stdout)

    def run_temp_fixture(
        self,
        *,
        documents: list[dict],
        document_id: str | None = None,
    ) -> tuple[str, str, int]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            notes_dir = root / "notes"
            expected_dir = root / "expected"
            left_dir = root / "left"
            right_dir = root / "right"
            notes_dir.mkdir()
            expected_dir.mkdir()
            left_dir.mkdir()
            right_dir.mkdir()

            for document in documents:
                (notes_dir / f"{document['document_id']}.txt").write_text(
                    document["raw_text"],
                    encoding="utf-8",
                )
                self.write_expected(
                    expected_dir,
                    document["document_id"],
                    document["expected_items"],
                    document["invalid_extractions"],
                )
                self.write_prediction(left_dir, document["document_id"], document["left_items"])
                self.write_prediction(right_dir, document["document_id"], document["right_items"])

            argv = [
                "--left-name",
                "baseline",
                "--left-dir",
                str(left_dir),
                "--right-name",
                "llm",
                "--right-dir",
                str(right_dir),
                "--notes-dir",
                str(notes_dir),
                "--expected-dir",
                str(expected_dir),
            ]
            if document_id:
                argv.extend(["--document-id", document_id])
            return self.run_main(argv)

    def run_main(self, argv: list[str]) -> tuple[str, str, int]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = compare_prediction_runs.main(argv)
        return stdout.getvalue(), stderr.getvalue(), exit_code

    def document_fixture(
        self,
        *,
        document_id: str,
        raw_text: str,
        expected_items: list[dict] | None = None,
        left_items: list[dict] | None = None,
        right_items: list[dict] | None = None,
        invalid_extractions: list[dict] | None = None,
    ) -> dict:
        return {
            "document_id": document_id,
            "raw_text": raw_text,
            "expected_items": expected_items or [],
            "left_items": left_items or [],
            "right_items": right_items or [],
            "invalid_extractions": invalid_extractions or [],
        }

    def expected_item(
        self,
        *,
        item_type: str,
        name: str,
        status: str | None = "active",
        source_quote: str | None = None,
    ) -> dict:
        item = {"type": item_type, "name": name}
        if status is not None:
            item["status"] = status
        if source_quote is not None:
            item["source_quote"] = source_quote
        return item

    def prediction_item(
        self,
        *,
        item_type: str = "condition",
        name: str = "hypertension",
        status: str | None = "active",
        source_quote: str = "Hypertension.",
        source_start_char: int = 0,
        source_end_char: int | None = None,
    ) -> dict:
        if source_end_char is None:
            source_end_char = source_start_char + len(source_quote)
        item = {
            "type": item_type,
            "name": name,
            "confidence": 0.75,
            "source_quote": source_quote,
            "source_start_char": source_start_char,
            "source_end_char": source_end_char,
            "section_id": "note_test:section:001",
            "section_name": "Assessment",
        }
        if status is not None:
            item["status"] = status
        return item

    def write_expected(
        self,
        expected_dir: Path,
        document_id: str,
        items: list[dict],
        invalid_extractions: list[dict] | None = None,
    ) -> None:
        (expected_dir / f"{document_id}.expected.json").write_text(
            json.dumps({"items": items, "invalid_extractions": invalid_extractions or []}),
            encoding="utf-8",
        )

    def write_prediction(
        self,
        predictions_dir: Path,
        document_id: str,
        items: list[dict],
    ) -> None:
        (predictions_dir / f"{document_id}.predicted.json").write_text(
            json.dumps(
                {
                    "schema_version": "prediction-format-v1",
                    "document_id": document_id,
                    "extractor": {
                        "name": "test-extractor",
                        "version": "test-v1",
                    },
                    "items": items,
                }
            ),
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
