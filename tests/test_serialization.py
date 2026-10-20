from __future__ import annotations

import unittest

from film_values.models import (
    ClaimDependence,
    ClaimTarget,
    ClaimType,
    EvidenceRecord,
    EvidenceVerificationResult,
    NarrativeSegment,
    SourceSalience,
    SourceStance,
    SourceType,
    Theme,
    VerificationReason,
)
from film_values.serialization import (
    evidence_record_from_dict,
    evidence_record_to_dict,
    verification_result_from_dict,
    verification_result_to_dict,
)


class SerializationTests(unittest.TestCase):
    def example(self) -> EvidenceRecord:
        return EvidenceRecord(
            film_id="film-1",
            source_id="source-1",
            lineage_id="lineage-1",
            source_type=SourceType.CONTEMPORARY_REVIEW,
            exact_evidence_span="The film makes excess seductive.",
            locator="paragraph 4",
            claim_target=ClaimTarget.FILM,
            claim_type=ClaimType.FILM_STANCE_ATTRIBUTION,
            theme=Theme.CONSUMERISM_MATERIALISM,
            narrative_segment=NarrativeSegment.MAIN_BODY,
            source_salience=SourceSalience.IMPORTANT,
            claim_dependence=ClaimDependence.INDEPENDENT_INTERPRETATION,
            source_stance=SourceStance.AFFIRMATIVE,
        )

    def test_round_trip(self) -> None:
        original = self.example()
        self.assertEqual(evidence_record_from_dict(evidence_record_to_dict(original)), original)

    def test_unknown_field_is_rejected(self) -> None:
        value = evidence_record_to_dict(self.example())
        value["model_guess"] = "probably consumerism"
        with self.assertRaisesRegex(ValueError, "extra=.*model_guess"):
            evidence_record_from_dict(value)

    def test_missing_field_is_rejected(self) -> None:
        value = evidence_record_to_dict(self.example())
        del value["exact_evidence_span"]
        with self.assertRaisesRegex(ValueError, "missing=.*exact_evidence_span"):
            evidence_record_from_dict(value)

    def test_boolean_string_is_rejected(self) -> None:
        value = evidence_record_to_dict(self.example())
        value["explicit_temporal_contrast"] = "false"
        with self.assertRaisesRegex(ValueError, "must be a boolean"):
            evidence_record_from_dict(value)

    def test_derivative_claim_round_trip_preserves_attribution_audit_fields(self) -> None:
        original = EvidenceRecord(
            film_id="film-1",
            source_id="source-later",
            lineage_id="lineage-later",
            source_type=SourceType.SCHOLARSHIP,
            exact_evidence_span="As source 1 argues, the film makes excess seductive.",
            locator="page 27",
            claim_target=ClaimTarget.FILM,
            claim_type=ClaimType.FILM_STANCE_ATTRIBUTION,
            theme=Theme.CONSUMERISM_MATERIALISM,
            narrative_segment=NarrativeSegment.MAIN_BODY,
            source_salience=SourceSalience.CENTRAL,
            source_stance=SourceStance.AFFIRMATIVE,
            claim_dependence=ClaimDependence.ATTRIBUTED_DERIVATIVE,
            attributed_source_ids=("source-1",),
            attribution_span="As source 1 argues",
        )
        encoded = evidence_record_to_dict(original)
        self.assertEqual(encoded["attributed_source_ids"], ["source-1"])
        self.assertEqual(evidence_record_from_dict(encoded), original)

    def test_derivative_claim_requires_source_identifier_and_attribution_span(self) -> None:
        value = evidence_record_to_dict(self.example())
        value["claim_dependence"] = "attributed_derivative"
        with self.assertRaisesRegex(ValueError, "requires at least one source"):
            evidence_record_from_dict(value)

        value["attributed_source_ids"] = ["source-2"]
        with self.assertRaisesRegex(ValueError, "requires a nonempty attribution span"):
            evidence_record_from_dict(value)

    def test_independent_claim_rejects_attribution_metadata(self) -> None:
        value = evidence_record_to_dict(self.example())
        value["attributed_source_ids"] = ["source-2"]
        value["attribution_span"] = "According to source 2"
        with self.assertRaisesRegex(ValueError, "Independent interpretation"):
            evidence_record_from_dict(value)

    def test_derivative_claim_rejects_self_attribution(self) -> None:
        value = evidence_record_to_dict(self.example())
        value["claim_dependence"] = "attributed_derivative"
        value["attributed_source_ids"] = ["source-1"]
        value["attribution_span"] = "The source says"
        value["exact_evidence_span"] = "The source says excess is seductive."
        with self.assertRaisesRegex(ValueError, "own claim"):
            evidence_record_from_dict(value)

    def test_direct_construction_rejects_untyped_dependence_value(self) -> None:
        fields = evidence_record_to_dict(self.example())
        fields["claim_dependence"] = "attributed_derivative"
        fields["attributed_source_ids"] = ("source-2",)
        fields["attribution_span"] = "The earlier source says"
        fields["exact_evidence_span"] = "The earlier source says excess is seductive."
        fields["source_type"] = SourceType(fields["source_type"])
        fields["claim_target"] = ClaimTarget(fields["claim_target"])
        fields["claim_type"] = ClaimType(fields["claim_type"])
        fields["theme"] = Theme(fields["theme"])
        fields["narrative_segment"] = NarrativeSegment(fields["narrative_segment"])
        fields["source_salience"] = SourceSalience(fields["source_salience"])
        fields["source_stance"] = SourceStance(fields["source_stance"])
        with self.assertRaisesRegex(TypeError, "must be a ClaimDependence"):
            EvidenceRecord(**fields)

    def test_verification_round_trip(self) -> None:
        original = EvidenceVerificationResult(
            accepted=False,
            reason_codes=(VerificationReason.STANCE_UNSUPPORTED,),
            explanation="The quoted passage does not attribute a stance to the film.",
        )
        self.assertEqual(
            verification_result_from_dict(verification_result_to_dict(original)),
            original,
        )

    def test_claim_dependence_failure_reason_round_trip(self) -> None:
        original = EvidenceVerificationResult(
            accepted=False,
            reason_codes=(VerificationReason.CLAIM_DEPENDENCE_INCORRECT,),
            explanation="The passage only repeats the selected release review.",
        )
        self.assertEqual(
            verification_result_from_dict(verification_result_to_dict(original)),
            original,
        )

    def test_accepted_verification_rejects_failure_codes(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires only"):
            EvidenceVerificationResult(
                accepted=True,
                reason_codes=(
                    VerificationReason.ACCEPTED,
                    VerificationReason.THEME_UNSUPPORTED,
                ),
                explanation="Contradictory result.",
            )

    def test_rejected_verification_rejects_accepted_code(self) -> None:
        with self.assertRaisesRegex(ValueError, "may not contain"):
            verification_result_from_dict(
                {
                    "accepted": False,
                    "reason_codes": ["accepted"],
                    "explanation": "Contradictory result.",
                }
            )


if __name__ == "__main__":
    unittest.main()
