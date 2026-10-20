from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from film_values.rankings import (
    RankingRow,
    audit_frames,
    order_cross_table_tie,
    resolve_pilot_titles,
    write_resolved_titles_csv,
)
from film_values.sampling import PilotSlot


def row(rank: int, *, eligibility: str = "eligible") -> RankingRow:
    eligible_rank = None
    exclusion_reason = "not_narrative_feature" if eligibility != "eligible" else ""
    return RankingRow(
        cohort_year=1982,
        title=f"Film {rank}",
        stable_title_id=f"film-{rank}",
        first_domestic_release_date="1982-01-01",
        release_date_precision="day",
        release_date_source="https://example.test/release",
        source_regime="bom_total_gross",
        primary_source_citation="Box Office Mojo, 1982 release-year chart",
        primary_source_url=(
            "https://www.boxofficemojo.com/year/1982/?grossesOption=totalGrosses"
        ),
        source_table_year=1982,
        source_amount_type="release_run_total",
        metric="domestic_gross",
        territory_definition="Domestic",
        amount=Decimal(1000000 - rank),
        amount_estimated=False,
        source_row_order=rank,
        cohort_rank=rank,
        eligible_rank=eligible_rank,
        reissue_flag=False,
        eligibility=eligibility,
        exclusion_reason=exclusion_reason,
        tie_flag=False,
        near_tie_flag=False,
        secondary_source_citation="",
        secondary_source_url="",
        secondary_rank=None,
        secondary_amount=None,
        conflict_code="",
        adjudication_note="",
        retrieved_at_utc="2026-10-19T20:00:00Z",
        artifact_path="",
        artifact_sha256="",
    )


class RankingAuditTests(unittest.TestCase):
    def test_complete_frame_requires_contiguous_top_35(self) -> None:
        complete = audit_frames([row(rank) for rank in range(1, 36)])
        self.assertTrue(complete[0].complete)

        incomplete = audit_frames([row(rank) for rank in range(1, 35)])
        self.assertFalse(incomplete[0].complete)
        self.assertIn("frame_ends_before_rank_35", incomplete[0].errors)

    def test_duplicate_rank_fails_frame(self) -> None:
        rows = [row(rank) for rank in range(1, 36)]
        rows[-1] = replace(rows[-1], cohort_rank=34)
        audit = audit_frames(rows)[0]
        self.assertIn("duplicate_cohort_rank", audit.errors)

    def test_historical_year_rejects_modern_regime(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires source_regime"):
            replace(row(1), cohort_year=1960)

    def test_modern_regime_rejects_rental_amount_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "does not permit source_amount_type"):
            replace(
                row(1),
                source_amount_type="projected_ultimate",
            )

    def test_frame_rejects_mixed_historical_amount_types(self) -> None:
        rows = [
            replace(
                row(rank),
                cohort_year=1965,
                first_domestic_release_date="1965-01-01",
                source_regime="variety_rental",
                metric="distributor_rental",
                source_amount_type="cumulative_to_date",
            )
            for rank in range(1, 36)
        ]
        rows[-1] = replace(rows[-1], source_amount_type="projected_ultimate")
        audit = audit_frames(rows)[0]
        self.assertIn("mixed_source_amount_types", audit.errors)

    def test_strict_boolean_and_hash_pairing(self) -> None:
        with self.assertRaisesRegex(ValueError, "both be set or empty"):
            replace(row(1), artifact_path="restricted/page.html")

    def test_cross_table_tie_order_is_deterministic_and_input_independent(self) -> None:
        first = replace(row(21), stable_title_id="afi:one", amount=Decimal(3000000))
        second = replace(
            row(22),
            stable_title_id="afi:two",
            amount=Decimal(3000000),
            source_table_year=1983,
        )
        forward = order_cross_table_tie([first, second], seed="public-commit")
        reverse = order_cross_table_tie([second, first], seed="public-commit")
        self.assertEqual(forward, reverse)
        self.assertEqual({item.stable_title_id for item in forward}, {"afi:one", "afi:two"})

    def test_cross_table_tie_rejects_different_amounts(self) -> None:
        first = row(21)
        second = replace(row(22), source_table_year=1983)
        with self.assertRaisesRegex(ValueError, "one nonempty retained amount"):
            order_cross_table_tie([first, second], seed="public-commit")


class TitleResolutionTests(unittest.TestCase):
    def test_uses_frozen_rank_order_without_compressing_frame(self) -> None:
        rows = [row(rank) for rank in range(1, 36)]
        rows[12] = row(13, eligibility="ineligible")
        slot = PilotSlot(
            period_start=1976,
            period_end=1988,
            assignment="backup_1",
            release_year=1982,
            selected_rank=13,
            rank_replacement_order=(13, 19, 11, 12, 14, 15, 16, 17, 18, 20),
        )
        resolved = resolve_pilot_titles(rows, [slot])
        self.assertEqual(resolved[0].row.cohort_rank, 19)
        self.assertEqual(resolved[0].skipped_ranks, (13,))

    def test_incomplete_frame_blocks_title_resolution(self) -> None:
        slot = PilotSlot(1976, 1988, "backup_1", 1982, 13, (13, 19))
        with self.assertRaisesRegex(ValueError, "incomplete frames"):
            resolve_pilot_titles([row(rank) for rank in range(1, 30)], [slot])

    def test_resolved_output_records_skips_and_source(self) -> None:
        rows = [row(rank) for rank in range(1, 36)]
        rows[12] = row(13, eligibility="ineligible")
        slot = PilotSlot(1976, 1988, "backup_1", 1982, 13, (13, 19))
        resolved = resolve_pilot_titles(rows, [slot])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "resolved.csv"
            write_resolved_titles_csv(path, resolved)
            text = path.read_text(encoding="utf-8")
        self.assertIn("13,19,13,film-19,Film 19", text)
        self.assertIn("boxofficemojo.com", text)


if __name__ == "__main__":
    unittest.main()
