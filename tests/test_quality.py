from __future__ import annotations

import hashlib
import unittest
from dataclasses import replace

from film_values import (
    EndingResponse,
    FilmStance,
    NarrativeSegment,
    SourceSalience,
    SourceStance,
    SourceType,
    Theme,
)
from film_values.aggregate import FilmThemeScore, SourceVote
from film_values.quality import (
    AssignedSourceAgreement,
    FROZEN_PILOT_PERIODS,
    GateResult,
    GateStatus,
    LateRetributionRun,
    ManifestSource,
    MechanicalGateInputs,
    NegativeControlAssignment,
    NegativeControlKind,
    NegativeControlResult,
    OmissionRun,
    PilotDecision,
    PilotValidationManifest,
    SensitivityAssessment,
    SensitivitySection,
    SourceAgreement,
    SourceSlot,
    ThirdPassUnit,
    ValidationFilm,
    compare_film_scores,
    compare_late_retribution,
    compare_leave_one_source_out,
    compare_source_votes,
    evaluate_film_repeatability,
    evaluate_mechanical_gates,
    evaluate_pilot,
    evaluate_source_repeatability,
    negative_control_assignment_digest,
    summarize_negative_controls,
    summarize_period_agreements,
    summarize_source_agreements,
    summarize_third_pass,
)


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


SLOTS = (
    SourceSlot.C_TRADE,
    SourceSlot.C_GENERAL,
    SourceSlot.R_LATER,
    SourceSlot.P_SYNOPSIS,
)
SLOT_TYPES = {
    SourceSlot.C_TRADE: SourceType.CONTEMPORARY_REVIEW,
    SourceSlot.C_GENERAL: SourceType.CONTEMPORARY_REVIEW,
    SourceSlot.R_LATER: SourceType.RETROSPECTIVE_ESSAY,
    SourceSlot.S_ACADEMIC: SourceType.SCHOLARSHIP,
    SourceSlot.P_SYNOPSIS: SourceType.REFERENCE_SYNOPSIS,
    SourceSlot.R_LATER_2: SourceType.RETROSPECTIVE_ESSAY,
}


def source_for(film_id: str, slot: SourceSlot) -> ManifestSource:
    source_id = f"{film_id}-{slot.value.lower()}"
    return ManifestSource(
        source_id=source_id,
        lineage_id=f"lineage-{source_id}",
        slot=slot,
        source_type=SLOT_TYPES[slot],
        content_hash=sha(f"content-{source_id}"),
        permission_basis="licensed research access",
        permitted_model_environments=frozenset({"secure-local"}),
        processing_permitted=True,
        eligibility_verified=True,
    )


def base_films() -> tuple[ValidationFilm, ...]:
    return tuple(
        ValidationFilm(
            film_id=f"film-{number}",
            period=period,
            untouched=True,
            selection_log_hash=sha(f"selection-{number}"),
            bundle_hash=sha(f"bundle-{number}"),
            sources=tuple(source_for(f"film-{number}", slot) for slot in SLOTS),
        )
        for number, period in enumerate(FROZEN_PILOT_PERIODS, start=1)
    )


def control_assignments(
    films: tuple[ValidationFilm, ...],
) -> tuple[NegativeControlAssignment, ...]:
    target_by_film = {
        film.film_id: films[(index + 1) % len(films)].film_id
        for index, film in enumerate(films)
    }
    assignments = []
    for film in films:
        for source in film.sources:
            assignments.extend(
                (
                    NegativeControlAssignment(
                        assignment_id=f"corrupt-{source.source_id}",
                        source_id=source.source_id,
                        kind=NegativeControlKind.CORRUPTED_QUOTATION,
                        source_film_id=film.film_id,
                        target_film_id=film.film_id,
                        source_content_hash=source.content_hash,
                        intervention_hash=sha(f"corrupt-{source.source_id}"),
                        target_unmentioned_verified=False,
                    ),
                    NegativeControlAssignment(
                        assignment_id=f"wrong-{source.source_id}",
                        source_id=source.source_id,
                        kind=NegativeControlKind.WRONG_FILM,
                        source_film_id=film.film_id,
                        target_film_id=target_by_film[film.film_id],
                        source_content_hash=source.content_hash,
                        intervention_hash=sha(f"wrong-{source.source_id}"),
                        target_unmentioned_verified=True,
                    ),
                )
            )
    return tuple(assignments)


