"""Core evidence and aggregation rules for the Popular Film Values Study."""

from .aggregate import (
    FilmThemeScore,
    SourceVote,
    aggregate_film_theme,
    collapse_source_records,
    glamorize_then_punish,
    not_evidenced_score,
)
from .evidence import (
    evidence_record_spans_match,
    evidence_span_matches,
    normalize_evidence_text,
    validate_claim_attribution_sources,
)
from .models import (
    ClaimDependence,
    ClaimTarget,
    ClaimType,
    EndingResponse,
    EvidenceRecord,
    EvidenceVerificationResult,
    FilmStance,
    NarrativeSegment,
    SourceSalience,
    SourceStance,
    SourceType,
    Theme,
    VerificationReason,
)
from .serialization import (
    evidence_record_from_dict,
    evidence_record_to_dict,
    verification_result_from_dict,
    verification_result_to_dict,
)

__all__ = [
    "ClaimDependence",
    "ClaimTarget",
    "ClaimType",
    "EndingResponse",
    "EvidenceRecord",
    "EvidenceVerificationResult",
    "FilmStance",
    "FilmThemeScore",
    "NarrativeSegment",
    "SourceSalience",
    "SourceStance",
    "SourceType",
    "SourceVote",
    "Theme",
    "VerificationReason",
    "aggregate_film_theme",
    "collapse_source_records",
    "evidence_span_matches",
    "evidence_record_spans_match",
    "evidence_record_from_dict",
    "evidence_record_to_dict",
    "glamorize_then_punish",
    "not_evidenced_score",
    "normalize_evidence_text",
    "validate_claim_attribution_sources",
    "verification_result_from_dict",
    "verification_result_to_dict",
]
