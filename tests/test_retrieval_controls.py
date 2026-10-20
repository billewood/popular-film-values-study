from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from film_values.retrieval_controls import (
    MetadataError,
    audit_frozen_source_bundle,
    extraction_source_type_for_slot,
    load_json,
    validate_archive_access_manifest,
    validate_source_retrieval_log,
)
from film_values.models import SourceType


ROOT = Path(__file__).resolve().parents[1]


def template(name: str) -> dict:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def example_triplet() -> tuple[dict, dict, dict]:
    return (
        template("archive-access-manifest.template.json"),
        template("source-retrieval-log.template.json"),
        template("frozen-source-bundle.template.json"),
    )


def candidate_for(log: dict, slot: str) -> dict:
    return next(item for item in log["candidates"] if item["slot"] == slot)


def query_for(log: dict, slot: str) -> dict:
    return next(item for item in log["queries"] if item["slot"] == slot)


def inventory_for(manifest: dict, slot: str, system_code: str | None = None) -> dict:
    matches = [
        item
        for item in manifest["source_system_inventory"]
        if item["slot"] == slot
        and (system_code is None or item["source_system_code"] == system_code)
    ]
    if system_code is None:
        active = [item for item in matches if item["access_disposition"] == "available"]
        if len(active) == 1:
            return active[0]
    if len(matches) != 1:
        raise AssertionError(
            f"expected one inventory entry for {slot}/{system_code}, found {len(matches)}"
        )
    return matches[0]


def add_independent_pair_checks(log: dict, candidate_id: str) -> None:
    for other in log["candidates"]:
        other_id = other["candidate_id"]
        if other_id == candidate_id:
            continue
        candidate_a, candidate_b = sorted([other_id, candidate_id])
        log["duplicate_checks"].append(
            {
                "candidate_id_a": candidate_a,
                "candidate_id_b": candidate_b,
                "method": "token_5_shingle_minhash",
                "estimated_jaccard": 0,
                "hash_match": "none",
                "provenance_flags": [],
                "classification": "independent",
                "lineage_disposition": "independent",
                "adjudication_note": "Synthetic pairwise check for test fixture.",
                "checked_at_utc": "2026-10-19T12:31:00Z",
            }
        )


def remove_candidate_for_slot(log: dict, slot: str) -> None:
    candidate = candidate_for(log, slot)
    query = query_for(log, slot)
    candidate_id = candidate["candidate_id"]
    log["candidates"].remove(candidate)
    log["duplicate_checks"] = [
        item
        for item in log["duplicate_checks"]
        if candidate_id not in {item["candidate_id_a"], item["candidate_id_b"]}
    ]
    query["candidate_ids_and_ranks"] = []
    query["unfiltered_result_count_reported"] = 0
    query["result_count_reported"] = 0
    query["results_screened"] = 0
    query["stop_reason"] = "completed_without_eligible_candidate"
    if slot == "S_ACADEMIC":
        second_query = copy.deepcopy(query)
        second_query.update(
            {
                "query_id": "query-template-s-academic-2",
                "query_sequence": 2,
                "query_template_id": "scholarship_title_medium",
                "exact_query": '"Example Film" (film OR cinema)',
                "query_timestamp_utc": "2026-10-19T12:19:30Z",
                "stop_reason": "no_results",
            }
        )
        second_query["query_components"].update(
            {
                "director_value": None,
                "medium_terms": ["film", "cinema"],
            }
        )
        log["queries"].append(second_query)


def install_later_2_substitute(log: dict, bundle: dict) -> None:
    remove_candidate_for_slot(log, "S_ACADEMIC")
    source_query = copy.deepcopy(query_for(log, "R_LATER"))
    source_query.update(
        {
            "query_id": "query-template-r-later-2",
            "slot": "R_LATER_2",
            "hierarchy_step_id": "hierarchy-template-r-later-2-1",
            "resource_or_outlet": "Film at Lincoln Center / Film Comment",
            "query_sequence": 1,
            "query_timestamp_utc": "2026-10-19T12:26:00Z",
            "candidate_ids_and_ranks": [
                {"candidate_id": "candidate-template-r-later-2", "rank": 1}
            ],
        }
    )
    log["queries"].append(source_query)

    source_candidate = copy.deepcopy(candidate_for(log, "R_LATER"))
    source_candidate.update(
        {
            "candidate_id": "candidate-template-r-later-2",
            "slot": "R_LATER_2",
            "hierarchy_step_id": "hierarchy-template-r-later-2-1",
            "source_id": "source-template-r-later-2",
            "lineage_id": "lineage-template-r-later-2",
            "article_title": "Second Synthetic Retrospective Essay",
            "author_display": "Second Retrospective Critic Example",
            "author_id": "author-template-later-2",
            "outlet": "Film at Lincoln Center / Film Comment",
            "publisher": "Second Synthetic Institution Publisher",
            "database_document_id": "doc-template-r-later-2",
            "canonical_url": "https://example.org/source/r-later-2",
            "permalink_or_archive_locator": "synthetic-archive:r-later-2:1",
            "query_id": "query-template-r-later-2",
            "accessed_at_utc": "2026-10-19T12:27:00Z",
            "raw_sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
            "normalized_text_sha256": "6666666666666666666666666666666666666666666666666666666666666666",
        }
    )
    log["candidates"].append(source_candidate)
    add_independent_pair_checks(log, source_candidate["candidate_id"])

    bundle["slot_assignments"]["S_ACADEMIC"] = None
    bundle["slot_assignments"]["R_LATER_2"] = "candidate-template-r-later-2"
    bundle["unfilled_canonical_slots"] = ["S_ACADEMIC"]
    bundle["academic_search_disposition"] = "exhausted_no_eligible_source"
    bundle["scholarship_substitution"] = True


