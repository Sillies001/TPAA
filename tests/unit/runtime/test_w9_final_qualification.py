from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tpaa_api.runtime import register_product_runtime_routes
from tpaa_application import ApplicationService
from tpaa_qualification import (
    W9_EVIDENCE_CATEGORIES,
    W9EvidenceGate,
    W9FinalQualificationStatus,
    W9QualificationError,
    build_w9_final_qualification_status,
)
from tpaa_runtime import (
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
)
from tpaa_storage import bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.5.0"
CANDIDATE = "a" * 64
REVISION = "b" * 40
SIGNATURE = "c" * 64


class _UnusedStorage:
    def execute(self) -> Any:
        raise AssertionError("storage is outside the W9 status read")


def _accepted_records(*, candidate: str = CANDIDATE) -> list[dict[str, object]]:
    return [
        {
            "category": category,
            "state": "ACCEPTED",
            "reason_code": "APPROVED_EVIDENCE",
            "candidate_identity_sha256": candidate,
            "evidence_sha256": f"{index:x}" * 64,
        }
        for index, category in enumerate(W9_EVIDENCE_CATEGORIES, start=1)
    ]


def _formal_status(records: list[dict[str, object]]) -> dict[str, object]:
    return build_w9_final_qualification_status(
        records,
        candidate_identity_sha256=CANDIDATE,
        source_revision=REVISION,
        unwaived_blocker_count=0,
        unwaived_high_count=0,
        protected_main_exact=True,
        hosted_ci_success=True,
        independent_approval_complete=True,
        signature_sha256=SIGNATURE,
    ).execute()


def test_w9_local_closure_is_explicit_no_go_without_zero_finding_claim() -> None:
    status = W9FinalQualificationStatus.local_closed().execute()

    assert status["schema"] == "TPAA_W9_FINAL_QUALIFICATION_STATUS_V1"
    assert status["stage_status"] == "CLOSED_LOCAL_WITH_RELEASE_GATES"
    assert status["decision"] == "NO_GO"
    assert status["formal_release_allowed"] is False
    assert status["formal_release_claimed"] is False
    assert status["unwaived_findings"] == {"blocker": None, "high": None}
    assert tuple(item["category"] for item in status["gates"]) == (
        W9_EVIDENCE_CATEGORIES
    )


def test_w9_formal_go_requires_every_gate_on_one_exact_candidate() -> None:
    status = _formal_status(_accepted_records())
    assert status["decision"] == "GO"
    assert status["stage_status"] == "FORMALLY_QUALIFIED"
    assert status["all_evidence_bound_to_one_candidate"] is True
    assert status["formal_release_allowed"] is True

    drifted = _accepted_records()
    drifted[4]["candidate_identity_sha256"] = "d" * 64
    mismatch = _formal_status(drifted)
    assert mismatch["decision"] == "NO_GO"
    assert mismatch["formal_release_allowed"] is False


@pytest.mark.parametrize(
    "field",
    (
        "protected_main_exact",
        "hosted_ci_success",
        "independent_approval_complete",
    ),
)
def test_w9_rejects_truthy_non_boolean_release_claims(field: str) -> None:
    arguments: dict[str, Any] = {
        "candidate_identity_sha256": CANDIDATE,
        "source_revision": REVISION,
        "unwaived_blocker_count": 0,
        "unwaived_high_count": 0,
        "protected_main_exact": True,
        "hosted_ci_success": True,
        "independent_approval_complete": True,
        "signature_sha256": SIGNATURE,
    }
    arguments[field] = "false"

    with pytest.raises(W9QualificationError, match=f"W9_BOOLEAN_INVALID:{field}"):
        build_w9_final_qualification_status(_accepted_records(), **arguments)


def test_w9_rejects_boolean_finding_counts_and_invalid_record_types() -> None:
    with pytest.raises(
        W9QualificationError,
        match="W9_FINDING_COUNT_INVALID:unwaived_blocker_count",
    ):
        build_w9_final_qualification_status(
            _accepted_records(),
            candidate_identity_sha256=CANDIDATE,
            source_revision=REVISION,
            unwaived_blocker_count=True,
            unwaived_high_count=0,
            protected_main_exact=True,
            hosted_ci_success=True,
            independent_approval_complete=True,
            signature_sha256=SIGNATURE,
        )

    invalid = _accepted_records()
    invalid[0]["reason_code"] = None
    with pytest.raises(W9QualificationError, match="W9_TEXT_INVALID:reason_code"):
        _formal_status(invalid)


def test_w9_rejects_incomplete_or_reordered_evidence() -> None:
    missing_hash = _accepted_records()
    missing_hash[0]["evidence_sha256"] = None
    with pytest.raises(W9QualificationError, match="W9_SHA256_INVALID"):
        _formal_status(missing_hash)

    reordered = _accepted_records()
    reordered.reverse()
    with pytest.raises(W9QualificationError, match="W9_CATEGORY_SET_OR_ORDER_INVALID"):
        _formal_status(reordered)

    with pytest.raises(
        W9QualificationError,
        match="W9_UNACCEPTED_EVIDENCE_BINDING_FORBIDDEN",
    ):
        W9EvidenceGate(
            category=W9_EVIDENCE_CATEGORIES[0],
            state="PENDING_TARGET",
            reason_code="TARGET_REQUIRED",
            candidate_identity_sha256=CANDIDATE,
        )


def test_w9_runtime_status_is_machine_readable_and_missing_status_fails_closed() -> None:
    configured = ApplicationService(
        get_storage_baseline_status=_UnusedStorage(),
        w9_final_qualification_status=W9FinalQualificationStatus.local_closed(),
    )
    response = TestClient(
        register_product_runtime_routes(FastAPI(), configured)
    ).get("/runtime/final-qualification")
    assert response.status_code == 200
    assert response.json()["decision"] == "NO_GO"

    missing = ApplicationService(get_storage_baseline_status=_UnusedStorage())
    unavailable = TestClient(
        register_product_runtime_routes(FastAPI(), missing)
    ).get("/runtime/final-qualification")
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == (
        "W9_FINAL_QUALIFICATION_NOT_CONFIGURED"
    )


def test_w9_status_is_wired_into_production_composition(tmp_path: Path) -> None:
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)
    runtime = build_desktop_production_runtime(
        ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.1",
            authority_root=BASELINE / "canonical",
            object_root=tmp_path / "objects",
            desktop_database_path=database,
        )
    )

    status = runtime.application.w9_final_qualification_status()
    assert status["stage_status"] == "CLOSED_LOCAL_WITH_RELEASE_GATES"
    assert status["formal_release_allowed"] is False
