"""Strict JSON-compatible serialization for model-facing records."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from .models import (
    ClaimTarget,
    ClaimType,
    EndingResponse,
    EvidenceRecord,
    NarrativeSegment,
    SourceSalience,
    SourceStance,
    SourceType,
    Theme,
)


_EVIDENCE_FIELDS = {
    "film_id",
    "source_id",
    "lineage_id",
    "source_type",
    "exact_evidence_span",
    "locator",
    "claim_target",
    "claim_type",
    "theme",
    "narrative_segment",
    "source_salience",
    "source_stance",
    "ending_response",
    "explicit_temporal_contrast",
}


def evidence_record_from_dict(value: Mapping[str, Any]) -> EvidenceRecord:
    """Parse one strict record, rejecting missing or unexpected fields."""

    keys = set(value)
    missing = _EVIDENCE_FIELDS - keys
    extra = keys - _EVIDENCE_FIELDS
    if missing or extra:
        raise ValueError(
            f"Evidence record fields differ from schema; missing={sorted(missing)}, "
            f"extra={sorted(extra)}"
        )
    string_fields = _EVIDENCE_FIELDS - {
        "source_salience",
        "ending_response",
        "explicit_temporal_contrast",
    }
    wrong_strings = sorted(
        field for field in string_fields if not isinstance(value[field], str)
    )
    if wrong_strings:
        raise ValueError(f"Evidence record fields must be strings: {wrong_strings}")
    if type(value["source_salience"]) is not int:
        raise ValueError("source_salience must be an integer")
    if not isinstance(value["explicit_temporal_contrast"], bool):
        raise ValueError("explicit_temporal_contrast must be a boolean")
    ending = value["ending_response"]
    if ending is not None and not isinstance(ending, str):
        raise ValueError("ending_response must be a string or null")
    return EvidenceRecord(
        film_id=value["film_id"],
        source_id=value["source_id"],
        lineage_id=value["lineage_id"],
        source_type=SourceType(value["source_type"]),
        exact_evidence_span=value["exact_evidence_span"],
        locator=value["locator"],
        claim_target=ClaimTarget(value["claim_target"]),
        claim_type=ClaimType(value["claim_type"]),
        theme=Theme(value["theme"]),
        narrative_segment=NarrativeSegment(value["narrative_segment"]),
        source_salience=SourceSalience(value["source_salience"]),
        source_stance=SourceStance(value["source_stance"]),
        ending_response=EndingResponse(ending) if ending is not None else None,
        explicit_temporal_contrast=value["explicit_temporal_contrast"],
    )


def evidence_record_to_dict(record: EvidenceRecord) -> dict[str, Any]:
    """Return the schema-compatible representation of one evidence record."""

    output = asdict(record)
    for key, value in tuple(output.items()):
        if hasattr(value, "value"):
            output[key] = value.value
    return output
