"""Executable integrity and repeatability gates for the frozen film pilot.

Agreement numbers alone are insufficient: a report cannot pass after silently
dropping a film, source, control, comparison cell, or leave-one-out run.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from statistics import median
from typing import Iterable, Sequence

from .aggregate import (
    FilmThemeScore,
    SourceVote,
    aggregate_film_theme,
    glamorize_then_punish,
    not_evidenced_score,
)
from .models import (
    EndingResponse,
    FilmStance,
    NarrativeSegment,
    SourceSalience,
    SourceStance,
    SourceType,
    Theme,
)


SOURCE_MEDIAN_JACCARD_MIN = 0.80
SOURCE_SHARE_JACCARD_CUTOFF = 0.67
SOURCE_SHARE_AT_CUTOFF_MIN = 0.80
PERIOD_MEDIAN_JACCARD_MIN = 0.67
SOURCE_ATTRIBUTE_EXACT_MIN = 0.80
THIRD_PASS_FRACTION_MAX = 0.20
FILM_CENTRALITY_EXACT_MIN = 0.80

FROZEN_PILOT_PERIODS = (
    "1950-1962",
    "1963-1975",
    "1976-1988",
    "1989-2001",
    "2002-2014",
    "2015-2025",
)

_MECHANICAL_GATE_NAMES = (
    "coverage",
    "rights",
    "schema_and_provenance",
    "exact_evidence",
    "ending_integrity",
)
_SOURCE_HARD_GATE_NAMES = (
    "source_manifest_alignment",
    "third_pass_integrity",
)
_SOURCE_REPEATABILITY_GATE_NAMES = (
    "source_median_positive_jaccard",
    "source_share_jaccard_at_least_0.67",
    *(f"period_median_positive_jaccard:{period}" for period in FROZEN_PILOT_PERIODS),
    "source_salience_exact",
    "source_stance_exact",
    "third_pass_fraction",
)
_FILM_HARD_GATE_NAMES = (
    "film_component_manifest_alignment",
    "film_score_universe",
    "glamorize_then_punish_universe",
    "replicate_film_no_polarity_reversal",
    "leave_one_source_out_no_polarity_reversal",
)
_FILM_REPEATABILITY_GATE_NAMES = (
    "film_centrality_exact",
    "glamorize_then_punish_exact",
)

_SHA256 = re.compile(r"[0-9a-f]{64}")


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NOT_EVALUABLE = "not_evaluable"


class PilotDecision(str, Enum):
    PROCEED = "proceed"
    REVISE_AND_REVALIDATE = "revise_and_revalidate"
    STOP_OR_NARROW = "stop_or_narrow"


class SourceSlot(str, Enum):
    C_TRADE = "C_TRADE"
    C_GENERAL = "C_GENERAL"
    R_LATER = "R_LATER"
    S_ACADEMIC = "S_ACADEMIC"
    P_SYNOPSIS = "P_SYNOPSIS"
    R_LATER_2 = "R_LATER_2"


class NegativeControlKind(str, Enum):
    CORRUPTED_QUOTATION = "corrupted_quotation"
    WRONG_FILM = "wrong_film"


class SensitivitySection(str, Enum):
    SOURCE_STRATA = "source_strata"
    HISTORICAL_DISAGREEMENT = "historical_disagreement"
    LEAVE_ONE_SOURCE_OUT = "leave_one_source_out"
    ONE_SOURCE_DEPENDENCE = "one_source_dependence"
    PROCESSING_FAILURES = "processing_failures"
    BOTH_EMPTY_AND_JACCARD = "both_empty_and_jaccard"


_SLOT_SOURCE_TYPE = {
    SourceSlot.C_TRADE: SourceType.CONTEMPORARY_REVIEW,
    SourceSlot.C_GENERAL: SourceType.CONTEMPORARY_REVIEW,
    SourceSlot.R_LATER: SourceType.RETROSPECTIVE_ESSAY,
    SourceSlot.S_ACADEMIC: SourceType.SCHOLARSHIP,
    SourceSlot.P_SYNOPSIS: SourceType.REFERENCE_SYNOPSIS,
    SourceSlot.R_LATER_2: SourceType.RETROSPECTIVE_ESSAY,
}
_CORE_SLOTS = {
    SourceSlot.C_TRADE,
    SourceSlot.C_GENERAL,
    SourceSlot.P_SYNOPSIS,
}
_LATER_SLOTS = {
    SourceSlot.R_LATER,
    SourceSlot.S_ACADEMIC,
    SourceSlot.R_LATER_2,
}


def _require_bool(value: object, name: str) -> None:
    if type(value) is not bool:
        raise TypeError(f"{name} must be a bool")


def _require_count(value: object, name: str) -> None:
    if type(value) is not int:
        raise TypeError(f"{name} must be an int")
    if value < 0:
        raise ValueError(f"{name} may not be negative")


def _require_nonempty(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if not value.strip():
        raise ValueError(f"{name} may not be empty")


def _require_sha256(value: object, name: str) -> None:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    if _SHA256.fullmatch(value) is None:
        raise ValueError(f"{name} must be a lowercase SHA-256 digest")


def _canonical_digest(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _unit_label(key: tuple[Theme, NarrativeSegment]) -> str:
    return f"{key[0].value}|{key[1].value}"


def _cell_label(key: tuple[str, Theme, NarrativeSegment]) -> str:
    return f"{key[0]}|{key[1].value}|{key[2].value}"


def _late_cell_label(key: tuple[str, Theme]) -> str:
    return f"{key[0]}|{key[1].value}"


def _require_gate_roster(
    component: str,
    gates: object,
    expected_names: tuple[str, ...],
) -> None:
    if type(gates) is not tuple or any(not isinstance(gate, GateResult) for gate in gates):
        raise TypeError(f"{component} gates must be a tuple of GateResult values")
    actual_names = tuple(gate.name for gate in gates)
    if actual_names != expected_names:
        raise ValueError(
            f"{component} gate roster differs from the frozen roster: "
            f"expected {expected_names!r}, observed {actual_names!r}"
        )


@dataclass(frozen=True, slots=True)
class GateResult:
    name: str
    status: GateStatus
    observed: float | int | str | None
    criterion: str
    details: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_nonempty(self.name, "GateResult.name")
        _require_nonempty(self.criterion, "GateResult.criterion")
        if not isinstance(self.status, GateStatus):
            raise TypeError("GateResult.status must be a GateStatus")
        if type(self.details) is not tuple or any(
            not isinstance(value, str) for value in self.details
        ):
            raise TypeError("GateResult.details must be a tuple of strings")


def _rate_gate(
    name: str,
    value: float | None,
    threshold: float,
    *,
    at_most: bool = False,
) -> GateResult:
    relation = "at most" if at_most else "at least"
    if value is None:
        return GateResult(
            name=name,
            status=GateStatus.NOT_EVALUABLE,
            observed=None,
            criterion=f"{relation} {threshold:.2f}",
            details=("No qualifying comparison unit was available.",),
        )
    if not 0 <= value <= 1:
        raise ValueError(f"Rate for {name} must be between zero and one")
    passed = value <= threshold if at_most else value >= threshold
    return GateResult(
        name=name,
        status=GateStatus.PASS if passed else GateStatus.FAIL,
        observed=value,
        criterion=f"{relation} {threshold:.2f}",
    )


@dataclass(frozen=True, slots=True)
class ManifestSource:
    source_id: str
    lineage_id: str
    slot: SourceSlot
    source_type: SourceType
    content_hash: str
    permission_basis: str
    permitted_model_environments: frozenset[str]
    processing_permitted: bool
    eligibility_verified: bool

    def __post_init__(self) -> None:
        _require_nonempty(self.source_id, "ManifestSource.source_id")
        _require_nonempty(self.lineage_id, "ManifestSource.lineage_id")
        _require_nonempty(self.permission_basis, "ManifestSource.permission_basis")
        _require_sha256(self.content_hash, "ManifestSource.content_hash")
        if not isinstance(self.slot, SourceSlot):
            raise TypeError("ManifestSource.slot must be a SourceSlot")
        if not isinstance(self.source_type, SourceType):
            raise TypeError("ManifestSource.source_type must be a SourceType")
        if self.source_type is not _SLOT_SOURCE_TYPE[self.slot]:
            raise ValueError("Source type does not match the frozen source slot")
        if type(self.permitted_model_environments) is not frozenset or any(
            not isinstance(value, str) or not value.strip()
            for value in self.permitted_model_environments
        ):
            raise TypeError(
                "permitted_model_environments must be a frozenset of nonempty strings"
            )
        _require_bool(self.processing_permitted, "processing_permitted")
        _require_bool(self.eligibility_verified, "eligibility_verified")


@dataclass(frozen=True, slots=True)
class ValidationFilm:
    film_id: str
    period: str
    untouched: bool
    selection_log_hash: str
    bundle_hash: str
    sources: tuple[ManifestSource, ...]

    def __post_init__(self) -> None:
        _require_nonempty(self.film_id, "ValidationFilm.film_id")
        _require_nonempty(self.period, "ValidationFilm.period")
        _require_bool(self.untouched, "ValidationFilm.untouched")
        _require_sha256(self.selection_log_hash, "ValidationFilm.selection_log_hash")
        _require_sha256(self.bundle_hash, "ValidationFilm.bundle_hash")
        if type(self.sources) is not tuple or any(
            not isinstance(source, ManifestSource) for source in self.sources
        ):
            raise TypeError("ValidationFilm.sources must be a tuple of ManifestSource")
        source_ids = [source.source_id for source in self.sources]
        slots = [source.slot for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("A validation film may not repeat a source_id")
        if len(slots) != len(set(slots)):
            raise ValueError("A validation film may not assign a source slot twice")


@dataclass(frozen=True, slots=True)
class PilotValidationManifest:
    films: tuple[ValidationFilm, ...]
    pipeline_frozen_hash: str
    control_assignment_set_hash: str
    frozen_before_validation: bool

    def __post_init__(self) -> None:
        if type(self.films) is not tuple or any(
            not isinstance(film, ValidationFilm) for film in self.films
        ):
            raise TypeError("films must be a tuple of ValidationFilm")
        _require_sha256(self.pipeline_frozen_hash, "pipeline_frozen_hash")
        _require_sha256(
            self.control_assignment_set_hash, "control_assignment_set_hash"
        )
        _require_bool(self.frozen_before_validation, "frozen_before_validation")
        film_ids = [film.film_id for film in self.films]
        source_ids = [source.source_id for film in self.films for source in film.sources]
        if len(film_ids) != len(set(film_ids)):
            raise ValueError("Manifest film_ids must be unique")
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("Manifest source_ids must be globally unique")

    @property
    def digest(self) -> str:
        films = []
        for film in sorted(self.films, key=lambda item: item.film_id):
            sources = []
            for source in sorted(film.sources, key=lambda item: item.source_id):
                sources.append(
                    {
                        "source_id": source.source_id,
                        "lineage_id": source.lineage_id,
                        "slot": source.slot.value,
                        "source_type": source.source_type.value,
                        "content_hash": source.content_hash,
                        "permission_basis": source.permission_basis,
                        "permitted_model_environments": sorted(
                            source.permitted_model_environments
                        ),
                        "processing_permitted": source.processing_permitted,
                        "eligibility_verified": source.eligibility_verified,
                    }
                )
            films.append(
                {
                    "film_id": film.film_id,
                    "period": film.period,
                    "untouched": film.untouched,
                    "selection_log_hash": film.selection_log_hash,
                    "bundle_hash": film.bundle_hash,
                    "sources": sources,
                }
            )
        return _canonical_digest(
            {
                "films": films,
                "pipeline_frozen_hash": self.pipeline_frozen_hash,
                "control_assignment_set_hash": self.control_assignment_set_hash,
                "frozen_before_validation": self.frozen_before_validation,
            }
        )

    @property
    def film_ids(self) -> frozenset[str]:
        return frozenset(film.film_id for film in self.films)

    @property
    def eligible_source_ids(self) -> frozenset[str]:
        return frozenset(
            source.source_id
            for film in self.films
            for source in film.sources
            if source.eligibility_verified
        )

    @property
    def source_index(self) -> dict[str, tuple[ValidationFilm, ManifestSource]]:
        return {
            source.source_id: (film, source)
            for film in self.films
            for source in film.sources
        }


@dataclass(frozen=True, slots=True)
class SourceAgreement:
    source_id: str
    film_id: str
    lineage_id: str
    source_content_hash: str
    source_slot: SourceSlot
    source_type: SourceType
    left_votes: tuple[SourceVote, ...]
    right_votes: tuple[SourceVote, ...]
    left_units: frozenset[tuple[Theme, NarrativeSegment]]
    right_units: frozenset[tuple[Theme, NarrativeSegment]]
    salience_exact_units: frozenset[tuple[Theme, NarrativeSegment]]
    stance_exact_units: frozenset[tuple[Theme, NarrativeSegment]]
    direct_polarity_flip_units: frozenset[tuple[Theme, NarrativeSegment]]

    def __post_init__(self) -> None:
        for name in ("source_id", "film_id", "lineage_id"):
            _require_nonempty(getattr(self, name), f"SourceAgreement.{name}")
        _require_sha256(
            self.source_content_hash, "SourceAgreement.source_content_hash"
        )
        if not isinstance(self.source_slot, SourceSlot):
            raise TypeError("SourceAgreement.source_slot must be a SourceSlot")
        if not isinstance(self.source_type, SourceType):
            raise TypeError("SourceAgreement.source_type must be a SourceType")
        for field in ("left_votes", "right_votes"):
            values = getattr(self, field)
            if type(values) is not tuple or any(
                not isinstance(value, SourceVote) for value in values
            ):
                raise TypeError(f"SourceAgreement.{field} must contain SourceVote values")
        for field in (
            "left_units",
            "right_units",
            "salience_exact_units",
            "stance_exact_units",
            "direct_polarity_flip_units",
        ):
            values = getattr(self, field)
            if type(values) is not frozenset:
                raise TypeError(f"SourceAgreement.{field} must be a frozenset")
            for value in values:
                if (
                    not isinstance(value, tuple)
                    or len(value) != 2
                    or not isinstance(value[0], Theme)
                    or not isinstance(value[1], NarrativeSegment)
                ):
                    raise TypeError(f"Invalid source agreement unit in {field}")
        joint = self.left_units & self.right_units
        if not self.salience_exact_units <= joint:
            raise ValueError("Salience-exact units must be jointly proposed")
        if not self.stance_exact_units <= joint:
            raise ValueError("Stance-exact units must be jointly proposed")
        if not self.direct_polarity_flip_units <= joint:
            raise ValueError("Polarity-flip units must be jointly proposed")
        if self.direct_polarity_flip_units & self.stance_exact_units:
            raise ValueError("A polarity reversal cannot also be stance-exact")

    @property
    def positive_jaccard(self) -> float | None:
        union = self.left_units | self.right_units
        return _ratio(len(self.left_units & self.right_units), len(union))

    @property
    def left_positive(self) -> int:
        return len(self.left_units)

    @property
    def right_positive(self) -> int:
        return len(self.right_units)

    @property
    def joint_positive(self) -> int:
        return len(self.left_units & self.right_units)

    @property
    def union_positive(self) -> int:
        return len(self.left_units | self.right_units)

    @property
    def salience_exact(self) -> int:
        return len(self.salience_exact_units)

    @property
    def stance_exact(self) -> int:
        return len(self.stance_exact_units)

    @property
    def direct_polarity_flips(self) -> int:
        return len(self.direct_polarity_flip_units)


@dataclass(frozen=True, slots=True)
class SourceAgreementSummary:
    comparable_sources: int
    both_empty_sources: int
    median_positive_jaccard: float | None
    proportion_at_least_two_thirds: float | None
    salience_exact_rate: float | None
    stance_exact_rate: float | None
    direct_polarity_flips: int

    def __post_init__(self) -> None:
        for name in (
            "comparable_sources",
            "both_empty_sources",
            "direct_polarity_flips",
        ):
            _require_count(getattr(self, name), f"SourceAgreementSummary.{name}")
        for name in (
            "median_positive_jaccard",
            "proportion_at_least_two_thirds",
            "salience_exact_rate",
            "stance_exact_rate",
        ):
            value = getattr(self, name)
            if value is not None and (
                not isinstance(value, float) or not 0 <= value <= 1
            ):
                raise ValueError(f"{name} must be None or a rate from zero to one")

    @property
    def total_sources(self) -> int:
        return self.comparable_sources + self.both_empty_sources

    @property
    def both_empty_rate(self) -> float | None:
        return _ratio(self.both_empty_sources, self.total_sources)


@dataclass(frozen=True, slots=True)
class AssignedSourceAgreement:
    period: str
    agreement: SourceAgreement

    def __post_init__(self) -> None:
        _require_nonempty(self.period, "AssignedSourceAgreement.period")
        if not isinstance(self.agreement, SourceAgreement):
            raise TypeError("agreement must be a SourceAgreement")

    @property
    def source_id(self) -> str:
        return self.agreement.source_id

    @property
    def film_id(self) -> str:
        return self.agreement.film_id


@dataclass(frozen=True, slots=True)
class PeriodAgreementSummary:
    period: str
    total_sources: int
    comparable_sources: int
    both_empty_sources: int
    median_positive_jaccard: float | None
    gate: GateResult


@dataclass(frozen=True, slots=True)
class ThirdPassUnit:
    source_id: str
    film_id: str
    theme: Theme
    narrative_segment: NarrativeSegment
    selected_existing_span_verified: bool
    verification_record_hash: str

    def __post_init__(self) -> None:
        _require_nonempty(self.source_id, "ThirdPassUnit.source_id")
        _require_nonempty(self.film_id, "ThirdPassUnit.film_id")
        if not isinstance(self.theme, Theme):
            raise TypeError("ThirdPassUnit.theme must be a Theme")
        if not isinstance(self.narrative_segment, NarrativeSegment):
            raise TypeError("ThirdPassUnit.narrative_segment must be a NarrativeSegment")
        _require_bool(
            self.selected_existing_span_verified, "selected_existing_span_verified"
        )
        _require_sha256(self.verification_record_hash, "verification_record_hash")

    @property
    def key(self) -> tuple[str, str, Theme, NarrativeSegment]:
        return (self.source_id, self.film_id, self.theme, self.narrative_segment)


@dataclass(frozen=True, slots=True)
class ThirdPassSummary:
    required_units: int
    proposed_union_units: int
    fraction: float | None
    integrity_gate: GateResult
    fraction_gate: GateResult


@dataclass(frozen=True, slots=True)
class SourceRepeatabilityEvaluation:
    manifest_digest: str
    source_ids: frozenset[str]
    film_ids: frozenset[str]
    assigned: tuple[AssignedSourceAgreement, ...]
    third_pass_units: tuple[ThirdPassUnit, ...]
    overall: SourceAgreementSummary
    periods: tuple[PeriodAgreementSummary, ...]
    third_pass: ThirdPassSummary
    hard_gates: tuple[GateResult, ...]
    gates: tuple[GateResult, ...]


def _validate_source_vote(vote: object, film_id: str, source: ManifestSource) -> None:
    if not isinstance(vote, SourceVote):
        raise TypeError("Source comparisons require SourceVote values")
    if vote.film_id != film_id:
        raise ValueError("Source vote film_id does not match the manifest anchor")
    if vote.source_id != source.source_id:
        raise ValueError("Source vote source_id does not match the manifest anchor")
    if vote.lineage_id != source.lineage_id:
        raise ValueError("Source vote lineage_id does not match the manifest anchor")
    if vote.source_type is not source.source_type:
        raise ValueError("Source vote source_type does not match the manifest anchor")
    if not isinstance(vote.theme, Theme) or not isinstance(
        vote.narrative_segment, NarrativeSegment
    ):
        raise TypeError("Source vote theme and segment must use frozen enums")
    if not isinstance(vote.salience, SourceSalience) or not isinstance(
        vote.stance, SourceStance
    ):
        raise TypeError("Source vote salience and stance must use frozen enums")
    if (
        source.source_type is SourceType.REFERENCE_SYNOPSIS
        and vote.stance is not SourceStance.UNSTATED
    ):
        raise ValueError("Reference-synopsis votes may not supply film stance")
    _require_count(vote.evidence_count, "SourceVote.evidence_count")
    if vote.evidence_count == 0:
        raise ValueError("A positive SourceVote must contain evidence")
    if type(vote.ending_responses) is not frozenset or any(
        not isinstance(value, EndingResponse) for value in vote.ending_responses
    ):
        raise TypeError("SourceVote.ending_responses must contain EndingResponse values")
    if vote.ending_responses and vote.narrative_segment is not NarrativeSegment.ENDING:
        raise ValueError("Ending responses are permitted only on ending votes")


def compare_source_votes(
    left: Iterable[SourceVote],
    right: Iterable[SourceVote],
    *,
    film_id: str,
    source: ManifestSource,
) -> SourceAgreement:
    """Compare one frozen source across two independent replicates."""

    _require_nonempty(film_id, "film_id")
    if not isinstance(source, ManifestSource):
        raise TypeError("source must be a ManifestSource")
    if not source.eligibility_verified:
        raise ValueError("Cannot compare an ineligible or unverified source")

    left_votes = tuple(left)
    right_votes = tuple(right)

    def make_map(
        items: Iterable[SourceVote],
    ) -> dict[tuple[Theme, NarrativeSegment], SourceVote]:
        mapped: dict[tuple[Theme, NarrativeSegment], SourceVote] = {}
        for item in items:
            _validate_source_vote(item, film_id, source)
            key = (item.theme, item.narrative_segment)
            if key in mapped:
                raise ValueError(f"Duplicate comparison unit: {_unit_label(key)}")
            mapped[key] = item
        return mapped

    left_map = make_map(left_votes)
    right_map = make_map(right_votes)
    left_units = frozenset(left_map)
    right_units = frozenset(right_map)
    joint = left_units & right_units
    return SourceAgreement(
        source_id=source.source_id,
        film_id=film_id,
        lineage_id=source.lineage_id,
        source_content_hash=source.content_hash,
        source_slot=source.slot,
        source_type=source.source_type,
        left_votes=left_votes,
        right_votes=right_votes,
        left_units=left_units,
        right_units=right_units,
        salience_exact_units=frozenset(
            key for key in joint if left_map[key].salience is right_map[key].salience
        ),
        stance_exact_units=frozenset(
            key for key in joint if left_map[key].stance is right_map[key].stance
        ),
        direct_polarity_flip_units=frozenset(
            key
            for key in joint
            if {left_map[key].stance, right_map[key].stance}
            == {SourceStance.AFFIRMATIVE, SourceStance.CRITICAL}
        ),
    )


def summarize_source_agreements(
    agreements: Sequence[SourceAgreement],
) -> SourceAgreementSummary:
    if any(not isinstance(item, SourceAgreement) for item in agreements):
        raise TypeError("agreements must contain SourceAgreement values")
    jaccards = [
        agreement.positive_jaccard
        for agreement in agreements
        if agreement.positive_jaccard is not None
    ]
    joint = sum(agreement.joint_positive for agreement in agreements)
    return SourceAgreementSummary(
        comparable_sources=len(jaccards),
        both_empty_sources=len(agreements) - len(jaccards),
        median_positive_jaccard=median(jaccards) if jaccards else None,
        proportion_at_least_two_thirds=_ratio(
            sum(value >= SOURCE_SHARE_JACCARD_CUTOFF for value in jaccards),
            len(jaccards),
        ),
        salience_exact_rate=_ratio(
            sum(agreement.salience_exact for agreement in agreements), joint
        ),
        stance_exact_rate=_ratio(
            sum(agreement.stance_exact for agreement in agreements), joint
        ),
        direct_polarity_flips=sum(
            agreement.direct_polarity_flips for agreement in agreements
        ),
    )


def summarize_period_agreements(
    assigned: Sequence[AssignedSourceAgreement],
    expected_periods: Sequence[str] = FROZEN_PILOT_PERIODS,
) -> tuple[PeriodAgreementSummary, ...]:
    periods = tuple(expected_periods)
    if periods != FROZEN_PILOT_PERIODS:
        raise ValueError("Pilot period summaries must use the six frozen periods")
    source_ids = [item.source_id for item in assigned]
    if len(source_ids) != len(set(source_ids)):
        raise ValueError("Each source_id must have exactly one period assignment")
    unexpected = sorted({item.period for item in assigned} - set(periods))
    if unexpected:
        raise ValueError(f"Unexpected periods: {', '.join(unexpected)}")

    summaries: list[PeriodAgreementSummary] = []
    for period in periods:
        agreements = [item.agreement for item in assigned if item.period == period]
        summary = summarize_source_agreements(agreements)
        summaries.append(
            PeriodAgreementSummary(
                period=period,
                total_sources=summary.total_sources,
                comparable_sources=summary.comparable_sources,
                both_empty_sources=summary.both_empty_sources,
                median_positive_jaccard=summary.median_positive_jaccard,
                gate=_rate_gate(
                    f"period_median_positive_jaccard:{period}",
                    summary.median_positive_jaccard,
                    PERIOD_MEDIAN_JACCARD_MIN,
                ),
            )
        )
    return tuple(summaries)


def summarize_third_pass(
    required_units: int,
    proposed_union_units: int,
    *,
    integrity_errors: Sequence[str] = (),
) -> ThirdPassSummary:
    _require_count(required_units, "required_units")
    _require_count(proposed_union_units, "proposed_union_units")
    if required_units > proposed_union_units:
        raise ValueError("required_units may not exceed proposed_union_units")
    if any(not isinstance(value, str) for value in integrity_errors):
        raise TypeError("integrity_errors must contain strings")
    fraction = _ratio(required_units, proposed_union_units)
    return ThirdPassSummary(
        required_units=required_units,
        proposed_union_units=proposed_union_units,
        fraction=fraction,
        integrity_gate=GateResult(
            name="third_pass_integrity",
            status=GateStatus.FAIL if integrity_errors else GateStatus.PASS,
            observed=len(integrity_errors),
            criterion=(
                "every adjudicated unit was proposed and selected an existing exact span"
            ),
            details=tuple(integrity_errors),
        ),
        fraction_gate=_rate_gate(
            "third_pass_fraction",
            fraction,
            THIRD_PASS_FRACTION_MAX,
            at_most=True,
        ),
    )


def evaluate_source_repeatability(
    manifest: PilotValidationManifest,
    assigned: Sequence[AssignedSourceAgreement],
    *,
    third_pass_units: Sequence[ThirdPassUnit],
) -> SourceRepeatabilityEvaluation:
    assigned_items = tuple(assigned)
    adjudicated_items = tuple(third_pass_units)
    if any(not isinstance(item, AssignedSourceAgreement) for item in assigned_items):
        raise TypeError("assigned must contain AssignedSourceAgreement values")
    if any(not isinstance(item, ThirdPassUnit) for item in adjudicated_items):
        raise TypeError("third_pass_units must contain ThirdPassUnit values")
    periods = summarize_period_agreements(assigned_items)
    overall = summarize_source_agreements(
        [item.agreement for item in assigned_items]
    )
    expected_sources = manifest.eligible_source_ids
    actual_sources = frozenset(item.source_id for item in assigned_items)
    actual_films = frozenset(item.film_id for item in assigned_items)
    alignment_errors = [
        *(f"missing_source:{value}" for value in sorted(expected_sources - actual_sources)),
        *(f"unexpected_source:{value}" for value in sorted(actual_sources - expected_sources)),
    ]
    for item in assigned_items:
        expected = manifest.source_index.get(item.source_id)
        if expected is None:
            continue
        film, source = expected
        if item.film_id != film.film_id:
            alignment_errors.append(f"film_mismatch:{item.source_id}")
        if item.period != film.period:
            alignment_errors.append(f"period_mismatch:{item.source_id}")
        if item.agreement.lineage_id != source.lineage_id:
            alignment_errors.append(f"lineage_mismatch:{item.source_id}")
        if item.agreement.source_content_hash != source.content_hash:
            alignment_errors.append(f"content_hash_mismatch:{item.source_id}")
        if item.agreement.source_slot is not source.slot:
            alignment_errors.append(f"source_slot_mismatch:{item.source_id}")
        if item.agreement.source_type is not source.source_type:
            alignment_errors.append(f"source_type_mismatch:{item.source_id}")
        rebuilt_agreement = compare_source_votes(
            item.agreement.left_votes,
            item.agreement.right_votes,
            film_id=film.film_id,
            source=source,
        )
        if rebuilt_agreement != item.agreement:
            alignment_errors.append(f"agreement_summary_mismatch:{item.source_id}")
    alignment_gate = GateResult(
        name="source_manifest_alignment",
        status=GateStatus.FAIL if alignment_errors else GateStatus.PASS,
        observed=len(alignment_errors),
        criterion="agreement results cover the exact frozen source universe",
        details=tuple(sorted(alignment_errors)),
    )

    proposed_units = {
        (item.source_id, item.film_id, theme, segment)
        for item in assigned_items
        for theme, segment in item.agreement.left_units | item.agreement.right_units
    }
    adjudication_keys = [item.key for item in adjudicated_items]
    if len(adjudication_keys) != len(set(adjudication_keys)):
        raise ValueError("A source-level unit may not receive two third-pass records")
    integrity_errors = []
    for item in adjudicated_items:
        if item.key not in proposed_units:
            integrity_errors.append(
                "unproposed:"
                + "|".join(
                    (
                        item.source_id,
                        item.film_id,
                        item.theme.value,
                        item.narrative_segment.value,
                    )
                )
            )
        if not item.selected_existing_span_verified:
            integrity_errors.append(
                "unverified_span:"
                + "|".join(
                    (
                        item.source_id,
                        item.film_id,
                        item.theme.value,
                        item.narrative_segment.value,
                    )
                )
            )
    third_pass = summarize_third_pass(
        len(adjudicated_items),
        len(proposed_units),
        integrity_errors=integrity_errors,
    )
    gates = (
        _rate_gate(
            "source_median_positive_jaccard",
            overall.median_positive_jaccard,
            SOURCE_MEDIAN_JACCARD_MIN,
        ),
        _rate_gate(
            "source_share_jaccard_at_least_0.67",
            overall.proportion_at_least_two_thirds,
            SOURCE_SHARE_AT_CUTOFF_MIN,
        ),
        *(period.gate for period in periods),
        _rate_gate(
            "source_salience_exact",
            overall.salience_exact_rate,
            SOURCE_ATTRIBUTE_EXACT_MIN,
        ),
        _rate_gate(
            "source_stance_exact",
            overall.stance_exact_rate,
            SOURCE_ATTRIBUTE_EXACT_MIN,
        ),
        third_pass.fraction_gate,
    )
    return SourceRepeatabilityEvaluation(
        manifest_digest=manifest.digest,
        source_ids=actual_sources,
        film_ids=actual_films,
        assigned=assigned_items,
        third_pass_units=adjudicated_items,
        overall=overall,
        periods=periods,
        third_pass=third_pass,
        hard_gates=(alignment_gate, third_pass.integrity_gate),
        gates=gates,
    )


def _film_key(score: FilmThemeScore) -> tuple[str, Theme, NarrativeSegment]:
    return (score.film_id, score.theme, score.narrative_segment)


def _validate_film_score(score: object) -> None:
    if not isinstance(score, FilmThemeScore):
        raise TypeError("Film comparisons require FilmThemeScore values")
    _require_nonempty(score.film_id, "FilmThemeScore.film_id")
    if not isinstance(score.theme, Theme) or not isinstance(
        score.narrative_segment, NarrativeSegment
    ):
        raise TypeError("Film score theme and segment must use frozen enums")
    _require_count(score.centrality, "FilmThemeScore.centrality")
    if score.centrality > 3:
        raise ValueError("FilmThemeScore.centrality must be between zero and three")
    if not isinstance(score.stance, FilmStance):
        raise TypeError("FilmThemeScore.stance must be a FilmStance")
    for name in (
        "supporting_lineages",
        "affirmative_votes",
        "critical_votes",
        "mixed_votes",
        "unstated_votes",
    ):
        _require_count(getattr(score, name), f"FilmThemeScore.{name}")
    vote_total = (
        score.affirmative_votes
        + score.critical_votes
        + score.mixed_votes
        + score.unstated_votes
    )
    if vote_total != score.supporting_lineages:
        raise ValueError("Film stance vote counts must equal supporting_lineages")
    if score.centrality == 0:
        if (
            score.stance is not FilmStance.NOT_EVIDENCED
            or score.supporting_lineages != 0
        ):
            raise ValueError("A zero-centrality cell must be fully not-evidenced")
    elif score.stance is FilmStance.NOT_EVIDENCED or score.supporting_lineages == 0:
        raise ValueError("A positive-centrality cell requires evidence and a stance")
    if score.centrality == 3 and score.supporting_lineages < 2:
        raise ValueError("Consensus-central status requires at least two lineages")
    if score.centrality > 0:
        directional = score.affirmative_votes + score.critical_votes
        if directional >= 2 and score.affirmative_votes / directional >= 2 / 3:
            expected_stance = FilmStance.AFFIRMATIVE
        elif directional >= 2 and score.critical_votes / directional >= 2 / 3:
            expected_stance = FilmStance.CRITICAL
        elif score.mixed_votes > 0 or (
            score.affirmative_votes > 0 and score.critical_votes > 0
        ):
            expected_stance = FilmStance.MIXED_CONTESTED
        else:
            expected_stance = FilmStance.UNRESOLVED
        if score.stance is not expected_stance:
            raise ValueError("FilmThemeScore.stance is inconsistent with its vote counts")
    if type(score.ending_responses) is not frozenset or any(
        not isinstance(value, EndingResponse) for value in score.ending_responses
    ):
        raise TypeError("FilmThemeScore.ending_responses has invalid values")
    if score.ending_responses and score.narrative_segment is not NarrativeSegment.ENDING:
        raise ValueError("Ending responses are permitted only on ending scores")
    if score.centrality == 0 and score.ending_responses:
        raise ValueError("A not-evidenced cell may not contain ending responses")


def _unique_film_map(
    scores: Iterable[FilmThemeScore],
) -> dict[tuple[str, Theme, NarrativeSegment], FilmThemeScore]:
    mapped: dict[tuple[str, Theme, NarrativeSegment], FilmThemeScore] = {}
    for score in scores:
        _validate_film_score(score)
        key = _film_key(score)
        if key in mapped:
            raise ValueError(f"Duplicate comparison unit: {_cell_label(key)}")
        mapped[key] = score
    return mapped


def _expected_film_cells(
    film_ids: Iterable[str],
) -> set[tuple[str, Theme, NarrativeSegment]]:
    return {
        (film_id, theme, segment)
        for film_id in film_ids
        for theme in Theme
        for segment in NarrativeSegment
    }


def _derive_film_score_grid(
    manifest: PilotValidationManifest,
    assigned: Sequence[AssignedSourceAgreement],
    *,
    replicate: str,
    omitted_source_id: str | None = None,
) -> tuple[FilmThemeScore, ...]:
    if replicate not in {"left", "right"}:
        raise ValueError("replicate must be left or right")
    groups: dict[
        tuple[str, Theme, NarrativeSegment], list[SourceVote]
    ] = {}
    for item in assigned:
        if item.source_id == omitted_source_id:
            continue
        votes = (
            item.agreement.left_votes
            if replicate == "left"
            else item.agreement.right_votes
        )
        for vote in votes:
            groups.setdefault(_film_key_from_vote(vote), []).append(vote)

    scores = []
    for film_id in sorted(manifest.film_ids):
        for theme in Theme:
            for segment in NarrativeSegment:
                key = (film_id, theme, segment)
                votes = groups.get(key, ())
                scores.append(
                    aggregate_film_theme(votes)
                    if votes
                    else not_evidenced_score(film_id, theme, segment)
                )
    return tuple(scores)


def _film_key_from_vote(
    vote: SourceVote,
) -> tuple[str, Theme, NarrativeSegment]:
    return (vote.film_id, vote.theme, vote.narrative_segment)


@dataclass(frozen=True, slots=True)
class FilmAgreement:
    manifest_digest: str
    expected_film_ids: frozenset[str]
    left_film_ids: frozenset[str]
    right_film_ids: frozenset[str]
    left_scores: tuple[FilmThemeScore, ...]
    right_scores: tuple[FilmThemeScore, ...]
    expected_cells: int
    evidenced_cells: int
    centrality_exact_cells: int
    stance_exact_cells: int
    direct_polarity_flip_cells: tuple[str, ...]
    left_missing_cells: tuple[str, ...]
    right_missing_cells: tuple[str, ...]
    left_extra_cells: tuple[str, ...]
    right_extra_cells: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_sha256(self.manifest_digest, "FilmAgreement.manifest_digest")
        for name in ("left_scores", "right_scores"):
            values = getattr(self, name)
            if type(values) is not tuple or any(
                not isinstance(value, FilmThemeScore) for value in values
            ):
                raise TypeError(f"FilmAgreement.{name} must contain FilmThemeScore values")
        for name in (
            "expected_cells",
            "evidenced_cells",
            "centrality_exact_cells",
            "stance_exact_cells",
        ):
            _require_count(getattr(self, name), f"FilmAgreement.{name}")
        if self.centrality_exact_cells > self.evidenced_cells:
            raise ValueError("centrality_exact_cells exceeds evidenced_cells")
        if self.stance_exact_cells > self.evidenced_cells:
            raise ValueError("stance_exact_cells exceeds evidenced_cells")

    @property
    def centrality_exact_rate(self) -> float | None:
        return _ratio(self.centrality_exact_cells, self.evidenced_cells)

    @property
    def stance_exact_rate(self) -> float | None:
        return _ratio(self.stance_exact_cells, self.evidenced_cells)

    @property
    def direct_polarity_flips(self) -> int:
        return len(self.direct_polarity_flip_cells)

    @property
    def universe_complete(self) -> bool:
        return not (
            self.left_missing_cells
            or self.right_missing_cells
            or self.left_extra_cells
            or self.right_extra_cells
        )


def compare_film_scores(
    left: Iterable[FilmThemeScore],
    right: Iterable[FilmThemeScore],
    *,
    manifest: PilotValidationManifest,
) -> FilmAgreement:
    """Compare full replicate cell grids tied to the validation manifest."""

    if not isinstance(manifest, PilotValidationManifest):
        raise TypeError("manifest must be a PilotValidationManifest")
    left_items = tuple(left)
    right_items = tuple(right)
    left_map = _unique_film_map(left_items)
    right_map = _unique_film_map(right_items)
    expected = _expected_film_cells(manifest.film_ids)
    left_keys = set(left_map)
    right_keys = set(right_map)
    evidenced = {
        key
        for key in left_keys | right_keys
        if (key in left_map and left_map[key].centrality > 0)
        or (key in right_map and right_map[key].centrality > 0)
    }
    centrality_exact = 0
    stance_exact = 0
    flips: list[str] = []
    for key in evidenced:
        left_score = left_map.get(key)
        right_score = right_map.get(key)
        if left_score is None or right_score is None:
            continue
        centrality_exact += left_score.centrality == right_score.centrality
        stance_exact += left_score.stance is right_score.stance
        if {left_score.stance, right_score.stance} == {
            FilmStance.AFFIRMATIVE,
            FilmStance.CRITICAL,
        }:
            flips.append(_cell_label(key))
    return FilmAgreement(
        manifest_digest=manifest.digest,
        expected_film_ids=manifest.film_ids,
        left_film_ids=frozenset(key[0] for key in left_keys),
        right_film_ids=frozenset(key[0] for key in right_keys),
        left_scores=left_items,
        right_scores=right_items,
        expected_cells=len(expected),
        evidenced_cells=len(evidenced),
        centrality_exact_cells=centrality_exact,
        stance_exact_cells=stance_exact,
        direct_polarity_flip_cells=tuple(sorted(flips)),
        left_missing_cells=tuple(
            sorted(_cell_label(key) for key in expected - left_keys)
        ),
        right_missing_cells=tuple(
            sorted(_cell_label(key) for key in expected - right_keys)
        ),
        left_extra_cells=tuple(
            sorted(_cell_label(key) for key in left_keys - expected)
        ),
        right_extra_cells=tuple(
            sorted(_cell_label(key) for key in right_keys - expected)
        ),
    )


@dataclass(frozen=True, slots=True)
class LateRetributionRun:
    replicate_id: str
    assessed_cells: frozenset[tuple[str, Theme]]
    flagged_cells: frozenset[tuple[str, Theme]]
    calculation_record_hash: str

    def __post_init__(self) -> None:
        _require_nonempty(self.replicate_id, "LateRetributionRun.replicate_id")
        _require_sha256(
            self.calculation_record_hash,
            "LateRetributionRun.calculation_record_hash",
        )
        for name in ("assessed_cells", "flagged_cells"):
            values = getattr(self, name)
            if type(values) is not frozenset:
                raise TypeError(f"{name} must be a frozenset")
            for value in values:
                if (
                    not isinstance(value, tuple)
                    or len(value) != 2
                    or not isinstance(value[0], str)
                    or not value[0].strip()
                    or not isinstance(value[1], Theme)
                ):
                    raise TypeError(
                        f"Invalid glamorize_then_punish cell in {name}"
                    )
        if not self.flagged_cells <= self.assessed_cells:
            raise ValueError(
                "Flagged glamorize_then_punish cells must have been assessed"
            )


@dataclass(frozen=True, slots=True)
class LateRetributionAgreement:
    manifest_digest: str
    left_run: LateRetributionRun
    right_run: LateRetributionRun
    flagged_union_cells: int
    jointly_flagged_cells: int
    disagreement_cells: int
    exact_rate: float | None
    universe_gate: GateResult
    gate: GateResult

    def __post_init__(self) -> None:
        _require_sha256(self.manifest_digest, "LateRetributionAgreement.manifest_digest")
        if not isinstance(self.left_run, LateRetributionRun) or not isinstance(
            self.right_run, LateRetributionRun
        ):
            raise TypeError("Late-retribution agreement must retain two run records")
        for name in (
            "flagged_union_cells",
            "jointly_flagged_cells",
            "disagreement_cells",
        ):
            _require_count(getattr(self, name), f"LateRetributionAgreement.{name}")
        if self.jointly_flagged_cells + self.disagreement_cells != self.flagged_union_cells:
            raise ValueError(
                "glamorize_then_punish union accounting is inconsistent"
            )
        expected_rate = _ratio(self.jointly_flagged_cells, self.flagged_union_cells)
        if self.exact_rate != expected_rate:
            raise ValueError(
                "glamorize_then_punish exact_rate is inconsistent"
            )


def compare_late_retribution(
    left: LateRetributionRun,
    right: LateRetributionRun,
    *,
    manifest: PilotValidationManifest,
    left_scores: Sequence[FilmThemeScore],
    right_scores: Sequence[FilmThemeScore],
) -> LateRetributionAgreement:
    if not isinstance(left, LateRetributionRun) or not isinstance(
        right, LateRetributionRun
    ):
        raise TypeError(
            "glamorize_then_punish comparisons require two run records"
        )
    if left.replicate_id == right.replicate_id:
        raise ValueError(
            "glamorize_then_punish replicates must have distinct IDs"
        )
    expected = {(film_id, theme) for film_id in manifest.film_ids for theme in Theme}
    expected_score_cells = _expected_film_cells(manifest.film_ids)
    left_score_map = _unique_film_map(left_scores)
    right_score_map = _unique_film_map(right_scores)
    missing_left = sorted(expected - left.assessed_cells, key=_late_cell_label)
    missing_right = sorted(expected - right.assessed_cells, key=_late_cell_label)
    extra_left = sorted(left.assessed_cells - expected, key=_late_cell_label)
    extra_right = sorted(right.assessed_cells - expected, key=_late_cell_label)
    universe_errors = [
        *(f"left_missing:{_late_cell_label(key)}" for key in missing_left),
        *(f"right_missing:{_late_cell_label(key)}" for key in missing_right),
        *(f"left_extra:{_late_cell_label(key)}" for key in extra_left),
        *(f"right_extra:{_late_cell_label(key)}" for key in extra_right),
    ]
    for label, score_map, run in (
        ("left", left_score_map, left),
        ("right", right_score_map, right),
    ):
        if set(score_map) != expected_score_cells:
            universe_errors.append(f"{label}_score_universe_incomplete")
            continue
        calculated = {
            (film_id, theme)
            for film_id, theme in expected
            if glamorize_then_punish(
                score_map[(film_id, theme, NarrativeSegment.MAIN_BODY)],
                score_map[(film_id, theme, NarrativeSegment.ENDING)],
            )
        }
        for key in sorted(calculated - run.flagged_cells, key=_late_cell_label):
            universe_errors.append(f"{label}_missing_flag:{_late_cell_label(key)}")
        for key in sorted(run.flagged_cells - calculated, key=_late_cell_label):
            universe_errors.append(f"{label}_unsupported_flag:{_late_cell_label(key)}")
    universe_gate = GateResult(
        name="glamorize_then_punish_universe",
        status=GateStatus.FAIL if universe_errors else GateStatus.PASS,
        observed=len(universe_errors),
        criterion=(
            "both replicates assess every manifest film/theme cell for "
            "glamorize_then_punish exactly once"
        ),
        details=tuple(universe_errors),
    )
    union = left.flagged_cells | right.flagged_cells
    joint = left.flagged_cells & right.flagged_cells
    disagreement = left.flagged_cells ^ right.flagged_cells
    exact_rate = _ratio(len(joint), len(union))
    if not union:
        flag_gate = GateResult(
            name="glamorize_then_punish_exact",
            status=GateStatus.NOT_EVALUABLE,
            observed=None,
            criterion=(
                "agreement for every glamorize_then_punish cell flagged by "
                "either replicate"
            ),
            details=(
                "Neither replicate flagged a glamorize_then_punish cell.",
            ),
        )
    else:
        flag_gate = GateResult(
            name="glamorize_then_punish_exact",
            status=GateStatus.PASS if not disagreement else GateStatus.FAIL,
            observed=exact_rate,
            criterion=(
                "agreement for every glamorize_then_punish cell flagged by "
                "either replicate"
            ),
            details=tuple(sorted(_late_cell_label(key) for key in disagreement)),
        )
    return LateRetributionAgreement(
        manifest_digest=manifest.digest,
        left_run=left,
        right_run=right,
        flagged_union_cells=len(union),
        jointly_flagged_cells=len(joint),
        disagreement_cells=len(disagreement),
        exact_rate=exact_rate,
        universe_gate=universe_gate,
        gate=flag_gate,
    )


@dataclass(frozen=True, slots=True)
class OmissionRun:
    omitted_source_id: str
    included_source_ids_left: frozenset[str]
    included_source_ids_right: frozenset[str]
    left_scores: tuple[FilmThemeScore, ...]
    right_scores: tuple[FilmThemeScore, ...]
    left_late_retribution: LateRetributionRun
    right_late_retribution: LateRetributionRun
    upstream_provenance_verified: bool
    provenance_verification_hash: str

    def __post_init__(self) -> None:
        _require_nonempty(self.omitted_source_id, "OmissionRun.omitted_source_id")
        for name in ("included_source_ids_left", "included_source_ids_right"):
            values = getattr(self, name)
            if type(values) is not frozenset or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise TypeError(f"{name} must be a frozenset of nonempty strings")
        for name in ("left_scores", "right_scores"):
            values = getattr(self, name)
            if type(values) is not tuple or any(
                not isinstance(value, FilmThemeScore) for value in values
            ):
                raise TypeError(f"{name} must be a tuple of FilmThemeScore")
        if not isinstance(self.left_late_retribution, LateRetributionRun) or not isinstance(
            self.right_late_retribution, LateRetributionRun
        ):
            raise TypeError(
                "OmissionRun glamorize_then_punish values must be run records"
            )
        _require_bool(self.upstream_provenance_verified, "upstream_provenance_verified")
        _require_sha256(
            self.provenance_verification_hash, "provenance_verification_hash"
        )


@dataclass(frozen=True, slots=True)
class LeaveOneOutAgreement:
    manifest_digest: str
    runs: tuple[OmissionRun, ...]
    baseline_left_scores: tuple[FilmThemeScore, ...]
    baseline_right_scores: tuple[FilmThemeScore, ...]
    baseline_left_late_retribution: LateRetributionRun
    baseline_right_late_retribution: LateRetributionRun
    expected_omissions: int
    completed_omissions: int
    evidenced_cell_comparisons: int
    direct_polarity_flip_cells: tuple[str, ...]
    missing_omissions: tuple[str, ...]
    unexpected_omissions: tuple[str, ...]
    not_evaluable_omissions: tuple[str, ...]
    provenance_violations: tuple[str, ...]
    centrality_change_cells: tuple[str, ...]
    stance_change_cells: tuple[str, ...]
    late_retribution_change_cells: tuple[str, ...]
    gate: GateResult

    @property
    def direct_polarity_flips(self) -> int:
        return len(self.direct_polarity_flip_cells)


def compare_leave_one_source_out(
    runs: Sequence[OmissionRun],
    *,
    manifest: PilotValidationManifest,
    baseline_left_scores: Sequence[FilmThemeScore],
    baseline_right_scores: Sequence[FilmThemeScore],
    baseline_left_late_retribution: LateRetributionRun,
    baseline_right_late_retribution: LateRetributionRun,
) -> LeaveOneOutAgreement:
    """Verify each omission provenance record and compare its two replicates."""

    run_items = tuple(runs)
    baseline_left_items = tuple(baseline_left_scores)
    baseline_right_items = tuple(baseline_right_scores)
    if any(not isinstance(run, OmissionRun) for run in run_items):
        raise TypeError("runs must contain OmissionRun values")
    omitted_ids = [run.omitted_source_id for run in run_items]
    if len(omitted_ids) != len(set(omitted_ids)):
        raise ValueError("Each source may have only one omission run")
    expected = manifest.eligible_source_ids
    actual = frozenset(omitted_ids)
    missing = tuple(sorted(expected - actual))
    unexpected = tuple(sorted(actual - expected))

    baseline_left_map = _unique_film_map(baseline_left_items)
    baseline_right_map = _unique_film_map(baseline_right_items)
    baseline_agreement = compare_film_scores(
        baseline_left_items, baseline_right_items, manifest=manifest
    )
    baseline_late = compare_late_retribution(
        baseline_left_late_retribution,
        baseline_right_late_retribution,
        manifest=manifest,
        left_scores=baseline_left_items,
        right_scores=baseline_right_items,
    )
    baseline_integrity = baseline_agreement.universe_complete and (
        baseline_late.universe_gate.status is GateStatus.PASS
    )

    comparisons = 0
    flips: list[str] = []
    not_evaluable: list[str] = []
    provenance: list[str] = []
    centrality_changes: list[str] = []
    stance_changes: list[str] = []
    late_changes: list[str] = []
    for run in run_items:
        if run.omitted_source_id not in expected:
            continue
        expected_included = expected - {run.omitted_source_id}
        if run.included_source_ids_left != expected_included:
            provenance.append(f"left_source_set:{run.omitted_source_id}")
        if run.included_source_ids_right != expected_included:
            provenance.append(f"right_source_set:{run.omitted_source_id}")
        if not run.upstream_provenance_verified:
            provenance.append(f"unverified:{run.omitted_source_id}")
        agreement = compare_film_scores(
            run.left_scores, run.right_scores, manifest=manifest
        )
        late = compare_late_retribution(
            run.left_late_retribution,
            run.right_late_retribution,
            manifest=manifest,
            left_scores=run.left_scores,
            right_scores=run.right_scores,
        )
        if not agreement.universe_complete:
            provenance.append(f"incomplete_film_universe:{run.omitted_source_id}")
        if late.universe_gate.status is not GateStatus.PASS:
            provenance.append(f"incomplete_late_universe:{run.omitted_source_id}")
        comparisons += agreement.evidenced_cells
        if agreement.evidenced_cells == 0:
            not_evaluable.append(run.omitted_source_id)
        flips.extend(
            f"{run.omitted_source_id}|{cell}"
            for cell in agreement.direct_polarity_flip_cells
        )
        left_map = _unique_film_map(run.left_scores)
        right_map = _unique_film_map(run.right_scores)
        if baseline_integrity and agreement.universe_complete:
            for replicate, base_map, omission_map in (
                ("left", baseline_left_map, left_map),
                ("right", baseline_right_map, right_map),
            ):
                for key in sorted(base_map, key=_cell_label):
                    if base_map[key].centrality != omission_map[key].centrality:
                        centrality_changes.append(
                            f"{run.omitted_source_id}|{replicate}|{_cell_label(key)}"
                        )
                    if base_map[key].stance is not omission_map[key].stance:
                        stance_changes.append(
                            f"{run.omitted_source_id}|{replicate}|{_cell_label(key)}"
                        )
            for replicate, base_run, omission_run in (
                (
                    "left",
                    baseline_left_late_retribution,
                    run.left_late_retribution,
                ),
                (
                    "right",
                    baseline_right_late_retribution,
                    run.right_late_retribution,
                ),
            ):
                for key in base_run.flagged_cells ^ omission_run.flagged_cells:
                    late_changes.append(
                        f"{run.omitted_source_id}|{replicate}|{_late_cell_label(key)}"
                    )

    if missing or unexpected or provenance or flips:
        status = GateStatus.FAIL
    elif not run_items or not baseline_integrity or not_evaluable:
        status = GateStatus.NOT_EVALUABLE
    else:
        status = GateStatus.PASS
    details = tuple(
        [
            *(f"missing:{value}" for value in missing),
            *(f"unexpected:{value}" for value in unexpected),
            *(f"provenance:{value}" for value in sorted(provenance)),
            *sorted(flips),
            *(f"no_evidenced_cells:{value}" for value in sorted(not_evaluable)),
        ]
    )
    return LeaveOneOutAgreement(
        manifest_digest=manifest.digest,
        runs=run_items,
        baseline_left_scores=baseline_left_items,
        baseline_right_scores=baseline_right_items,
        baseline_left_late_retribution=baseline_left_late_retribution,
        baseline_right_late_retribution=baseline_right_late_retribution,
        expected_omissions=len(expected),
        completed_omissions=len(actual & expected),
        evidenced_cell_comparisons=comparisons,
        direct_polarity_flip_cells=tuple(sorted(flips)),
        missing_omissions=missing,
        unexpected_omissions=unexpected,
        not_evaluable_omissions=tuple(sorted(not_evaluable)),
        provenance_violations=tuple(sorted(provenance)),
        centrality_change_cells=tuple(sorted(centrality_changes)),
        stance_change_cells=tuple(sorted(stance_changes)),
        late_retribution_change_cells=tuple(sorted(late_changes)),
        gate=GateResult(
            name="leave_one_source_out_no_polarity_reversal",
            status=status,
            observed=len(flips),
            criterion=(
                "one provenance-verified omission per manifest source and zero "
                "between-replicate polarity reversals"
            ),
            details=details,
        ),
    )


@dataclass(frozen=True, slots=True)
class FilmRepeatabilityEvaluation:
    manifest_digest: str
    agreement: FilmAgreement
    late_retribution: LateRetributionAgreement
    leave_one_out: LeaveOneOutAgreement
    hard_gates: tuple[GateResult, ...]
    repeatability_gates: tuple[GateResult, ...]


def evaluate_film_repeatability(
    agreement: FilmAgreement,
    late_retribution: LateRetributionAgreement,
    leave_one_out: LeaveOneOutAgreement,
) -> FilmRepeatabilityEvaluation:
    if not isinstance(agreement, FilmAgreement):
        raise TypeError("agreement must be a FilmAgreement")
    if not isinstance(late_retribution, LateRetributionAgreement):
        raise TypeError(
            "glamorize_then_punish must be a LateRetributionAgreement"
        )
    if not isinstance(leave_one_out, LeaveOneOutAgreement):
        raise TypeError("leave_one_out must be a LeaveOneOutAgreement")
    digests = {
        agreement.manifest_digest,
        late_retribution.manifest_digest,
        leave_one_out.manifest_digest,
    }
    alignment = GateResult(
        name="film_component_manifest_alignment",
        status=GateStatus.PASS if len(digests) == 1 else GateStatus.FAIL,
        observed=len(digests),
        criterion="all film-level components use one frozen manifest",
    )
    universe_errors = (
        agreement.left_missing_cells
        + agreement.right_missing_cells
        + agreement.left_extra_cells
        + agreement.right_extra_cells
    )
    film_universe = GateResult(
        name="film_score_universe",
        status=GateStatus.FAIL if universe_errors else GateStatus.PASS,
        observed=len(universe_errors),
        criterion="both replicates contain the complete manifest film/theme/segment grid",
        details=universe_errors,
    )
    if agreement.evidenced_cells == 0:
        polarity_status = GateStatus.NOT_EVALUABLE
        polarity_details = ("No evidenced film cell was available.",)
    elif agreement.direct_polarity_flips:
        polarity_status = GateStatus.FAIL
        polarity_details = agreement.direct_polarity_flip_cells
    else:
        polarity_status = GateStatus.PASS
        polarity_details = ()
    polarity = GateResult(
        name="replicate_film_no_polarity_reversal",
        status=polarity_status,
        observed=agreement.direct_polarity_flips,
        criterion="zero affirmative-versus-critical reversals",
        details=polarity_details,
    )
    return FilmRepeatabilityEvaluation(
        manifest_digest=agreement.manifest_digest,
        agreement=agreement,
        late_retribution=late_retribution,
        leave_one_out=leave_one_out,
        hard_gates=(
            alignment,
            film_universe,
            late_retribution.universe_gate,
            polarity,
            leave_one_out.gate,
        ),
        repeatability_gates=(
            _rate_gate(
                "film_centrality_exact",
                agreement.centrality_exact_rate,
                FILM_CENTRALITY_EXACT_MIN,
            ),
            late_retribution.gate,
        ),
    )


@dataclass(frozen=True, slots=True)
class NegativeControlAssignment:
    assignment_id: str
    source_id: str
    kind: NegativeControlKind
    source_film_id: str
    target_film_id: str
    source_content_hash: str
    intervention_hash: str
    target_unmentioned_verified: bool

    def __post_init__(self) -> None:
        for name in (
            "assignment_id",
            "source_id",
            "source_film_id",
            "target_film_id",
        ):
            _require_nonempty(
                getattr(self, name), f"NegativeControlAssignment.{name}"
            )
        if not isinstance(self.kind, NegativeControlKind):
            raise TypeError("kind must be a NegativeControlKind")
        _require_sha256(self.source_content_hash, "source_content_hash")
        _require_sha256(self.intervention_hash, "intervention_hash")
        _require_bool(self.target_unmentioned_verified, "target_unmentioned_verified")

    @property
    def digest(self) -> str:
        return _canonical_digest(
            {
                "assignment_id": self.assignment_id,
                "source_id": self.source_id,
                "kind": self.kind.value,
                "source_film_id": self.source_film_id,
                "target_film_id": self.target_film_id,
                "source_content_hash": self.source_content_hash,
                "intervention_hash": self.intervention_hash,
                "target_unmentioned_verified": self.target_unmentioned_verified,
            }
        )


def negative_control_assignment_digest(
    assignments: Sequence[NegativeControlAssignment],
) -> str:
    if any(not isinstance(item, NegativeControlAssignment) for item in assignments):
        raise TypeError("assignments must contain NegativeControlAssignment values")
    ids = [item.assignment_id for item in assignments]
    if len(ids) != len(set(ids)):
        raise ValueError("Negative-control assignment IDs must be unique")
    return _canonical_digest(sorted(item.digest for item in assignments))


@dataclass(frozen=True, slots=True)
class NegativeControlResult:
    assignment_id: str
    assignment_hash: str
    accepted_records: int

    def __post_init__(self) -> None:
        _require_nonempty(self.assignment_id, "NegativeControlResult.assignment_id")
        _require_sha256(self.assignment_hash, "NegativeControlResult.assignment_hash")
        _require_count(self.accepted_records, "NegativeControlResult.accepted_records")


@dataclass(frozen=True, slots=True)
class NegativeControlSummary:
    manifest_digest: str
    expected_source_ids: frozenset[str]
    assignments: tuple[NegativeControlAssignment, ...]
    results: tuple[NegativeControlResult, ...]
    corrupted_runs: int
    corrupted_rejected: int
    corrupted_accepted_records: int
    wrong_film_runs: int
    wrong_film_rejected: int
    wrong_film_accepted_records: int
    missing_controls: tuple[str, ...]
    duplicate_controls: tuple[str, ...]
    unexpected_controls: tuple[str, ...]
    assignment_violations: tuple[str, ...]
    gate: GateResult


def summarize_negative_controls(
    manifest: PilotValidationManifest,
    assignments: Sequence[NegativeControlAssignment],
    results: Sequence[NegativeControlResult],
) -> NegativeControlSummary:
    """Verify frozen control identities, pairings, execution, and rejection."""

    assignment_items = tuple(assignments)
    result_items = tuple(results)
    if any(
        not isinstance(item, NegativeControlAssignment) for item in assignment_items
    ):
        raise TypeError("assignments must contain NegativeControlAssignment values")
    if any(not isinstance(item, NegativeControlResult) for item in result_items):
        raise TypeError("results must contain NegativeControlResult values")
    assignment_ids = [item.assignment_id for item in assignment_items]
    if len(assignment_ids) != len(set(assignment_ids)):
        raise ValueError("Negative-control assignment IDs must be unique")
    result_ids = [item.assignment_id for item in result_items]
    result_counts = Counter(result_ids)
    assignment_map = {item.assignment_id: item for item in assignment_items}
    result_map = {item.assignment_id: item for item in result_items}
    expected_sources = manifest.eligible_source_ids
    required_pairs = {
        (source_id, kind) for source_id in expected_sources for kind in NegativeControlKind
    }
    actual_pairs = {(item.source_id, item.kind) for item in assignment_items}
    missing = tuple(
        sorted(
            f"{source_id}|{kind.value}"
            for source_id, kind in required_pairs - actual_pairs
        )
    )
    pair_counts = Counter((item.source_id, item.kind) for item in assignment_items)
    duplicate = tuple(
        sorted(
            f"{source_id}|{kind.value}"
            for (source_id, kind), count in pair_counts.items()
            if count != 1
        )
    )
    unexpected = tuple(
        sorted(
            f"{source_id}|{kind.value}"
            for source_id, kind in actual_pairs - required_pairs
        )
    )
    violations: list[str] = []
    if (
        negative_control_assignment_digest(assignment_items)
        != manifest.control_assignment_set_hash
    ):
        violations.append("assignment_set_hash_mismatch")
    for assignment in assignment_items:
        expected = manifest.source_index.get(assignment.source_id)
        if expected is None:
            violations.append(f"unknown_source:{assignment.assignment_id}")
            continue
        film, source = expected
        if assignment.source_film_id != film.film_id:
            violations.append(f"source_film_mismatch:{assignment.assignment_id}")
        if assignment.source_content_hash != source.content_hash:
            violations.append(f"source_hash_mismatch:{assignment.assignment_id}")
        if assignment.intervention_hash == assignment.source_content_hash:
            violations.append(f"unchanged_intervention:{assignment.assignment_id}")
        if assignment.kind is NegativeControlKind.CORRUPTED_QUOTATION:
            if assignment.target_film_id != film.film_id:
                violations.append(f"corruption_target_mismatch:{assignment.assignment_id}")
        else:
            if assignment.target_film_id == film.film_id:
                violations.append(f"wrong_film_not_deranged:{assignment.assignment_id}")
            if assignment.target_film_id not in manifest.film_ids:
                violations.append(f"wrong_film_outside_manifest:{assignment.assignment_id}")
            if not assignment.target_unmentioned_verified:
                violations.append(f"target_mentions_source:{assignment.assignment_id}")
    for value in sorted(set(assignment_map) - set(result_map)):
        violations.append(f"missing_result:{value}")
    for value in sorted(set(result_map) - set(assignment_map)):
        violations.append(f"unexpected_result:{value}")
    for value, count in sorted(result_counts.items()):
        if count != 1:
            violations.append(f"duplicate_result:{value}")
    for assignment_id in sorted(set(assignment_map) & set(result_map)):
        if result_map[assignment_id].assignment_hash != assignment_map[assignment_id].digest:
            violations.append(f"result_hash_mismatch:{assignment_id}")

    corrupted_ids = {
        item.assignment_id
        for item in assignment_items
        if item.kind is NegativeControlKind.CORRUPTED_QUOTATION
    }
    wrong_ids = {
        item.assignment_id
        for item in assignment_items
        if item.kind is NegativeControlKind.WRONG_FILM
    }
    corrupted_results = [
        item for item in result_items if item.assignment_id in corrupted_ids
    ]
    wrong_results = [item for item in result_items if item.assignment_id in wrong_ids]
    corrupted_accepted = sum(item.accepted_records for item in corrupted_results)
    wrong_accepted = sum(item.accepted_records for item in wrong_results)
    accepted_violations = corrupted_accepted + wrong_accepted
    failed = bool(missing or duplicate or unexpected or violations or accepted_violations)
    return NegativeControlSummary(
        manifest_digest=manifest.digest,
        expected_source_ids=expected_sources,
        assignments=assignment_items,
        results=result_items,
        corrupted_runs=len(corrupted_results),
        corrupted_rejected=sum(item.accepted_records == 0 for item in corrupted_results),
        corrupted_accepted_records=corrupted_accepted,
        wrong_film_runs=len(wrong_results),
        wrong_film_rejected=sum(item.accepted_records == 0 for item in wrong_results),
        wrong_film_accepted_records=wrong_accepted,
        missing_controls=missing,
        duplicate_controls=duplicate,
        unexpected_controls=unexpected,
        assignment_violations=tuple(sorted(violations)),
        gate=GateResult(
            name="negative_controls",
            status=GateStatus.FAIL if failed else GateStatus.PASS,
            observed=accepted_violations,
            criterion=(
                "one frozen control of each kind per manifest source, verified pairing, "
                "and zero accepted control records"
            ),
            details=tuple(
                [
                    *(f"missing:{value}" for value in missing),
                    *(f"duplicate:{value}" for value in duplicate),
                    *(f"unexpected:{value}" for value in unexpected),
                    *(f"assignment:{value}" for value in sorted(violations)),
                ]
            ),
        ),
    )


@dataclass(frozen=True, slots=True)
class MechanicalGateInputs:
    processed_source_ids: frozenset[str]
    actual_model_environment: str
    public_repository_scan_verified: bool
    publicly_committed_credentials: int
    publicly_committed_restricted_full_texts: int
    publicly_committed_unlicensed_corpora: int
    accepted_records: int
    accepted_record_source_ids: frozenset[str]
    schema_valid_records: int
    provenance_complete_records: int
    exact_evidence_records: int
    ending_cells_assessed: int
    late_retribution_results: int
    late_retribution_results_with_separate_evidence: int
    external_punishment_only_main_stance_changes: int

    def __post_init__(self) -> None:
        for name in ("processed_source_ids", "accepted_record_source_ids"):
            values = getattr(self, name)
            if type(values) is not frozenset or any(
                not isinstance(value, str) or not value.strip() for value in values
            ):
                raise TypeError(f"{name} must be a frozenset of nonempty strings")
        _require_nonempty(self.actual_model_environment, "actual_model_environment")
        _require_bool(
            self.public_repository_scan_verified, "public_repository_scan_verified"
        )
        count_fields = (
            "publicly_committed_credentials",
            "publicly_committed_restricted_full_texts",
            "publicly_committed_unlicensed_corpora",
            "accepted_records",
            "schema_valid_records",
            "provenance_complete_records",
            "exact_evidence_records",
            "ending_cells_assessed",
            "late_retribution_results",
            "late_retribution_results_with_separate_evidence",
            "external_punishment_only_main_stance_changes",
        )
        for field in count_fields:
            _require_count(getattr(self, field), f"MechanicalGateInputs.{field}")
        if self.accepted_records == 0 and self.accepted_record_source_ids:
            raise ValueError("Zero accepted records cannot identify accepted-record sources")
        if self.accepted_records and not self.accepted_record_source_ids:
            raise ValueError("Accepted records must identify at least one frozen source")
        if len(self.accepted_record_source_ids) > self.accepted_records:
            raise ValueError("Accepted-record source count exceeds accepted records")
        if not self.accepted_record_source_ids <= self.processed_source_ids:
            raise ValueError("Accepted records identify an unprocessed source")
        bounded = (
            (self.schema_valid_records, self.accepted_records),
            (self.provenance_complete_records, self.accepted_records),
            (self.exact_evidence_records, self.accepted_records),
            (self.late_retribution_results, self.ending_cells_assessed),
            (
                self.late_retribution_results_with_separate_evidence,
                self.late_retribution_results,
            ),
        )
        if any(numerator > denominator for numerator, denominator in bounded):
            raise ValueError("A successful mechanical count exceeds its denominator")


@dataclass(frozen=True, slots=True)
class MechanicalGateEvaluation:
    manifest_digest: str
    film_ids: frozenset[str]
    source_ids: frozenset[str]
    expected_periods: tuple[str, ...]
    inputs: MechanicalGateInputs
    gates: tuple[GateResult, ...]


def evaluate_mechanical_gates(
    manifest: PilotValidationManifest,
    inputs: MechanicalGateInputs,
) -> MechanicalGateEvaluation:
    if not isinstance(manifest, PilotValidationManifest):
        raise TypeError("manifest must be a PilotValidationManifest")
    if not isinstance(inputs, MechanicalGateInputs):
        raise TypeError("inputs must be MechanicalGateInputs")
    period_counts = Counter(film.period for film in manifest.films)
    coverage_errors = [
        *(
            f"missing_period:{period}"
            for period in FROZEN_PILOT_PERIODS
            if period_counts[period] == 0
        ),
        *(
            f"duplicate_period:{period}"
            for period in FROZEN_PILOT_PERIODS
            if period_counts[period] > 1
        ),
        *(
            f"unexpected_period:{period}"
            for period in sorted(set(period_counts) - set(FROZEN_PILOT_PERIODS))
        ),
    ]
    if not manifest.frozen_before_validation:
        coverage_errors.append("manifest_not_frozen_before_validation")
    for film in manifest.films:
        eligible = [source for source in film.sources if source.eligibility_verified]
        slots = {source.slot for source in eligible}
        if not film.untouched:
            coverage_errors.append(f"not_untouched:{film.film_id}")
        if len(eligible) < 4:
            coverage_errors.append(f"fewer_than_four_sources:{film.film_id}")
        for slot in sorted(_CORE_SLOTS - slots, key=lambda value: value.value):
            coverage_errors.append(f"missing_slot:{film.film_id}|{slot.value}")
        if not slots & _LATER_SLOTS:
            coverage_errors.append(f"missing_later_source:{film.film_id}")
        if SourceSlot.R_LATER_2 in slots and SourceSlot.R_LATER not in slots:
            coverage_errors.append(
                f"orphan_scholarship_substitute:{film.film_id}"
            )
        if SourceSlot.R_LATER_2 in slots and SourceSlot.S_ACADEMIC in slots:
            coverage_errors.append(
                f"substitute_coexists_with_academic:{film.film_id}"
            )
        lineages = [source.lineage_id for source in eligible]
        if len(lineages) != len(set(lineages)):
            coverage_errors.append(f"dependent_sources:{film.film_id}")
    coverage = GateResult(
        name="coverage",
        status=GateStatus.FAIL if coverage_errors else GateStatus.PASS,
        observed=len(manifest.films),
        criterion=(
            "one untouched validation film in each frozen period with both "
            "contemporary slots, synopsis, later/scholarly source, and four lineages"
        ),
        details=tuple(coverage_errors),
    )

    expected_sources = manifest.eligible_source_ids
    rights_errors = [
        *(
            f"missing_processed_source:{value}"
            for value in sorted(expected_sources - inputs.processed_source_ids)
        ),
        *(
            f"unexpected_processed_source:{value}"
            for value in sorted(inputs.processed_source_ids - expected_sources)
        ),
    ]
    for source_id in sorted(expected_sources & inputs.processed_source_ids):
        _, source = manifest.source_index[source_id]
        if not source.processing_permitted:
            rights_errors.append(f"processing_not_permitted:{source_id}")
        if inputs.actual_model_environment not in source.permitted_model_environments:
            rights_errors.append(f"environment_not_permitted:{source_id}")
    if not inputs.public_repository_scan_verified:
        rights_errors.append("public_repository_scan_not_verified")
    for name in (
        "publicly_committed_credentials",
        "publicly_committed_restricted_full_texts",
        "publicly_committed_unlicensed_corpora",
    ):
        value = getattr(inputs, name)
        if value:
            rights_errors.append(f"{name}:{value}")
    if not expected_sources and not inputs.processed_source_ids:
        rights_status = GateStatus.NOT_EVALUABLE
    else:
        rights_status = GateStatus.FAIL if rights_errors else GateStatus.PASS
    rights = GateResult(
        name="rights",
        status=rights_status,
        observed=f"{len(inputs.processed_source_ids)}/{len(expected_sources)}",
        criterion=(
            "exact manifest source set; recorded permission compatible with the actual "
            "model environment; verified zero public credentials, restricted text, or "
            "unlicensed corpora"
        ),
        details=tuple(rights_errors),
    )

    if inputs.accepted_records == 0:
        schema_status = GateStatus.NOT_EVALUABLE
    elif (
        inputs.schema_valid_records == inputs.accepted_records
        and inputs.provenance_complete_records == inputs.accepted_records
        and inputs.accepted_record_source_ids <= expected_sources
    ):
        schema_status = GateStatus.PASS
    else:
        schema_status = GateStatus.FAIL
    schema = GateResult(
        name="schema_and_provenance",
        status=schema_status,
        observed=(
            f"schema:{inputs.schema_valid_records}/{inputs.accepted_records};"
            f"provenance:{inputs.provenance_complete_records}/{inputs.accepted_records}"
        ),
        criterion="100% schema-valid and manifest-linked provenance-complete records",
    )

    if inputs.accepted_records == 0:
        evidence_status = GateStatus.NOT_EVALUABLE
    elif inputs.exact_evidence_records == inputs.accepted_records:
        evidence_status = GateStatus.PASS
    else:
        evidence_status = GateStatus.FAIL
    evidence = GateResult(
        name="exact_evidence",
        status=evidence_status,
        observed=f"{inputs.exact_evidence_records}/{inputs.accepted_records}",
        criterion="100% exact evidence matches",
    )

    expected_ending_cells = len(manifest.film_ids) * len(Theme)
    if inputs.ending_cells_assessed == 0:
        ending_status = GateStatus.NOT_EVALUABLE
    elif (
        inputs.ending_cells_assessed == expected_ending_cells
        and inputs.late_retribution_results_with_separate_evidence
        == inputs.late_retribution_results
        and inputs.external_punishment_only_main_stance_changes == 0
    ):
        ending_status = GateStatus.PASS
    else:
        ending_status = GateStatus.FAIL
    ending = GateResult(
        name="ending_integrity",
        status=ending_status,
        observed=(
            "separate_evidence:"
            f"{inputs.late_retribution_results_with_separate_evidence}/"
            f"{inputs.late_retribution_results}"
        ),
        criterion=(
            "all glamorize_then_punish results have separate main/ending evidence; "
            "zero external-punishment-only main-stance changes"
        ),
        details=(
            f"ending_cells_assessed:{inputs.ending_cells_assessed}/{expected_ending_cells}",
            "external_punishment_only_main_stance_changes:"
            f"{inputs.external_punishment_only_main_stance_changes}",
        ),
    )
    return MechanicalGateEvaluation(
        manifest_digest=manifest.digest,
        film_ids=manifest.film_ids,
        source_ids=inputs.processed_source_ids,
        expected_periods=FROZEN_PILOT_PERIODS,
        inputs=inputs,
        gates=(coverage, rights, schema, evidence, ending),
    )


@dataclass(frozen=True, slots=True)
class SensitivityAssessment:
    manifest_digest: str
    report_hash: str
    completed_sections: frozenset[SensitivitySection]
    review_completed: bool
    systematic_period_failure: bool
    pervasive_one_source_dependence: bool
    model_source_interaction_failure: bool

    def __post_init__(self) -> None:
        _require_sha256(self.manifest_digest, "SensitivityAssessment.manifest_digest")
        _require_sha256(self.report_hash, "SensitivityAssessment.report_hash")
        if type(self.completed_sections) is not frozenset or any(
            not isinstance(value, SensitivitySection)
            for value in self.completed_sections
        ):
            raise TypeError("completed_sections must contain SensitivitySection values")
        for name in (
            "review_completed",
            "systematic_period_failure",
            "pervasive_one_source_dependence",
            "model_source_interaction_failure",
        ):
            _require_bool(getattr(self, name), f"SensitivityAssessment.{name}")


@dataclass(frozen=True, slots=True)
class PilotEvaluation:
    decision: PilotDecision
    hard_gates: tuple[GateResult, ...]
    repeatability_gates: tuple[GateResult, ...]
    failed_gates: tuple[str, ...]
    not_evaluable_gates: tuple[str, ...]
    decision_reasons: tuple[str, ...]


def evaluate_pilot(
    manifest: PilotValidationManifest,
    mechanical: MechanicalGateEvaluation,
    negative_controls: NegativeControlSummary,
    source_repeatability: SourceRepeatabilityEvaluation,
    film_repeatability: FilmRepeatabilityEvaluation,
    *,
    sensitivity: SensitivityAssessment,
    material_pipeline_change: bool,
    revision_feasible_without_changing_estimand: bool,
) -> PilotEvaluation:
    """Apply the frozen rule after explicit integrity and sensitivity review."""

    if not isinstance(manifest, PilotValidationManifest):
        raise TypeError("manifest must be a PilotValidationManifest")
    if not isinstance(mechanical, MechanicalGateEvaluation):
        raise TypeError("mechanical must be a MechanicalGateEvaluation")
    if not isinstance(negative_controls, NegativeControlSummary):
        raise TypeError("negative_controls must be a NegativeControlSummary")
    if not isinstance(source_repeatability, SourceRepeatabilityEvaluation):
        raise TypeError("source_repeatability must be a SourceRepeatabilityEvaluation")
    if not isinstance(film_repeatability, FilmRepeatabilityEvaluation):
        raise TypeError("film_repeatability must be a FilmRepeatabilityEvaluation")
    if not isinstance(sensitivity, SensitivityAssessment):
        raise TypeError("sensitivity must be a SensitivityAssessment")
    _require_bool(material_pipeline_change, "material_pipeline_change")
    _require_bool(
        revision_feasible_without_changing_estimand,
        "revision_feasible_without_changing_estimand",
    )

    _require_gate_roster(
        "mechanical", mechanical.gates, _MECHANICAL_GATE_NAMES
    )
    if negative_controls.gate.name != "negative_controls":
        raise ValueError(
            "negative-control gate differs from the frozen gate roster"
        )
    _require_gate_roster(
        "source hard", source_repeatability.hard_gates, _SOURCE_HARD_GATE_NAMES
    )
    _require_gate_roster(
        "source repeatability",
        source_repeatability.gates,
        _SOURCE_REPEATABILITY_GATE_NAMES,
    )
    _require_gate_roster(
        "film hard", film_repeatability.hard_gates, _FILM_HARD_GATE_NAMES
    )
    _require_gate_roster(
        "film repeatability",
        film_repeatability.repeatability_gates,
        _FILM_REPEATABILITY_GATE_NAMES,
    )

    rebuilt_mechanical = evaluate_mechanical_gates(manifest, mechanical.inputs)
    if rebuilt_mechanical != mechanical:
        raise ValueError(
            "mechanical evaluation is inconsistent with its retained inputs"
        )
    rebuilt_controls = summarize_negative_controls(
        manifest,
        negative_controls.assignments,
        negative_controls.results,
    )
    if rebuilt_controls != negative_controls:
        raise ValueError(
            "negative-control evaluation is inconsistent with its retained inputs"
        )
    rebuilt_source = evaluate_source_repeatability(
        manifest,
        source_repeatability.assigned,
        third_pass_units=source_repeatability.third_pass_units,
    )
    if rebuilt_source != source_repeatability:
        raise ValueError(
            "source-repeatability evaluation is inconsistent with its retained inputs"
        )
    rebuilt_agreement = compare_film_scores(
        film_repeatability.agreement.left_scores,
        film_repeatability.agreement.right_scores,
        manifest=manifest,
    )
    rebuilt_late = compare_late_retribution(
        film_repeatability.late_retribution.left_run,
        film_repeatability.late_retribution.right_run,
        manifest=manifest,
        left_scores=rebuilt_agreement.left_scores,
        right_scores=rebuilt_agreement.right_scores,
    )
    leave_one_out = film_repeatability.leave_one_out
    if (
        leave_one_out.baseline_left_scores != rebuilt_agreement.left_scores
        or leave_one_out.baseline_right_scores != rebuilt_agreement.right_scores
        or leave_one_out.baseline_left_late_retribution != rebuilt_late.left_run
        or leave_one_out.baseline_right_late_retribution != rebuilt_late.right_run
    ):
        raise ValueError(
            "leave-one-out baselines differ from the retained film replicates"
        )
    rebuilt_leave_one_out = compare_leave_one_source_out(
        leave_one_out.runs,
        manifest=manifest,
        baseline_left_scores=leave_one_out.baseline_left_scores,
        baseline_right_scores=leave_one_out.baseline_right_scores,
        baseline_left_late_retribution=leave_one_out.baseline_left_late_retribution,
        baseline_right_late_retribution=leave_one_out.baseline_right_late_retribution,
    )
    rebuilt_film = evaluate_film_repeatability(
        rebuilt_agreement,
        rebuilt_late,
        rebuilt_leave_one_out,
    )
    if rebuilt_film != film_repeatability:
        raise ValueError(
            "film-repeatability evaluation is inconsistent with its component metrics"
        )

    component_digests = {
        mechanical.manifest_digest,
        negative_controls.manifest_digest,
        source_repeatability.manifest_digest,
        film_repeatability.manifest_digest,
        sensitivity.manifest_digest,
    }
    alignment_errors = []
    if component_digests != {manifest.digest}:
        alignment_errors.append("component manifest digests differ")
    if mechanical.source_ids != manifest.eligible_source_ids:
        alignment_errors.append("mechanical source universe differs from manifest")
    if source_repeatability.source_ids != manifest.eligible_source_ids:
        alignment_errors.append("agreement source universe differs from manifest")
    if negative_controls.expected_source_ids != manifest.eligible_source_ids:
        alignment_errors.append("control source universe differs from manifest")
    if mechanical.film_ids != manifest.film_ids:
        alignment_errors.append("mechanical film universe differs from manifest")
    if source_repeatability.film_ids != manifest.film_ids:
        alignment_errors.append("source agreement film universe differs from manifest")
    if film_repeatability.agreement.expected_film_ids != manifest.film_ids:
        alignment_errors.append("film agreement universe differs from manifest")
    if mechanical.expected_periods != FROZEN_PILOT_PERIODS:
        alignment_errors.append("mechanical periods differ from frozen periods")
    if (
        tuple(item.period for item in source_repeatability.periods)
        != FROZEN_PILOT_PERIODS
    ):
        alignment_errors.append("source periods differ from frozen periods")
    positive_source_ids = frozenset(
        item.source_id
        for item in source_repeatability.assigned
        if item.agreement.left_units or item.agreement.right_units
    )
    missing_accepted_sources = (
        positive_source_ids - mechanical.inputs.accepted_record_source_ids
    )
    if missing_accepted_sources:
        alignment_errors.append(
            "accepted-record source universe omits positive replicate sources: "
            + ",".join(sorted(missing_accepted_sources))
        )
    minimum_accepted_records = sum(
        item.agreement.union_positive
        for item in source_repeatability.assigned
    )
    if mechanical.inputs.accepted_records < minimum_accepted_records:
        alignment_errors.append(
            "accepted-record denominator is smaller than the positive replicate-unit minimum"
        )
    derived_left_scores = _derive_film_score_grid(
        manifest,
        source_repeatability.assigned,
        replicate="left",
    )
    derived_right_scores = _derive_film_score_grid(
        manifest,
        source_repeatability.assigned,
        replicate="right",
    )
    if _unique_film_map(derived_left_scores) != _unique_film_map(
        rebuilt_agreement.left_scores
    ):
        alignment_errors.append(
            "left film scores do not derive from the retained left source votes"
        )
    if _unique_film_map(derived_right_scores) != _unique_film_map(
        rebuilt_agreement.right_scores
    ):
        alignment_errors.append(
            "right film scores do not derive from the retained right source votes"
        )
    for run in leave_one_out.runs:
        expected_left_omission = _derive_film_score_grid(
            manifest,
            source_repeatability.assigned,
            replicate="left",
            omitted_source_id=run.omitted_source_id,
        )
        expected_right_omission = _derive_film_score_grid(
            manifest,
            source_repeatability.assigned,
            replicate="right",
            omitted_source_id=run.omitted_source_id,
        )
        if _unique_film_map(expected_left_omission) != _unique_film_map(
            run.left_scores
        ):
            alignment_errors.append(
                f"left omission scores do not omit source:{run.omitted_source_id}"
            )
        if _unique_film_map(expected_right_omission) != _unique_film_map(
            run.right_scores
        ):
            alignment_errors.append(
                f"right omission scores do not omit source:{run.omitted_source_id}"
            )
    flagged_union = film_repeatability.late_retribution.flagged_union_cells
    if mechanical.inputs.late_retribution_results != flagged_union:
        alignment_errors.append(
            "ending-integrity result count differs from the flagged film/theme union"
        )
    if (
        mechanical.inputs.late_retribution_results_with_separate_evidence
        != flagged_union
    ):
        alignment_errors.append(
            "separate-evidence count differs from the flagged film/theme union"
        )
    alignment = GateResult(
        name="evaluation_manifest_alignment",
        status=GateStatus.FAIL if alignment_errors else GateStatus.PASS,
        observed=len(alignment_errors),
        criterion="every component uses the exact frozen film/source/period manifest",
        details=tuple(alignment_errors),
    )

    missing_sections = frozenset(SensitivitySection) - sensitivity.completed_sections
    if not sensitivity.review_completed or missing_sections:
        sensitivity_status = GateStatus.NOT_EVALUABLE
    elif (
        sensitivity.systematic_period_failure
        or sensitivity.pervasive_one_source_dependence
        or sensitivity.model_source_interaction_failure
    ):
        sensitivity_status = GateStatus.FAIL
    else:
        sensitivity_status = GateStatus.PASS
    sensitivity_details = tuple(
        [
            *(
                f"missing_section:{value.value}"
                for value in sorted(missing_sections, key=lambda item: item.value)
            ),
            *(("review_not_completed",) if not sensitivity.review_completed else ()),
            *(
                ("systematic_period_failure",)
                if sensitivity.systematic_period_failure
                else ()
            ),
            *(
                ("pervasive_one_source_dependence",)
                if sensitivity.pervasive_one_source_dependence
                else ()
            ),
            *(
                ("model_source_interaction_failure",)
                if sensitivity.model_source_interaction_failure
                else ()
            ),
        ]
    )
    sensitivity_gate = GateResult(
        name="sensitivity_review",
        status=sensitivity_status,
        observed=len(sensitivity.completed_sections),
        criterion="all required sensitivity sections reviewed with no systematic failure",
        details=sensitivity_details,
    )
    pipeline_stability = GateResult(
        name="pipeline_stability",
        status=GateStatus.FAIL if material_pipeline_change else GateStatus.PASS,
        observed=int(material_pipeline_change),
        criterion="no material pipeline change after validation began",
    )

    hard_gates = (
        *mechanical.gates,
        negative_controls.gate,
        *source_repeatability.hard_gates,
        *film_repeatability.hard_gates,
        alignment,
        sensitivity_gate,
        pipeline_stability,
    )
    repeatability_gates = (
        *source_repeatability.gates,
        *film_repeatability.repeatability_gates,
    )
    gate_names = [gate.name for gate in (*hard_gates, *repeatability_gates)]
    if len(set(gate_names)) != len(gate_names):
        raise ValueError("Pilot gate names must be unique")
    failed = tuple(
        gate.name
        for gate in (*hard_gates, *repeatability_gates)
        if gate.status is GateStatus.FAIL
    )
    not_evaluable = tuple(
        gate.name
        for gate in (*hard_gates, *repeatability_gates)
        if gate.status is GateStatus.NOT_EVALUABLE
    )
    reasons = [
        *(f"failed:{name}" for name in failed),
        *(f"not_evaluable:{name}" for name in not_evaluable),
    ]
    if not reasons:
        decision = PilotDecision.PROCEED
    elif revision_feasible_without_changing_estimand:
        decision = PilotDecision.REVISE_AND_REVALIDATE
    else:
        decision = PilotDecision.STOP_OR_NARROW
    return PilotEvaluation(
        decision=decision,
        hard_gates=hard_gates,
        repeatability_gates=repeatability_gates,
        failed_gates=failed,
        not_evaluable_gates=not_evaluable,
        decision_reasons=tuple(reasons),
    )
