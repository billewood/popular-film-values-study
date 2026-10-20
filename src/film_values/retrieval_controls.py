"""Dependency-free validation and audit controls for frozen source bundles.

The JSON files governed here contain metadata only.  Source text and credentials
belong outside the repository and are rejected when represented as document keys.
The bundled JSON Schemas are the structural contract; this module implements the
schema subset they use and the cross-record rules that JSON Schema cannot express.
"""

from __future__ import annotations

import argparse
import calendar
import ipaddress
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import parse_qsl, urlparse

from .models import SourceType


SCHEMA_VERSION = "0.1"
PROTOCOL_VERSION = "0.1"

CANONICAL_SLOTS = (
    "C_TRADE",
    "C_GENERAL",
    "R_LATER",
    "S_ACADEMIC",
    "P_SYNOPSIS",
)
ALL_SLOTS = CANONICAL_SLOTS + ("R_LATER_2",)

SLOT_SOURCE_TYPES = {
    "C_TRADE": "contemporary_trade_review",
    "C_GENERAL": "contemporary_general_review",
    "R_LATER": "later_essay",
    "S_ACADEMIC": "scholarly_analysis",
    "P_SYNOPSIS": "detailed_synopsis",
    "R_LATER_2": "later_essay",
}

SLOT_EXTRACTION_SOURCE_TYPES = {
    "C_TRADE": SourceType.CONTEMPORARY_REVIEW.value,
    "C_GENERAL": SourceType.CONTEMPORARY_REVIEW.value,
    "R_LATER": SourceType.RETROSPECTIVE_ESSAY.value,
    "S_ACADEMIC": SourceType.SCHOLARSHIP.value,
    "P_SYNOPSIS": SourceType.REFERENCE_SYNOPSIS.value,
    "R_LATER_2": SourceType.RETROSPECTIVE_ESSAY.value,
}

# Machine-readable form of the fixed hierarchy in SOURCE_RETRIEVAL.md.  The
# manifest must inventory every slot/system pair.  Systems without a usable
# route remain explicit as unavailable, not verified, or without coverage; they
# may not be silently omitted, substituted, or reordered.
SOURCE_SYSTEM_RULES: dict[str, dict[str, tuple[int, int]]] = {
    "C_TRADE": {
        "variety": (1, 1),
        "hollywood_reporter": (1, 2),
        "boxoffice": (1, 3),
        "motion_picture_daily": (1, 4),
        "film_daily": (1, 5),
    },
    "C_GENERAL": {
        "new_york_times": (1, 1),
        "los_angeles_times": (1, 2),
        "washington_post": (1, 3),
        "chicago_tribune": (1, 4),
        "christian_science_monitor": (1, 5),
        "time": (1, 6),
        "newsweek": (1, 7),
        "first_engagement_city_daily": (1, 8),
    },
    "R_LATER": {
        "bfi_sight_and_sound": (1, 1),
        "film_at_lincoln_center_film_comment": (1, 2),
        "museum_of_modern_art": (1, 3),
        "library_of_congress": (1, 4),
        "academy": (1, 5),
        "american_film_institute": (1, 6),
        "new_york_times": (2, 1),
        "los_angeles_times": (2, 2),
        "washington_post": (2, 3),
        "new_yorker": (2, 4),
        "chicago_reader_or_rogerebert": (2, 5),
        "time": (2, 6),
        "criterion_current": (3, 1),
        "other_commissioned_edition": (3, 2),
    },
    "S_ACADEMIC": {
        "fiaf": (1, 1),
        "film_and_television_literature_index": (1, 2),
        "jstor": (1, 3),
        "project_muse": (1, 4),
        "crossref_openalex_unpaywall": (1, 5),
        "mla_international_bibliography": (1, 6),
        "worldcat_and_local_catalog": (1, 7),
        "google_scholar": (1, 8),
    },
    "P_SYNOPSIS": {
        "afi_catalog": (1, 1),
        "film_index_international": (1, 2),
        "bfi_or_national_film_institute": (1, 3),
        "accountable_film_reference": (1, 4),
        "scholarly_film_encyclopedia": (1, 5),
    },
}
SOURCE_SYSTEM_RULES["R_LATER_2"] = SOURCE_SYSTEM_RULES["R_LATER"]

SOURCE_SYSTEM_DISPLAY_NAMES = {
    "variety": "Variety",
    "hollywood_reporter": "The Hollywood Reporter",
    "boxoffice": "Boxoffice",
    "motion_picture_daily": "Motion Picture Daily",
    "film_daily": "Film Daily",
    "new_york_times": "The New York Times",
    "los_angeles_times": "Los Angeles Times",
    "washington_post": "The Washington Post",
    "chicago_tribune": "Chicago Tribune",
    "christian_science_monitor": "The Christian Science Monitor",
    "time": "Time",
    "newsweek": "Newsweek",
    "first_engagement_city_daily": "First-engagement city daily",
    "bfi_sight_and_sound": "BFI / Sight and Sound",
    "film_at_lincoln_center_film_comment": "Film at Lincoln Center / Film Comment",
    "museum_of_modern_art": "Museum of Modern Art",
    "library_of_congress": "Library of Congress",
    "academy": "Academy Museum or Academy of Motion Picture Arts and Sciences",
    "american_film_institute": "American Film Institute",
    "new_yorker": "The New Yorker",
    "chicago_reader_or_rogerebert": "Chicago Reader or RogerEbert.com",
    "criterion_current": "Criterion Current",
    "other_commissioned_edition": "Other commissioned edition",
    "fiaf": "FIAF International Index to Film Periodicals",
    "film_and_television_literature_index": "Film & Television Literature Index",
    "jstor": "JSTOR",
    "project_muse": "Project MUSE",
    "crossref_openalex_unpaywall": "Crossref, OpenAlex, and Unpaywall",
    "mla_international_bibliography": "MLA International Bibliography",
    "worldcat_and_local_catalog": "WorldCat and local library catalog",
    "google_scholar": "Google Scholar",
    "afi_catalog": "AFI Catalog",
    "film_index_international": "Film Index International",
    "bfi_or_national_film_institute": "BFI or national film institute",
    "accountable_film_reference": "Accountable film reference work",
    "scholarly_film_encyclopedia": "Scholarly film encyclopedia",
}

SOURCE_SYSTEM_OUTLET_ALIASES = {
    "bfi_sight_and_sound": {"BFI", "Sight and Sound", "BFI / Sight and Sound"},
    "film_at_lincoln_center_film_comment": {
        "Film at Lincoln Center",
        "Film Comment",
        "Film at Lincoln Center / Film Comment",
    },
    "academy": {
        "Academy Museum",
        "Academy of Motion Picture Arts and Sciences",
        "Academy Museum or Academy of Motion Picture Arts and Sciences",
    },
    "chicago_reader_or_rogerebert": {
        "Chicago Reader",
        "RogerEbert.com",
        "Chicago Reader or RogerEbert.com",
    },
}

SCHOLARLY_FORM_PRIORITY = {
    "peer_reviewed_film_article": 1,
    "scholarly_book_chapter_film": 2,
    "peer_reviewed_comparative_article": 3,
    "scholarly_book_section": 4,
    "doctoral_dissertation_chapter": 5,
}

EXCLUSION_REASONS = frozenset(
    {
        "not_about_sampled_film",
        "wrong_document_type",
        "outside_date_window",
        "incomplete_text",
        "insufficient_length",
        "missing_authorship_or_date",
        "duplicate_or_dependent",
        "no_processing_rights",
        "access_failure",
        "ocr_unusable",
        "eligibility_ambiguous",
        "other_predefined",
    }
)

OTHER_PREDEFINED_DETAIL_CODES = frozenset(
    {
        "promotional_or_studio_authored",
        "anonymous_capsule_or_rating_only",
        "audience_or_social_content",
        "unsupported_audio_without_transcript",
        "personal_or_fan_site",
        "snippet_abstract_or_preview_only",
        "plot_only_outside_synopsis_slot",
        "ai_generated_or_provenance_uncertain",
        "wrong_release_remake_or_adaptation",
        "interview_without_independent_analysis",
        "untraceable_translation_or_repost",
        "pirated_or_circumvented_copy",
    }
)

EXHAUSTED_STOP_REASONS = frozenset(
    {
        "resource_exhausted",
        "screening_cap_reached",
        "no_results",
        "access_blocked",
        "completed_without_eligible_candidate",
    }
)

_DEPENDENCE_FLAGS = frozenset(
    {
        "shared_byline",
        "wire_or_syndication_credit",
        "explicit_republication",
        "revised_version",
        "translated_version",
        "database_copy",
    }
)

_ALLOWED_QUERY_WORDS = frozenset(
    {
        "and",
        "or",
        "not",
        "site",
        "title",
        "abstract",
        "subject",
        "full",
        "text",
        "film",
        "movie",
        "cinema",
        "motion",
        "picture",
        "review",
        "criticism",
        "essay",
        "analysis",
        "synopsis",
    }
)

_THEME_QUERY_TERMS = frozenset(
    {
        "selfish",
        "selfishness",
        "selfless",
        "selflessness",
        "altruism",
        "altruistic",
        "greed",
        "consumerism",
        "consumerist",
        "materialism",
        "materialist",
        "status",
        "fame",
        "power",
        "achievement",
        "competition",
        "competitive",
        "romance",
        "romantic",
        "love",
        "friendship",
        "community",
        "solidarity",
        "care",
        "service",
        "sacrifice",
        "sacrificial",
        "justice",
        "duty",
        "creativity",
        "beauty",
        "knowledge",
        "truth",
        "discovery",
        "religion",
        "religious",
        "spiritual",
        "existential",
        "meaning",
        "pleasure",
        "adventure",
        "revenge",
        "freedom",
        "autonomy",
        "punished",
        "punishment",
        "capitalism",
        "capitalist",
        "morality",
        "moral",
    }
)

_SENSITIVE_QUERY_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "key",
        "token",
        "access_token",
        "auth",
        "authorization",
        "password",
        "passwd",
        "cookie",
        "session",
        "session_id",
        "signature",
        "sig",
    }
)

INCLUDABLE_RIGHTS_CLASSES = frozenset(
    {
        "public_domain_verified",
        "open_license_verified",
        "publisher_public_terms_reviewed",
        "subscription_personal_research",
        "subscription_tdm_authorized",
        "permission_granted",
    }
)

RIGHTS_CLASS_BASIS_TYPES = {
    "public_domain_verified": ("public_domain_status", {"public_domain_statement", "item_rights_statement"}),
    "open_license_verified": ("open_license", {"open_license", "item_rights_statement"}),
    "publisher_public_terms_reviewed": ("publisher_terms", {"provider_terms", "item_rights_statement"}),
    "subscription_personal_research": (
        "subscription_license",
        {"subscription_license", "institutional_license_review"},
    ),
    "subscription_tdm_authorized": (
        "tdm_authorization",
        {"tdm_authorization", "institutional_license_review"},
    ),
    "permission_granted": ("written_permission", {"written_permission"}),
}

_FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "access_token",
        "refresh_token",
        "session_token",
        "authorization_header",
        "password",
        "passphrase",
        "secret",
        "credentials",
        "cookie",
        "cookies",
    }
)
_FORBIDDEN_SOURCE_TEXT_KEYS = frozenset(
    {
        "full_text",
        "raw_text",
        "source_text",
        "document_text",
        "article_text",
        "ocr_text",
        "body_text",
        "content_text",
        "evidence_span",
        "exact_evidence_span",
    }
)

_SENSITIVE_VALUE_PATTERNS = (
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|password|passwd|"
        r"authorization|cookie|session[_-]?id)\s*[:=]\s*\S+",
        re.IGNORECASE,
    ),
    re.compile(r"\bbearer\s+[A-Za-z0-9._~+/=-]{8,}", re.IGNORECASE),
)

_SOURCE_TEXT_PASTE_PATTERN = re.compile(
    r"\b(?:full|complete)\s+(?:subscriber\s+)?(?:article|chapter|source|document)\s+"
    r"(?:text\s+)?(?:pasted|copied|follows|below)\b",
    re.IGNORECASE,
)


class MetadataError(ValueError):
    """Raised when a JSON document cannot be safely loaded."""


@dataclass(frozen=True, slots=True)
class AuditResult:
    """Complete result of structural and cross-document validation."""

    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    summary: Mapping[str, Any]

    @property
    def ok(self) -> bool:
        return not self.errors


def extraction_source_type_for_slot(slot: str) -> SourceType:
    """Map a retrieval slot to the exact downstream evidence SourceType."""

    try:
        return SourceType(SLOT_EXTRACTION_SOURCE_TYPES[slot])
    except KeyError as exc:
        raise ValueError(f"unknown retrieval slot: {slot!r}") from exc


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise MetadataError(f"duplicate JSON key: {key!r}")
        value[key] = item
    return value


def _reject_nonfinite(value: str) -> None:
    raise MetadataError(f"non-finite JSON number is not permitted: {value}")


def load_json(path: str | Path) -> dict[str, Any]:
    """Load a strict UTF-8 JSON object, rejecting duplicates and non-finite values."""

    source = Path(path)
    try:
        value = json.loads(
            source.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MetadataError(f"cannot load {source}: {exc}") from exc
    if not isinstance(value, dict):
        raise MetadataError(f"{source} must contain a JSON object at its root")
    return value


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=None)
def _load_schema(filename: str) -> dict[str, Any]:
    return load_json(_repository_root() / "schemas" / filename)


def _join_path(path: str, part: str | int) -> str:
    if isinstance(part, int):
        return f"{path}[{part}]"
    return f"{path}.{part}" if path else part


def _json_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return left == right


def _matches_type(value: Any, expected: str) -> bool:
    return {
        "object": isinstance(value, dict),
        "array": isinstance(value, list),
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "null": value is None,
    }.get(expected, False)


