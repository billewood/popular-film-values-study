from __future__ import annotations

import csv
import re
import unittest
from collections import Counter
from pathlib import Path

from film_values.rankings import audit_frames, read_ranking_csv, resolve_pilot_titles
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


if __name__ == "__main__":
    unittest.main()