def manifest_and_assignments() -> tuple[
    PilotValidationManifest, tuple[NegativeControlAssignment, ...]
]:
    films = base_films()
    assignments = control_assignments(films)
    manifest = PilotValidationManifest(
        films=films,
        pipeline_frozen_hash=sha("pipeline-v1"),
        control_assignment_set_hash=negative_control_assignment_digest(assignments),
        frozen_before_validation=True,
    )
    return manifest, assignments


def source_vote(
    film_id: str,
    source: ManifestSource,
    theme: Theme = Theme.SELFISHNESS,
    *,
    stance: SourceStance = SourceStance.AFFIRMATIVE,
    narrative_segment: NarrativeSegment = NarrativeSegment.MAIN_BODY,
    ending_responses: frozenset[EndingResponse] = frozenset(),
) -> SourceVote:
    return SourceVote(
        film_id=film_id,
        source_id=source.source_id,
        lineage_id=source.lineage_id,
        source_type=source.source_type,
        theme=theme,
        narrative_segment=narrative_segment,
        salience=SourceSalience.IMPORTANT,
        stance=stance,
        ending_responses=ending_responses,
        evidence_count=1,
    )


def assigned_agreements(
    manifest: PilotValidationManifest,
) -> tuple[AssignedSourceAgreement, ...]:
    assigned = []
    for film in manifest.films:
        for source in film.sources:
            main_vote = source_vote(
                film.film_id,
                source,
                stance=(
                    SourceStance.UNSTATED
                    if source.source_type is SourceType.REFERENCE_SYNOPSIS
                    else SourceStance.AFFIRMATIVE
                ),
            )
            ending_vote = source_vote(
                film.film_id,
                source,
                stance=(
                    SourceStance.UNSTATED
                    if source.source_type is SourceType.REFERENCE_SYNOPSIS
                    else SourceStance.CRITICAL
                ),
                narrative_segment=NarrativeSegment.ENDING,
                ending_responses=frozenset(
                    {EndingResponse.EXTERNAL_PUNISHMENT_ONLY}
                ),
            )
            assigned.append(
                AssignedSourceAgreement(
                    period=film.period,
                    agreement=compare_source_votes(
                        [main_vote, ending_vote],
                        [main_vote, ending_vote],
                        film_id=film.film_id,
                        source=source,
                    ),
                )
            )
    return tuple(assigned)


def zero_score(film_id: str, theme: Theme, segment: NarrativeSegment) -> FilmThemeScore:
    return FilmThemeScore(
        film_id=film_id,
        theme=theme,
        narrative_segment=segment,
        centrality=0,
        stance=FilmStance.NOT_EVIDENCED,
        supporting_lineages=0,
        affirmative_votes=0,
        critical_votes=0,
        mixed_votes=0,
        unstated_votes=0,
        ending_responses=frozenset(),
    )


def full_scores(manifest: PilotValidationManifest) -> tuple[FilmThemeScore, ...]:
    scores = []
    for film_id in sorted(manifest.film_ids):
        for theme in Theme:
            for segment in NarrativeSegment:
                score = zero_score(film_id, theme, segment)
                if theme is Theme.SELFISHNESS and segment is NarrativeSegment.MAIN_BODY:
                    score = replace(
                        score,
                        centrality=2,
                        stance=FilmStance.AFFIRMATIVE,
                        supporting_lineages=4,
                        affirmative_votes=3,
                        unstated_votes=1,
                    )
                elif theme is Theme.SELFISHNESS and segment is NarrativeSegment.ENDING:
                    score = replace(
                        score,
                        centrality=2,
                        stance=FilmStance.CRITICAL,
                        supporting_lineages=4,
                        critical_votes=3,
                        unstated_votes=1,
                        ending_responses=frozenset(
                            {EndingResponse.EXTERNAL_PUNISHMENT_ONLY}
                        ),
                    )
                scores.append(score)
    return tuple(scores)


def late_run(
    manifest: PilotValidationManifest,
    replicate_id: str,
    *,
    flags: frozenset[tuple[str, Theme]] | None = None,
    assessed: frozenset[tuple[str, Theme]] | None = None,
) -> LateRetributionRun:
    all_cells = frozenset(
        (film_id, theme) for film_id in manifest.film_ids for theme in Theme
    )
    if flags is None:
        flags = frozenset(
            (film_id, Theme.SELFISHNESS) for film_id in manifest.film_ids
        )
    return LateRetributionRun(
        replicate_id=replicate_id,
        assessed_cells=all_cells if assessed is None else assessed,
        flagged_cells=flags,
        calculation_record_hash=sha(f"late-{replicate_id}"),
    )


