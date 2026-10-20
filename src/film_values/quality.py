"""Agreement summaries for independent machine-coding replicates."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Iterable, Sequence

from .aggregate import FilmThemeScore, SourceVote
from .models import FilmStance, SourceStance


@dataclass(frozen=True, slots=True)
class SourceAgreement:
    positive_jaccard: float | None
    left_positive: int
    right_positive: int
    joint_positive: int
    salience_exact: int
    stance_exact: int
    direct_polarity_flips: int


@dataclass(frozen=True, slots=True)
class SourceAgreementSummary:
    comparable_sources: int
    both_empty_sources: int
    median_positive_jaccard: float | None
    proportion_at_least_two_thirds: float | None
    salience_exact_rate: float | None
    stance_exact_rate: float | None
    direct_polarity_flips: int


@dataclass(frozen=True, slots=True)
class FilmAgreement:
    evidenced_cells: int
    centrality_exact_rate: float | None
    stance_exact_rate: float | None
    direct_polarity_flips: int


def _ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _source_key(vote: SourceVote) -> tuple[object, ...]:
    return (vote.source_id, vote.theme, vote.narrative_segment)


def _film_key(score: FilmThemeScore) -> tuple[object, ...]:
    return (score.film_id, score.theme, score.narrative_segment)


def _unique_map(items: Iterable[object], key_function) -> dict[tuple[object, ...], object]:
    mapped: dict[tuple[object, ...], object] = {}
    for item in items:
        key = key_function(item)
        if key in mapped:
            raise ValueError(f"Duplicate comparison unit: {key}")
        mapped[key] = item
    return mapped


def compare_source_votes(
    left: Iterable[SourceVote], right: Iterable[SourceVote]
) -> SourceAgreement:
    """Compare two replicates after evidence has been collapsed to source votes."""

    left_map = _unique_map(left, _source_key)
    right_map = _unique_map(right, _source_key)
    left_keys = set(left_map)
    right_keys = set(right_map)
    union = left_keys | right_keys
    joint = left_keys & right_keys
    jaccard = len(joint) / len(union) if union else None
    salience_exact = 0
    stance_exact = 0
    flips = 0
    for key in joint:
        left_vote = left_map[key]
        right_vote = right_map[key]
        assert isinstance(left_vote, SourceVote)
        assert isinstance(right_vote, SourceVote)
        salience_exact += left_vote.salience is right_vote.salience
        stance_exact += left_vote.stance is right_vote.stance
        flips += {
            left_vote.stance,
            right_vote.stance,
        } == {SourceStance.AFFIRMATIVE, SourceStance.CRITICAL}
    return SourceAgreement(
        positive_jaccard=jaccard,
        left_positive=len(left_keys),
        right_positive=len(right_keys),
        joint_positive=len(joint),
        salience_exact=salience_exact,
        stance_exact=stance_exact,
        direct_polarity_flips=flips,
    )


def summarize_source_agreements(
    agreements: Sequence[SourceAgreement],
) -> SourceAgreementSummary:
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
            sum(value >= 2 / 3 for value in jaccards), len(jaccards)
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


def compare_film_scores(
    left: Iterable[FilmThemeScore], right: Iterable[FilmThemeScore]
) -> FilmAgreement:
    """Compare replicate film scores without letting shared zero cells inflate agreement."""

    left_map = _unique_map(left, _film_key)
    right_map = _unique_map(right, _film_key)
    keys = set(left_map) | set(right_map)
    evidenced = [
        key
        for key in keys
        if (
            (key in left_map and left_map[key].centrality > 0)
            or (key in right_map and right_map[key].centrality > 0)
        )
    ]
    centrality_exact = 0
    stance_exact = 0
    flips = 0
    for key in evidenced:
        left_score = left_map.get(key)
        right_score = right_map.get(key)
        if left_score is None or right_score is None:
            continue
        assert isinstance(left_score, FilmThemeScore)
        assert isinstance(right_score, FilmThemeScore)
        centrality_exact += left_score.centrality == right_score.centrality
        stance_exact += left_score.stance is right_score.stance
        flips += {left_score.stance, right_score.stance} == {
            FilmStance.AFFIRMATIVE,
            FilmStance.CRITICAL,
        }
    denominator = len(evidenced)
    return FilmAgreement(
        evidenced_cells=denominator,
        centrality_exact_rate=_ratio(centrality_exact, denominator),
        stance_exact_rate=_ratio(stance_exact, denominator),
        direct_polarity_flips=flips,
    )
