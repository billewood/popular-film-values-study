"""Validation and title resolution for frozen annual popularity frames."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable, Sequence

from .sampling import PilotSlot


RANKING_FIELDS: tuple[str, ...] = (
    "cohort_year",
    "title",
    "stable_title_id",
    "first_domestic_release_date",
    "release_date_precision",
    "release_date_source",
    "source_regime",
    "primary_source_citation",
    "primary_source_url",
    "source_table_year",
    "source_amount_type",
    "metric",
    "territory_definition",
    "amount",
    "amount_estimated",
    "source_row_order",
    "cohort_rank",
    "eligible_rank",
    "reissue_flag",
    "eligibility",
    "exclusion_reason",
    "tie_flag",
    "near_tie_flag",
    "secondary_source_citation",
    "secondary_source_url",
    "secondary_rank",
    "secondary_amount",
    "conflict_code",
    "adjudication_note",
    "retrieved_at_utc",
    "artifact_path",
    "artifact_sha256",
)

ELIGIBILITY_VALUES = frozenset({"eligible", "ineligible", "unresolved"})
REGIME_BY_PERIOD = ((1950, 1981, "variety_rental"), (1982, 2025, "bom_total_gross"))
METRIC_BY_REGIME = {
    "variety_rental": "distributor_rental",
    "bom_total_gross": "domestic_gross",
}
DATE_PRECISIONS = frozenset({"day", "month", "year", "inferred", "unresolved"})
_SHA256 = re.compile(r"^[a-f0-9]{64}$")


def _required_text(value: str, field: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError(f"{field} may not be empty")
    return value


def _parse_bool(value: str, field: str) -> bool:
    normalized = value.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{field} must be true or false")


def _parse_optional_int(value: str, field: str) -> int | None:
    if not value.strip():
        return None
    try:
        parsed = int(value)
    except ValueError as error:
        raise ValueError(f"{field} must be an integer or empty") from error
    if parsed < 1:
        raise ValueError(f"{field} must be positive")
    return parsed


def _parse_optional_decimal(value: str, field: str) -> Decimal | None:
    if not value.strip():
        return None
    try:
        parsed = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"{field} must be numeric or empty") from error
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{field} must be a finite nonnegative number")
    return parsed


def _validate_partial_date(value: str, precision: str) -> None:
    if precision == "unresolved":
        if value:
            raise ValueError("unresolved release date must be empty")
        return
    patterns = {
        "day": r"^\d{4}-\d{2}-\d{2}$",
        "month": r"^\d{4}-\d{2}$",
        "year": r"^\d{4}$",
        "inferred": r"^\d{4}(?:-\d{2}(?:-\d{2})?)?$",
    }
    if not re.fullmatch(patterns[precision], value):
        raise ValueError(
            "first_domestic_release_date does not match release_date_precision"
        )
    if precision == "day":
        datetime.strptime(value, "%Y-%m-%d")
    elif precision == "month":
        datetime.strptime(value, "%Y-%m")


@dataclass(frozen=True, slots=True)
class RankingRow:
    cohort_year: int
    title: str
    stable_title_id: str
    first_domestic_release_date: str
    release_date_precision: str
    release_date_source: str
    source_regime: str
    primary_source_citation: str
    primary_source_url: str
    source_table_year: int
    source_amount_type: str
    metric: str
    territory_definition: str
    amount: Decimal | None
    amount_estimated: bool
    source_row_order: int
    cohort_rank: int
    eligible_rank: int | None
    reissue_flag: bool
    eligibility: str
    exclusion_reason: str
    tie_flag: bool
    near_tie_flag: bool
    secondary_source_citation: str
    secondary_source_url: str
    secondary_rank: int | None
    secondary_amount: Decimal | None
    conflict_code: str
    adjudication_note: str
    retrieved_at_utc: str
    artifact_path: str
    artifact_sha256: str

    def __post_init__(self) -> None:
        if not 1950 <= self.cohort_year <= 2025:
            raise ValueError("cohort_year is outside the frozen study window")
        for field in (
            "title",
            "stable_title_id",
            "release_date_source",
            "primary_source_citation",
            "primary_source_url",
            "source_amount_type",
            "metric",
            "territory_definition",
            "retrieved_at_utc",
        ):
            _required_text(str(getattr(self, field)), field)
        if self.release_date_precision not in DATE_PRECISIONS:
            raise ValueError(f"unknown release_date_precision: {self.release_date_precision}")
        _validate_partial_date(
            self.first_domestic_release_date, self.release_date_precision
        )
        expected_regime = next(
            regime
            for start, end, regime in REGIME_BY_PERIOD
            if start <= self.cohort_year <= end
        )
        if self.source_regime != expected_regime:
            raise ValueError(
                f"{self.cohort_year} requires source_regime {expected_regime}"
            )
        if self.metric != METRIC_BY_REGIME[self.source_regime]:
            raise ValueError(
                f"{self.source_regime} requires metric "
                f"{METRIC_BY_REGIME[self.source_regime]}"
            )
        if self.source_table_year < self.cohort_year:
            raise ValueError("source_table_year may not precede cohort_year")
        if self.source_row_order < 1 or self.cohort_rank < 1:
            raise ValueError("source_row_order and cohort_rank must be positive")
        if self.eligibility not in ELIGIBILITY_VALUES:
            raise ValueError(f"unknown eligibility: {self.eligibility}")
        if self.eligibility == "eligible" and self.exclusion_reason.strip():
            raise ValueError("eligible rows may not have an exclusion_reason")
        if self.eligibility != "eligible" and not self.exclusion_reason.strip():
            raise ValueError("noneligible rows require an exclusion_reason")
        if self.reissue_flag and self.eligibility == "eligible":
            raise ValueError("a rerelease may not be eligible")
        if self.eligible_rank is not None and self.eligibility != "eligible":
            raise ValueError("only eligible rows may have eligible_rank")
        if bool(self.artifact_path) != bool(self.artifact_sha256):
            raise ValueError("artifact_path and artifact_sha256 must both be set or empty")
        if self.artifact_sha256 and not _SHA256.fullmatch(self.artifact_sha256):
            raise ValueError("artifact_sha256 must be lowercase hexadecimal SHA-256")
        try:
            timestamp = datetime.fromisoformat(self.retrieved_at_utc.replace("Z", "+00:00"))
        except ValueError as error:
            raise ValueError("retrieved_at_utc must be an ISO-8601 timestamp") from error
        if timestamp.utcoffset() is None or timestamp.utcoffset().total_seconds() != 0:
            raise ValueError("retrieved_at_utc must include a UTC offset")


@dataclass(frozen=True, slots=True)
class FrameAudit:
    cohort_year: int
    complete: bool
    maximum_rank: int
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResolvedPilotTitle:
    slot: PilotSlot
    row: RankingRow
    skipped_ranks: tuple[int, ...]


def ranking_row_from_csv(row: dict[str, str]) -> RankingRow:
    return RankingRow(
        cohort_year=int(row["cohort_year"]),
        title=row["title"].strip(),
        stable_title_id=row["stable_title_id"].strip(),
        first_domestic_release_date=row["first_domestic_release_date"].strip(),
        release_date_precision=row["release_date_precision"].strip(),
        release_date_source=row["release_date_source"].strip(),
        source_regime=row["source_regime"].strip(),
        primary_source_citation=row["primary_source_citation"].strip(),
        primary_source_url=row["primary_source_url"].strip(),
        source_table_year=int(row["source_table_year"]),
        source_amount_type=row["source_amount_type"].strip(),
        metric=row["metric"].strip(),
        territory_definition=row["territory_definition"].strip(),
        amount=_parse_optional_decimal(row["amount"], "amount"),
        amount_estimated=_parse_bool(row["amount_estimated"], "amount_estimated"),
        source_row_order=int(row["source_row_order"]),
        cohort_rank=int(row["cohort_rank"]),
        eligible_rank=_parse_optional_int(row["eligible_rank"], "eligible_rank"),
        reissue_flag=_parse_bool(row["reissue_flag"], "reissue_flag"),
        eligibility=row["eligibility"].strip(),
        exclusion_reason=row["exclusion_reason"].strip(),
        tie_flag=_parse_bool(row["tie_flag"], "tie_flag"),
        near_tie_flag=_parse_bool(row["near_tie_flag"], "near_tie_flag"),
        secondary_source_citation=row["secondary_source_citation"].strip(),
        secondary_source_url=row["secondary_source_url"].strip(),
        secondary_rank=_parse_optional_int(row["secondary_rank"], "secondary_rank"),
        secondary_amount=_parse_optional_decimal(
            row["secondary_amount"], "secondary_amount"
        ),
        conflict_code=row["conflict_code"].strip(),
        adjudication_note=row["adjudication_note"].strip(),
        retrieved_at_utc=row["retrieved_at_utc"].strip(),
        artifact_path=row["artifact_path"].strip(),
        artifact_sha256=row["artifact_sha256"].strip(),
    )


def read_ranking_csv(path: str | Path) -> list[RankingRow]:
    with Path(path).open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = set(RANKING_FIELDS) - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Ranking CSV is missing columns: {sorted(missing)}")
        return [ranking_row_from_csv(row) for row in reader]


def audit_frames(
    rows: Iterable[RankingRow],
    *,
    required_years: Iterable[int] | None = None,
    minimum_rank: int = 35,
) -> list[FrameAudit]:
    by_year: dict[int, list[RankingRow]] = {}
    for row in rows:
        by_year.setdefault(row.cohort_year, []).append(row)
    years = sorted(set(required_years) if required_years is not None else by_year)
    audits: list[FrameAudit] = []
    for year in years:
        frame = by_year.get(year, [])
        errors: list[str] = []
        if not frame:
            errors.append("frame_missing")
            audits.append(FrameAudit(year, False, 0, tuple(errors)))
            continue
        ranks = [row.cohort_rank for row in frame]
        maximum_rank = max(ranks)
        if len(ranks) != len(set(ranks)):
            errors.append("duplicate_cohort_rank")
        expected = set(range(1, maximum_rank + 1))
        if set(ranks) != expected:
            errors.append("noncontiguous_cohort_rank")
        if maximum_rank < minimum_rank:
            errors.append(f"frame_ends_before_rank_{minimum_rank}")
        ids = [row.stable_title_id for row in frame]
        if len(ids) != len(set(ids)):
            errors.append("duplicate_stable_title_id")
        source_positions = [
            (row.source_table_year, row.source_row_order) for row in frame
        ]
        if len(source_positions) != len(set(source_positions)):
            errors.append("duplicate_source_table_position")
        eligible_ranks = sorted(
            row.eligible_rank for row in frame if row.eligible_rank is not None
        )
        if eligible_ranks and eligible_ranks != list(range(1, len(eligible_ranks) + 1)):
            errors.append("noncontiguous_eligible_rank")
        audits.append(FrameAudit(year, not errors, maximum_rank, tuple(errors)))
    return audits


def resolve_pilot_titles(
    rows: Sequence[RankingRow], slots: Sequence[PilotSlot]
) -> list[ResolvedPilotTitle]:
    required_years = {slot.release_year for slot in slots}
    failed = [
        audit for audit in audit_frames(rows, required_years=required_years) if not audit.complete
    ]
    if failed:
        detail = "; ".join(
            f"{audit.cohort_year}: {','.join(audit.errors)}" for audit in failed
        )
        raise ValueError(f"Cannot resolve titles from incomplete frames: {detail}")
    row_by_year_rank = {(row.cohort_year, row.cohort_rank): row for row in rows}
    resolved: list[ResolvedPilotTitle] = []
    for slot in slots:
        skipped: list[int] = []
        for rank in slot.rank_replacement_order:
            row = row_by_year_rank[(slot.release_year, rank)]
            if row.eligibility == "eligible":
                resolved.append(
                    ResolvedPilotTitle(slot=slot, row=row, skipped_ranks=tuple(skipped))
                )
                break
            skipped.append(rank)
        else:
            raise ValueError(
                f"No eligible title remains for {slot.assignment} {slot.release_year}"
            )
    return resolved


def write_resolved_titles_csv(
    path: str | Path, resolved: Sequence[ResolvedPilotTitle]
) -> None:
    fields = (
        "period_start",
        "period_end",
        "assignment",
        "cohort_year",
        "selected_rank",
        "resolved_rank",
        "skipped_ranks",
        "stable_title_id",
        "title",
        "primary_source_citation",
        "primary_source_url",
    )
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for item in resolved:
            writer.writerow(
                {
                    "period_start": item.slot.period_start,
                    "period_end": item.slot.period_end,
                    "assignment": item.slot.assignment,
                    "cohort_year": item.row.cohort_year,
                    "selected_rank": item.slot.selected_rank,
                    "resolved_rank": item.row.cohort_rank,
                    "skipped_ranks": ";".join(str(rank) for rank in item.skipped_ranks),
                    "stable_title_id": item.row.stable_title_id,
                    "title": item.row.title,
                    "primary_source_citation": item.row.primary_source_citation,
                    "primary_source_url": item.row.primary_source_url,
                }
            )