def omission_runs(
    manifest: PilotValidationManifest,
    scores: tuple[FilmThemeScore, ...],
) -> tuple[OmissionRun, ...]:
    runs = []
    for source_id in sorted(manifest.eligible_source_ids):
        included = manifest.eligible_source_ids - {source_id}
        film, omitted_source = manifest.source_index[source_id]
        omission_scores = []
        for score in scores:
            if (
                score.film_id != film.film_id
                or score.theme is not Theme.SELFISHNESS
                or score.narrative_segment
                not in {NarrativeSegment.MAIN_BODY, NarrativeSegment.ENDING}
            ):
                omission_scores.append(score)
                continue
            if omitted_source.source_type is SourceType.REFERENCE_SYNOPSIS:
                omission_scores.append(
                    replace(
                        score,
                        supporting_lineages=3,
                        affirmative_votes=(
                            3
                            if score.narrative_segment is NarrativeSegment.MAIN_BODY
                            else 0
                        ),
                        critical_votes=(
                            3
                            if score.narrative_segment is NarrativeSegment.ENDING
                            else 0
                        ),
                        unstated_votes=0,
                    )
                )
            else:
                omission_scores.append(
                    replace(
                        score,
                        supporting_lineages=3,
                        affirmative_votes=(
                            2
                            if score.narrative_segment is NarrativeSegment.MAIN_BODY
                            else 0
                        ),
                        critical_votes=(
                            2
                            if score.narrative_segment is NarrativeSegment.ENDING
                            else 0
                        ),
                        unstated_votes=1,
                    )
                )
        omission_score_tuple = tuple(omission_scores)
        runs.append(
            OmissionRun(
                omitted_source_id=source_id,
                included_source_ids_left=included,
                included_source_ids_right=included,
                left_scores=omission_score_tuple,
                right_scores=omission_score_tuple,
                left_late_retribution=late_run(
                    manifest, f"omit-left-{source_id}"
                ),
                right_late_retribution=late_run(
                    manifest, f"omit-right-{source_id}"
                ),
                upstream_provenance_verified=True,
                provenance_verification_hash=sha(f"omit-proof-{source_id}"),
            )
        )
    return tuple(runs)


def mechanical_inputs(manifest: PilotValidationManifest) -> MechanicalGateInputs:
    source_ids = manifest.eligible_source_ids
    accepted_records = len(source_ids) * 2
    return MechanicalGateInputs(
        processed_source_ids=source_ids,
        actual_model_environment="secure-local",
        public_repository_scan_verified=True,
        publicly_committed_credentials=0,
        publicly_committed_restricted_full_texts=0,
        publicly_committed_unlicensed_corpora=0,
        accepted_records=accepted_records,
        accepted_record_source_ids=source_ids,
        schema_valid_records=accepted_records,
        provenance_complete_records=accepted_records,
        exact_evidence_records=accepted_records,
        ending_cells_assessed=len(manifest.film_ids) * len(Theme),
        late_retribution_results=len(manifest.film_ids),
        late_retribution_results_with_separate_evidence=len(manifest.film_ids),
        external_punishment_only_main_stance_changes=0,
    )


def sensitivity(manifest: PilotValidationManifest) -> SensitivityAssessment:
    return SensitivityAssessment(
        manifest_digest=manifest.digest,
        report_hash=sha("sensitivity-report"),
        completed_sections=frozenset(SensitivitySection),
        review_completed=True,
        systematic_period_failure=False,
        pervasive_one_source_dependence=False,
        model_source_interaction_failure=False,
    )


def complete_reports():
    manifest, assignments = manifest_and_assignments()
    assigned = assigned_agreements(manifest)
    source_report = evaluate_source_repeatability(
        manifest, assigned, third_pass_units=()
    )
    scores = full_scores(manifest)
    baseline_left_late = late_run(manifest, "baseline-left")
    baseline_right_late = late_run(manifest, "baseline-right")
    agreement = compare_film_scores(scores, scores, manifest=manifest)
    late = compare_late_retribution(
        baseline_left_late,
        baseline_right_late,
        manifest=manifest,
        left_scores=scores,
        right_scores=scores,
    )
    leave_one_out = compare_leave_one_source_out(
        omission_runs(manifest, scores),
        manifest=manifest,
        baseline_left_scores=scores,
        baseline_right_scores=scores,
        baseline_left_late_retribution=baseline_left_late,
        baseline_right_late_retribution=baseline_right_late,
    )
    film_report = evaluate_film_repeatability(agreement, late, leave_one_out)
    controls = summarize_negative_controls(
        manifest,
        assignments,
        tuple(
            NegativeControlResult(item.assignment_id, item.digest, 0)
            for item in assignments
        ),
    )
    mechanical = evaluate_mechanical_gates(manifest, mechanical_inputs(manifest))
    return (
        manifest,
        assignments,
        mechanical,
        controls,
        source_report,
        film_report,
        sensitivity(manifest),
    )


