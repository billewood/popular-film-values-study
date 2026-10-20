"""Deterministic source- and film-level aggregation rules."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

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


_CENTRALITY_ELIGIBLE_CLAIMS = {
    ClaimType.PLOT_FACT,
    ClaimType.FILM_THEME_ATTRIBUTION,
    ClaimType.FILM_STANCE_ATTRIBUTION,
    ClaimType.PLOT_CONSEQUENCE,
}

_CONSEQUENTIAL_ENDINGS = {
    EndingResponse.EXTERNAL_PUNISHMENT_ONLY,
    EndingResponse.REMORSE_VERBAL_RECOGNITION,
    EndingResponse.CHANGED_BEHAVIOR,
    EndingResponse.COSTLY_REPAIR_SACRIFICE,
}


@dataclass(frozen=True, slots=True)
class SourceVote:
    film_id: str
    source_id: str
    lineage_id: str
    source_type: SourceType
    theme: Theme
    narrative_segment: NarrativeSegment
    salience: SourceSalience
    stance: SourceStance
    ending_responses: frozenset[EndingResponse]
    evidence_count: int


@dataclass(frozen=True, slots=True)
class FilmThemeScore:
    film_id: str
    theme: Theme
    narrative_segment: NarrativeSegment
    centrality: int
    stance: FilmStance
    supporting_lineages: int
    affirmative_votes: int
    critical_votes: int
    mixed_votes: int
    unstated_votes: int
    ending_responses: frozenset[EndingResponse]


def not_evidenced_score(
    film_id: str,
    theme: Theme,
    narrative_segment: NarrativeSegment,
) -> FilmThemeScore:
    """Represent a prespecified film/theme/segment with no accepted evidence."""

    if not film_id.strip():
        raise ValueError("film_id may not be empty")
    return FilmThemeScore(
        film_id=film_id,
        theme=theme,
        narrative_segment=narrative_segment,
        centrality=0,
        stance=FilmStance.NOT_EVIDENCED,
        supporting_lineages=0,
        affirmative_votes=0,
        critical_votes=0,
        mixed_votes=0,
        unstated_votes=0,
        ending_responses=frozenset(),
    )


def _combine_stances(stances: Iterable[SourceStance]) -> SourceStance:
    observed = set(stances)
    observed.discard(SourceStance.UNSTATED)
    if not observed:
        return SourceStance.UNSTATED
    if SourceStance.MIXED in observed or len(observed) > 1:
        return SourceStance.MIXED
    return next(iter(observed))


def _contributes_to_film_theme(record: EvidenceRecord) -> bool:
    """Return whether a claim is evidence about the sampled film's thematic content."""

    if record.claim_type not in _CENTRALITY_ELIGIBLE_CLAIMS:
        return False
    if record.claim_type in {
        ClaimType.FILM_THEME_ATTRIBUTION,
        ClaimType.FILM_STANCE_ATTRIBUTION,
    }:
        return record.claim_target is ClaimTarget.FILM
    return record.claim_target in {ClaimTarget.FILM, ClaimTarget.CHARACTER}


def _contributes_to_film_stance(record: EvidenceRecord) -> bool:
    """Apply the film-attribution rule and bar synopsis-slot stance votes."""

    if record.source_type is SourceType.REFERENCE_SYNOPSIS:
        return False
    if record.claim_type is ClaimType.FILM_STANCE_ATTRIBUTION:
        return record.claim_target is ClaimTarget.FILM
    if record.claim_type is ClaimType.PLOT_CONSEQUENCE:
        return record.claim_target in {ClaimTarget.FILM, ClaimTarget.CHARACTER}
    return False


def collapse_source_records(records: Iterable[EvidenceRecord]) -> list[SourceVote]:
    """Collapse passages to one vote per source, theme, and segment."""

    groups: dict[tuple[str, str, Theme, NarrativeSegment], list[EvidenceRecord]] = defaultdict(list)
    for record in records:
        key = (
            record.film_id,
            record.source_id,
            record.theme,
            record.narrative_segment,
        )
        groups[key].append(record)

    votes: list[SourceVote] = []
    for group in groups.values():
        first = group[0]
        if any(record.lineage_id != first.lineage_id for record in group):
            raise ValueError("One source_id may not refer to multiple evidence lineages")
        if any(record.source_type is not first.source_type for record in group):
            raise ValueError("One source_id may not refer to multiple source types")

        scoreable = [record for record in group if _contributes_to_film_theme(record)]
        if not scoreable:
            # Critic preference and reception claims are retained as evidence
            # records for audit, but they are outside the film-theme estimand.
            continue

        eligible_stances = (
            record.source_stance
            for record in scoreable
            if _contributes_to_film_stance(record)
        )
        votes.append(
            SourceVote(
                film_id=first.film_id,
                source_id=first.source_id,
                lineage_id=first.lineage_id,
                source_type=first.source_type,
                theme=first.theme,
                narrative_segment=first.narrative_segment,
                salience=max(record.source_salience for record in scoreable),
                stance=_combine_stances(eligible_stances),
                ending_responses=frozenset(
                    record.ending_response
                    for record in scoreable
                    if record.ending_response is not None
                ),
                evidence_count=len(scoreable),
            )
        )
    return votes