def _resolve_ref(root_schema: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        raise MetadataError(f"only local JSON Schema references are supported: {reference}")
    node: Any = root_schema
    for part in reference[2:].split("/"):
        key = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or key not in node:
            raise MetadataError(f"unresolvable JSON Schema reference: {reference}")
        node = node[key]
    if not isinstance(node, dict):
        raise MetadataError(f"JSON Schema reference is not an object: {reference}")
    return node


def _format_is_valid(value: str, format_name: str) -> bool:
    try:
        if format_name == "date":
            if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
                return False
            date.fromisoformat(value)
            return True
        if format_name == "date-time":
            if "T" not in value:
                return False
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.tzinfo is not None
        if format_name == "uri":
            return bool(urlparse(value).scheme)
    except ValueError:
        return False
    return True


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _normalize_sort_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def _normalized_phrase_present(haystack: Any, needle: Any) -> bool:
    normalized_haystack = _normalize_sort_text(haystack)
    normalized_needle = _normalize_sort_text(needle)
    if not normalized_haystack or not normalized_needle:
        return False
    return f" {normalized_needle} " in f" {normalized_haystack} "


def _safe_public_http_url_error(value: Any) -> str | None:
    """Return a reason when a purported public locator is unsafe or credential-bearing."""

    if not isinstance(value, str) or not value:
        return "must be a nonempty HTTP(S) public URL"
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "must use http or https and include a hostname"
    if parsed.username is not None or parsed.password is not None:
        return "must not embed user information or credentials"
    hostname = parsed.hostname.casefold().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        return "must not identify a local-only host"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        return "must not identify a private, loopback, reserved, or link-local address"
    for key, _ in parse_qsl(parsed.query, keep_blank_values=True):
        normalized_key = key.casefold().replace("-", "_")
        if normalized_key in _SENSITIVE_QUERY_KEYS:
            return f"must not contain credential-like query parameter {key!r}"
    if re.search(
        r"(?:api[_-]?key|access[_-]?token|session[_-]?id|password|authorization|signature|sig)=",
        value,
        flags=re.IGNORECASE,
    ):
        return "must not contain credential-like query parameters"
    return None


def _query_neutrality_errors(
    query: Mapping[str, Any],
    retrieval_log: Mapping[str, Any],
    path: str,
) -> list[str]:
    """Validate typed bibliographic components and reject untyped/thematic hooks."""

    errors: list[str] = []
    components = query.get("query_components")
    if not isinstance(components, dict):
        return errors
    title_value = components.get("title_value")
    title_variant = components.get("title_variant")
    release_title = retrieval_log.get("film_title")
    alternate_titles = retrieval_log.get("alternate_titles", [])
    if title_variant == "release_title" and title_value != release_title:
        errors.append(f"{path}.query_components.title_value: must equal the frozen release title")
    elif title_variant == "alternate_title" and title_value not in alternate_titles:
        errors.append(
            f"{path}.query_components.title_value: alternate title is absent from retrieval_log.alternate_titles"
        )
    elif title_variant == "ocr_relaxed_title":
        allowed_title_tokens: set[str] = set()
        for title in [release_title, *alternate_titles]:
            allowed_title_tokens.update(_normalize_sort_text(title).split())
        relaxed_tokens = set(_normalize_sort_text(title_value).split())
        if not relaxed_tokens or not relaxed_tokens.issubset(allowed_title_tokens):
            errors.append(
                f"{path}.query_components.title_value: OCR relaxation may use only frozen title tokens"
            )
        if not components.get("ocr_relaxation_reason"):
            errors.append(
                f"{path}.query_components.ocr_relaxation_reason: required for an OCR-relaxed query"
            )
    elif components.get("ocr_relaxation_reason") is not None:
        errors.append(
            f"{path}.query_components.ocr_relaxation_reason: allowed only for an OCR-relaxed title"
        )

    director_value = components.get("director_value")
    film_director = retrieval_log.get("film_director")
    if director_value is not None:
        normalized_director = _normalize_sort_text(director_value)
        frozen_director = _normalize_sort_text(film_director)
        if not normalized_director or normalized_director not in {
            frozen_director,
            frozen_director.split()[-1] if frozen_director else "",
        }:
            errors.append(
                f"{path}.query_components.director_value: must be the frozen director name or surname"
            )

    anchor = retrieval_log.get("release_date_anchor")
    anchor_year = None
    if isinstance(anchor, dict) and isinstance(anchor.get("date"), str):
        try:
            anchor_year = date.fromisoformat(anchor["date"]).year
        except ValueError:
            pass
    if components.get("release_year") is not None and components.get("release_year") != anchor_year:
        errors.append(
            f"{path}.query_components.release_year: must equal the frozen release-anchor year"
        )

    template_id = query.get("query_template_id")
    slot = query.get("slot")
    if isinstance(template_id, str):
        if template_id.startswith("scholarship_") and slot != "S_ACADEMIC":
            errors.append(f"{path}.query_template_id: scholarship template requires S_ACADEMIC")
        if template_id.startswith("synopsis_") and slot != "P_SYNOPSIS":
            errors.append(f"{path}.query_template_id: synopsis template requires P_SYNOPSIS")
        if "alternate" in template_id and title_variant != "alternate_title":
            errors.append(f"{path}.query_template_id: alternate-title template requires alternate_title")
        if template_id == "ocr_relaxed_title_director" and title_variant != "ocr_relaxed_title":
            errors.append(f"{path}.query_template_id: OCR template requires ocr_relaxed_title")
        director_templates = {
            "title_director",
            "alternate_title_director",
            "scholarship_title_director",
            "scholarship_alternate_director",
            "synopsis_title_director",
            "ocr_relaxed_title_director",
        }
        medium_templates = {
            "title_medium_document",
            "alternate_title_medium_document",
            "scholarship_title_medium",
            "scholarship_alternate_medium",
        }
        medium_terms = components.get("medium_terms", [])
        document_terms = components.get("document_terms", [])
        if template_id in director_templates and director_value is None:
            errors.append(f"{path}.query_components.director_value: required by query template")
        normalized_title_length = len(_normalize_sort_text(title_value).replace(" ", ""))
        short_title_requires_disambiguation = 0 < normalized_title_length <= 3
        if (
            template_id not in director_templates
            and director_value is not None
            and not short_title_requires_disambiguation
        ):
            errors.append(f"{path}.query_components.director_value: not allowed by query template")
        if template_id in medium_templates and not medium_terms:
            errors.append(f"{path}.query_components.medium_terms: required by query template")
        if template_id not in medium_templates and medium_terms:
            errors.append(f"{path}.query_components.medium_terms: not allowed by query template")
        if template_id in {"title_medium_document", "alternate_title_medium_document"}:
            allowed_documents = (
                {"review"}
                if slot in {"C_TRADE", "C_GENERAL"}
                else {"essay", "criticism", "analysis"}
            )
            if not document_terms or not set(document_terms).issubset(allowed_documents):
                errors.append(
                    f"{path}.query_components.document_terms: incompatible with slot and query template"
                )
        elif document_terms:
            errors.append(f"{path}.query_components.document_terms: not allowed by query template")
        if slot != "S_ACADEMIC" and components.get("field_scopes"):
            errors.append(f"{path}.query_components.field_scopes: allowed only for scholarship")

    site_domain = components.get("site_domain")
    if site_domain is not None:
        reason = _safe_public_http_url_error(f"https://{site_domain}/")
        if reason:
            errors.append(f"{path}.query_components.site_domain: {reason}")
        if query.get("access_route") != "open_web":
            errors.append(f"{path}.query_components.site_domain: allowed only for open_web queries")

    exact_query = query.get("exact_query")
    if isinstance(exact_query, str):
        if not _normalized_phrase_present(exact_query, title_value):
            errors.append(
                f"{path}.exact_query: must contain the declared title_value"
            )
        if director_value is not None and not _normalized_phrase_present(
            exact_query, director_value
        ):
            errors.append(
                f"{path}.exact_query: must contain the declared director_value"
            )
        release_year = components.get("release_year")
        if release_year is not None and str(release_year) not in exact_query:
            errors.append(
                f"{path}.exact_query: must contain the declared release_year"
            )
        for term in [*components.get("medium_terms", []), *components.get("document_terms", [])]:
            if not _normalized_phrase_present(exact_query, term):
                errors.append(
                    f"{path}.exact_query: must contain declared neutral term {term!r}"
                )
        if site_domain is not None and site_domain.casefold() not in exact_query.casefold():
            errors.append(
                f"{path}.exact_query: must contain the declared site_domain"
            )
        residual = exact_query.casefold()
        removals = [title_value, director_value, site_domain]
        for item in removals:
            if isinstance(item, str) and item:
                residual = re.sub(re.escape(item.casefold()), " ", residual)
        tokens = re.findall(r"[^\W\d_]+", residual, flags=re.UNICODE)
        theme_tokens = sorted(set(tokens) & _THEME_QUERY_TERMS)
        if theme_tokens:
            errors.append(
                f"{path}.exact_query: contains prohibited theme term(s): {', '.join(theme_tokens)}"
            )
        unknown_tokens = sorted(set(tokens) - _ALLOWED_QUERY_WORDS)
        if unknown_tokens:
            errors.append(
                f"{path}.exact_query: contains untyped non-bibliographic term(s): {', '.join(unknown_tokens)}"
            )

    for filter_index, query_filter in enumerate(query.get("filters", [])):
        if not isinstance(query_filter, dict):
            continue
        filter_path = f"{path}.filters[{filter_index}]"
        name = query_filter.get("name")
        value = query_filter.get("value")
        if not isinstance(value, str):
            continue
        if name in {"full_text", "peer_reviewed"} and value.casefold() not in {"true", "false"}:
            errors.append(f"{filter_path}.value: must be true or false")
        filter_tokens = set(
            re.findall(
                r"[^\W\d_]+",
                unicodedata.normalize("NFKC", value).casefold(),
                flags=re.UNICODE,
            )
        )
        theme_tokens = sorted(filter_tokens & _THEME_QUERY_TERMS)
        if theme_tokens:
            errors.append(
                f"{filter_path}.value: contains prohibited theme term(s): {', '.join(theme_tokens)}"
            )
        if name == "publication_date" and re.fullmatch(
            r"[0-9TtZz:+./ -]+(?:\s+(?:to|through)\s+[0-9TtZz:+./ -]+)?",
            value,
            flags=re.IGNORECASE,
        ) is None:
            errors.append(f"{filter_path}.value: must contain only a neutral date or date range")
        if name == "language" and re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", value) is None:
            errors.append(f"{filter_path}.value: must be a language tag")
        if name == "document_type":
            filter_tokens = set(re.findall(r"[^\W\d_]+", value.casefold(), flags=re.UNICODE))
            if not filter_tokens or not filter_tokens.issubset(_ALLOWED_QUERY_WORDS):
                errors.append(f"{filter_path}.value: contains a non-neutral document term")

    disambiguation_flags = retrieval_log.get("identity_disambiguation_flags", [])
    normalized_title = _normalize_sort_text(title_value).replace(" ", "")
    if (0 < len(normalized_title) <= 3) or bool(disambiguation_flags):
        if director_value is None or components.get("release_year") is None:
            errors.append(
                f"{path}.query_components: identity-disambiguated titles require director_value and release_year"
            )
    return errors


def _schema_errors(
    value: Any,
    schema: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    path: str,
) -> list[str]:
    """Validate the JSON Schema 2020-12 subset used by this repository."""

    errors: list[str] = []
    if "$ref" in schema:
        return _schema_errors(value, _resolve_ref(root_schema, schema["$ref"]), root_schema, path)

    expected = schema.get("type")
    if expected is not None:
        allowed_types = [expected] if isinstance(expected, str) else expected
        if not any(_matches_type(value, item) for item in allowed_types):
            errors.append(f"{path}: expected type {allowed_types}, got {type(value).__name__}")
            return errors

    if "const" in schema and not _json_equal(value, schema["const"]):
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and not any(_json_equal(value, item) for item in schema["enum"]):
        errors.append(f"{path}: value {value!r} is not in the allowed enumeration")

    for sub_schema in schema.get("allOf", []):
        errors.extend(_schema_errors(value, sub_schema, root_schema, path))
    if "if" in schema:
        condition_met = not _schema_errors(value, schema["if"], root_schema, path)
        branch = schema.get("then") if condition_met else schema.get("else")
        if branch is not None:
            errors.extend(_schema_errors(value, branch, root_schema, path))

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{_join_path(path, key)}: required field is missing")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(properties)):
                errors.append(f"{_join_path(path, key)}: unexpected field")
        for key, sub_value in value.items():
            if key in properties:
                errors.extend(
                    _schema_errors(
                        sub_value,
                        properties[key],
                        root_schema,
                        _join_path(path, key),
                    )
                )

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: requires at least {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: permits at most {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            markers = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(markers) != len(set(markers)):
                errors.append(f"{path}: array items must be unique")
        if "items" in schema:
            for index, item in enumerate(value):
                errors.extend(
                    _schema_errors(item, schema["items"], root_schema, _join_path(path, index))
                )

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: string is shorter than {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: string is longer than {schema['maxLength']} characters")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{path}: string does not match required pattern")
        if "format" in schema and not _format_is_valid(value, schema["format"]):
            errors.append(f"{path}: invalid {schema['format']} value")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: value is below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: value exceeds maximum {schema['maximum']}")

    return errors


def _forbidden_field_errors(value: Any, path: str = "$meta") -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = key.casefold().replace("-", "_")
            item_path = _join_path(path, key)
            if normalized in _FORBIDDEN_SECRET_KEYS:
                errors.append(f"{item_path}: credential or secret fields are forbidden")
            if normalized in _FORBIDDEN_SOURCE_TEXT_KEYS:
                errors.append(f"{item_path}: source full-text fields are forbidden")
            errors.extend(_forbidden_field_errors(item, item_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_forbidden_field_errors(item, _join_path(path, index)))
    return errors


def _forbidden_value_errors(value: Any, path: str = "$meta") -> list[str]:
    """Reject high-confidence credential and source-text paste signatures in free text."""

    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            errors.extend(_forbidden_value_errors(item, _join_path(path, key)))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_forbidden_value_errors(item, _join_path(path, index)))
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in _SENSITIVE_VALUE_PATTERNS):
            errors.append(f"{path}: credential-like value is forbidden in public metadata")
        if _SOURCE_TEXT_PASTE_PATTERN.search(value):
            errors.append(f"{path}: source-text paste marker is forbidden in public metadata")
    return errors


def _validate_against_schema(value: Mapping[str, Any], filename: str, label: str) -> list[str]:
    schema = _load_schema(filename)
    return (
        _forbidden_field_errors(value, label)
        + _forbidden_value_errors(value, label)
        + _schema_errors(value, schema, schema, label)
    )


def _duplicates(values: Iterable[tuple[str, Any]]) -> list[tuple[str, list[str]]]:
    grouped: dict[Any, list[str]] = {}
    for label, value in values:
        if value is None:
            continue
        marker = value.casefold().strip() if isinstance(value, str) else value
        grouped.setdefault(marker, []).append(label)
    return [(str(value), labels) for value, labels in grouped.items() if len(labels) > 1]


def validate_archive_access_manifest(manifest: Mapping[str, Any]) -> tuple[str, ...]:
    """Validate one archive access manifest, without reading any credentials."""

    errors = _validate_against_schema(
        manifest, "archive-access-manifest.schema.json", "manifest"
    )
    environments = manifest.get("extraction_environments", [])
    resources = manifest.get("resources", [])
    source_inventory = manifest.get("source_system_inventory", [])
    hierarchy = manifest.get("search_hierarchy", [])
    if (
        not isinstance(environments, list)
        or not isinstance(resources, list)
        or not isinstance(source_inventory, list)
        or not isinstance(hierarchy, list)
    ):
        return tuple(errors)

    env_ids = [item.get("environment_id") for item in environments if isinstance(item, dict)]
    resource_ids = [item.get("resource_id") for item in resources if isinstance(item, dict)]
    for _, labels in _duplicates((str(index), value) for index, value in enumerate(env_ids)):
        errors.append(f"manifest.extraction_environments: duplicate environment_id at {labels}")
    for _, labels in _duplicates((str(index), value) for index, value in enumerate(resource_ids)):
        errors.append(f"manifest.resources: duplicate resource_id at {labels}")

    known_envs = {item for item in env_ids if isinstance(item, str)}
    resource_by_id = {
        item["resource_id"]: item
        for item in resources
        if isinstance(item, dict) and isinstance(item.get("resource_id"), str)
    }
    manifest_frozen = _parse_datetime(manifest.get("frozen_at_utc"))
    for index, resource in enumerate(resources):
        if not isinstance(resource, dict):
            continue
        path = f"manifest.resources[{index}]"
        allowed = resource.get("allowed_environment_ids", [])
        if isinstance(allowed, list):
            for environment_id in allowed:
                if environment_id not in known_envs:
                    errors.append(f"{path}.allowed_environment_ids: unknown {environment_id!r}")
        permission = resource.get("model_processing_permission")
        if permission in {"allowed", "restricted"} and not allowed:
            errors.append(
                f"{path}.allowed_environment_ids: at least one environment is required "
                f"when model processing is {permission}"
            )
        if permission in {"prohibited", "unknown"} and allowed:
            errors.append(
                f"{path}.allowed_environment_ids: must be empty when model processing is {permission}"
            )
        for url_index, url in enumerate(resource.get("documentation_urls", [])):
            reason = _safe_public_http_url_error(url)
            if reason:
                errors.append(f"{path}.documentation_urls[{url_index}]: {reason}")
        rights_ids: set[str] = set()
        for reference_index, reference in enumerate(resource.get("rights_references", [])):
            if not isinstance(reference, dict):
                continue
            reference_path = f"{path}.rights_references[{reference_index}]"
            reference_id = reference.get("rights_reference_id")
            if isinstance(reference_id, str):
                if reference_id in rights_ids:
                    errors.append(f"{reference_path}.rights_reference_id: duplicate within resource")
                rights_ids.add(reference_id)
            public_url = reference.get("public_url")
            if public_url is not None:
                reason = _safe_public_http_url_error(public_url)
                if reason:
                    errors.append(f"{reference_path}.public_url: {reason}")
            reviewed_at = _parse_date(reference.get("reviewed_at"))
            if manifest_frozen is not None and reviewed_at is not None:
                if reviewed_at > manifest_frozen.date():
                    errors.append(
                        f"{reference_path}.reviewed_at: rights review cannot postdate manifest freeze"
                    )
        license_reviewed = _parse_date(resource.get("license_reviewed_at"))
        if manifest_frozen is not None and license_reviewed is not None:
            if license_reviewed > manifest_frozen.date():
                errors.append(f"{path}.license_reviewed_at: cannot postdate manifest freeze")
        retention_deadline = _parse_date(resource.get("retention_deadline"))
        if (
            resource.get("access_status") == "available"
            and manifest_frozen is not None
            and retention_deadline is not None
            and retention_deadline < manifest_frozen.date()
        ):
            errors.append(f"{path}.retention_deadline: available resource was already expired")

    expected_inventory_pairs = {
        (slot, system_code)
        for slot, system_rules in SOURCE_SYSTEM_RULES.items()
        for system_code in system_rules
    }
    inventory_by_pair: dict[tuple[str, str], Mapping[str, Any]] = {}
    inventory_ids: set[str] = set()
    interval_ids: set[str] = set()
    for index, entry in enumerate(source_inventory):
        if not isinstance(entry, dict):
            continue
        path = f"manifest.source_system_inventory[{index}]"
        entry_id = entry.get("inventory_entry_id")
        if isinstance(entry_id, str):
            if entry_id in inventory_ids:
                errors.append(f"{path}.inventory_entry_id: duplicate inventory entry")
            inventory_ids.add(entry_id)
        slot = entry.get("slot")
        system_code = entry.get("source_system_code")
        pair = (str(slot), str(system_code))
        if pair in inventory_by_pair:
            errors.append(
                f"{path}: duplicate coverage/access disposition for slot/system {pair!r}"
            )
        else:
            inventory_by_pair[pair] = entry
        expected_order = SOURCE_SYSTEM_RULES.get(str(slot), {}).get(str(system_code))
        if expected_order is None:
            errors.append(
                f"{path}.source_system_code: {system_code!r} is not in the frozen hierarchy for {slot!r}"
            )
        elif expected_order != (entry.get("system_tier"), entry.get("system_rank")):
            errors.append(
                f"{path}: source_system_code {system_code!r} requires system_tier/system_rank "
                f"{expected_order}, not {(entry.get('system_tier'), entry.get('system_rank'))}"
            )
        expected_name = SOURCE_SYSTEM_DISPLAY_NAMES.get(str(system_code))
        if expected_name is not None and _normalize_sort_text(
            entry.get("source_system_name")
        ) != _normalize_sort_text(expected_name):
            errors.append(
                f"{path}.source_system_name: source_system_code {system_code!r} requires {expected_name!r}"
            )

        checked_at = _parse_date(entry.get("checked_at"))
        if manifest_frozen is not None and checked_at is not None:
            if checked_at > manifest_frozen.date():
                errors.append(f"{path}.checked_at: cannot postdate manifest freeze")

        assessed_ids = entry.get("assessed_resource_ids", [])
        if not isinstance(assessed_ids, list):
            assessed_ids = []
        assessed_resources: list[Mapping[str, Any]] = []
        for resource_id in assessed_ids:
            resource = resource_by_id.get(resource_id)
            if resource is None:
                errors.append(
                    f"{path}.assessed_resource_ids: unknown resource {resource_id!r}"
                )
                continue
            assessed_resources.append(resource)
            if slot not in resource.get("supported_slots", []):
                errors.append(
                    f"{path}.assessed_resource_ids: resource {resource_id!r} does not support slot {slot!r}"
                )

        access_disposition = entry.get("access_disposition")
        assessed_statuses = {item.get("access_status") for item in assessed_resources}
        if access_disposition == "available" and "available" not in assessed_statuses:
            errors.append(
                f"{path}.access_disposition: available requires an assessed resource frozen as available"
            )
        elif access_disposition == "pending" and "pending" not in assessed_statuses:
            errors.append(
                f"{path}.access_disposition: pending requires an assessed resource frozen as pending"
            )
        elif access_disposition == "unavailable" and assessed_statuses & {
            "available",
            "pending",
        }:
            errors.append(
                f"{path}.access_disposition: unavailable conflicts with an assessed available or pending resource"
            )

        coverage_disposition = entry.get("coverage_disposition")
        intervals = entry.get("coverage_intervals", [])
        if not isinstance(intervals, list):
            intervals = []
        reason = entry.get("disposition_reason")
        if coverage_disposition == "documented_intervals" and not intervals:
            errors.append(
                f"{path}.coverage_intervals: documented_intervals requires at least one interval"
            )
        if coverage_disposition in {"no_coverage", "not_verified"} and intervals:
            errors.append(
                f"{path}.coverage_intervals: {coverage_disposition} must not claim coverage intervals"
            )
        if (
            access_disposition != "available"
            or coverage_disposition in {"no_coverage", "not_verified"}
        ) and (not isinstance(reason, str) or not reason.strip()):
            errors.append(
                f"{path}.disposition_reason: unavailable, pending, no-coverage, and unverified dispositions require a documented reason"
            )

        expected_dimension = (
            "film_release_date"
            if slot == "P_SYNOPSIS"
            else "source_publication_or_issue_date"
        )
        interval_resource_ids: set[str] = set()
        for interval_index, interval in enumerate(intervals):
            if not isinstance(interval, dict):
                continue
            interval_path = f"{path}.coverage_intervals[{interval_index}]"
            interval_id = interval.get("coverage_interval_id")
            if isinstance(interval_id, str):
                if interval_id in interval_ids:
                    errors.append(
                        f"{interval_path}.coverage_interval_id: duplicate coverage interval"
                    )
                interval_ids.add(interval_id)
            if interval.get("date_dimension") != expected_dimension:
                errors.append(
                    f"{interval_path}.date_dimension: slot {slot} requires {expected_dimension!r}"
                )
            start = _parse_date(interval.get("start_date"))
            end = _parse_date(interval.get("end_date"))
            if start is not None and end is not None and start > end:
                errors.append(f"{interval_path}: start_date must not follow end_date")
            interval_resource_id = interval.get("resource_id")
            if isinstance(interval_resource_id, str):
                interval_resource_ids.add(interval_resource_id)
                if interval_resource_id not in assessed_ids:
                    errors.append(
                        f"{interval_path}.resource_id: must be listed in assessed_resource_ids"
                    )
                if interval_resource_id not in resource_by_id:
                    errors.append(
                        f"{interval_path}.resource_id: unknown resource {interval_resource_id!r}"
                    )
            start_issue = interval.get("start_issue")
            end_issue = interval.get("end_issue")
            if (start_issue is None) != (end_issue is None):
                errors.append(
                    f"{interval_path}: start_issue and end_issue must both be supplied or both be null"
                )
            documentation_url = interval.get("documentation_url")
            if documentation_url is not None:
                url_reason = _safe_public_http_url_error(documentation_url)
                if url_reason:
                    errors.append(f"{interval_path}.documentation_url: {url_reason}")
            interval_checked = _parse_date(interval.get("checked_at"))
            if manifest_frozen is not None and interval_checked is not None:
                if interval_checked > manifest_frozen.date():
                    errors.append(
                        f"{interval_path}.checked_at: cannot postdate manifest freeze"
                    )
            if interval_checked is not None and end is not None and end > interval_checked:
                errors.append(
                    f"{interval_path}.end_date: documented coverage cannot extend beyond checked_at"
                )
            if (
                checked_at is not None
                and interval_checked is not None
                and interval_checked > checked_at
            ):
                errors.append(
                    f"{interval_path}.checked_at: cannot postdate its inventory disposition check"
                )
        if access_disposition == "available" and coverage_disposition == "documented_intervals":
            available_interval_resources = {
                resource_id
                for resource_id in interval_resource_ids
                if resource_by_id.get(resource_id, {}).get("access_status") == "available"
            }
            if not available_interval_resources:
                errors.append(
                    f"{path}: available documented coverage requires an interval on an available resource"
                )

    actual_inventory_pairs = set(inventory_by_pair)
    for slot, system_code in sorted(expected_inventory_pairs - actual_inventory_pairs):
        errors.append(
            "manifest.source_system_inventory: missing explicit coverage/access "
            f"disposition for {slot}/{system_code}"
        )
    for slot, system_code in sorted(actual_inventory_pairs - expected_inventory_pairs):
        errors.append(
            "manifest.source_system_inventory: unexpected coverage/access "
            f"disposition for {slot}/{system_code}"
        )

    step_ids: set[str] = set()
    coordinates: set[tuple[Any, Any, Any, Any]] = set()
    system_metadata: dict[tuple[Any, Any], tuple[Any, Any]] = {}
    for index, step in enumerate(hierarchy):
        if not isinstance(step, dict):
            continue
        path = f"manifest.search_hierarchy[{index}]"
        step_id = step.get("hierarchy_step_id")
        if isinstance(step_id, str):
            if step_id in step_ids:
                errors.append(f"{path}.hierarchy_step_id: duplicate hierarchy step")
            step_ids.add(step_id)
        slot = step.get("slot")
        system_code = step.get("source_system_code")
        inventory_entry = inventory_by_pair.get((str(slot), str(system_code)))
        if inventory_entry is None:
            errors.append(
                f"{path}: hierarchy route lacks a source-system inventory disposition"
            )
        else:
            if inventory_entry.get("access_disposition") != "available":
                errors.append(
                    f"{path}: hierarchy route requires an available inventory access disposition"
                )
            if inventory_entry.get("coverage_disposition") != "documented_intervals":
                errors.append(
                    f"{path}: hierarchy route requires documented coverage intervals"
                )
        slot_rules = SOURCE_SYSTEM_RULES.get(str(slot), {})
        expected_order = slot_rules.get(str(system_code))
        if expected_order is None:
            errors.append(
                f"{path}.source_system_code: {system_code!r} is not in the frozen hierarchy for {slot!r}"
            )
        elif expected_order != (step.get("system_tier"), step.get("system_rank")):
            errors.append(
                f"{path}: source_system_code {system_code!r} requires system_tier/system_rank "
                f"{expected_order}, not {(step.get('system_tier'), step.get('system_rank'))}"
            )
        expected_name = SOURCE_SYSTEM_DISPLAY_NAMES.get(str(system_code))
        if expected_name is not None and _normalize_sort_text(step.get("source_system_name")) != _normalize_sort_text(expected_name):
            errors.append(
                f"{path}.source_system_name: source_system_code {system_code!r} requires {expected_name!r}"
            )
        coordinate = (
            slot,
            step.get("system_tier"),
            step.get("system_rank"),
            step.get("route_rank"),
        )
        if coordinate in coordinates:
            errors.append(f"{path}: duplicate slot/tier/system_rank/route_rank coordinate")
        coordinates.add(coordinate)
        system_key = (slot, step.get("source_system_id"))
        system_value = (
            step.get("source_system_code"),
            step.get("system_tier"),
            step.get("system_rank"),
        )
        prior_value = system_metadata.get(system_key)
        if prior_value is not None and prior_value != system_value:
            errors.append(f"{path}: one source system must keep one tier and system rank")
        system_metadata[system_key] = system_value
        resource_id = step.get("resource_id")
        resource = resource_by_id.get(resource_id)
        if resource is None:
            errors.append(f"{path}.resource_id: unknown resource {resource_id!r}")
        elif slot not in resource.get("supported_slots", []):
            errors.append(f"{path}: resource does not declare support for slot {slot!r}")
        elif resource.get("access_status") != "available":
            errors.append(
                f"{path}.resource_id: search hierarchy may contain only resources frozen as available"
            )
        if inventory_entry is not None:
            covered_resources = {
                interval.get("resource_id")
                for interval in inventory_entry.get("coverage_intervals", [])
                if isinstance(interval, dict)
            }
            if resource_id not in covered_resources:
                errors.append(
                    f"{path}.resource_id: hierarchy route has no documented coverage interval"
                )

    hierarchy_resources_by_pair: dict[tuple[str, str], set[Any]] = {}
    for step in hierarchy:
        if not isinstance(step, dict):
            continue
        pair = (str(step.get("slot")), str(step.get("source_system_code")))
        hierarchy_resources_by_pair.setdefault(pair, set()).add(step.get("resource_id"))
    for pair, inventory_entry in inventory_by_pair.items():
        if (
            inventory_entry.get("access_disposition") != "available"
            or inventory_entry.get("coverage_disposition") != "documented_intervals"
        ):
            continue
        expected_route_resources = {
            interval.get("resource_id")
            for interval in inventory_entry.get("coverage_intervals", [])
            if isinstance(interval, dict)
            and resource_by_id.get(interval.get("resource_id"), {}).get("access_status")
            == "available"
        }
        missing_route_resources = expected_route_resources - hierarchy_resources_by_pair.get(
            pair, set()
        )
        if missing_route_resources:
            errors.append(
                "manifest.search_hierarchy: documented available coverage for "
                f"{pair[0]}/{pair[1]} lacks route(s) for {sorted(missing_route_resources)}"
            )
    return tuple(errors)


def _selected_candidate_errors(candidate: Mapping[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    nonempty_fields = (
        "source_id",
        "lineage_id",
        "article_title",
        "author_display",
        "author_id",
        "outlet",
        "publication_date",
        "publisher",
        "language",
        "normalized_text_sha256",
    )
    for field in nonempty_fields:
        if candidate.get(field) is None or candidate.get(field) == "":
            errors.append(f"{path}.{field}: selected candidate requires a resolved value")
    if candidate.get("publication_date_precision") == "unknown":
        errors.append(f"{path}.publication_date_precision: selected candidate cannot be unknown")
    if candidate.get("sampled_film_identity_verified") is not True:
        errors.append(f"{path}.sampled_film_identity_verified: must be true when selected")
    slot = candidate.get("slot")
    expected_extraction_type = SLOT_EXTRACTION_SOURCE_TYPES.get(str(slot))
    if expected_extraction_type and candidate.get("extraction_source_type") != expected_extraction_type:
        errors.append(
            f"{path}.extraction_source_type: slot {slot} must map to extraction SourceType "
            f"{expected_extraction_type!r}"
        )
    language_basis = candidate.get("language_basis")
    language = candidate.get("language")
    original_language = candidate.get("original_language")
    translation_reference = candidate.get("translation_reference")
    if language_basis == "original_english":
        if not isinstance(language, str) or not language.casefold().startswith("en"):
            errors.append(f"{path}.language: original-English source must use an English language tag")
        if original_language is not None or translation_reference is not None:
            errors.append(
                f"{path}: original-English source must not declare translation metadata"
            )
    elif language_basis == "authorized_published_english_translation":
        if not isinstance(language, str) or not language.casefold().startswith("en"):
            errors.append(f"{path}.language: authorized translation used for extraction must be English")
        if not isinstance(original_language, str) or original_language.casefold().startswith("en"):
            errors.append(
                f"{path}.original_language: authorized English translation requires a non-English original"
            )
        if not isinstance(translation_reference, dict):
            errors.append(
                f"{path}.translation_reference: authorized published translation requires a reference"
            )
    else:
        errors.append(
            f"{path}.language_basis: selected candidate must be original English or an authorized published English translation"
        )
    identifiers = (
        candidate.get("doi_or_isbn"),
        candidate.get("database_document_id"),
        candidate.get("canonical_url"),
        candidate.get("permalink_or_archive_locator"),
    )
    if not any(isinstance(value, str) and value.strip() for value in identifiers):
        errors.append(f"{path}: selected candidate requires at least one stable identifier")
    if candidate.get("acquisition_status") not in {
        "complete_source_authorized",
        "provider_workbench_only",
    }:
        errors.append(f"{path}.acquisition_status: selected candidate lacks authorized complete text")
    if candidate.get("source_completeness_verified") is not True:
        errors.append(f"{path}.source_completeness_verified: must be true when selected")
    if candidate.get("rights_class") not in INCLUDABLE_RIGHTS_CLASSES:
        errors.append(f"{path}.rights_class: selected candidate has no includable rights class")
    permission = candidate.get("processing_permission")
    if not isinstance(permission, dict) or permission.get("status") != "allowed":
        errors.append(f"{path}.processing_permission: selected candidate must be explicitly allowed")
    elif not permission.get("rights_reference_ids"):
        errors.append(
            f"{path}.processing_permission.rights_reference_ids: selected candidate requires structured rights references"
        )
    canonical_url = candidate.get("canonical_url")
    if canonical_url is not None:
        reason = _safe_public_http_url_error(canonical_url)
        if reason:
            errors.append(f"{path}.canonical_url: {reason}")
    translation_reference = candidate.get("translation_reference")
    if isinstance(translation_reference, dict) and translation_reference.get("public_url") is not None:
        reason = _safe_public_http_url_error(translation_reference.get("public_url"))
        if reason:
            errors.append(f"{path}.translation_reference.public_url: {reason}")
    return errors


def _publication_date_matches_precision(value: Any, precision: Any) -> bool:
    if value is None and precision == "unknown":
        return True
    if not isinstance(value, str):
        return False
    try:
        if precision == "day" and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
            date.fromisoformat(value)
            return True
        if precision == "month" and re.fullmatch(r"[0-9]{4}-[0-9]{2}", value):
            year, month = (int(part) for part in value.split("-"))
            return 1 <= year <= 9999 and 1 <= month <= 12
        if precision == "year" and re.fullmatch(r"[0-9]{4}", value):
            return 1 <= int(value) <= 9999
    except ValueError:
        return False
    return False


def _publication_date_interval(value: Any, precision: Any) -> tuple[date, date] | None:
    """Expand an honestly recorded partial date to its complete possible interval."""

    if not _publication_date_matches_precision(value, precision) or not isinstance(value, str):
        return None
    if precision == "day":
        parsed = date.fromisoformat(value)
        return parsed, parsed
    if precision == "month":
        year, month = (int(part) for part in value.split("-"))
        return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])
    if precision == "year":
        year = int(value)
        return date(year, 1, 1), date(year, 12, 31)
    return None


def _date_window_status(slot: Any, interval: tuple[date, date] | None, anchor: date) -> str:
    if slot == "P_SYNOPSIS":
        return "not_applicable"
    if interval is None:
        return "unresolved"
    earliest, latest = interval
    if slot in {"C_TRADE", "C_GENERAL"}:
        lower = anchor - timedelta(days=30)
        upper = anchor + timedelta(days=365)
        if earliest >= lower and latest <= upper:
            return "eligible"
        if latest < lower or earliest > upper:
            return "outside"
        return "ambiguous"
    if slot in {"R_LATER", "R_LATER_2"}:
        lower = anchor + timedelta(days=730)
        if earliest >= lower:
            return "eligible"
        if latest < lower:
            return "outside"
        return "ambiguous"
    if slot == "S_ACADEMIC":
        if earliest >= anchor:
            return "eligible"
        if latest < anchor:
            return "outside"
        return "ambiguous"
    return "unresolved"


def _eligible_length_errors(candidate: Mapping[str, Any], path: str) -> list[str]:
    """Apply the frozen, slot-specific substantive-length rules."""

    errors: list[str] = []
    slot = candidate.get("slot")
    total = candidate.get("word_count_total")
    relevant = candidate.get("word_count_relevant")
    pages = candidate.get("continuous_relevant_pages")
    exception = candidate.get("contemporary_short_review_exception")

    if isinstance(total, int) and isinstance(relevant, int) and relevant > total:
        errors.append(f"{path}: word_count_relevant cannot exceed word_count_total")

    if slot in {"C_TRADE", "C_GENERAL"}:
        if isinstance(relevant, int) and relevant >= 200:
            if exception is not None:
                errors.append(
                    f"{path}.contemporary_short_review_exception: allowed only for 100-199 words"
                )
        elif isinstance(relevant, int) and 100 <= relevant <= 199:
            required_true = (
                "provider_labels_item_as_review",
                "complete_editorial_item_verified",
                "declared_before_theme_extraction",
            )
            if not isinstance(exception, dict) or not all(
                exception.get(field) is True for field in required_true
            ) or not isinstance(exception.get("documentation"), str) or not exception["documentation"].strip():
                errors.append(
                    f"{path}: a 100-199 word contemporary review requires the documented short-review exception"
                )
        else:
            errors.append(f"{path}.word_count_relevant: contemporary review must contain at least 100 words")
    elif slot in {"R_LATER", "R_LATER_2"}:
        if not isinstance(total, int) or total < 600:
            errors.append(f"{path}.word_count_total: later essay requires at least 600 words total")
        if not isinstance(relevant, int) or relevant < 400:
            errors.append(
                f"{path}.word_count_relevant: later essay requires at least 400 relevant words"
            )
        if exception is not None:
            errors.append(f"{path}.contemporary_short_review_exception: not allowed for later essays")
    elif slot == "S_ACADEMIC":
        word_rule = isinstance(relevant, int) and relevant >= 1000
        page_rule = isinstance(pages, int) and pages >= 3
        if not (word_rule or page_rule):
            errors.append(
                f"{path}: academic source requires at least 1,000 relevant words or three continuous relevant pages"
            )
        if exception is not None:
            errors.append(f"{path}.contemporary_short_review_exception: not allowed for scholarship")
    elif slot == "P_SYNOPSIS":
        if not isinstance(relevant, int) or relevant < 300:
            errors.append(f"{path}.word_count_relevant: synopsis requires at least 300 words")
        if exception is not None:
            errors.append(f"{path}.contemporary_short_review_exception: not allowed for synopsis")
    return errors


def _obvious_exclusion_consistency_errors(
    candidate: Mapping[str, Any], path: str
) -> list[str]:
    """Reject exclusion codes contradicted by the candidate's objective metadata."""

    reason = candidate.get("exclusion_reason")
    errors: list[str] = []
    if reason == "not_about_sampled_film" and candidate.get("sampled_film_identity_verified") is not False:
        errors.append(
            f"{path}.exclusion_reason: not_about_sampled_film requires sampled_film_identity_verified=false"
        )
    elif reason == "outside_date_window" and candidate.get("date_window_status") != "outside":
        errors.append(
            f"{path}.exclusion_reason: outside_date_window requires date_window_status='outside'"
        )
    elif reason == "incomplete_text" and not (
        candidate.get("acquisition_status") in {"metadata_only", "incomplete"}
        or candidate.get("source_completeness_verified") is False
    ):
        errors.append(
            f"{path}.exclusion_reason: incomplete_text is contradicted by complete-source metadata"
        )
    elif reason == "insufficient_length" and not _eligible_length_errors(candidate, path):
        errors.append(
            f"{path}.exclusion_reason: insufficient_length is contradicted by the recorded length"
        )
    elif reason == "missing_authorship_or_date":
        required_values = (
            candidate.get("author_display"),
            candidate.get("author_id"),
            candidate.get("outlet"),
            candidate.get("publisher"),
            candidate.get("publication_date"),
        )
        if all(isinstance(value, str) and value.strip() for value in required_values):
            errors.append(
                f"{path}.exclusion_reason: missing_authorship_or_date is contradicted by resolved metadata"
            )
    elif reason == "no_processing_rights" and (
        candidate.get("rights_class") in INCLUDABLE_RIGHTS_CLASSES
        and isinstance(candidate.get("processing_permission"), dict)
        and candidate["processing_permission"].get("status") == "allowed"
    ):
        errors.append(
            f"{path}.exclusion_reason: no_processing_rights is contradicted by allowed item rights"
        )
    elif reason == "access_failure" and candidate.get("acquisition_status") != "inaccessible":
        errors.append(
            f"{path}.exclusion_reason: access_failure requires acquisition_status='inaccessible'"
        )
    return errors


def validate_source_retrieval_log(retrieval_log: Mapping[str, Any]) -> tuple[str, ...]:
    """Validate query/candidate metadata and within-log references."""

    errors = _validate_against_schema(
        retrieval_log, "source-retrieval-log.schema.json", "retrieval_log"
    )
    queries = retrieval_log.get("queries", [])
    candidates = retrieval_log.get("candidates", [])
    duplicate_checks = retrieval_log.get("duplicate_checks", [])
    if (
        not isinstance(queries, list)
        or not isinstance(candidates, list)
        or not isinstance(duplicate_checks, list)
    ):
        return tuple(errors)

    anchor: date | None = None
    anchor_record = retrieval_log.get("release_date_anchor")
    if isinstance(anchor_record, dict) and isinstance(anchor_record.get("date"), str):
        try:
            anchor = date.fromisoformat(anchor_record["date"])
        except ValueError:
            pass
    created_at = _parse_datetime(retrieval_log.get("created_at_utc"))
    disambiguation_flags = retrieval_log.get("identity_disambiguation_flags", [])
    if isinstance(disambiguation_flags, list):
        release_title_length = len(
            _normalize_sort_text(retrieval_log.get("film_title")).replace(" ", "")
        )
        if 0 < release_title_length <= 3 and "short_title" not in disambiguation_flags:
            errors.append(
                "retrieval_log.identity_disambiguation_flags: short titles require short_title"
            )
        if release_title_length > 3 and "short_title" in disambiguation_flags:
            errors.append(
                "retrieval_log.identity_disambiguation_flags: short_title contradicts the release title"
            )

    query_by_id: dict[str, Mapping[str, Any]] = {}
    query_path_by_id: dict[str, str] = {}
    queries_by_step: dict[str, list[Mapping[str, Any]]] = {}
    for index, query in enumerate(queries):
        if not isinstance(query, dict):
            continue
        query_id = query.get("query_id")
        path = f"retrieval_log.queries[{index}]"
        if isinstance(query_id, str):
            if query_id in query_by_id:
                errors.append(f"{path}.query_id: duplicate query_id {query_id!r}")
            query_by_id[query_id] = query
            query_path_by_id[query_id] = path
        step_id = query.get("hierarchy_step_id")
        if isinstance(step_id, str):
            queries_by_step.setdefault(step_id, []).append(query)
        if query.get("film_id") != retrieval_log.get("film_id"):
            errors.append(f"{path}.film_id: must match retrieval_log.film_id")
        errors.extend(_query_neutrality_errors(query, retrieval_log, path))
        query_time = _parse_datetime(query.get("query_timestamp_utc"))
        if created_at is not None and query_time is not None and query_time < created_at:
            errors.append(f"{path}.query_timestamp_utc: cannot predate retrieval-log creation")
        screened = query.get("results_screened")
        reported = query.get("result_count_reported")
        unfiltered_reported = query.get("unfiltered_result_count_reported")
        cap = query.get("screening_cap")
        expected_cap = 20 if query.get("access_route") == "open_web" else 50
        if cap != expected_cap:
            errors.append(
                f"{path}.screening_cap: must be {expected_cap} for access route {query.get('access_route')!r}"
            )
        if isinstance(screened, int) and isinstance(cap, int) and screened > cap:
            errors.append(f"{path}.results_screened: cannot exceed screening_cap")
        if isinstance(screened, int) and isinstance(reported, int):
            expected_screened = min(reported, expected_cap)
            if query.get("stop_reason") != "access_blocked" and screened != expected_screened:
                errors.append(
                    f"{path}.results_screened: must equal min(result_count_reported, screening_cap) "
                    f"({expected_screened})"
                )
        elif reported is None and query.get("stop_reason") not in {
            "access_blocked",
            "screening_cap_reached",
        }:
            errors.append(
                f"{path}.result_count_reported: null is allowed only for access_blocked or screening_cap_reached"
            )
        post_count_filter_names = {
            item.get("name")
            for item in query.get("filters", [])
            if isinstance(item, dict)
        } & {"language", "full_text", "peer_reviewed"}
        if isinstance(reported, int):
            if not isinstance(unfiltered_reported, int) or unfiltered_reported < reported:
                errors.append(
                    f"{path}.unfiltered_result_count_reported: must be an integer at least as large as result_count_reported"
                )
            elif not post_count_filter_names and unfiltered_reported != reported:
                errors.append(
                    f"{path}.unfiltered_result_count_reported: must equal result_count_reported when no post-count filter is used"
                )
        elif unfiltered_reported is not None:
            errors.append(
                f"{path}.unfiltered_result_count_reported: must be null when result_count_reported is null"
            )
        listed = query.get("candidate_ids_and_ranks", [])
        if isinstance(listed, list) and isinstance(screened, int) and len(listed) != screened:
            errors.append(
                f"{path}.candidate_ids_and_ranks: must contain exactly one record for every screened result"
            )

    candidate_by_id: dict[str, Mapping[str, Any]] = {}
    selected_by_slot: dict[str, list[str]] = {}
    candidate_path_by_id: dict[str, str] = {}
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            continue
        path = f"retrieval_log.candidates[{index}]"
        candidate_id = candidate.get("candidate_id")
        if isinstance(candidate_id, str):
            if candidate_id in candidate_by_id:
                errors.append(f"{path}.candidate_id: duplicate candidate_id {candidate_id!r}")
            candidate_by_id[candidate_id] = candidate
            candidate_path_by_id[candidate_id] = path
        if candidate.get("film_id") != retrieval_log.get("film_id"):
            errors.append(f"{path}.film_id: must match retrieval_log.film_id")
        canonical_url = candidate.get("canonical_url")
        if canonical_url is not None:
            reason_url = _safe_public_http_url_error(canonical_url)
            if reason_url:
                errors.append(f"{path}.canonical_url: {reason_url}")
        archive_locator = candidate.get("permalink_or_archive_locator")
        if isinstance(archive_locator, str) and "://" in archive_locator:
            reason_url = _safe_public_http_url_error(archive_locator)
            if reason_url:
                errors.append(f"{path}.permalink_or_archive_locator: {reason_url}")
        if not _publication_date_matches_precision(
            candidate.get("publication_date"), candidate.get("publication_date_precision")
        ):
            errors.append(
                f"{path}.publication_date: value must match publication_date_precision"
            )
        if anchor is not None:
            interval = _publication_date_interval(
                candidate.get("publication_date"), candidate.get("publication_date_precision")
            )
            expected_window_status = _date_window_status(candidate.get("slot"), interval, anchor)
            if candidate.get("date_window_status") != expected_window_status:
                errors.append(
                    f"{path}.date_window_status: must be {expected_window_status!r} for the "
                    "recorded date precision and release anchor"
                )

        status = candidate.get("selection_status")
        reason = candidate.get("exclusion_reason")
        if status == "excluded" and reason not in EXCLUSION_REASONS:
            errors.append(f"{path}.exclusion_reason: excluded candidate needs an allowed reason code")
        if status == "excluded":
            errors.extend(_obvious_exclusion_consistency_errors(candidate, path))
        if status != "excluded" and reason is not None:
            errors.append(f"{path}.exclusion_reason: only excluded candidates may have a reason")
        if reason == "other_predefined" and not candidate.get("exclusion_detail_code"):
            errors.append(f"{path}.exclusion_detail_code: required for other_predefined")
        if reason == "other_predefined" and candidate.get("exclusion_detail_code") not in OTHER_PREDEFINED_DETAIL_CODES:
            errors.append(f"{path}.exclusion_detail_code: is not a frozen other_predefined code")
        if reason != "other_predefined" and candidate.get("exclusion_detail_code") is not None:
            errors.append(f"{path}.exclusion_detail_code: only allowed for other_predefined")

        query = query_by_id.get(candidate.get("query_id"))
        if query is None:
            errors.append(f"{path}.query_id: does not reference a query in this log")
        else:
            if candidate.get("slot") != query.get("slot"):
                errors.append(f"{path}.slot: must match the originating query slot")
            if candidate.get("access_route") != query.get("access_route"):
                errors.append(f"{path}.access_route: must match the originating query")
            if candidate.get("hierarchy_step_id") != query.get("hierarchy_step_id"):
                errors.append(f"{path}.hierarchy_step_id: must match the originating query")
            accessed_at = _parse_datetime(candidate.get("accessed_at_utc"))
            query_time = _parse_datetime(query.get("query_timestamp_utc"))
            if accessed_at is not None and query_time is not None and accessed_at < query_time:
                errors.append(f"{path}.accessed_at_utc: cannot predate the originating query")
        permission = candidate.get("processing_permission")
        if isinstance(permission, dict):
            verified_at = _parse_datetime(permission.get("verified_at_utc"))
            if created_at is not None and verified_at is not None and verified_at < created_at:
                errors.append(
                    f"{path}.processing_permission.verified_at_utc: cannot predate retrieval-log creation"
                )
        translation_reference = candidate.get("translation_reference")
        if isinstance(translation_reference, dict):
            public_url = translation_reference.get("public_url")
            if public_url is not None:
                reason_url = _safe_public_http_url_error(public_url)
                if reason_url:
                    errors.append(f"{path}.translation_reference.public_url: {reason_url}")
            verified_at = _parse_datetime(translation_reference.get("verified_at_utc"))
            if created_at is not None and verified_at is not None and verified_at < created_at:
                errors.append(
                    f"{path}.translation_reference.verified_at_utc: cannot predate retrieval-log creation"
                )
        retention_deadline = _parse_date(candidate.get("retention_deadline"))
        accessed_at = _parse_datetime(candidate.get("accessed_at_utc"))
        if retention_deadline is not None and accessed_at is not None:
            if retention_deadline < accessed_at.date():
                errors.append(f"{path}.retention_deadline: source was already expired when accessed")

        if status == "selected":
            slot = candidate.get("slot")
            if isinstance(slot, str) and isinstance(candidate_id, str):
                selected_by_slot.setdefault(slot, []).append(candidate_id)
        if status in {"selected", "eligible_not_selected"}:
            errors.extend(_selected_candidate_errors(candidate, path))
            slot = candidate.get("slot")
            expected_type = SLOT_SOURCE_TYPES.get(str(slot))
            if expected_type is not None and candidate.get("source_type") != expected_type:
                errors.append(
                    f"{path}.source_type: slot {slot} requires {expected_type!r}"
                )
            expected_extraction_type = SLOT_EXTRACTION_SOURCE_TYPES.get(str(slot))
            if (
                expected_extraction_type is not None
                and candidate.get("extraction_source_type") != expected_extraction_type
            ):
                errors.append(
                    f"{path}.extraction_source_type: slot {slot} requires {expected_extraction_type!r}"
                )
            scholarly_form = candidate.get("scholarly_form")
            if slot == "S_ACADEMIC" and scholarly_form not in SCHOLARLY_FORM_PRIORITY:
                errors.append(f"{path}.scholarly_form: eligible scholarship needs a frozen form")
            if slot != "S_ACADEMIC" and scholarly_form is not None:
                errors.append(f"{path}.scholarly_form: allowed only for S_ACADEMIC")
            if slot in {"C_TRADE", "C_GENERAL"} and candidate.get("publication_date_precision") != "day":
                errors.append(
                    f"{path}.publication_date_precision: deterministic contemporary selection requires day precision"
                )
            expected_status = "not_applicable" if candidate.get("slot") == "P_SYNOPSIS" else "eligible"
            if candidate.get("date_window_status") != expected_status:
                errors.append(
                    f"{path}.date_window_status: eligible candidate must be {expected_status!r}"
                )
            if candidate.get("sampled_film_identity_verified") is not True:
                errors.append(
                    f"{path}.sampled_film_identity_verified: eligible candidate must match the sampled film"
                )
            errors.extend(_eligible_length_errors(candidate, path))
        if candidate.get("slot") == "S_ACADEMIC" and anchor is not None:
            interval = _publication_date_interval(
                candidate.get("publication_date"), candidate.get("publication_date_precision")
            )
            expected_contemporary = bool(
                interval is not None
                and interval[0] >= anchor
                and interval[1] <= anchor + timedelta(days=365)
            )
            if candidate.get("contemporary_scholarship") is not expected_contemporary:
                errors.append(
                    f"{path}.contemporary_scholarship: must be {expected_contemporary!r} for the recorded date"
                )
        elif candidate.get("contemporary_scholarship") is not False:
            errors.append(
                f"{path}.contemporary_scholarship: must be false outside S_ACADEMIC"
            )

    for slot, candidate_ids in selected_by_slot.items():
        if len(candidate_ids) > 1:
            errors.append(
                f"retrieval_log.candidates: slot {slot} has multiple selected candidates {candidate_ids}"
            )

    listed_pairs: dict[str, tuple[str, int]] = {}
    for index, query in enumerate(queries):
        if not isinstance(query, dict):
            continue
        path = f"retrieval_log.queries[{index}].candidate_ids_and_ranks"
        seen_in_query: set[str] = set()
        seen_ranks: set[int] = set()
        screened = query.get("results_screened")
        for item in query.get("candidate_ids_and_ranks", []):
            if not isinstance(item, dict):
                continue
            candidate_id = item.get("candidate_id")
            rank = item.get("rank")
            if candidate_id in seen_in_query:
                errors.append(f"{path}: duplicate candidate_id {candidate_id!r}")
            if isinstance(candidate_id, str):
                seen_in_query.add(candidate_id)
                if candidate_id not in candidate_by_id:
                    errors.append(f"{path}: unknown candidate_id {candidate_id!r}")
                if candidate_id in listed_pairs:
                    errors.append(f"{path}: candidate_id {candidate_id!r} appears in more than one query")
                listed_pairs[candidate_id] = (str(query.get("query_id")), rank)
            if isinstance(rank, int):
                if rank in seen_ranks:
                    errors.append(f"{path}: duplicate result rank {rank}")
                seen_ranks.add(rank)
                if isinstance(screened, int) and rank > screened:
                    errors.append(f"{path}: result rank {rank} exceeds results_screened")
        if isinstance(screened, int) and seen_ranks != set(range(1, screened + 1)):
            errors.append(f"{path}: result ranks must exactly cover 1 through results_screened")

    for candidate_id, candidate in candidate_by_id.items():
        listed = listed_pairs.get(candidate_id)
        path = candidate_path_by_id[candidate_id]
        if listed is None:
            errors.append(f"{path}: candidate is absent from query candidate_ids_and_ranks")
        elif listed != (candidate.get("query_id"), candidate.get("result_rank")):
            errors.append(f"{path}: originating query/rank disagrees with the query log")
        if candidate.get("candidate_rank") != candidate.get("result_rank"):
            errors.append(f"{path}.candidate_rank: must equal the logged provider result rank")

    for query_id, query in query_by_id.items():
        path = query_path_by_id[query_id]
        query_candidates = [
            candidate_by_id[item.get("candidate_id")]
            for item in query.get("candidate_ids_and_ranks", [])
            if isinstance(item, dict) and item.get("candidate_id") in candidate_by_id
        ]
        eligible_count = sum(
            candidate.get("selection_status") in {"selected", "eligible_not_selected"}
            for candidate in query_candidates
        )
        pending_count = sum(
            candidate.get("selection_status") == "pending" for candidate in query_candidates
        )
        stop_reason = query.get("stop_reason")
        reported = query.get("result_count_reported")
        screened = query.get("results_screened")
        cap = query.get("screening_cap")
        listed = query.get("candidate_ids_and_ranks", [])
        if stop_reason == "eligible_candidate_found" and eligible_count == 0:
            errors.append(f"{path}.stop_reason: eligible_candidate_found requires an eligible candidate")
        if stop_reason != "eligible_candidate_found" and eligible_count:
            errors.append(f"{path}.stop_reason: must record eligible_candidate_found")
        if pending_count:
            errors.append(
                f"{path}.stop_reason: a completed query cannot retain pending candidates"
            )
        if stop_reason == "no_results" and (reported != 0 or screened != 0 or listed):
            errors.append(f"{path}.stop_reason: no_results requires zero reported/screened/listed results")
        if stop_reason == "access_blocked" and (screened != 0 or listed):
            errors.append(f"{path}.stop_reason: access_blocked requires zero screened/listed results")
        if stop_reason == "screening_cap_reached" and not (
            screened == cap and (reported is None or (isinstance(reported, int) and reported > cap))
        ):
            errors.append(
                f"{path}.stop_reason: screening_cap_reached requires the full cap and more or unknown results"
            )
        if stop_reason in {"resource_exhausted", "completed_without_eligible_candidate"}:
            if (
                not isinstance(reported, int)
                or not isinstance(screened, int)
                or not isinstance(cap, int)
                or screened != min(reported, cap)
            ):
                errors.append(f"{path}.stop_reason: exhaustion requires a fully screened reported result set")

    for step_id, step_queries in queries_by_step.items():
        ordered = sorted(step_queries, key=lambda item: item.get("query_sequence", 0))
        sequences = [item.get("query_sequence") for item in ordered]
        if sequences != list(range(1, len(sequences) + 1)):
            errors.append(
                f"retrieval_log.queries: hierarchy step {step_id!r} query_sequence must be contiguous from 1"
            )
        timestamps = [_parse_datetime(item.get("query_timestamp_utc")) for item in ordered]
        comparable = [item for item in timestamps if item is not None]
        if comparable != sorted(comparable):
            errors.append(f"retrieval_log.queries: hierarchy step {step_id!r} timestamps are out of order")
        for query in ordered[:-1]:
            if query.get("stop_reason") == "eligible_candidate_found":
                errors.append(
                    f"retrieval_log.queries: hierarchy step {step_id!r} continued after an eligible candidate"
                )
        slot = str(ordered[0].get("slot")) if ordered else ""
        if slot in {"C_TRADE", "C_GENERAL", "R_LATER", "R_LATER_2"} and ordered:
            frozen_filters = ordered[0].get("filters")
            frozen_sort = ordered[0].get("sort_order")
            for query in ordered[1:]:
                if query.get("filters") != frozen_filters:
                    errors.append(
                        f"retrieval_log.queries: hierarchy step {step_id!r} changed filters within its frozen query sequence"
                    )
                if query.get("sort_order") != frozen_sort:
                    errors.append(
                        f"retrieval_log.queries: hierarchy step {step_id!r} changed sort_order within its frozen query sequence"
                    )
        expected_specs = _required_query_specs(retrieval_log, slot)
        observed_specs = [_query_spec(query) for query in ordered]
        non_ocr_specs = [
            item for item in observed_specs if item[0] != "ocr_relaxed_title_director"
        ]
        if non_ocr_specs != expected_specs[: len(non_ocr_specs)]:
            errors.append(
                f"retrieval_log.queries: hierarchy step {step_id!r} does not follow the frozen query sequence"
            )
        if any(item[0] == "ocr_relaxed_title_director" for item in observed_specs):
            if non_ocr_specs != expected_specs:
                errors.append(
                    f"retrieval_log.queries: hierarchy step {step_id!r} used OCR relaxation before neutral queries were exhausted"
                )

    acquired_ids = sorted(
        candidate_id
        for candidate_id, candidate in candidate_by_id.items()
        if candidate.get("acquisition_status")
        in {"complete_source_authorized", "provider_workbench_only"}
    )
    expected_pairs = {tuple(pair) for pair in combinations(acquired_ids, 2)}
    recorded_pairs: set[tuple[str, str]] = set()
    for index, check in enumerate(duplicate_checks):
        if not isinstance(check, dict):
            continue
        path = f"retrieval_log.duplicate_checks[{index}]"
        candidate_a = check.get("candidate_id_a")
        candidate_b = check.get("candidate_id_b")
        if not isinstance(candidate_a, str) or not isinstance(candidate_b, str):
            continue
        pair = (candidate_a, candidate_b)
        if candidate_a >= candidate_b:
            errors.append(f"{path}: candidate IDs must be stored in ascending order")
        if pair in recorded_pairs:
            errors.append(f"{path}: duplicate pairwise comparison")
        recorded_pairs.add(pair)
        if pair not in expected_pairs:
            errors.append(f"{path}: pair does not identify two acquired candidates")
            continue
        left = candidate_by_id[candidate_a]
        right = candidate_by_id[candidate_b]
        raw_equal = bool(left.get("raw_sha256")) and left.get("raw_sha256") == right.get("raw_sha256")
        normalized_equal = bool(left.get("normalized_text_sha256")) and (
            left.get("normalized_text_sha256") == right.get("normalized_text_sha256")
        )
        expected_hash_match = (
            "both"
            if raw_equal and normalized_equal
            else "raw"
            if raw_equal
            else "normalized"
            if normalized_equal
            else "none"
        )
        if check.get("hash_match") != expected_hash_match:
            errors.append(f"{path}.hash_match: must be {expected_hash_match!r} for recorded hashes")
        similarity = check.get("estimated_jaccard")
        flags = set(check.get("provenance_flags", []))
        classification = check.get("classification")
        disposition = check.get("lineage_disposition")
        common_synopsis_exception = "common_embedded_synopsis" in flags
        if expected_hash_match != "none":
            expected_classification = "exact_duplicate"
            expected_disposition = "same_lineage"
        elif flags & _DEPENDENCE_FLAGS:
            expected_classification = "provenance_dependent"
            expected_disposition = "same_lineage"
        elif isinstance(similarity, (int, float)) and similarity >= 0.80:
            if common_synopsis_exception:
                expected_classification = "independent"
                expected_disposition = "independent"
            else:
                expected_classification = "near_duplicate_same_lineage"
                expected_disposition = "same_lineage"
        elif isinstance(similarity, (int, float)) and similarity >= 0.60:
            expected_classification = "lineage_review_required"
            expected_disposition = None
        else:
            expected_classification = "independent"
            expected_disposition = "independent"
        if classification != expected_classification:
            errors.append(
                f"{path}.classification: must be {expected_classification!r} for hashes, similarity, and provenance"
            )
        if expected_disposition is not None and disposition != expected_disposition:
            errors.append(
                f"{path}.lineage_disposition: must be {expected_disposition!r} for this classification"
            )
        if classification == "lineage_review_required" and disposition == "unresolved":
            if left.get("selection_status") == "selected" or right.get("selection_status") == "selected":
                errors.append(f"{path}: a pair involving a selected candidate cannot remain unresolved")
        if disposition == "same_lineage" and left.get("lineage_id") != right.get("lineage_id"):
            errors.append(f"{path}: same-lineage disposition requires equal lineage_id values")
        if disposition == "independent" and left.get("lineage_id") == right.get("lineage_id"):
            errors.append(f"{path}: independent disposition requires different lineage_id values")
        if (
            left.get("selection_status") == "selected"
            and right.get("selection_status") == "selected"
            and disposition != "independent"
        ):
            errors.append(f"{path}: two selected candidates must be independent")
        checked_at = _parse_datetime(check.get("checked_at_utc"))
        accessed_times = [
            _parse_datetime(left.get("accessed_at_utc")),
            _parse_datetime(right.get("accessed_at_utc")),
        ]
        if checked_at is not None and any(
            item is not None and checked_at < item for item in accessed_times
        ):
            errors.append(f"{path}.checked_at_utc: duplicate check cannot predate source access")
    missing_pairs = sorted(expected_pairs - recorded_pairs)
    extra_pairs = sorted(recorded_pairs - expected_pairs)
    if missing_pairs:
        errors.append(f"retrieval_log.duplicate_checks: missing acquired-candidate pairs {missing_pairs}")
    if extra_pairs:
        errors.append(f"retrieval_log.duplicate_checks: contains unexpected pairs {extra_pairs}")

    dependent_candidate_ids = {
        candidate_id
        for check in duplicate_checks
        if isinstance(check, dict) and check.get("lineage_disposition") == "same_lineage"
        for candidate_id in (check.get("candidate_id_a"), check.get("candidate_id_b"))
        if isinstance(candidate_id, str)
    }
    for candidate_id, candidate in candidate_by_id.items():
        if (
            candidate.get("selection_status") == "excluded"
            and candidate.get("exclusion_reason") == "duplicate_or_dependent"
            and candidate_id not in dependent_candidate_ids
        ):
            errors.append(
                f"{candidate_path_by_id[candidate_id]}.exclusion_reason: duplicate_or_dependent requires a same-lineage pairwise check"
            )

    return tuple(errors)


def _manifest_indexes(
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, Mapping[str, Any]]]:
    environment_values = manifest.get("extraction_environments", [])
    resource_values = manifest.get("resources", [])
    if not isinstance(environment_values, list):
        environment_values = []
    if not isinstance(resource_values, list):
        resource_values = []
    environments = {
        item["environment_id"]: item
        for item in environment_values
        if isinstance(item, dict) and isinstance(item.get("environment_id"), str)
    }
    resources = {
        item["resource_id"]: item
        for item in resource_values
        if isinstance(item, dict) and isinstance(item.get("resource_id"), str)
    }
    return environments, resources


def _required_query_specs(
    retrieval_log: Mapping[str, Any], slot: str
) -> list[tuple[str, str, str]]:
    """Return the frozen non-OCR query sequence for one route."""

    release_title = retrieval_log.get("film_title")
    alternate_titles = retrieval_log.get("alternate_titles", [])
    if not isinstance(release_title, str):
        return []
    if not isinstance(alternate_titles, list):
        alternate_titles = []
    specs: list[tuple[str, str, str]] = []
    if slot in {"C_TRADE", "C_GENERAL", "R_LATER", "R_LATER_2"}:
        specs.extend(
            (
                ("title_only", "release_title", release_title),
                ("title_director", "release_title", release_title),
                ("title_medium_document", "release_title", release_title),
            )
        )
        for title in alternate_titles:
            if isinstance(title, str):
                specs.extend(
                    (
                        ("alternate_title_only", "alternate_title", title),
                        ("alternate_title_director", "alternate_title", title),
                        ("alternate_title_medium_document", "alternate_title", title),
                    )
                )
    elif slot == "S_ACADEMIC":
        specs.extend(
            (
                ("scholarship_title_director", "release_title", release_title),
                ("scholarship_title_medium", "release_title", release_title),
            )
        )
        for title in alternate_titles:
            if isinstance(title, str):
                specs.extend(
                    (
                        ("scholarship_alternate_director", "alternate_title", title),
                        ("scholarship_alternate_medium", "alternate_title", title),
                    )
                )
    elif slot == "P_SYNOPSIS":
        specs.extend(
            (
                ("synopsis_title", "release_title", release_title),
                ("synopsis_title_director", "release_title", release_title),
            )
        )
        for title in alternate_titles:
            if isinstance(title, str):
                specs.append(("synopsis_alternate_title", "alternate_title", title))
    return specs


def _query_spec(query: Mapping[str, Any]) -> tuple[Any, Any, Any]:
    components = query.get("query_components")
    if not isinstance(components, dict):
        return query.get("query_template_id"), None, None
    return (
        query.get("query_template_id"),
        components.get("title_variant"),
        components.get("title_value"),
    )


def _step_status(
    step: Mapping[str, Any],
    queries_by_step: Mapping[str, list[Mapping[str, Any]]],
    candidate_by_id: Mapping[str, Mapping[str, Any]],
    retrieval_log: Mapping[str, Any],
) -> str:
    """Return unattempted, eligible, exhausted, or incomplete for a hierarchy route."""

    step_id = step.get("hierarchy_step_id")
    queries = sorted(
        queries_by_step.get(str(step_id), []), key=lambda item: item.get("query_sequence", 0)
    )
    if not queries:
        return "unattempted"
    for query in queries:
        candidate_ids = [
            item.get("candidate_id")
            for item in query.get("candidate_ids_and_ranks", [])
            if isinstance(item, dict)
        ]
        if any(
            candidate_by_id.get(str(candidate_id), {}).get("selection_status")
            in {"selected", "eligible_not_selected"}
            for candidate_id in candidate_ids
        ):
            return "eligible"
    if any(query.get("stop_reason") == "access_blocked" for query in queries):
        return "blocked"
    expected = _required_query_specs(retrieval_log, str(step.get("slot")))
    observed = [_query_spec(query) for query in queries]
    non_ocr = [item for item in observed if item[0] != "ocr_relaxed_title_director"]
    if non_ocr == expected and queries[-1].get("stop_reason") in EXHAUSTED_STOP_REASONS:
        return "exhausted"
    return "incomplete"


def _candidate_selection_key(
    candidate: Mapping[str, Any],
    query_by_id: Mapping[str, Mapping[str, Any]],
    hierarchy_by_id: Mapping[str, Mapping[str, Any]],
    anchor: date,
) -> tuple[Any, ...]:
    """Compute the protocol's content-blind selection order."""

    slot = str(candidate.get("slot"))
    step = hierarchy_by_id.get(str(candidate.get("hierarchy_step_id")), {})
    query = query_by_id.get(str(candidate.get("query_id")), {})
    interval = _publication_date_interval(
        candidate.get("publication_date"), candidate.get("publication_date_precision")
    )
    publication_date = interval[0] if interval is not None else date.max
    title_key = _normalize_sort_text(candidate.get("article_title"))
    author_key = _normalize_sort_text(candidate.get("author_display"))
    author_surname = author_key.split()[-1] if author_key else ""
    stable_tail = str(candidate.get("candidate_id"))
    if slot in {"C_TRADE", "C_GENERAL"}:
        return (
            step.get("system_rank", 10**9),
            abs((publication_date - anchor).days),
            publication_date,
            title_key,
            stable_tail,
        )
    if slot in {"R_LATER", "R_LATER_2"}:
        return (
            step.get("system_tier", 10**9),
            publication_date,
            author_surname,
            title_key,
            stable_tail,
        )
    if slot == "S_ACADEMIC":
        form_priority = SCHOLARLY_FORM_PRIORITY.get(str(candidate.get("scholarly_form")), 10**9)
        doi_or_isbn = _normalize_sort_text(candidate.get("doi_or_isbn"))
        page_start = _normalize_sort_text(candidate.get("citation_page_start"))
        if doi_or_isbn:
            bibliographic_key = (0, doi_or_isbn)
        elif page_start:
            bibliographic_key = (1, page_start)
        else:
            bibliographic_key = (2, title_key)
        return (form_priority, publication_date, bibliographic_key, title_key, stable_tail)
    return (
        step.get("system_rank", 10**9),
        step.get("route_rank", 10**9),
        query.get("query_sequence", 10**9),
        candidate.get("result_rank", 10**9),
        stable_tail,
    )


def _assigned_candidate_gate_errors(
    slot: str,
    candidate: Mapping[str, Any],
    environment_id: Any,
    query_by_id: Mapping[str, Mapping[str, Any]],
    environments: Mapping[str, Mapping[str, Any]],
    resources: Mapping[str, Mapping[str, Any]],
) -> list[str]:
    path = f"bundle.slot_assignments.{slot}"
    errors: list[str] = []
    if candidate.get("selection_status") != "selected":
        errors.append(f"{path}: referenced candidate is not marked selected")
    if candidate.get("slot") != slot:
        errors.append(f"{path}: candidate was screened for slot {candidate.get('slot')!r}")
    expected_type = SLOT_SOURCE_TYPES[slot]
    if candidate.get("source_type") != expected_type:
        errors.append(f"{path}: candidate source_type must be {expected_type!r}")
    expected_extraction_type = SLOT_EXTRACTION_SOURCE_TYPES[slot]
    if candidate.get("extraction_source_type") != expected_extraction_type:
        errors.append(
            f"{path}: candidate must map to extraction SourceType {expected_extraction_type!r}"
        )
    if candidate.get("rights_class") not in INCLUDABLE_RIGHTS_CLASSES:
        errors.append(f"{path}: candidate rights_class does not permit inclusion")
    if candidate.get("source_completeness_verified") is not True:
        errors.append(f"{path}: source completeness has not been verified")
    if candidate.get("acquisition_status") not in {
        "complete_source_authorized",
        "provider_workbench_only",
    }:
        errors.append(f"{path}: no authorized complete-source acquisition")

    processing = candidate.get("processing_permission")
    if not isinstance(processing, dict) or processing.get("status") != "allowed":
        errors.append(f"{path}: item-level model processing is not allowed")
    elif processing.get("environment_id") != environment_id:
        errors.append(
            f"{path}: item-level permission names {processing.get('environment_id')!r}, "
            f"not bundle environment {environment_id!r}"
        )

    query = query_by_id.get(str(candidate.get("query_id")))
    if query is None:
        errors.append(f"{path}: candidate has no originating query")
        return errors
    resource_id = query.get("resource_id")
    resource = resources.get(str(resource_id))
    if resource is None:
        errors.append(f"{path}: query resource {resource_id!r} is absent from access manifest")
        return errors
    if resource.get("access_status") != "available":
        errors.append(f"{path}: query resource was not frozen as available")
    if resource.get("full_text_acquisition") in {"metadata_only", "not_available", None}:
        errors.append(f"{path}: query resource supplies no authorized complete-source route")
    if resource.get("tdm_permission") not in {"allowed", "restricted"}:
        errors.append(f"{path}: resource TDM permission is not affirmative")
    if resource.get("model_processing_permission") not in {"allowed", "restricted"}:
        errors.append(f"{path}: resource model-processing permission is not affirmative")
    allowed_environment_ids = resource.get("allowed_environment_ids", [])
    if not isinstance(allowed_environment_ids, list) or environment_id not in allowed_environment_ids:
        errors.append(f"{path}: bundle environment is not allowed by the resource manifest")
    environment = environments.get(str(environment_id), {})
    workbench_only = (
        candidate.get("acquisition_status") == "provider_workbench_only"
        or resource.get("full_text_acquisition") == "provider_workbench"
        or resource.get("storage_permission") == "provider_workbench_only"
    )
    if workbench_only and environment.get("host_type") != "provider_workbench":
        errors.append(
            f"{path}: provider-workbench-only text requires a provider_workbench extraction environment"
        )
    if resource.get("storage_permission") in {"none", "unknown", None}:
        errors.append(f"{path}: resource does not permit an auditable source/evidence store")
    if resource.get("export_permission") not in {"reviewed_excerpts", "full_source_allowed"}:
        errors.append(
            f"{path}: resource does not permit export of the reviewed evidence excerpts required for audit"
        )
    resource_references = {
        item.get("rights_reference_id"): item
        for item in resource.get("rights_references", [])
        if isinstance(item, dict) and isinstance(item.get("rights_reference_id"), str)
    }
    resource_reference_ids = set(resource_references)
    candidate_reference_ids = (
        set(processing.get("rights_reference_ids", []))
        if isinstance(processing, dict)
        else set()
    )
    unknown_reference_ids = sorted(candidate_reference_ids - resource_reference_ids)
    if unknown_reference_ids:
        errors.append(
            f"{path}: candidate processing permission cites unknown resource rights references "
            f"{unknown_reference_ids}"
        )
    expected_rights = RIGHTS_CLASS_BASIS_TYPES.get(str(candidate.get("rights_class")))
    if expected_rights is not None and isinstance(processing, dict):
        expected_basis_type, allowed_reference_types = expected_rights
        if processing.get("basis_type") != expected_basis_type:
            errors.append(
                f"{path}: rights_class {candidate.get('rights_class')!r} requires processing "
                f"basis_type {expected_basis_type!r}"
            )
        cited_reference_types = {
            resource_references[reference_id].get("reference_type")
            for reference_id in candidate_reference_ids
            if reference_id in resource_references
        }
        if not (cited_reference_types & allowed_reference_types):
            errors.append(
                f"{path}: structured rights references do not support rights_class "
                f"{candidate.get('rights_class')!r}"
            )
    return errors


def audit_frozen_source_bundle(
    bundle: Mapping[str, Any],
    retrieval_log: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> AuditResult:
    """Audit all three metadata documents and enforce frozen bundle semantics."""

    errors = list(validate_archive_access_manifest(manifest))
    errors.extend(validate_source_retrieval_log(retrieval_log))
    errors.extend(
        _validate_against_schema(bundle, "frozen-source-bundle.schema.json", "bundle")
    )
    warnings: list[str] = []

    if bundle.get("archive_access_manifest_id") != manifest.get("manifest_id"):
        errors.append("bundle.archive_access_manifest_id: does not match manifest.manifest_id")
    if retrieval_log.get("archive_access_manifest_id") != manifest.get("manifest_id"):
        errors.append(
            "retrieval_log.archive_access_manifest_id: does not match manifest.manifest_id"
        )
    if bundle.get("retrieval_log_id") != retrieval_log.get("retrieval_log_id"):
        errors.append("bundle.retrieval_log_id: does not match retrieval_log.retrieval_log_id")
    if bundle.get("film_id") != retrieval_log.get("film_id"):
        errors.append("bundle.film_id: does not match retrieval_log.film_id")

    manifest_frozen = _parse_datetime(manifest.get("frozen_at_utc"))
    log_created = _parse_datetime(retrieval_log.get("created_at_utc"))
    bundle_frozen = _parse_datetime(bundle.get("frozen_at_utc"))
    if manifest_frozen is not None and log_created is not None and manifest_frozen > log_created:
        errors.append("chronology: archive access manifest must be frozen before retrieval begins")
    if bundle_frozen is not None:
        event_times: list[tuple[str, datetime]] = []
        if log_created is not None:
            event_times.append(("retrieval_log.created_at_utc", log_created))
        for index, query in enumerate(retrieval_log.get("queries", [])):
            if isinstance(query, dict):
                timestamp = _parse_datetime(query.get("query_timestamp_utc"))
                if timestamp is not None:
                    event_times.append((f"retrieval_log.queries[{index}].query_timestamp_utc", timestamp))
        for index, candidate in enumerate(retrieval_log.get("candidates", [])):
            if not isinstance(candidate, dict):
                continue
            timestamp = _parse_datetime(candidate.get("accessed_at_utc"))
            if timestamp is not None:
                event_times.append((f"retrieval_log.candidates[{index}].accessed_at_utc", timestamp))
            permission = candidate.get("processing_permission")
            if isinstance(permission, dict):
                timestamp = _parse_datetime(permission.get("verified_at_utc"))
                if timestamp is not None:
                    event_times.append(
                        (f"retrieval_log.candidates[{index}].processing_permission.verified_at_utc", timestamp)
                    )
            translation = candidate.get("translation_reference")
            if isinstance(translation, dict):
                timestamp = _parse_datetime(translation.get("verified_at_utc"))
                if timestamp is not None:
                    event_times.append(
                        (f"retrieval_log.candidates[{index}].translation_reference.verified_at_utc", timestamp)
                    )
        for index, check in enumerate(retrieval_log.get("duplicate_checks", [])):
            if isinstance(check, dict):
                timestamp = _parse_datetime(check.get("checked_at_utc"))
                if timestamp is not None:
                    event_times.append((f"retrieval_log.duplicate_checks[{index}].checked_at_utc", timestamp))
        for label, timestamp in event_times:
            if timestamp > bundle_frozen:
                errors.append(f"chronology: {label} cannot postdate bundle freeze")

    environments, resources = _manifest_indexes(manifest)
    environment_id = bundle.get("extraction_environment_id")
    if environment_id not in environments:
        errors.append("bundle.extraction_environment_id: environment is absent from manifest")

    query_values = retrieval_log.get("queries", [])
    candidate_values = retrieval_log.get("candidates", [])
    if not isinstance(query_values, list):
        query_values = []
    if not isinstance(candidate_values, list):
        candidate_values = []
    query_by_id = {
        item["query_id"]: item
        for item in query_values
        if isinstance(item, dict) and isinstance(item.get("query_id"), str)
    }
    candidate_by_id = {
        item["candidate_id"]: item
        for item in candidate_values
        if isinstance(item, dict) and isinstance(item.get("candidate_id"), str)
    }
    hierarchy_values = manifest.get("search_hierarchy", [])
    if not isinstance(hierarchy_values, list):
        hierarchy_values = []
    hierarchy_by_id = {
        item["hierarchy_step_id"]: item
        for item in hierarchy_values
        if isinstance(item, dict) and isinstance(item.get("hierarchy_step_id"), str)
    }
    steps_by_slot: dict[str, list[Mapping[str, Any]]] = {}
    for step in hierarchy_by_id.values():
        slot_value = step.get("slot")
        if isinstance(slot_value, str):
            steps_by_slot.setdefault(slot_value, []).append(step)
    inventory_values = manifest.get("source_system_inventory", [])
    if not isinstance(inventory_values, list):
        inventory_values = []
    inventory_by_pair = {
        (str(item.get("slot")), str(item.get("source_system_code"))): item
        for item in inventory_values
        if isinstance(item, dict)
    }
    anchor_record = retrieval_log.get("release_date_anchor")
    selection_anchor = None
    if isinstance(anchor_record, dict):
        selection_anchor = _parse_date(anchor_record.get("date"))

    def interval_relevant_to_film(slot: str, interval: Mapping[str, Any]) -> bool:
        """Whether a documented holding can contain evidence eligible for this film."""

        if selection_anchor is None or manifest_frozen is None:
            return False
        start = _parse_date(interval.get("start_date"))
        end = _parse_date(interval.get("end_date"))
        if start is None or end is None:
            return False
        if slot == "P_SYNOPSIS":
            return start <= selection_anchor <= end
        if slot in {"C_TRADE", "C_GENERAL"}:
            lower = selection_anchor - timedelta(days=30)
            upper = selection_anchor + timedelta(days=365)
        elif slot in {"R_LATER", "R_LATER_2"}:
            lower = selection_anchor + timedelta(days=730)
            upper = manifest_frozen.date()
        elif slot == "S_ACADEMIC":
            lower = selection_anchor
            upper = manifest_frozen.date()
        else:
            return False
        return lower <= upper and start <= upper and end >= lower

    def step_available(step: Mapping[str, Any]) -> bool:
        resource_id = str(step.get("resource_id"))
        resource = resources.get(resource_id)
        if resource is None or resource.get("access_status") != "available":
            return False
        entry = inventory_by_pair.get(
            (str(step.get("slot")), str(step.get("source_system_code")))
        )
        if (
            entry is None
            or entry.get("access_disposition") != "available"
            or entry.get("coverage_disposition") != "documented_intervals"
        ):
            return False
        return any(
            isinstance(interval, dict)
            and str(interval.get("resource_id")) == resource_id
            and interval_relevant_to_film(str(step.get("slot")), interval)
            for interval in entry.get("coverage_intervals", [])
        )

    def candidate_covered_by_step(
        candidate: Mapping[str, Any], step: Mapping[str, Any]
    ) -> bool:
        entry = inventory_by_pair.get(
            (str(step.get("slot")), str(step.get("source_system_code")))
        )
        if entry is None:
            return False
        resource_id = str(step.get("resource_id"))
        intervals = [
            interval
            for interval in entry.get("coverage_intervals", [])
            if isinstance(interval, dict)
            and str(interval.get("resource_id")) == resource_id
        ]
        if str(step.get("slot")) == "P_SYNOPSIS":
            target = (
                (selection_anchor, selection_anchor)
                if selection_anchor is not None
                else None
            )
        else:
            target = _publication_date_interval(
                candidate.get("publication_date"),
                candidate.get("publication_date_precision"),
            )
        if target is None:
            return False
        target_start, target_end = target
        for interval in intervals:
            start = _parse_date(interval.get("start_date"))
            end = _parse_date(interval.get("end_date"))
            if start is not None and end is not None:
                if start <= target_start and target_end <= end:
                    return True
        return False

    queries_by_step: dict[str, list[Mapping[str, Any]]] = {}
    for query in query_by_id.values():
        step_id = query.get("hierarchy_step_id")
        step = hierarchy_by_id.get(str(step_id))
        if step is None:
            errors.append(
                f"retrieval_log query {query.get('query_id')!r}: hierarchy_step_id {step_id!r} is absent from manifest"
            )
            continue
        queries_by_step.setdefault(str(step_id), []).append(query)
        if query.get("slot") != step.get("slot"):
            errors.append(
                f"retrieval_log query {query.get('query_id')!r}: slot disagrees with hierarchy step"
            )
        if query.get("resource_id") != step.get("resource_id"):
            errors.append(
                f"retrieval_log query {query.get('query_id')!r}: resource disagrees with hierarchy step"
            )
        if query.get("resource_or_outlet") != step.get("source_system_name"):
            errors.append(
                f"retrieval_log query {query.get('query_id')!r}: source system name disagrees with hierarchy step"
            )
        for query_filter in query.get("filters", []):
            if (
                isinstance(query_filter, dict)
                and query_filter.get("name") == "outlet"
                and _normalize_sort_text(query_filter.get("value"))
                != _normalize_sort_text(step.get("source_system_name"))
            ):
                errors.append(
                    f"retrieval_log query {query.get('query_id')!r}: outlet filter disagrees with hierarchy step"
                )
        resource = resources.get(str(step.get("resource_id")))
        if resource is not None and resource.get("access_status") != "available":
            errors.append(
                f"retrieval_log query {query.get('query_id')!r}: queried a resource not frozen as available"
            )
        elif not step_available(step):
            errors.append(
                f"retrieval_log query {query.get('query_id')!r}: hierarchy route lacks documented coverage relevant to this film"
            )
    assignments = bundle.get("slot_assignments")
    if not isinstance(assignments, dict):
        assignments = {}

    queried_slots = {query.get("slot") for query in query_by_id.values()}
    for slot in CANONICAL_SLOTS:
        has_available_route = any(step_available(step) for step in steps_by_slot.get(slot, []))
        if slot not in queried_slots and has_available_route:
            errors.append(f"retrieval_log.queries: frozen bundle requires a query for {slot}")
        if slot not in queried_slots and not has_available_route and assignments.get(slot) is not None:
            errors.append(
                f"bundle.slot_assignments.{slot}: cannot be filled when the frozen manifest has no available route"
            )

    for candidate_id, candidate in candidate_by_id.items():
        if candidate.get("selection_status") == "pending":
            errors.append(
                f"frozen retrieval log retains pending candidate {candidate_id!r}"
            )

    if selection_anchor is not None:
        for slot in ALL_SLOTS:
            eligible_candidates = [
                candidate
                for candidate in candidate_by_id.values()
                if candidate.get("slot") == slot
                and candidate.get("selection_status") in {"selected", "eligible_not_selected"}
            ]
            selected_candidates = [
                candidate
                for candidate in eligible_candidates
                if candidate.get("selection_status") == "selected"
            ]
            if not eligible_candidates:
                continue
            if len(selected_candidates) != 1:
                errors.append(
                    f"deterministic selection: slot {slot} has eligible candidates but not exactly one selected"
                )
                continue
            expected_candidate = min(
                eligible_candidates,
                key=lambda item: _candidate_selection_key(
                    item, query_by_id, hierarchy_by_id, selection_anchor
                ),
            )
            if selected_candidates[0].get("candidate_id") != expected_candidate.get("candidate_id"):
                errors.append(
                    f"deterministic selection: slot {slot} selected {selected_candidates[0].get('candidate_id')!r} "
                    f"instead of first candidate {expected_candidate.get('candidate_id')!r}"
                )

    def system_complete(slot: str, system_id: Any) -> bool:
        system_steps = sorted(
            [
                step
                for step in steps_by_slot.get(slot, [])
                if step.get("source_system_id") == system_id and step_available(step)
            ],
            key=lambda item: item.get("route_rank", 10**9),
        )
        if not system_steps:
            return True
        for step in system_steps:
            status = _step_status(step, queries_by_step, candidate_by_id, retrieval_log)
            if status == "eligible":
                earlier = [
                    item
                    for item in system_steps
                    if item.get("route_rank", 10**9) < step.get("route_rank", 10**9)
                ]
                return all(
                    _step_status(item, queries_by_step, candidate_by_id, retrieval_log)
                    in {"exhausted", "blocked"}
                    for item in earlier
                )
            if status not in {"exhausted", "blocked"}:
                return False
        return True

    def step_order_key(step: Mapping[str, Any]) -> tuple[Any, ...]:
        slot = str(step.get("slot"))
        if slot in {"R_LATER", "R_LATER_2"}:
            return (
                step.get("system_tier", 10**9),
                step.get("system_rank", 10**9),
                step.get("route_rank", 10**9),
            )
        return (step.get("system_rank", 10**9), step.get("route_rank", 10**9))

    # An unfilled canonical slot is a defensible coverage result only after every
    # frozen route whose documented holdings overlap this film has been exhausted
    # or was blocked.  Requiring merely one query for the slot would allow a
    # minimum-complete bundle to abandon (for example) R_LATER after its first
    # archive while silently skipping other available systems.
    for slot in CANONICAL_SLOTS:
        if assignments.get(slot) is not None:
            continue
        for step in sorted(steps_by_slot.get(slot, []), key=step_order_key):
            if not step_available(step):
                continue
            status = _step_status(step, queries_by_step, candidate_by_id, retrieval_log)
            if status not in {"exhausted", "blocked"}:
                errors.append(
                    f"unfilled canonical slot {slot}: available hierarchy route "
                    f"{step.get('hierarchy_step_id')!r} is {status}, not exhausted or blocked"
                )

    # Search routes are genuinely sequential, not merely given final ranks after
    # the fact.  Later routes may not be queried before earlier attempted routes.
    for slot, slot_steps in steps_by_slot.items():
        attempted = [step for step in slot_steps if queries_by_step.get(str(step.get("hierarchy_step_id")))]
        attempted.sort(key=step_order_key)
        last_time: datetime | None = None
        for step in attempted:
            times = [
                _parse_datetime(query.get("query_timestamp_utc"))
                for query in queries_by_step.get(str(step.get("hierarchy_step_id")), [])
            ]
            for candidate in candidate_by_id.values():
                if candidate.get("hierarchy_step_id") != step.get("hierarchy_step_id"):
                    continue
                times.append(_parse_datetime(candidate.get("accessed_at_utc")))
                permission = candidate.get("processing_permission")
                if isinstance(permission, dict):
                    times.append(_parse_datetime(permission.get("verified_at_utc")))
            comparable = sorted(item for item in times if item is not None)
            if not comparable:
                continue
            if last_time is not None and comparable[0] < last_time:
                errors.append(
                    f"search hierarchy: slot {slot} queried a lower-priority route before an earlier route was completed"
                )
            last_time = comparable[-1]

    for candidate in candidate_by_id.values():
        if candidate.get("selection_status") != "selected":
            continue
        slot = str(candidate.get("slot"))
        selected_step = hierarchy_by_id.get(str(candidate.get("hierarchy_step_id")))
        if selected_step is None:
            continue
        if not candidate_covered_by_step(candidate, selected_step):
            errors.append(
                f"retrieval candidate {candidate.get('candidate_id')!r}: source date is outside the frozen route's documented coverage interval"
            )
        selected_rank = selected_step.get("system_rank", 10**9)
        selected_tier = selected_step.get("system_tier", 10**9)
        selected_route = selected_step.get("route_rank", 10**9)
        selected_accessed = _parse_datetime(candidate.get("accessed_at_utc"))
        if slot != "S_ACADEMIC":
            system_code = str(selected_step.get("source_system_code"))
            allowed_outlets = SOURCE_SYSTEM_OUTLET_ALIASES.get(
                system_code, {selected_step.get("source_system_name")}
            )
            normalized_outlets = {_normalize_sort_text(value) for value in allowed_outlets}
            if _normalize_sort_text(candidate.get("outlet")) not in normalized_outlets:
                errors.append(
                    f"retrieval candidate {candidate.get('candidate_id')!r}: outlet must match its frozen source system"
                )
        required_systems: set[Any] = set()
        for step in steps_by_slot.get(slot, []):
            if not step_available(step):
                continue
            if slot in {"C_TRADE", "C_GENERAL", "P_SYNOPSIS"}:
                if step.get("system_rank", 10**9) < selected_rank:
                    required_systems.add(step.get("source_system_id"))
            elif slot in {"R_LATER", "R_LATER_2"}:
                if step.get("system_tier", 10**9) <= selected_tier:
                    required_systems.add(step.get("source_system_id"))
            elif slot == "S_ACADEMIC":
                form_priority = SCHOLARLY_FORM_PRIORITY.get(
                    str(candidate.get("scholarly_form")), 10**9
                )
                if form_priority > 2 or step.get("system_rank", 10**9) < selected_rank:
                    required_systems.add(step.get("source_system_id"))
        required_systems.add(selected_step.get("source_system_id"))
        for system_id in required_systems:
            if not system_complete(slot, system_id):
                errors.append(
                    f"search hierarchy: slot {slot} selected a source before required system "
                    f"{system_id!r} and its routes were completed"
                )
        if slot in {"R_LATER", "R_LATER_2"}:
            expected_commercial = selected_tier == 3
            if candidate.get("commercial_curatorial") is not expected_commercial:
                errors.append(
                    f"retrieval candidate {candidate.get('candidate_id')!r}: commercial_curatorial "
                    f"must be {expected_commercial!r} for retrospective tier {selected_tier}"
                )
        elif candidate.get("commercial_curatorial") is not False:
            errors.append(
                f"retrieval candidate {candidate.get('candidate_id')!r}: commercial_curatorial is allowed only for tier-3 retrospective essays"
            )

        if selected_accessed is not None:
            selected_form_priority = SCHOLARLY_FORM_PRIORITY.get(
                str(candidate.get("scholarly_form")), 10**9
            )
            for step in steps_by_slot.get(slot, []):
                later_than_stop = False
                if slot in {"C_TRADE", "C_GENERAL", "P_SYNOPSIS"}:
                    later_than_stop = step_order_key(step) > step_order_key(selected_step)
                elif slot in {"R_LATER", "R_LATER_2"}:
                    later_than_stop = (
                        step.get("system_tier", 10**9) > selected_tier
                        or (
                            step.get("source_system_id") == selected_step.get("source_system_id")
                            and step.get("route_rank", 10**9) > selected_route
                        )
                    )
                elif slot == "S_ACADEMIC" and selected_form_priority <= 2:
                    later_than_stop = step_order_key(step) > step_order_key(selected_step)
                if not later_than_stop:
                    continue
                for query in queries_by_step.get(str(step.get("hierarchy_step_id")), []):
                    query_time = _parse_datetime(query.get("query_timestamp_utc"))
                    if query_time is not None and query_time > selected_accessed:
                        errors.append(
                            f"search hierarchy: slot {slot} continued to a lower-priority route after an eligible source was acquired"
                        )
                        break

    assigned: list[tuple[str, str, Mapping[str, Any]]] = []
    for slot in ALL_SLOTS:
        candidate_id = assignments.get(slot)
        if candidate_id is None:
            continue
        candidate = candidate_by_id.get(str(candidate_id))
        if candidate is None:
            errors.append(f"bundle.slot_assignments.{slot}: unknown candidate_id {candidate_id!r}")
            continue
        assigned.append((slot, str(candidate_id), candidate))
        errors.extend(
            _assigned_candidate_gate_errors(
                slot, candidate, environment_id, query_by_id, environments, resources
            )
        )

    assigned_ids = [candidate_id for _, candidate_id, _ in assigned]
    if len(assigned_ids) != len(set(assigned_ids)):
        errors.append("bundle.slot_assignments: one candidate cannot fill two slots")
    if bundle_frozen is not None:
        for slot, candidate_id, candidate in assigned:
            retention_deadline = _parse_date(candidate.get("retention_deadline"))
            if retention_deadline is not None and retention_deadline < bundle_frozen.date():
                errors.append(
                    f"bundle.slot_assignments.{slot}: candidate {candidate_id!r} retention expired before bundle freeze"
                )

    for field in (
        "source_id",
        "lineage_id",
        "author_id",
        "outlet",
        "raw_sha256",
        "normalized_text_sha256",
    ):
        repeated = _duplicates(
            (f"{slot}:{candidate_id}", candidate.get(field))
            for slot, candidate_id, candidate in assigned
        )
        for value, labels in repeated:
            errors.append(
                f"bundle independence: repeated {field} {value!r} across {', '.join(labels)}"
            )

    unfilled = [slot for slot in CANONICAL_SLOTS if assignments.get(slot) is None]
    if bundle.get("unfilled_canonical_slots") != unfilled:
        errors.append(
            "bundle.unfilled_canonical_slots: must exactly list null canonical slots in protocol order"
        )

    has_academic = assignments.get("S_ACADEMIC") is not None
    has_later = assignments.get("R_LATER") is not None
    has_later_2 = assignments.get("R_LATER_2") is not None
    substitution = bundle.get("scholarship_substitution") is True
    disposition = bundle.get("academic_search_disposition")
    if has_later_2 and "R_LATER_2" not in queried_slots:
        errors.append("retrieval_log.queries: R_LATER_2 assignment requires its own logged query")
    academic_queries = [
        query for query in query_by_id.values() if query.get("slot") == "S_ACADEMIC"
    ]
    if has_later_2:
        if has_academic:
            errors.append("bundle: R_LATER_2 cannot coexist with S_ACADEMIC")
        if not has_later:
            errors.append("bundle: R_LATER_2 substitutes only for S_ACADEMIC and requires R_LATER")
        if not substitution:
            errors.append("bundle.scholarship_substitution: must be true when R_LATER_2 is assigned")
        if disposition != "exhausted_no_eligible_source":
            errors.append(
                "bundle.academic_search_disposition: R_LATER_2 requires an exhausted academic search"
            )
    elif substitution:
        errors.append("bundle.scholarship_substitution: true requires an R_LATER_2 assignment")

    if has_academic:
        if disposition != "source_selected":
            errors.append(
                "bundle.academic_search_disposition: S_ACADEMIC requires source_selected"
            )
        if substitution:
            errors.append("bundle.scholarship_substitution: must be false with S_ACADEMIC")
    elif disposition == "source_selected":
        errors.append("bundle.academic_search_disposition: source_selected requires S_ACADEMIC")
    if disposition == "exhausted_no_eligible_source" and has_academic:
        errors.append(
            "bundle.academic_search_disposition: exhausted search cannot include S_ACADEMIC"
        )
    if disposition == "exhausted_no_eligible_source":
        if not academic_queries:
            errors.append(
                "bundle.academic_search_disposition: exhausted search requires logged S_ACADEMIC queries"
            )
        elif any(
            query.get("stop_reason") == "eligible_candidate_found" for query in academic_queries
        ):
            errors.append(
                "bundle.academic_search_disposition: an academic query reports an eligible candidate"
            )
        available_academic_steps = [
            step for step in steps_by_slot.get("S_ACADEMIC", []) if step_available(step)
        ]
        incomplete_academic_steps = [
            step.get("hierarchy_step_id")
            for step in available_academic_steps
            if _step_status(step, queries_by_step, candidate_by_id, retrieval_log)
            != "exhausted"
        ]
        if incomplete_academic_steps:
            errors.append(
                "bundle.academic_search_disposition: all accessible scholarly systems and routes "
                f"must be exhausted; incomplete {incomplete_academic_steps}"
            )

    assigned_count = len(assigned_ids)
    hard_minimum = (
        assigned_count >= 4
        and assignments.get("C_TRADE") is not None
        and assignments.get("C_GENERAL") is not None
        and assignments.get("P_SYNOPSIS") is not None
        and (has_later or has_academic)
    )
    target_complete = (
        assigned_count == 5
        and assignments.get("C_TRADE") is not None
        and assignments.get("C_GENERAL") is not None
        and has_later
        and assignments.get("P_SYNOPSIS") is not None
        and (has_academic or has_later_2)
        and not (has_academic and has_later_2)
    )
    expected_status = (
        "target_complete" if target_complete else "minimum_complete" if hard_minimum else "ineligible"
    )
    if bundle.get("completion_status") != expected_status:
        errors.append(
            f"bundle.completion_status: must be {expected_status!r} for these assignments"
        )
    if bundle.get("completion_status") in {"target_complete", "minimum_complete"} and disposition == "not_complete":
        errors.append("bundle.academic_search_disposition: eligible frozen bundles cannot be not_complete")

    selected_ids = {
        candidate_id
        for candidate_id, candidate in candidate_by_id.items()
        if candidate.get("selection_status") == "selected"
    }
    unassigned_selected = sorted(selected_ids - set(assigned_ids))
    if unassigned_selected:
        errors.append(
            "selected candidates not assigned to this bundle: " + ", ".join(unassigned_selected)
        )
    if expected_status == "minimum_complete":
        warnings.append("bundle meets the hard four-source minimum but not the five-source target")
    if expected_status == "ineligible":
        warnings.append("bundle does not meet the hard four-source minimum")

    summary = {
        "bundle_id": bundle.get("bundle_id"),
        "film_id": bundle.get("film_id"),
        "declared_completion_status": bundle.get("completion_status"),
        "computed_completion_status": expected_status,
        "assigned_source_count": assigned_count,
        "canonical_slots_filled": len(CANONICAL_SLOTS) - len(unfilled),
        "scholarship_substitution": substitution,
        "extraction_environment_id": environment_id,
        "error_count": len(errors),
        "warning_count": len(warnings),
    }
    return AuditResult(tuple(errors), tuple(warnings), summary)


def audit_paths(
    manifest_path: str | Path,
    retrieval_log_path: str | Path,
    bundle_path: str | Path,
) -> AuditResult:
    """Load and audit one manifest/log/bundle triplet."""

    manifest = load_json(manifest_path)
    retrieval_log = load_json(retrieval_log_path)
    bundle = load_json(bundle_path)
    return audit_frozen_source_bundle(bundle, retrieval_log, manifest)


def _print_human(result: AuditResult) -> None:
    print("PASS" if result.ok else "FAIL")
    for key, value in result.summary.items():
        print(f"{key}: {value}")
    for error in result.errors:
        print(f"ERROR: {error}")
    for warning in result.warnings:
        print(f"WARNING: {warning}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit frozen film-source metadata controls")
    parser.add_argument("--manifest", required=True, help="archive access manifest JSON")
    parser.add_argument("--retrieval-log", required=True, help="candidate/query log JSON")
    parser.add_argument("--bundle", required=True, help="frozen source bundle JSON")
    parser.add_argument("--json", action="store_true", help="emit the audit result as JSON")
    args = parser.parse_args(argv)
    try:
        result = audit_paths(args.manifest, args.retrieval_log, args.bundle)
    except MetadataError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(
            json.dumps(
                {
                    "ok": result.ok,
                    "errors": result.errors,
                    "warnings": result.warnings,
                    "summary": result.summary,
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        _print_human(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