class SourceAgreementTests(unittest.TestCase):
    def test_both_empty_does_not_create_perfect_agreement(self) -> None:
        manifest, _ = manifest_and_assignments()
        film = manifest.films[0]
        agreement = compare_source_votes(
            [], [], film_id=film.film_id, source=film.sources[0]
        )
        self.assertIsNone(agreement.positive_jaccard)
        summary = summarize_source_agreements([agreement])
        self.assertEqual(summary.both_empty_sources, 1)
        self.assertEqual(summary.both_empty_rate, 1.0)

    def test_jaccard_and_polarity_use_positive_units(self) -> None:
        manifest, _ = manifest_and_assignments()
        film = manifest.films[0]
        source = film.sources[0]
        left = [
            source_vote(film.film_id, source, Theme.SELFISHNESS),
            source_vote(film.film_id, source, Theme.REVENGE),
        ]
        right = [
            source_vote(
                film.film_id,
                source,
                Theme.SELFISHNESS,
                stance=SourceStance.CRITICAL,
            ),
            source_vote(film.film_id, source, Theme.FREEDOM_AUTONOMY),
        ]
        agreement = compare_source_votes(
            left, right, film_id=film.film_id, source=source
        )
        self.assertAlmostEqual(agreement.positive_jaccard or 0, 1 / 3)
        self.assertEqual(agreement.direct_polarity_flips, 1)

    def test_identity_anchor_rejects_wrong_film(self) -> None:
        manifest, _ = manifest_and_assignments()
        film = manifest.films[0]
        source = film.sources[0]
        valid = source_vote(film.film_id, source)
        with self.assertRaisesRegex(ValueError, "film_id"):
            compare_source_votes(
                [valid],
                [replace(valid, film_id="different-film")],
                film_id=film.film_id,
                source=source,
            )

    def test_reference_synopsis_cannot_supply_a_stance_vote(self) -> None:
        manifest, _ = manifest_and_assignments()
        film = manifest.films[0]
        synopsis = next(
            source
            for source in film.sources
            if source.source_type is SourceType.REFERENCE_SYNOPSIS
        )
        directional = source_vote(film.film_id, synopsis)
        with self.assertRaisesRegex(ValueError, "may not supply film stance"):
            compare_source_votes(
                [directional],
                [directional],
                film_id=film.film_id,
                source=synopsis,
            )

    def test_strict_dto_invariants_reject_impossible_values(self) -> None:
        with self.assertRaises(TypeError):
            GateResult("gate", "fail", 1, "criterion")  # type: ignore[arg-type]
        unit = (Theme.SELFISHNESS, NarrativeSegment.MAIN_BODY)
        with self.assertRaisesRegex(ValueError, "jointly proposed"):
            SourceAgreement(
                source_id="s",
                film_id="f",
                lineage_id="l",
                source_content_hash=sha("source"),
                source_slot=SourceSlot.C_TRADE,
                source_type=SourceType.CONTEMPORARY_REVIEW,
                left_votes=(),
                right_votes=(),
                left_units=frozenset(),
                right_units=frozenset(),
                salience_exact_units=frozenset({unit}),
                stance_exact_units=frozenset(),
                direct_polarity_flip_units=frozenset(),
            )


