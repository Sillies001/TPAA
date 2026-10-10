from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from tpaa_application.ed2_assessment_result import (
    ED2AssessmentResultRepository,
    assessment_result_from_profile,
)
from tpaa_assessment.ed2_profile import (
    ed2_training_assessment_profile,
    evaluate_ed2_training_assessment,
)
from tpaa_storage import SQLiteDesktopUnitOfWork, bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
PROFILE = (
    ROOT
    / "docs"
    / "baseline"
    / "ED2-CONFORMANCE"
    / "TRAINING_ASSESSMENT_PROFILE.json"
)


def test_ed2_profile_document_matches_runtime_and_keeps_numeric_outputs_null() -> None:
    assert json.loads(PROFILE.read_text(encoding="utf-8")) == (
        ed2_training_assessment_profile()
    )
    result = evaluate_ed2_training_assessment(
        evidence_availability=("AVAILABLE",),
        p3_validity_statuses=("IN_DOMAIN",),
        approval_states=("DRAFT",),
    )
    assert result.qualification_status == "REVIEW_REQUIRED"
    assert result.competency_state == "DEMONSTRATED"
    assert result.numeric_score is None
    assert result.grade is None


def test_ed2_profile_preserves_unavailable_and_not_identifiable_states() -> None:
    unavailable = evaluate_ed2_training_assessment(
        evidence_availability=("UNAVAILABLE",),
        p3_validity_statuses=("IN_DOMAIN",),
        approval_states=("APPROVED",),
    )
    not_identifiable = evaluate_ed2_training_assessment(
        evidence_availability=("NOT_IDENTIFIABLE",),
        p3_validity_statuses=("IN_DOMAIN",),
        approval_states=("APPROVED",),
    )
    out_of_domain = evaluate_ed2_training_assessment(
        evidence_availability=("AVAILABLE",),
        p3_validity_statuses=("OUT_OF_DOMAIN",),
        approval_states=("APPROVED",),
    )
    assert unavailable.qualification_status == "REVIEW_REQUIRED"
    assert unavailable.competency_state == "UNAVAILABLE"
    assert not_identifiable.qualification_status == "NOT_IDENTIFIABLE"
    assert not_identifiable.competency_state == "NOT_IDENTIFIABLE"
    assert out_of_domain.qualification_status == "NOT_QUALIFIED"
    assert out_of_domain.competency_state == "NOT_DEMONSTRATED"


def test_ed2_assessment_result_restart_and_approval_successor(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    draft_id = str(uuid4())
    approved_id = str(uuid4())
    draft_profile = evaluate_ed2_training_assessment(
        evidence_availability=("AVAILABLE",),
        p3_validity_statuses=("IN_DOMAIN",),
        approval_states=("DRAFT",),
    )
    draft = assessment_result_from_profile(
        revision_kind="P4",
        revision_id=draft_id,
        result=draft_profile,
    )

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repository = ED2AssessmentResultRepository(uow.canonical_rows)
        repository.register(
            draft,
            created_at_utc="2026-10-08T00:00:00Z",
        )
        assert repository.exact(draft_id) == draft
        approved = repository.successor(
            previous_revision_id=draft_id,
            revision_kind="P4",
            revision_id=approved_id,
            approval_state="APPROVED",
            created_at_utc="2026-10-08T00:01:00Z",
        )
        assert approved.qualification_status == "QUALIFIED"
        assert approved.numeric_score is None
        assert approved.grade is None
        uow.commit()

    with SQLiteDesktopUnitOfWork(database) as uow:
        restarted = ED2AssessmentResultRepository(uow.canonical_rows)
        assert restarted.exact(draft_id) == draft
        assert restarted.exact(approved_id).qualification_status == "QUALIFIED"
        uow.commit()