class RetrievalControlTests(unittest.TestCase):
    def test_all_schemas_are_valid_json_schema_documents(self) -> None:
        for name in (
            "archive-access-manifest.schema.json",
            "source-retrieval-log.schema.json",
            "frozen-source-bundle.schema.json",
        ):
            value = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
            self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(value.get("additionalProperties", True))

    def test_target_complete_templates_pass(self) -> None:
        manifest, log, bundle = example_triplet()
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.summary["computed_completion_status"], "target_complete")
        self.assertEqual(result.summary["assigned_source_count"], 5)

    def test_manifest_inventory_accounts_for_every_canonical_system(self) -> None:
        manifest, _, _ = example_triplet()
        self.assertEqual(len(manifest["source_system_inventory"]), 54)
        self.assertEqual(validate_archive_access_manifest(manifest), ())

        missing = inventory_for(manifest, "C_TRADE", "hollywood_reporter")
        manifest["source_system_inventory"].remove(missing)
        errors = validate_archive_access_manifest(manifest)
        self.assertIn(
            "missing explicit coverage/access disposition for C_TRADE/hollywood_reporter",
            " ".join(errors),
        )

    def test_manifest_rejects_duplicate_system_dispositions(self) -> None:
        manifest, _, _ = example_triplet()
        duplicate = copy.deepcopy(
            inventory_for(manifest, "C_TRADE", "hollywood_reporter")
        )
        duplicate["inventory_entry_id"] = "inventory-template-duplicate-hollywood-reporter"
        manifest["source_system_inventory"].append(duplicate)
        errors = validate_archive_access_manifest(manifest)
        self.assertIn("duplicate coverage/access disposition", " ".join(errors))

    def test_unavailable_or_no_coverage_disposition_requires_reason(self) -> None:
        manifest, _, _ = example_triplet()
        unavailable = inventory_for(manifest, "C_TRADE", "hollywood_reporter")
        unavailable["disposition_reason"] = None
        errors = validate_archive_access_manifest(manifest)
        self.assertIn("require a documented reason", " ".join(errors))

        manifest, _, _ = example_triplet()
        no_coverage = inventory_for(manifest, "C_TRADE", "hollywood_reporter")
        no_coverage.update(
            {
                "access_disposition": "available",
                "coverage_disposition": "no_coverage",
                "assessed_resource_ids": ["resource-template-open"],
                "coverage_intervals": [],
                "disposition_reason": "The dated title list documents no holdings in the applicable window.",
            }
        )
        self.assertEqual(validate_archive_access_manifest(manifest), ())
        no_coverage["disposition_reason"] = None
        errors = validate_archive_access_manifest(manifest)
        self.assertIn("require a documented reason", " ".join(errors))

    def test_coverage_disposition_and_intervals_cannot_contradict(self) -> None:
        manifest, _, _ = example_triplet()
        inventory = inventory_for(manifest, "C_TRADE", "variety")
        inventory["coverage_intervals"] = []
        errors = validate_archive_access_manifest(manifest)
        self.assertIn("requires at least one interval", " ".join(errors))

        manifest, _, _ = example_triplet()
        no_coverage = inventory_for(manifest, "C_TRADE", "hollywood_reporter")
        no_coverage.update(
            {
                "access_disposition": "available",
                "coverage_disposition": "no_coverage",
                "assessed_resource_ids": ["resource-template-open"],
                "coverage_intervals": copy.deepcopy(
                    inventory_for(manifest, "C_TRADE", "variety")["coverage_intervals"]
                ),
                "disposition_reason": "No holdings in the applicable window.",
            }
        )
        errors = validate_archive_access_manifest(manifest)
        self.assertIn("no_coverage must not claim coverage intervals", " ".join(errors))

    def test_coverage_interval_dates_issues_and_freeze_are_validated(self) -> None:
        manifest, _, _ = example_triplet()
        interval = inventory_for(manifest, "C_TRADE", "variety")[
            "coverage_intervals"
        ][0]
        interval["start_date"] = "2020-01-02"
        interval["end_date"] = "2020-01-01"
        interval["start_issue"] = "Vol. 1, no. 1"
        interval["checked_at"] = "2026-10-20"
        errors = validate_archive_access_manifest(manifest)
        joined = " ".join(errors)
        self.assertIn("start_date must not follow end_date", joined)
        self.assertIn("start_issue and end_issue", joined)
        self.assertIn("cannot postdate manifest freeze", joined)

        manifest, _, _ = example_triplet()
        inventory = inventory_for(manifest, "C_TRADE", "variety")
        interval = inventory["coverage_intervals"][0]
        interval["end_date"] = "2026-10-20"
        interval["checked_at"] = "2026-10-19"
        errors = validate_archive_access_manifest(manifest)
        self.assertIn("cannot extend beyond checked_at", " ".join(errors))

        manifest, _, _ = example_triplet()
        inventory = inventory_for(manifest, "C_TRADE", "variety")
        inventory["checked_at"] = "2026-10-18"
        errors = validate_archive_access_manifest(manifest)
        self.assertIn("cannot postdate its inventory disposition", " ".join(errors))

    def test_synopsis_inventory_uses_film_release_date_coverage(self) -> None:
        manifest, _, _ = example_triplet()
        interval = inventory_for(manifest, "P_SYNOPSIS", "afi_catalog")[
            "coverage_intervals"
        ][0]
        interval["date_dimension"] = "source_publication_or_issue_date"
        errors = validate_archive_access_manifest(manifest)
        self.assertIn(
            "slot P_SYNOPSIS requires 'film_release_date'", " ".join(errors)
        )

    def test_documented_available_coverage_requires_a_hierarchy_route(self) -> None:
        manifest, _, _ = example_triplet()
        step = next(
            item for item in manifest["search_hierarchy"] if item["slot"] == "C_TRADE"
        )
        manifest["search_hierarchy"].remove(step)
        errors = validate_archive_access_manifest(manifest)
        self.assertIn("lacks route", " ".join(errors))

    def test_hierarchy_route_cannot_override_unavailable_inventory(self) -> None:
        manifest, _, _ = example_triplet()
        inventory = inventory_for(manifest, "C_TRADE", "variety")
        inventory.update(
            {
                "access_disposition": "unavailable",
                "coverage_disposition": "not_verified",
                "assessed_resource_ids": [],
                "coverage_intervals": [],
                "disposition_reason": "No authorized route at manifest freeze.",
            }
        )
        errors = validate_archive_access_manifest(manifest)
        joined = " ".join(errors)
        self.assertIn("requires an available inventory access disposition", joined)
        self.assertIn("requires documented coverage intervals", joined)

    def test_query_route_must_have_coverage_relevant_to_film_window(self) -> None:
        manifest, log, bundle = example_triplet()
        interval = inventory_for(manifest, "C_TRADE", "variety")[
            "coverage_intervals"
        ][0]
        interval["start_date"] = "2000-01-01"
        interval["end_date"] = "2026-10-19"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("coverage relevant to this film", " ".join(result.errors))

    def test_irrelevant_coverage_does_not_create_a_query_obligation(self) -> None:
        manifest, log, bundle = example_triplet()
        interval = inventory_for(manifest, "C_TRADE", "variety")[
            "coverage_intervals"
        ][0]
        interval["start_date"] = "2000-01-01"
        interval["end_date"] = "2026-10-19"
        remove_candidate_for_slot(log, "C_TRADE")
        log["queries"].remove(query_for(log, "C_TRADE"))
        bundle["slot_assignments"]["C_TRADE"] = None
        bundle["unfilled_canonical_slots"] = ["C_TRADE"]
        bundle["completion_status"] = "ineligible"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertTrue(result.ok, result.errors)

    def test_selected_source_date_must_fall_inside_route_coverage(self) -> None:
        manifest, log, bundle = example_triplet()
        interval = inventory_for(manifest, "C_TRADE", "variety")[
            "coverage_intervals"
        ][0]
        interval["start_date"] = "1950-01-02"
        interval["end_date"] = "1950-02-01"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn(
            "source date is outside the frozen route's documented coverage interval",
            " ".join(result.errors),
        )

    def test_theme_loaded_or_untyped_query_terms_are_rejected(self) -> None:
        _, log, _ = example_triplet()
        query_for(log, "C_TRADE")["exact_query"] += " greed"
        errors = validate_source_retrieval_log(log)
        self.assertIn("prohibited theme term", " ".join(errors))

        _, log, _ = example_triplet()
        query_for(log, "C_TRADE")["sort_order"] = "most_selfish_first"
        errors = validate_source_retrieval_log(log)
        self.assertIn("allowed enumeration", " ".join(errors))

        _, log, _ = example_triplet()
        query_for(log, "C_TRADE")["exact_query"] += " жадность"
        errors = validate_source_retrieval_log(log)
        self.assertIn("untyped non-bibliographic term", " ".join(errors))

        _, log, _ = example_triplet()
        query_for(log, "C_TRADE")["exact_query"] += " wealth"
        errors = validate_source_retrieval_log(log)
        self.assertIn("untyped non-bibliographic term", " ".join(errors))

        _, log, _ = example_triplet()
        query_for(log, "C_TRADE")["filters"].append(
            {"name": "outlet", "value": "selfishness"}
        )
        errors = validate_source_retrieval_log(log)
        self.assertIn("prohibited theme term", " ".join(errors))

    def test_exact_query_must_render_its_typed_components(self) -> None:
        _, log, _ = example_triplet()
        query_for(log, "C_TRADE")["exact_query"] = "film"
        errors = validate_source_retrieval_log(log)
        self.assertIn("must contain the declared title_value", " ".join(errors))

    def test_every_screened_result_must_have_a_candidate_record(self) -> None:
        _, log, _ = example_triplet()
        query = query_for(log, "C_TRADE")
        query["unfiltered_result_count_reported"] = 2
        query["result_count_reported"] = 2
        query["results_screened"] = 2
        errors = validate_source_retrieval_log(log)
        self.assertIn("one record for every screened result", " ".join(errors))

        query["candidate_ids_and_ranks"][0]["rank"] = 2
        errors = validate_source_retrieval_log(log)
        self.assertIn("ranks must exactly cover", " ".join(errors))

    def test_theme_word_inside_frozen_title_is_not_a_false_positive(self) -> None:
        manifest, log, bundle = example_triplet()
        log["film_title"] = "Love Story"
        for query in log["queries"]:
            query["query_components"]["title_value"] = "Love Story"
            query["exact_query"] = query["exact_query"].replace("Example Film", "Love Story")
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertTrue(result.ok, result.errors)

    def test_query_components_must_match_the_declared_template_shape(self) -> None:
        _, log, _ = example_triplet()
        query_for(log, "C_TRADE")["query_components"]["document_terms"] = ["review"]
        errors = validate_source_retrieval_log(log)
        self.assertIn("document_terms: not allowed by query template", " ".join(errors))

        _, log, _ = example_triplet()
        query = query_for(log, "S_ACADEMIC")
        query["query_components"]["director_value"] = None
        errors = validate_source_retrieval_log(log)
        self.assertIn("director_value: required by query template", " ".join(errors))

    def test_full_screening_cap_is_recomputed_for_every_route(self) -> None:
        _, log, _ = example_triplet()
        query = query_for(log, "C_TRADE")
        query["unfiltered_result_count_reported"] = 50
        query["result_count_reported"] = 50
        query["results_screened"] = 1
        errors = validate_source_retrieval_log(log)
        self.assertIn("must equal min(result_count_reported, screening_cap)", " ".join(errors))

        _, log, _ = example_triplet()
        query = query_for(log, "C_TRADE")
        query["access_route"] = "open_web"
        candidate_for(log, "C_TRADE")["access_route"] = "open_web"
        query["screening_cap"] = 50
        errors = validate_source_retrieval_log(log)
        self.assertIn("must be 20", " ".join(errors))

    def test_post_count_filters_preserve_unfiltered_result_count(self) -> None:
        _, log, _ = example_triplet()
        query = query_for(log, "S_ACADEMIC")
        query["filters"].append({"name": "full_text", "value": "true"})
        query["unfiltered_result_count_reported"] = 0
        errors = validate_source_retrieval_log(log)
        self.assertIn("at least as large", " ".join(errors))

        query["unfiltered_result_count_reported"] = 2
        self.assertEqual(validate_source_retrieval_log(log), ())

    def test_selected_source_cannot_skip_an_earlier_required_system(self) -> None:
        manifest, log, bundle = example_triplet()
        selected_step = next(
            item for item in manifest["search_hierarchy"] if item["slot"] == "C_TRADE"
        )
        selected_step.update(
            {
                "source_system_code": "hollywood_reporter",
                "source_system_name": "The Hollywood Reporter",
                "system_rank": 2,
            }
        )
        query_for(log, "C_TRADE")["resource_or_outlet"] = "The Hollywood Reporter"
        candidate_for(log, "C_TRADE")["outlet"] = "The Hollywood Reporter"
        earlier_step = copy.deepcopy(selected_step)
        earlier_step.update(
            {
                "hierarchy_step_id": "hierarchy-template-c-trade-earlier",
                "source_system_code": "variety",
                "source_system_id": "system-template-trade-earlier",
                "source_system_name": "Variety",
                "system_rank": 1,
            }
        )
        manifest["search_hierarchy"].append(earlier_step)
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("search hierarchy", " ".join(result.errors))

    def test_search_cannot_continue_to_lower_priority_after_selection(self) -> None:
        manifest, log, bundle = example_triplet()
        base = next(item for item in manifest["search_hierarchy"] if item["slot"] == "C_TRADE")
        later = copy.deepcopy(base)
        later.update(
            {
                "hierarchy_step_id": "hierarchy-template-c-trade-later",
                "source_system_code": "hollywood_reporter",
                "source_system_id": "system-template-trade-later",
                "source_system_name": "The Hollywood Reporter",
                "system_rank": 2,
            }
        )
        manifest["search_hierarchy"].append(later)
        query = copy.deepcopy(query_for(log, "C_TRADE"))
        query.update(
            {
                "query_id": "query-template-c-trade-later",
                "hierarchy_step_id": later["hierarchy_step_id"],
                "resource_or_outlet": later["source_system_name"],
                "query_timestamp_utc": "2026-10-19T12:29:00Z",
                "unfiltered_result_count_reported": 0,
                "result_count_reported": 0,
                "results_screened": 0,
                "candidate_ids_and_ranks": [],
                "stop_reason": "no_results",
            }
        )
        log["queries"].append(query)
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("continued to a lower-priority route", " ".join(result.errors))

        query["query_timestamp_utc"] = "2026-10-19T12:20:30Z"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("before an earlier route was completed", " ".join(result.errors))

    def test_unfilled_canonical_slot_requires_every_available_route(self) -> None:
        manifest, log, bundle = example_triplet()
        remove_candidate_for_slot(log, "R_LATER")
        bundle["slot_assignments"]["R_LATER"] = None
        bundle["unfilled_canonical_slots"] = ["R_LATER"]
        bundle["completion_status"] = "minimum_complete"

        first_inventory = inventory_for(
            manifest, "R_LATER", "bfi_sight_and_sound"
        )
        second_inventory = inventory_for(
            manifest,
            "R_LATER",
            "film_at_lincoln_center_film_comment",
        )
        second_inventory.update(
            {
                "access_disposition": "available",
                "coverage_disposition": "documented_intervals",
                "assessed_resource_ids": copy.deepcopy(
                    first_inventory["assessed_resource_ids"]
                ),
                "coverage_intervals": copy.deepcopy(
                    first_inventory["coverage_intervals"]
                ),
                "disposition_reason": None,
            }
        )
        second_inventory["coverage_intervals"][0][
            "coverage_interval_id"
        ] = "coverage-template-r-later-second"

        first_step = next(
            item
            for item in manifest["search_hierarchy"]
            if item["slot"] == "R_LATER"
        )
        second_step = copy.deepcopy(first_step)
        second_step.update(
            {
                "hierarchy_step_id": "hierarchy-template-r-later-second",
                "source_system_code": "film_at_lincoln_center_film_comment",
                "source_system_id": "system-template-r-later-second",
                "source_system_name": "Film at Lincoln Center / Film Comment",
                "system_rank": 2,
            }
        )
        manifest["search_hierarchy"].append(second_step)

        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn(
            "unfilled canonical slot R_LATER",
            " ".join(result.errors),
        )
        self.assertIn("unattempted", " ".join(result.errors))

        def exhaustive_route_queries(
            step: dict,
            *,
            id_prefix: str,
            minute: int,
        ) -> list[dict]:
            base_query = copy.deepcopy(original_query)
            specs = (
                (
                    "title_only",
                    None,
                    [],
                    [],
                    '"Example Film"',
                ),
                (
                    "title_director",
                    "Example Director",
                    [],
                    [],
                    '"Example Film" "Example Director"',
                ),
                (
                    "title_medium_document",
                    None,
                    ["film"],
                    ["essay"],
                    '"Example Film" film essay',
                ),
            )
            queries = []
            for sequence, (
                template_id,
                director,
                medium_terms,
                document_terms,
                exact_query,
            ) in enumerate(specs, start=1):
                query = copy.deepcopy(base_query)
                query.update(
                    {
                        "query_id": f"{id_prefix}-{sequence}",
                        "hierarchy_step_id": step["hierarchy_step_id"],
                        "resource_or_outlet": step["source_system_name"],
                        "query_sequence": sequence,
                        "query_template_id": template_id,
                        "exact_query": exact_query,
                        "query_timestamp_utc": (
                            f"2026-10-19T12:{minute + sequence - 1:02d}:00Z"
                        ),
                    }
                )
                query["query_components"].update(
                    {
                        "director_value": director,
                        "medium_terms": medium_terms,
                        "document_terms": document_terms,
                    }
                )
                queries.append(query)
            return queries

        original_query = query_for(log, "R_LATER")
        log["queries"].remove(original_query)
        log["queries"].extend(
            exhaustive_route_queries(
                first_step,
                id_prefix="query-template-r-later-first",
                minute=18,
            )
        )
        log["queries"].extend(
            exhaustive_route_queries(
                second_step,
                id_prefix="query-template-r-later-second",
                minute=28,
            )
        )
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertTrue(result.ok, result.errors)

    def test_manifest_system_code_enforces_frozen_outlet_hierarchy(self) -> None:
        manifest, log, bundle = example_triplet()
        step = next(item for item in manifest["search_hierarchy"] if item["slot"] == "C_TRADE")
        step["source_system_name"] = "Personal Fan Blog"
        query_for(log, "C_TRADE")["resource_or_outlet"] = "Personal Fan Blog"
        candidate_for(log, "C_TRADE")["outlet"] = "Personal Fan Blog"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("source_system_code", " ".join(result.errors))

    def test_query_must_match_its_frozen_hierarchy_step(self) -> None:
        manifest, log, bundle = example_triplet()
        query_for(log, "C_TRADE")["hierarchy_step_id"] = "hierarchy-template-c-general-1"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("disagrees with hierarchy step", " ".join(result.errors))

    def test_deterministic_selection_rejects_arbitrary_eligible_choice(self) -> None:
        manifest, log, bundle = example_triplet()
        selected = candidate_for(log, "C_TRADE")
        better = copy.deepcopy(selected)
        better.update(
            {
                "candidate_id": "candidate-template-c-trade-better",
                "candidate_rank": 2,
                "selection_status": "eligible_not_selected",
                "source_id": "source-template-c-trade-better",
                "lineage_id": "lineage-template-c-trade-better",
                "article_title": "Earlier Synthetic Trade Review",
                "author_display": "Better Trade Critic",
                "author_id": "author-template-trade-better",
                "outlet": "Synthetic Trade Supplement",
                "publication_date": "1950-02-01",
                "database_document_id": "doc-template-c-trade-better",
                "canonical_url": "https://example.org/source/c-trade-better",
                "result_rank": 2,
                "raw_sha256": "9999999999999999999999999999999999999999999999999999999999999999",
                "normalized_text_sha256": "8888888888888888888888888888888888888888888888888888888888888888",
            }
        )
        log["candidates"].append(better)
        query = query_for(log, "C_TRADE")
        query["unfiltered_result_count_reported"] = 2
        query["result_count_reported"] = 2
        query["results_screened"] = 2
        query["candidate_ids_and_ranks"].append(
            {"candidate_id": better["candidate_id"], "rank": 2}
        )
        add_independent_pair_checks(log, better["candidate_id"])
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("deterministic selection", " ".join(result.errors))

    def test_pairwise_duplicate_thresholds_and_complete_coverage_are_enforced(self) -> None:
        _, log, _ = example_triplet()
        check = log["duplicate_checks"][0]
        check["estimated_jaccard"] = 0.95
        errors = validate_source_retrieval_log(log)
        self.assertIn("near_duplicate_same_lineage", " ".join(errors))

        _, log, _ = example_triplet()
        log["duplicate_checks"].pop()
        errors = validate_source_retrieval_log(log)
        self.assertIn("missing acquired-candidate pairs", " ".join(errors))

        _, log, _ = example_triplet()
        log["duplicate_checks"][0]["estimated_jaccard"] = None
        errors = validate_source_retrieval_log(log)
        self.assertIn("expected type", " ".join(errors))

    def test_common_synopsis_exception_cannot_override_shared_byline(self) -> None:
        _, log, _ = example_triplet()
        check = log["duplicate_checks"][0]
        check.update(
            {
                "estimated_jaccard": 0.9,
                "provenance_flags": ["common_embedded_synopsis", "shared_byline"],
                "classification": "independent",
                "lineage_disposition": "independent",
            }
        )
        errors = validate_source_retrieval_log(log)
        self.assertIn("provenance_dependent", " ".join(errors))

    def test_language_gate_requires_english_or_authorized_published_translation(self) -> None:
        manifest, log, bundle = example_triplet()
        candidate_for(log, "C_TRADE")["language"] = "fr"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("original-English source", " ".join(result.errors))

        manifest, log, bundle = example_triplet()
        translated = candidate_for(log, "C_TRADE")
        translated.update(
            {
                "language": "en",
                "original_language": "fr",
                "language_basis": "authorized_published_english_translation",
                "translation_reference": {
                    "citation": "Synthetic authorized published translation record.",
                    "public_url": "https://example.org/translation-record",
                    "verified_at_utc": "2026-10-19T12:29:00Z",
                },
            }
        )
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertTrue(result.ok, result.errors)

    def test_translation_authorization_cannot_postdate_bundle_freeze(self) -> None:
        manifest, log, bundle = example_triplet()
        translated = candidate_for(log, "C_TRADE")
        translated.update(
            {
                "language": "en",
                "original_language": "fr",
                "language_basis": "authorized_published_english_translation",
                "translation_reference": {
                    "citation": "Synthetic authorized translation record.",
                    "public_url": "https://example.org/translation-record",
                    "verified_at_utc": "2027-01-01T00:00:00Z",
                },
            }
        )
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("translation_reference", " ".join(result.errors))

    def test_retrieval_slot_maps_to_exact_downstream_source_type(self) -> None:
        self.assertIs(
            extraction_source_type_for_slot("C_TRADE"), SourceType.CONTEMPORARY_REVIEW
        )
        self.assertIs(
            extraction_source_type_for_slot("R_LATER"), SourceType.RETROSPECTIVE_ESSAY
        )
        manifest, log, bundle = example_triplet()
        candidate_for(log, "C_TRADE")["extraction_source_type"] = "scholarship"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("extraction_source_type", " ".join(result.errors))

    def test_public_locators_reject_credentials_and_private_hosts(self) -> None:
        manifest, log, bundle = example_triplet()
        candidate_for(log, "C_TRADE")["canonical_url"] = "https://user:pass@example.org/source"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("must not embed", " ".join(result.errors))

        manifest, log, _ = example_triplet()
        manifest["resources"][0]["documentation_urls"][0] = (
            "https://example.org/terms?access_token=secret"
        )
        errors = validate_archive_access_manifest(manifest)
        self.assertIn("credential-like", " ".join(errors))

        manifest, _, _ = example_triplet()
        manifest["resources"][0]["rights_references"][0]["public_url"] = (
            "http://127.0.0.1/private"
        )
        errors = validate_archive_access_manifest(manifest)
        self.assertIn("private, loopback", " ".join(errors))

    def test_manifest_and_bundle_chronology_is_enforced(self) -> None:
        manifest, log, bundle = example_triplet()
        manifest["frozen_at_utc"] = "2026-10-19T12:16:00Z"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("manifest must be frozen before retrieval", " ".join(result.errors))

        manifest, log, bundle = example_triplet()
        bundle["frozen_at_utc"] = "2026-10-19T12:20:00Z"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("cannot postdate bundle freeze", " ".join(result.errors))

    def test_selected_but_unassigned_candidate_is_an_error(self) -> None:
        manifest, log, bundle = example_triplet()
        bundle["slot_assignments"]["C_TRADE"] = None
        bundle["unfilled_canonical_slots"] = ["C_TRADE"]
        bundle["completion_status"] = "ineligible"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("selected candidates not assigned", " ".join(result.errors))

    def test_structured_rights_references_are_cross_checked(self) -> None:
        manifest, log, bundle = example_triplet()
        candidate_for(log, "C_TRADE")["processing_permission"]["rights_reference_ids"] = [
            "rights-not-in-resource"
        ]
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("unknown resource rights references", " ".join(result.errors))

        manifest, log, bundle = example_triplet()
        candidate_for(log, "C_TRADE")["processing_permission"]["basis_type"] = "open_license"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("requires processing basis_type", " ".join(result.errors))

    def test_film_identity_and_release_anchor_are_required(self) -> None:
        manifest, log, bundle = example_triplet()
        del log["film_title"]
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("film_title", " ".join(result.errors))

        manifest, log, bundle = example_triplet()
        candidate_for(log, "C_TRADE")["sampled_film_identity_verified"] = False
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("sampled_film_identity_verified", " ".join(result.errors))

    def test_frozen_bundle_requires_a_query_attempt_for_each_canonical_slot(self) -> None:
        manifest, log, bundle = example_triplet()
        academic_query = query_for(log, "S_ACADEMIC")
        log["queries"].remove(academic_query)
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("requires a query for S_ACADEMIC", " ".join(result.errors))

    def test_contemporary_date_window_is_inclusive_at_both_boundaries(self) -> None:
        anchor = date.fromisoformat("1950-02-01")
        for publication_date in (anchor - timedelta(days=30), anchor + timedelta(days=365)):
            with self.subTest(publication_date=publication_date):
                manifest, log, bundle = example_triplet()
                candidate = candidate_for(log, "C_TRADE")
                candidate["publication_date"] = publication_date.isoformat()
                candidate["date_window_status"] = "eligible"
                result = audit_frozen_source_bundle(bundle, log, manifest)
                self.assertTrue(result.ok, result.errors)

    def test_contemporary_date_just_outside_window_fails(self) -> None:
        manifest, log, bundle = example_triplet()
        candidate = candidate_for(log, "C_TRADE")
        candidate["publication_date"] = "1950-01-01"
        candidate["date_window_status"] = "outside"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("eligible candidate must be 'eligible'", " ".join(result.errors))

    def test_partial_dates_use_possible_interval_not_imputed_day(self) -> None:
        manifest, log, bundle = example_triplet()
        candidate = candidate_for(log, "R_LATER")
        candidate["publication_date"] = "1960-03"
        candidate["publication_date_precision"] = "month"
        candidate["date_window_status"] = "eligible"
        self.assertTrue(audit_frozen_source_bundle(bundle, log, manifest).ok)

        candidate["publication_date"] = "1952"
        candidate["publication_date_precision"] = "year"
        candidate["date_window_status"] = "ambiguous"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("eligible candidate must be 'eligible'", " ".join(result.errors))

    def test_later_and_academic_date_thresholds_are_enforced(self) -> None:
        anchor = date.fromisoformat("1950-02-01")
        later_threshold = anchor + timedelta(days=730)

        manifest, log, bundle = example_triplet()
        later = candidate_for(log, "R_LATER")
        later["publication_date"] = later_threshold.isoformat()
        later["date_window_status"] = "eligible"
        academic = candidate_for(log, "S_ACADEMIC")
        academic["publication_date"] = anchor.isoformat()
        academic["date_window_status"] = "eligible"
        academic["contemporary_scholarship"] = True
        self.assertTrue(audit_frozen_source_bundle(bundle, log, manifest).ok)

        later["publication_date"] = (later_threshold - timedelta(days=1)).isoformat()
        later["date_window_status"] = "outside"
        academic["publication_date"] = (anchor - timedelta(days=1)).isoformat()
        academic["date_window_status"] = "outside"
        academic["contemporary_scholarship"] = False
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("candidates[2].date_window_status", " ".join(result.errors))
        self.assertIn("candidates[3].date_window_status", " ".join(result.errors))

    def test_short_contemporary_review_requires_all_exception_evidence(self) -> None:
        manifest, log, bundle = example_triplet()
        candidate = candidate_for(log, "C_TRADE")
        candidate["word_count_total"] = 199
        candidate["word_count_relevant"] = 199
        candidate["contemporary_short_review_exception"] = {
            "provider_labels_item_as_review": True,
            "complete_editorial_item_verified": True,
            "declared_before_theme_extraction": True,
            "documentation": "Provider label and complete scanned item verified in metadata review.",
        }
        self.assertTrue(audit_frozen_source_bundle(bundle, log, manifest).ok)

        candidate["contemporary_short_review_exception"] = None
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("100-199 word contemporary review", " ".join(result.errors))

        candidate["word_count_total"] = 99
        candidate["word_count_relevant"] = 99
        candidate["contemporary_short_review_exception"] = {
            "provider_labels_item_as_review": True,
            "complete_editorial_item_verified": True,
            "declared_before_theme_extraction": True,
            "documentation": "Complete item verified.",
        }
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("at least 100 words", " ".join(result.errors))

    def test_later_essay_requires_both_total_and_relevant_minima(self) -> None:
        manifest, log, bundle = example_triplet()
        later = candidate_for(log, "R_LATER")
        later["word_count_total"] = 600
        later["word_count_relevant"] = 400
        self.assertTrue(audit_frozen_source_bundle(bundle, log, manifest).ok)

        later["word_count_total"] = 599
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("600 words total", " ".join(result.errors))

        later["word_count_total"] = 600
        later["word_count_relevant"] = 399
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("400 relevant words", " ".join(result.errors))

    def test_academic_length_allows_words_or_three_continuous_pages(self) -> None:
        manifest, log, bundle = example_triplet()
        academic = candidate_for(log, "S_ACADEMIC")
        academic["word_count_relevant"] = 999
        academic["continuous_relevant_pages"] = 3
        self.assertTrue(audit_frozen_source_bundle(bundle, log, manifest).ok)

        academic["continuous_relevant_pages"] = 2
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("1,000 relevant words or three", " ".join(result.errors))

        academic["word_count_relevant"] = 1000
        academic["continuous_relevant_pages"] = None
        self.assertTrue(audit_frozen_source_bundle(bundle, log, manifest).ok)

    def test_synopsis_requires_300_relevant_words(self) -> None:
        manifest, log, bundle = example_triplet()
        synopsis = candidate_for(log, "P_SYNOPSIS")
        synopsis["word_count_relevant"] = 299
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("synopsis requires at least 300 words", " ".join(result.errors))

    def test_valid_r_later_2_substitution_passes(self) -> None:
        manifest, log, bundle = example_triplet()
        install_later_2_substitute(log, bundle)
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertTrue(result.ok, result.errors)
        self.assertTrue(result.summary["scholarship_substitution"])
        self.assertEqual(result.summary["computed_completion_status"], "target_complete")

    def test_four_source_hard_minimum_passes_but_warns(self) -> None:
        manifest, log, bundle = example_triplet()
        remove_candidate_for_slot(log, "S_ACADEMIC")
        bundle["slot_assignments"]["S_ACADEMIC"] = None
        bundle["unfilled_canonical_slots"] = ["S_ACADEMIC"]
        bundle["academic_search_disposition"] = "exhausted_no_eligible_source"
        bundle["completion_status"] = "minimum_complete"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.summary["assigned_source_count"], 4)
        self.assertIn("hard four-source minimum", " ".join(result.warnings))

    def test_missing_contemporary_slot_fails_hard_minimum(self) -> None:
        manifest, log, bundle = example_triplet()
        bundle["slot_assignments"]["C_GENERAL"] = None
        bundle["unfilled_canonical_slots"] = ["C_GENERAL"]
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertEqual(result.summary["computed_completion_status"], "ineligible")
        self.assertIn("completion_status", " ".join(result.errors))

    def test_rights_class_and_processing_environment_are_gates(self) -> None:
        for mutation, expected in (
            (
                lambda candidate: candidate.update({"rights_class": "rights_unknown"}),
                "rights_class",
            ),
            (
                lambda candidate: candidate["processing_permission"].update(
                    {"environment_id": "different-environment"}
                ),
                "item-level permission",
            ),
        ):
            with self.subTest(expected=expected):
                manifest, log, bundle = example_triplet()
                mutation(candidate_for(log, "C_TRADE"))
                result = audit_frozen_source_bundle(bundle, log, manifest)
                self.assertFalse(result.ok)
                self.assertIn(expected, " ".join(result.errors))

    def test_resource_permission_is_a_separate_gate(self) -> None:
        manifest, log, bundle = example_triplet()
        resource = manifest["resources"][0]
        resource["model_processing_permission"] = "prohibited"
        resource["allowed_environment_ids"] = []
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("resource model-processing permission", " ".join(result.errors))

    def test_workbench_only_text_requires_workbench_environment(self) -> None:
        manifest, log, bundle = example_triplet()
        resource = manifest["resources"][0]
        resource["full_text_acquisition"] = "provider_workbench"
        resource["storage_permission"] = "provider_workbench_only"
        for candidate in log["candidates"]:
            candidate["acquisition_status"] = "provider_workbench_only"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("provider_workbench extraction environment", " ".join(result.errors))

    def test_storage_and_export_permissions_are_inclusion_gates(self) -> None:
        manifest, log, bundle = example_triplet()
        resource = manifest["resources"][0]
        resource["storage_permission"] = "none"
        resource["export_permission"] = "none"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        joined = " ".join(result.errors)
        self.assertIn("auditable source/evidence store", joined)
        self.assertIn("reviewed evidence excerpts", joined)

    def test_independence_rejects_shared_author_outlet_lineage_or_hash(self) -> None:
        for field in (
            "author_id",
            "outlet",
            "lineage_id",
            "normalized_text_sha256",
        ):
            with self.subTest(field=field):
                manifest, log, bundle = example_triplet()
                trade = candidate_for(log, "C_TRADE")
                general = candidate_for(log, "C_GENERAL")
                general[field] = trade[field]
                result = audit_frozen_source_bundle(bundle, log, manifest)
                self.assertFalse(result.ok)
                self.assertIn(f"repeated {field}", " ".join(result.errors))

    def test_only_frozen_exclusion_reason_codes_are_accepted(self) -> None:
        _, log, _ = example_triplet()
        candidate = candidate_for(log, "C_TRADE")
        candidate["selection_status"] = "excluded"
        candidate["exclusion_reason"] = "theme_not_useful"
        errors = validate_source_retrieval_log(log)
        self.assertIn("allowed enumeration", " ".join(errors))

    def test_objective_exclusion_reasons_cannot_contradict_metadata(self) -> None:
        _, log, _ = example_triplet()
        candidate = candidate_for(log, "C_TRADE")
        candidate["selection_status"] = "excluded"
        candidate["exclusion_reason"] = "outside_date_window"
        query_for(log, "C_TRADE")["stop_reason"] = "completed_without_eligible_candidate"
        errors = validate_source_retrieval_log(log)
        self.assertIn("requires date_window_status='outside'", " ".join(errors))

    def test_frozen_query_cannot_retain_pending_candidates(self) -> None:
        manifest, log, bundle = example_triplet()
        candidate_for(log, "C_TRADE")["selection_status"] = "pending"
        query_for(log, "C_TRADE")["stop_reason"] = "resource_exhausted"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("pending", " ".join(result.errors))

    def test_other_predefined_requires_detail_code(self) -> None:
        _, log, _ = example_triplet()
        candidate = candidate_for(log, "C_TRADE")
        candidate["selection_status"] = "excluded"
        candidate["exclusion_reason"] = "other_predefined"
        errors = validate_source_retrieval_log(log)
        self.assertIn("exclusion_detail_code", " ".join(errors))

        candidate["exclusion_detail_code"] = "invented_after_screening"
        errors = validate_source_retrieval_log(log)
        self.assertIn("allowed enumeration", " ".join(errors))

    def test_eligibility_ambiguous_is_a_frozen_non_thematic_reason(self) -> None:
        _, log, _ = example_triplet()
        candidate = candidate_for(log, "C_TRADE")
        candidate["selection_status"] = "excluded"
        candidate["exclusion_reason"] = "eligibility_ambiguous"
        query = query_for(log, "C_TRADE")
        query["stop_reason"] = "completed_without_eligible_candidate"
        errors = validate_source_retrieval_log(log)
        self.assertEqual(errors, ())

    def test_r_later_2_cannot_coexist_with_academic_source(self) -> None:
        manifest, log, bundle = example_triplet()
        substitute = copy.deepcopy(candidate_for(log, "R_LATER"))
        substitute.update(
            {
                "candidate_id": "candidate-template-r-later-2",
                "slot": "R_LATER_2",
                "source_id": "source-template-r-later-2",
                "lineage_id": "lineage-template-r-later-2",
                "author_id": "author-template-r-later-2",
                "outlet": "Second Retrospective Outlet",
                "query_id": "query-template-r-later-2",
                "raw_sha256": "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
                "normalized_text_sha256": "6666666666666666666666666666666666666666666666666666666666666666",
            }
        )
        query = copy.deepcopy(query_for(log, "R_LATER"))
        query.update(
            {
                "query_id": "query-template-r-later-2",
                "slot": "R_LATER_2",
                "candidate_ids_and_ranks": [
                    {"candidate_id": "candidate-template-r-later-2", "rank": 1}
                ],
            }
        )
        log["queries"].append(query)
        log["candidates"].append(substitute)
        bundle["slot_assignments"]["R_LATER_2"] = "candidate-template-r-later-2"
        bundle["scholarship_substitution"] = True
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("cannot coexist", " ".join(result.errors))

    def test_tier_three_retrospective_must_be_flagged_commercial_curatorial(self) -> None:
        manifest, log, bundle = example_triplet()
        step = next(item for item in manifest["search_hierarchy"] if item["slot"] == "R_LATER")
        step.update(
            {
                "source_system_code": "criterion_current",
                "source_system_name": "Criterion Current",
                "system_tier": 3,
                "system_rank": 1,
            }
        )
        query_for(log, "R_LATER")["resource_or_outlet"] = "Criterion Current"
        candidate_for(log, "R_LATER")["outlet"] = "Criterion Current"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("commercial_curatorial", " ".join(result.errors))

    def test_substitution_requires_logged_completed_academic_search(self) -> None:
        manifest, log, bundle = example_triplet()
        install_later_2_substitute(log, bundle)
        academic_query = query_for(log, "S_ACADEMIC")
        academic_query["stop_reason"] = "access_blocked"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("all accessible scholarly systems and routes", " ".join(result.errors))

    def test_substitution_cannot_follow_only_one_failed_academic_query(self) -> None:
        manifest, log, bundle = example_triplet()
        install_later_2_substitute(log, bundle)
        second_query = next(
            item for item in log["queries"] if item["query_id"] == "query-template-s-academic-2"
        )
        log["queries"].remove(second_query)
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertFalse(result.ok)
        self.assertIn("all accessible scholarly systems and routes", " ".join(result.errors))

    def test_secret_and_source_text_fields_are_forbidden(self) -> None:
        manifest, log, _ = example_triplet()
        manifest["api_key"] = "do-not-store-this"
        candidate_for(log, "C_TRADE")["full_text"] = "do not store source text"
        self.assertIn("credential or secret", " ".join(validate_archive_access_manifest(manifest)))
        self.assertIn("source full-text", " ".join(validate_source_retrieval_log(log)))

        manifest, log, _ = example_triplet()
        manifest["notes"] = "Authorization: Bearer SECRET_TOKEN_VALUE"
        log["notes"] = "Full subscriber article pasted below."
        self.assertIn("credential-like value", " ".join(validate_archive_access_manifest(manifest)))
        self.assertIn("source-text paste marker", " ".join(validate_source_retrieval_log(log)))

    def test_short_title_queries_require_director_and_year(self) -> None:
        _, log, _ = example_triplet()
        log["film_title"] = "It"
        for query in log["queries"]:
            query["query_components"]["title_value"] = "It"
            query["exact_query"] = query["exact_query"].replace("Example Film", "It")
        errors = validate_source_retrieval_log(log)
        self.assertIn("short titles require short_title", " ".join(errors))

        log["identity_disambiguation_flags"] = ["short_title"]
        errors = validate_source_retrieval_log(log)
        self.assertIn("require director_value and release_year", " ".join(errors))

    def test_no_query_is_required_when_a_slot_has_no_available_route(self) -> None:
        manifest, log, bundle = example_triplet()
        unavailable = copy.deepcopy(manifest["resources"][0])
        unavailable.update(
            {
                "resource_id": "resource-template-unavailable-trade",
                "access_status": "unavailable",
                "full_text_acquisition": "not_available",
                "tdm_permission": "unknown",
                "model_processing_permission": "unknown",
                "allowed_environment_ids": [],
            }
        )
        manifest["resources"].append(unavailable)
        step = next(item for item in manifest["search_hierarchy"] if item["slot"] == "C_TRADE")
        manifest["search_hierarchy"].remove(step)
        inventory = inventory_for(manifest, "C_TRADE", "variety")
        inventory.update(
            {
                "access_disposition": "unavailable",
                "coverage_disposition": "not_verified",
                "assessed_resource_ids": [unavailable["resource_id"]],
                "coverage_intervals": [],
                "disposition_reason": "No authorized route was available at manifest freeze.",
            }
        )
        remove_candidate_for_slot(log, "C_TRADE")
        log["queries"].remove(query_for(log, "C_TRADE"))
        bundle["slot_assignments"]["C_TRADE"] = None
        bundle["unfilled_canonical_slots"] = ["C_TRADE"]
        bundle["completion_status"] = "ineligible"
        result = audit_frozen_source_bundle(bundle, log, manifest)
        self.assertTrue(result.ok, result.errors)

    def test_loader_rejects_duplicate_json_keys(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            path.write_text('{"manifest_id": "one", "manifest_id": "two"}', encoding="utf-8")
            with self.assertRaisesRegex(MetadataError, "duplicate JSON key"):
                load_json(path)


if __name__ == "__main__":
    unittest.main()
