"""Exact-evidence normalization and verification."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Collection, Iterable, Mapping

from .models import ClaimDependence, EvidenceRecord


_TYPOGRAPHIC_TRANSLATION = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201a": "'",
        "\u201b": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u201e": '"',
        "\u201f": '"',
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2015": "-",
        "\u2026": "...",
        "\u00a0": " ",
    }
)


def normalize_evidence_text(text: str) -> str:
    """Apply the protocol's loss-limited normalization.

    Normalization is deliberately conservative: canonically equivalent Unicode,
    typographic punctuation, and whitespace may change. Compatibility characters,
    case, words, and word order may not.
    """

    normalized = unicodedata.normalize("NFC", text).translate(_TYPOGRAPHIC_TRANSLATION)
    return re.sub(r"\s+", " ", normalized).strip()


def evidence_span_matches(source_text: str, evidence: str | EvidenceRecord) -> bool:
    """Return whether an evidence span occurs in the supplied archived source."""

    span = evidence.exact_evidence_span if isinstance(evidence, EvidenceRecord) else evidence
    normalized_span = normalize_evidence_text(span)
    if not normalized_span:
        return False
    return normalized_span in normalize_evidence_text(source_text)


def evidence_record_spans_match(source_text: str, record: EvidenceRecord) -> bool:
    """Verify the claim span and, when present, its exact attribution span."""

    if not evidence_span_matches(source_text, record):
        return False
    if record.attribution_span is None:
        return True
    return evidence_span_matches(source_text, record.attribution_span)


def validate_claim_attribution_sources(
    records: Iterable[EvidenceRecord],
    selected_source_ids_by_film: Mapping[str, Collection[str]],
) -> None:
    """Fail unless every derivative points inside its film's frozen source universe."""

    cached_universes: dict[str, frozenset[str]] = {}
    for record in records:
        if record.claim_dependence is not ClaimDependence.ATTRIBUTED_DERIVATIVE:
            continue

        if record.film_id not in selected_source_ids_by_film:
            raise ValueError(
                f"No frozen selected-source universe was supplied for film {record.film_id!r}"
            )
        if record.film_id not in cached_universes:
            raw_universe = selected_source_ids_by_film[record.film_id]
            if isinstance(raw_universe, (str, bytes)):
                raise TypeError("A selected-source universe must be a collection of IDs")
            if any(
                not isinstance(value, str) or not value.strip()
                for value in raw_universe
            ):
                raise ValueError("Selected-source universes must contain nonempty string IDs")
            cached_universes[record.film_id] = frozenset(raw_universe)

        universe = cached_universes[record.film_id]
        if record.source_id not in universe:
            raise ValueError(
                f"Evidence source {record.source_id!r} is not selected for film "
                f"{record.film_id!r}"
            )
        if record.source_id in record.attributed_source_ids:
            raise ValueError("A derivative claim may not attribute itself as its source")
        unknown = sorted(set(record.attributed_source_ids) - universe)
        if unknown:
            raise ValueError(
                f"Attributed source IDs are not selected for film {record.film_id!r}: "
                f"{unknown}"
            )
