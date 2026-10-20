"""Deterministic, metadata-only pilot sampling."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


PILOT_PERIODS: tuple[tuple[int, int], ...] = (
    (1950, 1962),
    (1963, 1975),
    (1976, 1988),
    (1989, 2001),
    (2002, 2014),
    (2015, 2025),
)


@dataclass(frozen=True, slots=True)
class FilmCandidate:
    film_id: str
    title: str
    release_year: int
    annual_rank: int
    popularity_source_id: str
    source_url: str
    eligible: bool = True
    exclusion_reason: str = ""

    def __post_init__(self) -> None:
        if not self.film_id.strip() or not self.title.strip():
            raise ValueError("film_id and title may not be empty")
        if not 1950 <= self.release_year <= 2025:
            raise ValueError("release_year is outside the frozen study window")
        if self.annual_rank < 1:
            raise ValueError("annual_rank must be positive")
        if not self.eligible and not self.exclusion_reason.strip():
            raise ValueError("ineligible candidates require an exclusion_reason")


@dataclass(frozen=True, slots=True)
class PilotSelection:
    film: FilmCandidate
    period_start: int
    period_end: int
    assignment: str
    selection_order: int


@dataclass(frozen=True, slots=True)
class PilotSlot:
    period_start: int
    period_end: int
    assignment: str
    release_year: int
    selected_rank: int
    rank_replacement_order: tuple[int, ...]


def period_for_year(year: int) -> tuple[int, int]:
    for start, end in PILOT_PERIODS:
        if start <= year <= end:
            return start, end
    raise ValueError(f"Year {year} is outside the pilot periods")


def _selection_key(seed: str, candidate: FilmCandidate) -> bytes:
    payload = f"{seed}|{candidate.film_id}|{candidate.release_year}|{candidate.annual_rank}"
    return hashlib.sha256(payload.encode("utf-8")).digest()


def _slot_key(seed: str, *parts: object) -> bytes:
    payload = "|".join((seed, *(str(part) for part in parts)))
    return hashlib.sha256(payload.encode("utf-8")).digest()


def draw_pilot_slots(
    *,
    seed: str,
    backups_per_period: int = 1,
    allowed_ranks: range = range(11, 26),
) -> list[PilotSlot]:
    """Select years and annual ranks before retrieving any film titles.

    The public seed fixes the year, initial rank, and within-year replacement
    order for each development, validation, and backup slot. This two-stage
    design avoids constructing a full 1,000-plus-film pilot frame while still
    preventing thematic or source-availability-based title selection.
    """

    if not seed:
        raise ValueError("seed may not be empty")
    if backups_per_period < 0:
        raise ValueError("backups_per_period may not be negative")
    rank_values = tuple(allowed_ranks)
    if not rank_values:
        raise ValueError("allowed_ranks may not be empty")

    assignments = ("development", "validation") + tuple(
        f"backup_{index}" for index in range(1, backups_per_period + 1)
    )
    slots: list[PilotSlot] = []
    for start, end in PILOT_PERIODS:
        years = sorted(
            range(start, end + 1),
            key=lambda year: (_slot_key(seed, "year", start, end, year), year),
        )
        if len(years) < len(assignments):
            raise ValueError(f"Period {start}-{end} has too few years for requested slots")
        for assignment, year in zip(assignments, years, strict=False):
            rank_order = tuple(
                sorted(
                    rank_values,
                    key=lambda rank: (
                        _slot_key(seed, "rank", start, end, assignment, year, rank),
                        rank,
                    ),
                )
            )
            slots.append(
                PilotSlot(
                    period_start=start,
                    period_end=end,
                    assignment=assignment,
                    release_year=year,
                    selected_rank=rank_order[0],
                    rank_replacement_order=rank_order,
                )
            )
    return slots


def draw_pilot(
    candidates: Iterable[FilmCandidate],
    *,
    seed: str,
    allowed_ranks: range = range(11, 26),
    backups_per_period: int = 1,
) -> list[PilotSelection]:
    """Draw one development, one validation, and optional backups per period.

    Selection uses only manifest candidate metadata. Each selected title within a
    period must come from a different release year so that a single year cannot
    supply both development and validation films.
    """

    if not seed:
        raise ValueError("seed may not be empty")
    if backups_per_period < 0:
        raise ValueError("backups_per_period may not be negative")

    needed = 2 + backups_per_period
    by_period: dict[tuple[int, int], list[FilmCandidate]] = {
        period: [] for period in PILOT_PERIODS
    }
    seen_ids: set[str] = set()

    for candidate in candidates:
        if candidate.film_id in seen_ids:
            raise ValueError(f"Duplicate film_id: {candidate.film_id}")
        seen_ids.add(candidate.film_id)
        if not candidate.eligible or candidate.annual_rank not in allowed_ranks:
            continue
        by_period[period_for_year(candidate.release_year)].append(candidate)

    selections: list[PilotSelection] = []
    assignments = ("development", "validation") + tuple(
        f"backup_{index}" for index in range(1, backups_per_period + 1)
    )

    for start, end in PILOT_PERIODS:
        ordered = sorted(
            by_period[(start, end)],
            key=lambda candidate: (_selection_key(seed, candidate), candidate.film_id),
        )
        distinct_years: list[FilmCandidate] = []
        used_years: set[int] = set()
        for candidate in ordered:
            if candidate.release_year in used_years:
                continue
            distinct_years.append(candidate)
            used_years.add(candidate.release_year)
            if len(distinct_years) == needed:
                break
        if len(distinct_years) < needed:
            raise ValueError(
                f"Period {start}-{end} has {len(distinct_years)} eligible distinct years; "
                f"{needed} required"
            )
        selections.extend(
            PilotSelection(
                film=film,
                period_start=start,
                period_end=end,
                assignment=assignment,
                selection_order=index,
            )
            for index, (film, assignment) in enumerate(
                zip(distinct_years, assignments, strict=True), start=1
            )
        )
    return selections


def read_candidates_csv(path: str | Path) -> list[FilmCandidate]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        required = {
            "film_id",
            "title",
            "release_year",
            "annual_rank",
            "popularity_source_id",
            "source_url",
            "eligible",
            "exclusion_reason",
        }
        missing = required - set(rows.fieldnames or ())
        if missing:
            raise ValueError(f"Candidate CSV is missing columns: {sorted(missing)}")
        return [
            FilmCandidate(
                film_id=row["film_id"],
                title=row["title"],
                release_year=int(row["release_year"]),
                annual_rank=int(row["annual_rank"]),
                popularity_source_id=row["popularity_source_id"],
                source_url=row["source_url"],
                eligible=row["eligible"].strip().lower() in {"1", "true", "yes"},
                exclusion_reason=row["exclusion_reason"],
            )
            for row in rows
        ]


def read_slots_csv(path: str | Path) -> list[PilotSlot]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = csv.DictReader(handle)
        required = {
            "period_start",
            "period_end",
            "assignment",
            "release_year",
            "selected_rank",
            "rank_replacement_order",
        }
        missing = required - set(rows.fieldnames or ())
        if missing:
            raise ValueError(f"Slot CSV is missing columns: {sorted(missing)}")
        slots: list[PilotSlot] = []
        for row in rows:
            replacement_order = tuple(
                int(rank) for rank in row["rank_replacement_order"].split(";") if rank
            )
            selected_rank = int(row["selected_rank"])
            if not replacement_order or replacement_order[0] != selected_rank:
                raise ValueError(
                    "rank_replacement_order must begin with selected_rank"
                )
            if len(replacement_order) != len(set(replacement_order)):
                raise ValueError("rank_replacement_order may not contain duplicates")
            if set(replacement_order) != set(range(11, 26)):
                raise ValueError("rank_replacement_order must contain ranks 11 through 25")
            period = (int(row["period_start"]), int(row["period_end"]))
            if period not in PILOT_PERIODS:
                raise ValueError(f"Unknown pilot period: {period}")
            release_year = int(row["release_year"])
            if not period[0] <= release_year <= period[1]:
                raise ValueError("release_year must fall within its pilot period")
            slots.append(
                PilotSlot(
                    period_start=period[0],
                    period_end=period[1],
                    assignment=row["assignment"],
                    release_year=release_year,
                    selected_rank=selected_rank,
                    rank_replacement_order=replacement_order,
                )
            )
        return slots


def write_selections_csv(
    path: str | Path,
    selections: Sequence[PilotSelection],
) -> None:
    fields = (
        "film_id",
        "title",
        "release_year",
        "annual_rank",
        "popularity_source_id",
        "source_url",
        "period_start",
        "period_end",
        "assignment",
        "selection_order",
    )
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for selection in selections:
            film = selection.film
            writer.writerow(
                {
                    "film_id": film.film_id,
                    "title": film.title,
                    "release_year": film.release_year,
                    "annual_rank": film.annual_rank,
                    "popularity_source_id": film.popularity_source_id,
                    "source_url": film.source_url,
                    "period_start": selection.period_start,
                    "period_end": selection.period_end,
                    "assignment": selection.assignment,
                    "selection_order": selection.selection_order,
                }
            )


def write_slots_csv(path: str | Path, slots: Sequence[PilotSlot]) -> None:
    fields = (
        "period_start",
        "period_end",
        "assignment",
        "release_year",
        "selected_rank",
        "rank_replacement_order",
    )
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for slot in slots:
            writer.writerow(
                {
                    "period_start": slot.period_start,
                    "period_end": slot.period_end,
                    "assignment": slot.assignment,
                    "release_year": slot.release_year,
                    "selected_rank": slot.selected_rank,
                    "rank_replacement_order": ";".join(
                        str(rank) for rank in slot.rank_replacement_order
                    ),
                }
            )