class SourceGateTests(unittest.TestCase):
    def test_periods_are_frozen_and_empty_period_is_not_evaluable(self) -> None:
        manifest, _ = manifest_and_assignments()
        item = assigned_agreements(manifest)[0]
        periods = summarize_period_agreements([item])
        self.assertEqual(tuple(value.period for value in periods), FROZEN_PILOT_PERIODS)
        self.assertEqual(periods[1].gate.status, GateStatus.NOT_EVALUABLE)
        with self.assertRaises(ValueError):
            summarize_period_agreements([item], ["early"])

    def test_third_pass_denominator_is_derived_and_integrity_checked(self) -> None:
        manifest, _ = manifest_and_assignments()
        assigned = assigned_agreements(manifest)
        report = evaluate_source_repeatability(
            manifest, assigned, third_pass_units=()
        )
        self.assertEqual(report.third_pass.proposed_union_units, len(assigned) * 2)
        self.assertEqual(report.third_pass.fraction, 0.0)

        first = assigned[0]
        invalid = ThirdPassUnit(
            source_id=first.source_id,
            film_id=first.film_id,
            theme=Theme.REVENGE,
            narrative_segment=NarrativeSegment.ENDING,
            selected_existing_span_verified=False,
            verification_record_hash=sha("third-pass"),
        )
        report = evaluate_source_repeatability(
            manifest, assigned, third_pass_units=(invalid,)
        )
        self.assertEqual(report.third_pass.integrity_gate.status, GateStatus.FAIL)

    def test_source_report_must_match_frozen_content_hash_and_slot(self) -> None:
        manifest, _ = manifest_and_assignments()
        assigned = list(assigned_agreements(manifest))
        assigned[0] = replace(
            assigned[0],
            agreement=replace(
                assigned[0].agreement,
                source_content_hash=sha("different-source-content"),
            ),
        )
        report = evaluate_source_repeatability(
            manifest, assigned, third_pass_units=()
        )
        gates = {gate.name: gate for gate in report.hard_gates}
        self.assertEqual(
            gates["source_manifest_alignment"].status, GateStatus.FAIL
        )

    def test_third_pass_boundary(self) -> None:
        self.assertEqual(
            summarize_third_pass(2, 10).fraction_gate.status, GateStatus.PASS
        )
        self.assertEqual(
            summarize_third_pass(3, 10).fraction_gate.status, GateStatus.FAIL
        )
        self.assertEqual(
            summarize_third_pass(0, 0).fraction_gate.status,
            GateStatus.NOT_EVALUABLE,
        )


class FilmAgreementTests(unittest.TestCase):
    def test_complete_grid_and_direct_polarity(self) -> None:
        manifest, _ = manifest_and_assignments()
        scores = full_scores(manifest)
        agreement = compare_film_scores(scores, scores, manifest=manifest)
        self.assertTrue(agreement.universe_complete)
        self.assertEqual(agreement.centrality_exact_rate, 1.0)

        right = list(scores)
        index = next(
            index
            for index, item in enumerate(right)
            if item.film_id == "film-1"
            and item.theme is Theme.SELFISHNESS
            and item.narrative_segment is NarrativeSegment.MAIN_BODY
        )
        right[index] = replace(
            right[index],
            stance=FilmStance.CRITICAL,
            affirmative_votes=0,
            critical_votes=3,
        )
        reversal = compare_film_scores(scores, right, manifest=manifest)
        self.assertEqual(reversal.direct_polarity_flips, 1)

    def test_missing_cell_fails_universe_instead_of_silently_passing(self) -> None:
        manifest, _ = manifest_and_assignments()
        scores = full_scores(manifest)
        incomplete = compare_film_scores(scores, scores[:-1], manifest=manifest)
        self.assertFalse(incomplete.universe_complete)

    def test_late_retribution_requires_complete_assessment_universe(self) -> None:
        manifest, _ = manifest_and_assignments()
        no_late_scores = tuple(
            zero_score(film_id, theme, segment)
            for film_id in sorted(manifest.film_ids)
            for theme in Theme
            for segment in NarrativeSegment
        )
        none = compare_late_retribution(
            late_run(manifest, "left", flags=frozenset()),
            late_run(manifest, "right", flags=frozenset()),
            manifest=manifest,
            left_scores=no_late_scores,
            right_scores=no_late_scores,
        )
        self.assertEqual(none.gate.status, GateStatus.NOT_EVALUABLE)
        self.assertEqual(
            none.universe_gate.name, "glamorize_then_punish_universe"
        )
        self.assertEqual(none.gate.name, "glamorize_then_punish_exact")
        self.assertIn("glamorize_then_punish", none.gate.criterion)
        self.assertIn("glamorize_then_punish", none.gate.details[0])
        scored = full_scores(manifest)
        omitted_true_flags = compare_late_retribution(
            late_run(manifest, "omitted-left", flags=frozenset()),
            late_run(manifest, "omitted-right", flags=frozenset()),
            manifest=manifest,
            left_scores=scored,
            right_scores=scored,
        )
        self.assertEqual(
            omitted_true_flags.universe_gate.status, GateStatus.FAIL
        )
        incomplete_cells = late_run(manifest, "all").assessed_cells - {
            ("film-1", Theme.REVENGE)
        }
        incomplete = compare_late_retribution(
            late_run(
                manifest,
                "left-incomplete",
                flags=frozenset(),
                assessed=incomplete_cells,
            ),
            late_run(manifest, "right-complete", flags=frozenset()),
            manifest=manifest,
            left_scores=scored,
            right_scores=scored,
        )
        self.assertEqual(incomplete.universe_gate.status, GateStatus.FAIL)

    def test_omission_requires_exact_source_sets_and_provenance(self) -> None:
        manifest, _ = manifest_and_assignments()
        scores = full_scores(manifest)
        left_late = late_run(manifest, "base-left")
        right_late = late_run(manifest, "base-right")
        runs = omission_runs(manifest, scores)
        passing = compare_leave_one_source_out(
            runs,
            manifest=manifest,
            baseline_left_scores=scores,
            baseline_right_scores=scores,
            baseline_left_late_retribution=left_late,
            baseline_right_late_retribution=right_late,
        )
        self.assertEqual(passing.gate.status, GateStatus.PASS)
        self.assertEqual(passing.centrality_change_cells, ())

        bad_first = replace(
            runs[0],
            included_source_ids_left=manifest.eligible_source_ids,
            upstream_provenance_verified=False,
        )
        failing = compare_leave_one_source_out(
            (bad_first, *runs[1:]),
            manifest=manifest,
            baseline_left_scores=scores,
            baseline_right_scores=scores,
            baseline_left_late_retribution=left_late,
            baseline_right_late_retribution=right_late,
        )
        self.assertEqual(failing.gate.status, GateStatus.FAIL)
        self.assertTrue(failing.provenance_violations)


