"""Exact-evidence normalization and verification."""

from __future__ import annotations

import re
import unicodedata

from .models import EvidenceRecord


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
