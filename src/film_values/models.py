"""Frozen ontology and typed evidence records."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class Theme(str, Enum):
    SELFISHNESS = "selfishness"
    CONSUMERISM_MATERIALISM = "consumerism_materialism"
    STATUS_FAME_POWER = "status_fame_power"
    ACHIEVEMENT_WORK_COMPETITION = "achievement_work_competition"
    ROMANTIC_FAMILIAL_LOVE = "romantic_familial_love"
    FRIENDSHIP_COMMUNITY_SOLIDARITY = "friendship_community_solidarity"
    CARE_SERVICE_SACRIFICE = "care_service_sacrifice"
    JUSTICE_DUTY_PUBLIC_GOOD = "justice_duty_public_good"
    ART_CREATIVITY_BEAUTY = "art_creativity_beauty"
    KNOWLEDGE_TRUTH_DISCOVERY = "knowledge_truth_discovery"
    RELIGIOUS_CONVICTION_INSTITUTIONS = "religious_conviction_institutions"
    SPIRITUAL_EXISTENTIAL_MEANING = "spiritual_existential_meaning"
    PLEASURE_ADVENTURE = "pleasure_adventure"
    REVENGE = "revenge"
    FREEDOM_AUTONOMY = "freedom_autonomy"


class NarrativeSegment(str, Enum):
    MAIN_BODY = "main_body"
    ENDING = "ending"
    GLOBAL_UNSPECIFIED = "global_unspecified"


class ClaimTarget(str, Enum):
    FILM = "film"
    CHARACTER = "character"
    FILMMAKER = "filmmaker"
    CRITIC = "critic"
    AUDIENCE = "audience"
    SOCIETY = "society"


class ClaimType(str, Enum):
    PLOT_FACT = "plot_fact"
    FILM_THEME_ATTRIBUTION = "film_theme_attribution"
    FILM_STANCE_ATTRIBUTION = "film_stance_attribution"
    PLOT_CONSEQUENCE = "plot_consequence"
    CRITIC_PREFERENCE = "critic_preference"
    RECEPTION_CLAIM = "reception_claim"


class ClaimDependence(str, Enum):
    """Whether a claim is the source's own interpretation or repeated authority."""

    INDEPENDENT_INTERPRETATION = "independent_interpretation"
    ATTRIBUTED_DERIVATIVE = "attributed_derivative"


class SourceType(str, Enum):
    CONTEMPORARY_REVIEW = "contemporary_review"
    RETROSPECTIVE_ESSAY = "retrospective_essay"
    SCHOLARSHIP = "scholarship"
    REFERENCE_SYNOPSIS = "reference_synopsis"


class SourceSalience(IntEnum):
    PRESENT_INCIDENTAL = 1
    IMPORTANT = 2
    CENTRAL = 3


class SourceStance(str, Enum):
    AFFIRMATIVE = "affirmative"
    CRITICAL = "critical"
    MIXED = "mixed"
    UNSTATED = "unstated"


class FilmStance(str, Enum):
    AFFIRMATIVE = "affirmative"
    CRITICAL = "critical"
    MIXED_CONTESTED = "mixed_contested"
    UNRESOLVED = "unresolved"
    NOT_EVIDENCED = "not_evidenced"


class EndingResponse(str, Enum):
    ORIGINAL_PURSUIT_REINFORCED = "original_pursuit_reinforced"
    EXTERNAL_PUNISHMENT_ONLY = "external_punishment_only"
    REMORSE_VERBAL_RECOGNITION = "remorse_verbal_recognition"
    CHANGED_BEHAVIOR = "changed_behavior"
    COSTLY_REPAIR_SACRIFICE = "costly_repair_sacrifice"
    AMBIGUOUS = "ambiguous"