class ControlAndMechanicalGateTests(unittest.TestCase):
    def test_controls_require_frozen_assignment_identity(self) -> None:
        manifest, assignments = manifest_and_assignments()
        results = tuple(
            NegativeControlResult(item.assignment_id, item.digest, 0)
            for item in assignments
        )
        passing = summarize_negative_controls(manifest, assignments, results)
        self.assertEqual(passing.gate.status, GateStatus.PASS)

        changed = replace(assignments[1], target_unmentioned_verified=False)
        failing = summarize_negative_controls(
            manifest, (assignments[0], changed, *assignments[2:]), results
        )
        self.assertEqual(failing.gate.status, GateStatus.FAIL)
        self.assertIn(
            "assignment_set_hash_mismatch", failing.assignment_violations
        )

    def test_accepted_control_record_fails(self) -> None:
        manifest, assignments = manifest_and_assignments()
        results = [
            NegativeControlResult(item.assignment_id, item.digest, 0)
            for item in assignments
        ]
        results[0] = replace(results[0], accepted_records=1)
        summary = summarize_negative_controls(manifest, assignments, results)
        self.assertEqual(summary.gate.status, GateStatus.FAIL)

    def test_coverage_is_manifest_linked_to_six_periods_and_slots(self) -> None:
        manifest, _ = manifest_and_assignments()
        complete = evaluate_mechanical_gates(manifest, mechanical_inputs(manifest))
        self.assertEqual(complete.gates[0].status, GateStatus.PASS)

        partial = replace(manifest, films=manifest.films[:-1])
        report = evaluate_mechanical_gates(partial, mechanical_inputs(partial))
        self.assertEqual(report.gates[0].status, GateStatus.FAIL)
        self.assertTrue(
            any("missing_period" in value for value in report.gates[0].details)
        )

        first = manifest.films[0]
        missing_synopsis = replace(first, sources=first.sources[:-1])
        missing_slot_manifest = replace(
            manifest, films=(missing_synopsis, *manifest.films[1:])
        )
        report = evaluate_mechanical_gates(
            missing_slot_manifest, mechanical_inputs(missing_slot_manifest)
        )
        self.assertEqual(report.gates[0].status, GateStatus.FAIL)

        orphan_sources = tuple(
            source_for(first.film_id, slot)
            for slot in (
                SourceSlot.C_TRADE,
                SourceSlot.C_GENERAL,
                SourceSlot.P_SYNOPSIS,
                SourceSlot.R_LATER_2,
            )
        )
        orphan_substitute = replace(first, sources=orphan_sources)
        orphan_manifest = replace(
            manifest, films=(orphan_substitute, *manifest.films[1:])
        )
        report = evaluate_mechanical_gates(
            orphan_manifest, mechanical_inputs(orphan_manifest)
        )
        self.assertEqual(report.gates[0].status, GateStatus.FAIL)
        self.assertTrue(
            any("orphan_scholarship_substitute" in value for value in report.gates[0].details)
        )

    def test_rights_gate_includes_environment_and_public_leaks(self) -> None:
        manifest, _ = manifest_and_assignments()
        credential_leak = replace(
            mechanical_inputs(manifest), publicly_committed_credentials=1
        )
        gates = {
            item.name: item
            for item in evaluate_mechanical_gates(manifest, credential_leak).gates
        }
        self.assertEqual(gates["rights"].status, GateStatus.FAIL)

        wrong_environment = replace(
            mechanical_inputs(manifest), actual_model_environment="external-api"
        )
        gates = {
            item.name: item
            for item in evaluate_mechanical_gates(manifest, wrong_environment).gates
        }
        self.assertEqual(gates["rights"].status, GateStatus.FAIL)

    def test_mechanical_counts_are_strict_integers(self) -> None:
        manifest, _ = manifest_and_assignments()
        with self.assertRaises(TypeError):
            replace(mechanical_inputs(manifest), accepted_records=True)


