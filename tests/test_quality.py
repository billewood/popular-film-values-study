from __future__ import annotations

import unittest
from dataclasses import replace

from film_values import (
    FilmStance,
    NarrativeSegment,
    SourceSalience,
    SourceStance,
    SourceType,
    Theme,
)
from film_values.aggregate import FilmThemeScore, SourceVote
from film_values.quality import (
    compare_film_scores,
    compare_source_votes,
    summarize_source_agreements,
)


def vote(
    theme: Theme,
    *,
    salience: SourceSalience = SourceSalience.IMPORTANT,
    stance: SourceStance = SourceStance.UNSTATED,
) -> SourceVote:
    return SourceVote(
        film_id="film-1",
        source_id="source-1",
        lineage_id="lineage-1",
        source_type=SourceType.CONTEMPORARY_REVIEW,
        theme=theme,
        narrative_segment=NarrativeSegment.MAIN_BODY,
        salience=salience,
        stance=stance,
        ending_responses=frozenset(),
        evidence_count=1,
    )


def score(
    theme: Theme,
    *,
    centrality: int = 2,
    stance: FilmStance = FilmStance.UNRESOLVED,
) -> FilmThemeScore:
    return FilmThemeScore(
        film_id="film-1",
        theme=theme,
        narrative_segment=NarrativeSegment.MAIN_BODY,
        centrality=centrality,
        stance=stance,
        supporting_lineages=1,
        affirmative_votes=0,
        critical_votes=0,
        mixed_votes=0,
        unstated_votes=1,
        ending_responses=frozenset(),
    )


class SourceAgreementTests(unittest.TestCase):
    def test_both_empty_does_not_create_perfect_agreement(self) -> None:
        agreement = compare_source_votes([], [])
        self.assertIsNone(agreement.positive_jaccard)
        summary = summarize_source_agreements([agreement])
        self.assertEqual(summary.both_empty_sources, 1)
        self.assertIsNone(summary.median_positive_jaccard)

    def test_jaccard_uses_positive_units(self) -> None:
        left = [vote(Theme.SELFISHNESS), vote(Theme.REVENGE)]
        right = [vote(Theme.SELFISHNESS), vote(Theme.FREEDOM_AUTONOMY)]
        agreement = compare_source_votes(left, right)
        self.assertAlmostEqual(agreement.positive_jaccard or 0, 1 / 3)
        self.assertEqual(agreement.joint_positive, 1)

    def test_direct_polarity_flip_is_counted(self) -> None:
        left = [vote(Theme.SELFISHNESS, stance=SourceStance.AFFIRMATIVE)]
        right = [vote(Theme.SELFISHNESS, stance=SourceStance.CRITICAL)]
        agreement = compare_source_votes(left, right)
        self.assertEqual(agreement.direct_polarity_flips, 1)
        self.assertEqual(agreement.stance_exact, 0)

    def test_duplicate_units_fail(self) -> None:
        item = vote(Theme.SELFISHNESS)
        with self.assertRaisesRegex(ValueError, "Duplicate comparison unit"):
            compare_source_votes([item, item], [])


class FilmAgreementTests(unittest.TestCase):
    def test_shared_zeros_are_excluded(self) -> None:
        empty = score(
            Theme.SELFISHNESS,
            centrality=0,
            stance=FilmStance.NOT_EVIDENCED,
        )
        agreement = compare_film_scores([empty], [empty])
        self.assertEqual(agreement.evidenced_cells, 0)
        self.assertIsNone(agreement.centrality_exact_rate)

    def test_missing_positive_counts_as_disagreement(self) -> None:
        positive = score(Theme.SELFISHNESS)
        agreement = compare_film_scores([positive], [])
        self.assertEqual(agreement.evidenced_cells, 1)
        self.assertEqual(agreement.centrality_exact_rate, 0)

    def test_film_polarity_flip_is_counted(self) -> None:
        positive = score(Theme.SELFISHNESS, stance=FilmStance.AFFIRMATIVE)
        negative = replace(positive, stance=FilmStance.CRITICAL)
        agreement = compare_film_scores([positive], [negative])
        self.assertEqual(agreement.direct_polarity_flips, 1)


if __name__ == "__main__":
    unittest.main()
