from __future__ import annotations

import csv
import re
import unittest
from collections import Counter
from pathlib import Path

from film_values.rankings import (
    PILOT_HISTORICAL_AMOUNT_TYPE,
    audit_frames,
    read_ranking_csv,
    resolve_pilot_titles,
)
from film_values.sampling import read_slots_csv


ROOT = Path(__file__).resolve().parents[1]
BOX_OFFICE = ROOT / "data" / "box_office"


class CommittedModernFrameTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = read_ranking_csv(BOX_OFFICE / "pilot_rankings_1982_2024.csv")
        cls.slots = [
            slot
            for slot in read_slots_csv(ROOT / "data" / "pilot_slots.csv")
            if slot.release_year >= 1982 and slot.frame_status == "required"
        ]

    def test_every_modern_slot_has_a_complete_top_35_frame(self) -> None:
        expected_years = {slot.release_year for slot in self.slots}
        audits = audit_frames(self.rows, required_years=expected_years)
        self.assertEqual(len(audits), 12)
        self.assertTrue(all(audit.complete for audit in audits), audits)
        self.assertEqual(
            Counter(row.cohort_year for row in self.rows),
            Counter({year: 35 for year in expected_years}),
        )

    def test_resolution_file_matches_executable_resolver(self) -> None:
        resolved = resolve_pilot_titles(self.rows, self.slots)
        computed = {
            (item.slot.period_start, item.slot.assignment): (
                item.row.cohort_year,
                item.row.cohort_rank,
                item.row.stable_title_id,
                item.row.title,
            )
            for item in resolved
        }
        with (BOX_OFFICE / "pilot_title_resolution_1982_2024.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            stored = {
                (int(row["period_start"]), row["assignment"]): (
                    int(row["cohort_year"]),
                    int(row["selected_rank"]),
                    row["stable_title_id"],
                    row["title"],
                )
                for row in csv.DictReader(handle)
            }
        self.assertEqual(computed, stored)

    def test_modern_artifact_gap_remains_explicit(self) -> None:
        # This assertion intentionally preserves the disclosed limitation until
        # a lawful source-artifact or response-hash freeze is added.
        self.assertTrue(all(not row.artifact_path for row in self.rows))
        self.assertTrue(all(not row.artifact_sha256 for row in self.rows))

    def test_every_accessed_url_has_a_later_response_fingerprint(self) -> None:
        with (BOX_OFFICE / "source_access_log.csv").open(newline="", encoding="utf-8") as handle:
            original = list(csv.DictReader(handle))
        with (BOX_OFFICE / "source_revalidation_log.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            revalidated = list(csv.DictReader(handle))
        original_keys = {(row["source"], row["cohort_year"], row["url"]) for row in original}
        revalidated_keys = {
            (row["source"], row["cohort_year"], row["url"]) for row in revalidated
        }
        self.assertEqual(original_keys, revalidated_keys)
        self.assertEqual(len(revalidated), 27)
        for row in revalidated:
            self.assertEqual(row["http_status"], "200")
            self.assertRegex(row["response_sha256"], re.compile(r"^[a-f0-9]{64}$"))
            self.assertGreater(int(row["response_bytes"]), 0)

    def test_live_revalidation_accounts_for_all_primary_rows(self) -> None:
        with (BOX_OFFICE / "live_frame_revalidation.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            checks = list(csv.DictReader(handle))
        self.assertEqual(len(checks), 12)
        self.assertEqual(sum(int(row["matched_rows"]) for row in checks), len(self.rows))
        self.assertTrue(all(int(row["mismatched_rows"]) == 0 for row in checks))
        self.assertTrue(all(row["result"] == "exact_match" for row in checks))


class CommittedHistoricalCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.historical_slots = {
            slot.release_year: slot
            for slot in read_slots_csv(ROOT / "data" / "pilot_slots.csv")
            if slot.release_year < 1982
        }
        with (BOX_OFFICE / "historical_frame_status.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            cls.status_rows = {
                int(row["cohort_year"]): row for row in csv.DictReader(handle)
            }

    def test_status_table_matches_every_historical_slot(self) -> None:
        self.assertEqual(set(self.status_rows), set(self.historical_slots))
        for year, row in self.status_rows.items():
            slot = self.historical_slots[year]
            self.assertEqual(int(row["selected_rank"]), slot.selected_rank)
            self.assertEqual(
                tuple(int(rank) for rank in row["rank_replacement_order"].split(";")),
                slot.rank_replacement_order,
            )
            self.assertEqual(row["assignment"], slot.assignment)
            self.assertEqual(row["amount_rule"], PILOT_HISTORICAL_AMOUNT_TYPE[year])

    def test_checkpoint_does_not_overstate_historical_freeze(self) -> None:
        self.assertEqual(self.status_rows[1960]["frame_status"], "blocked")
        self.assertEqual(self.historical_slots[1960].frame_status, "unconstructible")
        self.assertEqual(self.status_rows[1959]["top35_rows_frozen"], "false")
        self.assertIn("not frozen", self.status_rows[1959]["blocker_detail"].lower())
        for year in (1962, 1965, 1966, 1968):
            self.assertNotEqual(self.status_rows[year]["fully_reconstructible"], "true")

    def test_1959_reconstruction_is_structurally_complete_but_unresolved(self) -> None:
        rows = read_ranking_csv(BOX_OFFICE / "pilot_rankings_1959_provisional.csv")
        audits = audit_frames(rows, required_years={1959})
        self.assertEqual(len(rows), 36)
        self.assertEqual(len(audits), 1)
        self.assertTrue(audits[0].complete, audits[0])
        self.assertTrue(all(row.eligibility == "unresolved" for row in rows))
        self.assertTrue(all(row.source_amount_type == "cumulative_to_date" for row in rows))

    def test_1952_selected_rank_is_invariant_while_boundary_is_open(self) -> None:
        with (BOX_OFFICE / "historical_1952_projection_audit.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            rows = list(csv.DictReader(handle))
        selected = [row for row in rows if row["selected_rank_12_match"] == "true"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["title"], "With a Song in My Heart")
        self.assertEqual(selected[0]["latest_projected_amount"], "3250000")
        self.assertEqual(
            (selected[0]["provisional_rank_low"], selected[0]["provisional_rank_high"]),
            ("12", "12"),
        )
        by_title = {row["title"]: row for row in rows}
        self.assertEqual(
            (
                by_title["Because You're Mine"]["provisional_rank_low"],
                by_title["Because You're Mine"]["provisional_rank_high"],
            ),
            ("34", "35"),
        )
        for title in ("Lone Star", "She's Working Her Way Through College"):
            self.assertEqual(
                (
                    by_title[title]["provisional_rank_low"],
                    by_title[title]["provisional_rank_high"],
                ),
                ("35", "37"),
            )

    def test_post_cutoff_spartacus_amount_has_explicit_provenance(self) -> None:
        with (BOX_OFFICE / "historical_source_access_log.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            rows = list(csv.DictReader(handle))
        matching = [
            row
            for row in rows
            if row["issue_date"] == "1963-01-09"
            and "1960" in row["cohort_years"].split(";")
            and "Spartacus" in row["notes"]
        ]
        self.assertEqual(len(matching), 1)
        self.assertRegex(matching[0]["artifact_sha256"], re.compile(r"^[a-f0-9]{64}$"))
        self.assertIn("outside", matching[0]["notes"].lower())


if __name__ == "__main__":
    unittest.main()
