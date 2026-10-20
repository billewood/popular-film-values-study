from __future__ import annotations

import unittest

from film_values import (
    ClaimDependence,
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
    evidence_record_spans_match,
    evidence_span_matches,
    glamorize_then_punish,
    not_evidenced_score,
    validate_claim_attribution_sources,
)


def record(
    source_id: str,
    *,
    lineage_id: str | None = None,
    segment: NarrativeSegment = NarrativeSegment.MAIN_BODY,
    salience: SourceSalience = SourceSalience.IMPORTANT,
    stance: SourceStance = SourceStance.AFFIRMATIVE,
    claim_type: ClaimType = ClaimType.FILM_STANCE_ATTRIBUTION,
    claim_target: ClaimTarget = ClaimTarget.FILM,
    source_type: SourceType = SourceType.CONTEMPORARY_REVIEW,
    ending_response: EndingResponse | None = None,
    exact_evidence_span: str = "The film makes excess seductive.",
    claim_dependence: ClaimDependence = ClaimDependence.INDEPENDENT_INTERPRETATION,
    attributed_source_ids: tuple[str, ...] = (),
    attribution_span: str | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        film_id="film-1",
        source_id=source_id,
        lineage_id=lineage_id or source_id,
        source_type=source_type,
        exact_evidence_span=exact_evidence_span,
        locator="paragraph 4",
        claim_target=claim_target,
        claim_type=claim_type,
        theme=Theme.CONSUMERISM_MATERIALISM,
        narrative_segment=segment,
        source_salience=salience,
        source_stance=stance,
        ending_response=ending_response,
        claim_dependence=claim_dependence,
        attributed_source_ids=attributed_source_ids,
        attribution_span=attribution_span,
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

    def test_compatibility_characters_are_not_silently_rewritten(self) -> None:
        self.assertFalse(evidence_span_matches("Choice ① remains.", "Choice 1 remains."))
        self.assertFalse(evidence_span_matches("The value is x².", "The value is x2."))

    def test_derivative_record_checks_exact_attribution_span(self) -> None:
        derivative = record(
            "later",
            exact_evidence_span="As the earlier review put it, excess is seductive.",
            claim_dependence=ClaimDependence.ATTRIBUTED_DERIVATIVE,
            attributed_source_ids=("earlier",),
            attribution_span="As the earlier review put it",
        )
        self.assertTrue(
            evidence_record_spans_match(
                "As the earlier review put it, excess is seductive.",
                derivative,
            )
        )
        self.assertFalse(
            evidence_record_spans_match(
                "A different critic said excess is seductive.",
                derivative,
            )
        )

    def test_attributed_sources_must_be_selected_for_the_same_film(self) -> None:
        derivative = record(
            "later",
            exact_evidence_span="As the earlier review put it, excess is seductive.",
            claim_dependence=ClaimDependence.ATTRIBUTED_DERIVATIVE,
            attributed_source_ids=("earlier",),
            attribution_span="As the earlier review put it",
        )
        validate_claim_attribution_sources(
            [derivative],
            {"film-1": {"later", "earlier"}},
        )

        with self.assertRaisesRegex(ValueError, "not selected for film 'film-1'"):
            validate_claim_attribution_sources(
                [derivative],
                {
                    "film-1": {"later"},
                    "film-2": {"earlier"},
                },
            )

    def test_attributed_source_validation_fails_without_film_universe(self) -> None:
        derivative = record(
            "later",
            exact_evidence_span="As the earlier review put it, excess is seductive.",
            claim_dependence=ClaimDependence.ATTRIBUTED_DERIVATIVE,
            attributed_source_ids=("earlier",),
            attribution_span="As the earlier review put it",
        )
        with self.assertRaisesRegex(ValueError, "No frozen selected-source universe"):
            validate_claim_attribution_sources([derivative], {})


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
        self.assertEqual(votes, [])

    def test_critic_and_reception_claims_do_not_raise_centrality(self) -> None:
        votes = collapse_source_records(
            [
                record(
                    "s1",
                    salience=SourceSalience.CENTRAL,
                    claim_type=ClaimType.CRITIC_PREFERENCE,
                ),
                record(
                    "s2",
                    salience=SourceSalience.CENTRAL,
                    claim_type=ClaimType.RECEPTION_CLAIM,
                ),
            ]
        )
        self.assertEqual(votes, [])

    def test_nonfilm_attribution_does_not_raise_centrality(self) -> None:
        votes = collapse_source_records(
            [
                record(
                    "s1",
                    claim_type=ClaimType.FILM_THEME_ATTRIBUTION,
                    claim_target=ClaimTarget.CRITIC,
                )
            ]
        )
        self.assertEqual(votes, [])

    def test_critic_preference_cannot_inflate_valid_theme_salience(self) -> None:
        votes = collapse_source_records(
            [
                record(
                    "s1",
                    salience=SourceSalience.PRESENT_INCIDENTAL,
                    claim_type=ClaimType.FILM_THEME_ATTRIBUTION,
                ),
                record(
                    "s1",
                    salience=SourceSalience.CENTRAL,
                    claim_type=ClaimType.CRITIC_PREFERENCE,
                ),
            ]
        )
        self.assertEqual(votes[0].salience, SourceSalience.PRESENT_INCIDENTAL)

    def test_synopsis_contributes_presence_but_not_stance(self) -> None:
        votes = collapse_source_records(
            [
                record(
                    "synopsis",
                    source_type=SourceType.REFERENCE_SYNOPSIS,
                    claim_type=ClaimType.PLOT_CONSEQUENCE,
                    claim_target=ClaimTarget.CHARACTER,
                    salience=SourceSalience.CENTRAL,
                    stance=SourceStance.AFFIRMATIVE,
                )
            ]
        )
        self.assertEqual(votes[0].salience, SourceSalience.CENTRAL)
        self.assertIs(votes[0].stance, SourceStance.UNSTATED)

    def test_attributed_derivative_is_archived_but_does_not_vote(self) -> None:
        derivative = record(
            "later",
            exact_evidence_span="Quoting the release review, the film makes excess seductive.",
            claim_dependence=ClaimDependence.ATTRIBUTED_DERIVATIVE,
            attributed_source_ids=("release-review",),
            attribution_span="Quoting the release review",
            salience=SourceSalience.CENTRAL,
        )
        self.assertEqual(
            collapse_source_records(
                [derivative],
                selected_source_ids_by_film={"film-1": {"later", "release-review"}},
            ),
            [],
        )

    def test_derivative_collapse_fails_closed_without_frozen_source_universe(self) -> None:
        derivative = record(
            "later",
            exact_evidence_span="Quoting the release review, excess is seductive.",
            claim_dependence=ClaimDependence.ATTRIBUTED_DERIVATIVE,
            attributed_source_ids=("release-review",),
            attribution_span="Quoting the release review",
        )
        with self.assertRaisesRegex(ValueError, "requires the frozen selected-source"):
            collapse_source_records([derivative])


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

    def test_derivative_source_cannot_supply_independent_corroboration(self) -> None:
        original = record("release-review", salience=SourceSalience.CENTRAL)
        derivative = record(
            "later-scholarship",
            exact_evidence_span="The release review says the film makes excess seductive.",
            claim_dependence=ClaimDependence.ATTRIBUTED_DERIVATIVE,
            attributed_source_ids=("release-review",),
            attribution_span="The release review says",
            salience=SourceSalience.CENTRAL,
        )
        votes = collapse_source_records(
            [original, derivative],
            selected_source_ids_by_film={
                "film-1": {"release-review", "later-scholarship"}
            },
        )
        self.assertEqual([vote.source_id for vote in votes], ["release-review"])
        score = aggregate_film_theme(votes)
        self.assertEqual(score.supporting_lineages, 1)
        self.assertEqual(score.centrality, 2)
        self.assertIs(score.stance, FilmStance.UNRESOLVED)

    def test_derivative_record_cannot_inflate_an_independent_source_vote(self) -> None:
        independent = record(
            "later-scholarship",
            salience=SourceSalience.PRESENT_INCIDENTAL,
            stance=SourceStance.UNSTATED,
            claim_type=ClaimType.FILM_THEME_ATTRIBUTION,
        )
        derivative = record(
            "later-scholarship",
            exact_evidence_span="The release review says the film makes excess seductive.",
            claim_dependence=ClaimDependence.ATTRIBUTED_DERIVATIVE,
            attributed_source_ids=("release-review",),
            attribution_span="The release review says",
            salience=SourceSalience.CENTRAL,
            stance=SourceStance.AFFIRMATIVE,
        )
        vote = collapse_source_records(
            [independent, derivative],
            selected_source_ids_by_film={
                "film-1": {"later-scholarship", "release-review"}
            },
        )[0]
        self.assertIs(vote.salience, SourceSalience.PRESENT_INCIDENTAL)
        self.assertIs(vote.stance, SourceStance.UNSTATED)
        self.assertEqual(vote.evidence_count, 1)

    def test_two_concordant_directional_sources_set_stance(self) -> None:
        score = self.score(record("s1"), record("s2"))
        self.assertIs(score.stance, FilmStance.AFFIRMATIVE)

    def test_synopsis_cannot_supply_second_directional_vote(self) -> None:
        score = self.score(
            record("review"),
            record(
                "synopsis",
                source_type=SourceType.REFERENCE_SYNOPSIS,
                claim_type=ClaimType.PLOT_CONSEQUENCE,
                claim_target=ClaimTarget.CHARACTER,
            ),
        )
        self.assertIs(score.stance, FilmStance.UNRESOLVED)

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
