"""Shared prediction JSON formatting for clinical extraction outputs."""

from __future__ import annotations

from processor.src.domain.extraction_schema import ExtractedClinicalItem


PREDICTION_SCHEMA_VERSION = "prediction-format-v1"


def prediction_json_for_items(
    document_id: str,
    items: tuple[ExtractedClinicalItem, ...],
    *,
    extractor: dict,
) -> dict:
    """Build prediction JSON compatible with the evaluator contract."""

    return {
        "schema_version": PREDICTION_SCHEMA_VERSION,
        "document_id": document_id,
        "extractor": extractor,
        "items": [
            prediction_item_from_extracted_item(item)
            for item in sorted(items, key=prediction_sort_key)
        ],
    }


def prediction_sort_key(item: ExtractedClinicalItem) -> tuple[int, int, str, str, str]:
    """Return the deterministic ordering key for prediction output."""

    return (
        item.source_start_char,
        item.source_end_char,
        item.item_type.value,
        item.name,
        item.status or "",
    )


def prediction_item_from_extracted_item(item: ExtractedClinicalItem) -> dict:
    """Convert a validated domain item into evaluator prediction JSON."""

    prediction_item = {
        "type": item.item_type.value,
        "name": item.name,
    }
    if item.status is not None:
        prediction_item["status"] = item.status
    if item.confidence is not None:
        prediction_item["confidence"] = item.confidence
    prediction_item.update(
        {
            "source_quote": item.source_quote,
            "source_start_char": item.source_start_char,
            "source_end_char": item.source_end_char,
            "section_id": item.section_id,
            "section_name": item.section_name,
        }
    )
    return prediction_item
