from __future__ import annotations

import unittest

from film_values.models import (
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
