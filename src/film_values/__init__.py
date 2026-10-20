"""Core evidence and aggregation rules for the Popular Film Values Study."""

from .aggregate import (
    FilmThemeScore,
    SourceVote,
    aggregate_film_theme,
    collapse_source_records,
    glamorize_then_punish,
    not_evidenced_score,
)
from .evidence import evidence_span_matches, normalize_evidence_text
from .models import (
    ClaimTarget,
    ClaimType,
    EndingResponse,
    EvidenceRecord,
    FilmStance,
    NarrativeSegment,
    SourceSalience,
    SourceStance,
    SourceType,
    Theme,
)
from .serialization import evidence_record_from_dict, evidence_record_to_dict

__all__ = [
    "ClaimTarget",
    "ClaimType",
    "EndingResponse",
    "EvidenceRecord",
    "FilmStance",
    "FilmThemeScore",
    "NarrativeSegment",
    "SourceSalience",
    "SourceStance",
    "SourceType",
    "SourceVote",
    "Theme",
    "aggregate_film_theme",
    "collapse_source_records",
    "evidence_span_matches",
    "evidence_record_from_dict",
    "evidence_record_to_dict",
    "glamorize_then_punish",
    "not_evidenced_score",
    "normalize_evidence_text",
]