def _collapse_lineage_votes(votes: Iterable[SourceVote]) -> list[SourceVote]:
    """Prevent syndicated or otherwise dependent sources from multiplying votes."""

    groups: dict[str, list[SourceVote]] = defaultdict(list)
    for vote in votes:
        groups[vote.lineage_id].append(vote)

    collapsed: list[SourceVote] = []
    for group in groups.values():
        first = group[0]
        fields = ("film_id", "theme", "narrative_segment")
        for field in fields:
            if any(getattr(vote, field) != getattr(first, field) for vote in group):
                raise ValueError(f"A lineage may not mix {field} values within one aggregation")
        collapsed.append(
            SourceVote(
                film_id=first.film_id,
                source_id=first.source_id,
                lineage_id=first.lineage_id,
                source_type=first.source_type,
                theme=first.theme,
                narrative_segment=first.narrative_segment,
                salience=max(vote.salience for vote in group),
                stance=_combine_stances(vote.stance for vote in group),
                ending_responses=frozenset().union(
                    *(vote.ending_responses for vote in group)
                ),
                evidence_count=sum(vote.evidence_count for vote in group),
            )
        )
    return collapsed


def aggregate_film_theme(votes: Iterable[SourceVote]) -> FilmThemeScore:
    """Apply the preregistered centrality and stance rules to one film/theme/segment."""

    vote_list = list(votes)
    if not vote_list:
        raise ValueError("aggregate_film_theme requires at least one SourceVote")

    first = vote_list[0]
    for field in ("film_id", "theme", "narrative_segment"):
        if any(getattr(vote, field) != getattr(first, field) for vote in vote_list):
            raise ValueError(f"Votes must share one {field}")

    independent = _collapse_lineage_votes(vote_list)
    central_count = sum(vote.salience is SourceSalience.CENTRAL for vote in independent)
    important_count = sum(vote.salience is SourceSalience.IMPORTANT for vote in independent)

    if central_count >= 2:
        centrality = 3
    elif central_count >= 1 or important_count >= 2:
        centrality = 2
    else:
        centrality = 1

    positive = sum(vote.stance is SourceStance.AFFIRMATIVE for vote in independent)
    negative = sum(vote.stance is SourceStance.CRITICAL for vote in independent)
    mixed = sum(vote.stance is SourceStance.MIXED for vote in independent)
    unstated = sum(vote.stance is SourceStance.UNSTATED for vote in independent)
    directional = positive + negative

    if directional >= 2 and positive / directional >= 2 / 3:
        film_stance = FilmStance.AFFIRMATIVE
    elif directional >= 2 and negative / directional >= 2 / 3:
        film_stance = FilmStance.CRITICAL
    elif mixed > 0 or (positive > 0 and negative > 0):
        film_stance = FilmStance.MIXED_CONTESTED
    else:
        film_stance = FilmStance.UNRESOLVED

    return FilmThemeScore(
        film_id=first.film_id,
        theme=first.theme,
        narrative_segment=first.narrative_segment,
        centrality=centrality,
        stance=film_stance,
        supporting_lineages=len(independent),
        affirmative_votes=positive,
        critical_votes=negative,
        mixed_votes=mixed,
        unstated_votes=unstated,
        ending_responses=frozenset().union(
            *(vote.ending_responses for vote in independent)
        ),
    )


def glamorize_then_punish(
    main_body: FilmThemeScore,
    ending: FilmThemeScore,
) -> bool:
    """Return the frozen late-retribution indicator for one film and theme."""

    if main_body.film_id != ending.film_id or main_body.theme is not ending.theme:
        raise ValueError("Scores must refer to the same film and theme")
    if main_body.narrative_segment is not NarrativeSegment.MAIN_BODY:
        raise ValueError("main_body score must use the main_body segment")
    if ending.narrative_segment is not NarrativeSegment.ENDING:
        raise ValueError("ending score must use the ending segment")

    return (
        main_body.centrality >= 2
        and main_body.stance is FilmStance.AFFIRMATIVE
        and ending.stance is FilmStance.CRITICAL
        and bool(ending.ending_responses & _CONSEQUENTIAL_ENDINGS)
    )