class VerificationReason(str, Enum):
    ACCEPTED = "accepted"
    THEME_UNSUPPORTED = "theme_unsupported"
    CLAIM_TARGET_INCORRECT = "claim_target_incorrect"
    CLAIM_TYPE_INCORRECT = "claim_type_incorrect"
    SEGMENT_INFERRED = "segment_inferred"
    SALIENCE_OVERSTATED = "salience_overstated"
    STANCE_UNSUPPORTED = "stance_unsupported"
    CRITIC_PREFERENCE_MISCLASSIFIED = "critic_preference_misclassified"
    ENDING_RESPONSE_UNSUPPORTED = "ending_response_unsupported"
    CLAIM_DEPENDENCE_INCORRECT = "claim_dependence_incorrect"
    SELFISHNESS_GUARDRAIL_FAILED = "selfishness_guardrail_failed"
    CONSUMERISM_GUARDRAIL_FAILED = "consumerism_guardrail_failed"
    INSUFFICIENT_CONTEXT = "insufficient_context"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """One evidence-constrained claim extracted from one source."""

    film_id: str
    source_id: str
    lineage_id: str
    source_type: SourceType
    exact_evidence_span: str
    locator: str
    claim_target: ClaimTarget
    claim_type: ClaimType
    theme: Theme
    narrative_segment: NarrativeSegment
    source_salience: SourceSalience
    claim_dependence: ClaimDependence
    source_stance: SourceStance = SourceStance.UNSTATED
    ending_response: EndingResponse | None = None
    explicit_temporal_contrast: bool = False
    attributed_source_ids: tuple[str, ...] = ()
    attribution_span: str | None = None

    def __post_init__(self) -> None:
        required = {
            "film_id": self.film_id,
            "source_id": self.source_id,
            "lineage_id": self.lineage_id,
            "exact_evidence_span": self.exact_evidence_span,
            "locator": self.locator,
        }
        empty = [name for name, value in required.items() if not value.strip()]
        if empty:
            raise ValueError(f"EvidenceRecord fields may not be empty: {', '.join(empty)}")
        if (
            self.ending_response is not None
            and self.narrative_segment is not NarrativeSegment.ENDING
        ):
            raise ValueError("ending_response is permitted only for ending evidence")
        if not isinstance(self.claim_dependence, ClaimDependence):
            raise TypeError("claim_dependence must be a ClaimDependence value")
        if type(self.attributed_source_ids) is not tuple:
            raise TypeError("attributed_source_ids must be a tuple")
        if self.attribution_span is not None and not isinstance(
            self.attribution_span, str
        ):
            raise TypeError("attribution_span must be a string or None")
        if any(
            not isinstance(value, str) or not value.strip()
            for value in self.attributed_source_ids
        ):
            raise ValueError("attributed_source_ids must contain nonempty strings")
        if len(self.attributed_source_ids) != len(set(self.attributed_source_ids)):
            raise ValueError("attributed_source_ids must be unique")
        if self.source_id in self.attributed_source_ids:
            raise ValueError("A source may not be attributed as the origin of its own claim")

        if self.claim_dependence is ClaimDependence.INDEPENDENT_INTERPRETATION:
            if self.attributed_source_ids or self.attribution_span is not None:
                raise ValueError(
                    "Independent interpretation may not name attributed sources or a span"
                )
        elif self.claim_dependence is ClaimDependence.ATTRIBUTED_DERIVATIVE:
            if not self.attributed_source_ids:
                raise ValueError(
                    "Attributed derivative requires at least one source identifier"
                )
            if self.attribution_span is None or not self.attribution_span.strip():
                raise ValueError("Attributed derivative requires a nonempty attribution span")
            if self.attribution_span not in self.exact_evidence_span:
                raise ValueError(
                    "attribution_span must occur verbatim within exact_evidence_span"
                )


@dataclass(frozen=True, slots=True)
class EvidenceVerificationResult:
    """One strict verification decision for a proposed evidence record."""

    accepted: bool
    reason_codes: tuple[VerificationReason, ...]
    explanation: str

    def __post_init__(self) -> None:
        if not self.explanation.strip():
            raise ValueError("verification explanation may not be empty")
        if not self.reason_codes:
            raise ValueError("verification requires at least one reason code")
        if len(self.reason_codes) != len(set(self.reason_codes)):
            raise ValueError("verification reason codes must be unique")
        if self.accepted and self.reason_codes != (VerificationReason.ACCEPTED,):
            raise ValueError("accepted verification requires only the accepted reason code")
        if not self.accepted and VerificationReason.ACCEPTED in self.reason_codes:
            raise ValueError("rejected verification may not contain the accepted reason code")
