from __future__ import annotations

import unittest

from film_values import (
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
    aggregate_film_theme,
    collapse_source_records,
    evidence_span_matches,
    glamorize_then_punish,
    not_evidenced_score,
)


def record(
    source_id: str,
    *,
    lineage_id: str | None = None,
    segment: NarrativeSegment = NarrativeSegment.MAIN_BODY,
    salience: SourceSalience = SourceSalience.IMPORTANT,
    stance: SourceStance = SourceStance.AFFIRMATIVE,
    claim_type: ClaimType = ClaimType.FILM_STANCE_ATTRIBUTION,
    ending_response: EndingResponse | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        film_id="film-1",
        source_id=source_id,
        lineage_id=lineage_id or source_id,
        source_type=SourceType.CONTEMPORARY_REVIEW,
        exact_evidence_span="The film makes excess seductive.",
        locator="paragraph 4",
        claim_target=ClaimTarget.FILM,
        claim_type=claim_type,
        theme=Theme.CONSUMERISM_MATERIALISM,
        narrative_segment=segment,
        source_salience=salience,
        source_stance=stance,
        ending_response=ending_response,
    )


class EvidenceTests(unittest.TestCase):
    def test_typographic_punctuation_and_whitespace_are_normalized(self) -> None:
        source = "The film makes “excess” seductive — for a while."
        span = 'The film makes "excess" seductive - for a while.'
        self.assertTrue(evidence_span_matches(source, span))

    def test_invented_quote_is_rejected(self) -> None:
        self.assertFalse(
            evidence_span_matches("The film portrays wealth.", "The film celebrates wealth.")
        )


class SourceCollapseTests(unittest.TestCase):
    def test_conflicting_stance_within_source_becomes_mixed(self) -> None:
        votes = collapse_source_records(
            [
                record("s1", stance=SourceStance.AFFIRMATIVE),
                record("s1", stance=SourceStance.CRITICAL),
            ]
        )
        self.assertEqual(len(votes), 1)
        self.assertIs(votes[0].stance, SourceStance.MIXED)

    def test_critic_preference_does_not_vote_on_film_stance(self) -> None:
        votes = collapse_source_records(
            [record("s1", claim_type=ClaimType.CRITIC_PREFERENCE)]
        )
        self.assertIs(votes[0].stance, SourceStance.UNSTATED)


class FilmAggregationTests(unittest.TestCase):
    def score(self, *records: EvidenceRecord):
        return aggregate_film_theme(collapse_source_records(records))

    def test_two_independent_central_sources_produce_centrality_three(self) -> None:
        score = self.score(
            record("s1", salience=SourceSalience.CENTRAL),
            record("s2", salience=SourceSalience.CENTRAL),
        )
        self.assertEqual(score.centrality, 3)

    def test_one_central_source_produces_centrality_two(self) -> None:
        score = self.score(record("s1", salience=SourceSalience.CENTRAL))
        self.assertEqual(score.centrality, 2)

    def test_dependent_sources_count_as_one_lineage(self) -> None:
        score = self.score(
            record("s1", lineage_id="wire-1", salience=SourceSalience.CENTRAL),
            record("s2", lineage_id="wire-1", salience=SourceSalience.CENTRAL),
        )
        self.assertEqual(score.supporting_lineages, 1)
        self.assertEqual(score.centrality, 2)
        self.assertIs(score.stance, FilmStance.UNRESOLVED)

    def test_two_concordant_directional_sources_set_stance(self) -> None:
        score = self.score(record("s1"), record("s2"))
        self.assertIs(score.stance, FilmStance.AFFIRMATIVE)

    def test_one_directional_source_is_unresolved(self) -> None:
        score = self.score(record("s1"))
        self.assertIs(score.stance, FilmStance.UNRESOLVED)

    def test_source_silence_is_not_evidenced_not_absent(self) -> None:
        score = not_evidenced_score(
            "film-1",
            Theme.CONSUMERISM_MATERIALISM,
            NarrativeSegment.MAIN_BODY,
        )
        self.assertEqual(score.centrality, 0)
        self.assertIs(score.stance, FilmStance.NOT_EVIDENCED)

    def test_explicit_mixed_source_is_preserved(self) -> None:
        score = self.score(record("s1", stance=SourceStance.MIXED))
        self.assertIs(score.stance, FilmStance.MIXED_CONTESTED)

    def test_glamorize_then_punish_requires_consequential_ending(self) -> None:
        main = self.score(
            record("s1", salience=SourceSalience.CENTRAL),
            record("s2", salience=SourceSalience.CENTRAL),
        )
        ending = self.score(
            record(
                "s3",
                segment=NarrativeSegment.ENDING,
                stance=SourceStance.CRITICAL,
                ending_response=EndingResponse.EXTERNAL_PUNISHMENT_ONLY,
            ),
            record(
                "s4",
                segment=NarrativeSegment.ENDING,
                stance=SourceStance.CRITICAL,
                ending_response=EndingResponse.EXTERNAL_PUNISHMENT_ONLY,
            ),
        )
        self.assertTrue(glamorize_then_punish(main, ending))

        no_consequence = self.score(
            record(
                "s5",
                segment=NarrativeSegment.ENDING,
                stance=SourceStance.CRITICAL,
            ),
            record(
                "s6",
                segment=NarrativeSegment.ENDING,
                stance=SourceStance.CRITICAL,
            ),
        )
        self.assertFalse(glamorize_then_punish(main, no_consequence))


if __name__ == "__main__":
    unittest.main()
