from __future__ import annotations

import unittest

from film_values.sampling import (
    FilmCandidate,
    PILOT_PERIODS,
    draw_pilot,
    draw_pilot_slots,
)


def candidates() -> list[FilmCandidate]:
    rows: list[FilmCandidate] = []
    for start, _end in PILOT_PERIODS:
        for offset in range(4):
            year = start + offset
            rows.append(
                FilmCandidate(
                    film_id=f"film-{year}",
                    title=f"Film {year}",
                    release_year=year,
                    annual_rank=11 + offset,
                    popularity_source_id=f"rankings-{year}",
                    source_url=f"https://example.test/{year}",
                )
            )
    return rows


class SamplingTests(unittest.TestCase):
    def test_slot_draw_is_deterministic_and_uses_distinct_years(self) -> None:
        first = draw_pilot_slots(seed="public-commit-hash")
        second = draw_pilot_slots(seed="public-commit-hash")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 18)
        for period in PILOT_PERIODS:
            selected = [
                row for row in first if (row.period_start, row.period_end) == period
            ]
            self.assertEqual(
                [row.assignment for row in selected],
                ["development", "validation", "backup_1"],
            )
            self.assertEqual(len({row.release_year for row in selected}), 3)
            for row in selected:
                self.assertEqual(row.selected_rank, row.rank_replacement_order[0])
                self.assertEqual(set(row.rank_replacement_order), set(range(11, 26)))

    def test_draw_is_deterministic_and_balanced(self) -> None:
        first = draw_pilot(candidates(), seed="protocol-v0.1")
        second = draw_pilot(reversed(candidates()), seed="protocol-v0.1")
        self.assertEqual(first, second)
        self.assertEqual(len(first), 18)
        for period in PILOT_PERIODS:
            selected = [
                row for row in first if (row.period_start, row.period_end) == period
            ]
            self.assertEqual(
                [row.assignment for row in selected],
                ["development", "validation", "backup_1"],
            )
            self.assertEqual(len({row.film.release_year for row in selected}), 3)

    def test_rank_filter_excludes_main_corpus(self) -> None:
        rows = candidates()
        rows[0] = FilmCandidate(
            film_id="top-ten",
            title="Top Ten Film",
            release_year=1950,
            annual_rank=10,
            popularity_source_id="rankings-1950",
            source_url="https://example.test/top-ten",
        )
        result = draw_pilot(rows, seed="protocol-v0.1")
        self.assertNotIn("top-ten", {row.film.film_id for row in result})

    def test_duplicate_film_ids_fail(self) -> None:
        rows = candidates()
        rows.append(rows[0])
        with self.assertRaisesRegex(ValueError, "Duplicate film_id"):
            draw_pilot(rows, seed="protocol-v0.1")


if __name__ == "__main__":
    unittest.main()