class PilotDecisionTests(unittest.TestCase):
    def evaluate_complete(self, **overrides):
        (
            manifest,
            _,
            mechanical,
            controls,
            source_report,
            film_report,
            sensitivity_report,
        ) = complete_reports()
        values = {
            "sensitivity": sensitivity_report,
            "material_pipeline_change": False,
            "revision_feasible_without_changing_estimand": True,
        }
        values.update(overrides)
        return evaluate_pilot(
            manifest,
            mechanical,
            controls,
            source_report,
            film_report,
            **values,
        )

    def test_complete_passing_report_proceeds(self) -> None:
        evaluation = self.evaluate_complete()
        self.assertEqual(evaluation.decision, PilotDecision.PROCEED)
        self.assertEqual(evaluation.failed_gates, ())
        self.assertEqual(evaluation.not_evaluable_gates, ())

    def test_missing_substituted_or_duplicate_component_gate_is_rejected(self) -> None:
        (
            manifest,
            _,
            mechanical,
            controls,
            source_report,
            film_report,
            sensitivity_report,
        ) = complete_reports()

        def evaluate(changed_mechanical):
            return evaluate_pilot(
                manifest,
                changed_mechanical,
                controls,
                source_report,
                film_report,
                sensitivity=sensitivity_report,
                material_pipeline_change=False,
                revision_feasible_without_changing_estimand=True,
            )

        with self.assertRaisesRegex(ValueError, "frozen roster"):
            evaluate_pilot(
                manifest,
                replace(mechanical, gates=()),
                controls,
                replace(source_report, hard_gates=(), gates=()),
                replace(
                    film_report,
                    hard_gates=(),
                    repeatability_gates=(),
                ),
                sensitivity=sensitivity_report,
                material_pipeline_change=False,
                revision_feasible_without_changing_estimand=True,
            )
        with self.assertRaisesRegex(ValueError, "frozen roster"):
            evaluate(replace(mechanical, gates=mechanical.gates[:-1]))
        substituted = replace(
            mechanical.gates[0], name="not_the_coverage_gate"
        )
        with self.assertRaisesRegex(ValueError, "frozen roster"):
            evaluate(
                replace(
                    mechanical,
                    gates=(substituted, *mechanical.gates[1:]),
                )
            )
        with self.assertRaisesRegex(ValueError, "frozen roster"):
            evaluate(
                replace(
                    mechanical,
                    gates=(mechanical.gates[0], *mechanical.gates),
                )
            )

    def test_component_gate_values_are_rebuilt_from_retained_inputs(self) -> None:
        (
            manifest,
            _,
            mechanical,
            controls,
            source_report,
            film_report,
            sensitivity_report,
        ) = complete_reports()
        tampered_gate = replace(mechanical.gates[0], observed=999)
        tampered = replace(
            mechanical, gates=(tampered_gate, *mechanical.gates[1:])
        )
        with self.assertRaisesRegex(ValueError, "retained inputs"):
            evaluate_pilot(
                manifest,
                tampered,
                controls,
                source_report,
                film_report,
                sensitivity=sensitivity_report,
                material_pipeline_change=False,
                revision_feasible_without_changing_estimand=True,
            )

        tampered_source_item = replace(
            source_report.assigned[0],
            agreement=replace(
                source_report.assigned[0].agreement,
                salience_exact_units=frozenset(),
            ),
        )
        tampered_source = replace(
            source_report,
            assigned=(tampered_source_item, *source_report.assigned[1:]),
        )
        with self.assertRaisesRegex(ValueError, "retained inputs"):
            evaluate_pilot(
                manifest,
                mechanical,
                controls,
                tampered_source,
                film_report,
                sensitivity=sensitivity_report,
                material_pipeline_change=False,
                revision_feasible_without_changing_estimand=True,
            )

        tampered_film = replace(
            film_report,
            agreement=replace(
                film_report.agreement,
                centrality_exact_cells=0,
            ),
        )
        with self.assertRaisesRegex(ValueError, "component metrics"):
            evaluate_pilot(
                manifest,
                mechanical,
                controls,
                source_report,
                tampered_film,
                sensitivity=sensitivity_report,
                material_pipeline_change=False,
                revision_feasible_without_changing_estimand=True,
            )

        tampered_controls = replace(controls, corrupted_runs=0)
        with self.assertRaisesRegex(ValueError, "retained inputs"):
            evaluate_pilot(
                manifest,
                mechanical,
                tampered_controls,
                source_report,
                film_report,
                sensitivity=sensitivity_report,
                material_pipeline_change=False,
                revision_feasible_without_changing_estimand=True,
            )

    def test_cross_component_denominators_cannot_be_underreported(self) -> None:
        (
            manifest,
            _,
            _,
            controls,
            source_report,
            film_report,
            sensitivity_report,
        ) = complete_reports()
        one_source = frozenset({next(iter(manifest.eligible_source_ids))})
        understated_inputs = replace(
            mechanical_inputs(manifest),
            accepted_records=1,
            accepted_record_source_ids=one_source,
            schema_valid_records=1,
            provenance_complete_records=1,
            exact_evidence_records=1,
        )
        mechanical = evaluate_mechanical_gates(manifest, understated_inputs)
        result = evaluate_pilot(
            manifest,
            mechanical,
            controls,
            source_report,
            film_report,
            sensitivity=sensitivity_report,
            material_pipeline_change=False,
            revision_feasible_without_changing_estimand=True,
        )
        self.assertEqual(result.decision, PilotDecision.REVISE_AND_REVALIDATE)
        self.assertIn("evaluation_manifest_alignment", result.failed_gates)

    def test_ending_integrity_counts_must_match_flagged_union(self) -> None:
        (
            manifest,
            _,
            _,
            controls,
            source_report,
            film_report,
            sensitivity_report,
        ) = complete_reports()
        understated_inputs = replace(
            mechanical_inputs(manifest),
            late_retribution_results=0,
            late_retribution_results_with_separate_evidence=0,
        )
        mechanical = evaluate_mechanical_gates(manifest, understated_inputs)
        result = evaluate_pilot(
            manifest,
            mechanical,
            controls,
            source_report,
            film_report,
            sensitivity=sensitivity_report,
            material_pipeline_change=False,
            revision_feasible_without_changing_estimand=True,
        )
        self.assertEqual(result.decision, PilotDecision.REVISE_AND_REVALIDATE)
        self.assertIn("evaluation_manifest_alignment", result.failed_gates)

    def test_pipeline_and_sensitivity_judgments_are_explicit(self) -> None:
        (
            manifest,
            _,
            mechanical,
            controls,
            source_report,
            film_report,
            _,
        ) = complete_reports()
        with self.assertRaises(TypeError):
            evaluate_pilot(  # type: ignore[call-arg]
                manifest, mechanical, controls, source_report, film_report
            )

    def test_material_change_or_incomplete_sensitivity_cannot_proceed(self) -> None:
        changed = self.evaluate_complete(material_pipeline_change=True)
        self.assertEqual(changed.decision, PilotDecision.REVISE_AND_REVALIDATE)
        self.assertIn("pipeline_stability", changed.failed_gates)

        manifest = complete_reports()[0]
        incomplete = replace(
            sensitivity(manifest),
            completed_sections=frozenset(
                set(SensitivitySection) - {SensitivitySection.SOURCE_STRATA}
            ),
        )
        result = self.evaluate_complete(sensitivity=incomplete)
        self.assertEqual(result.decision, PilotDecision.REVISE_AND_REVALIDATE)
        self.assertIn("sensitivity_review", result.not_evaluable_gates)

    def test_unfixable_failure_stops(self) -> None:
        result = self.evaluate_complete(
            material_pipeline_change=True,
            revision_feasible_without_changing_estimand=False,
        )
        self.assertEqual(result.decision, PilotDecision.STOP_OR_NARROW)


if __name__ == "__main__":
    unittest.main()
