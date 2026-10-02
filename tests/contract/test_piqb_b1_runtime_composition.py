from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient

from tpaa_context import assert_p6_claim_allowed
from tpaa_runtime import (
    ProductAdmissionResolver,
    ProductRuntimeConfig,
    RuntimeProfile,
    build_desktop_application,
    build_service_application,
    create_full_desktop_app,
    create_full_service_app,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW_PATH = ROOT / "tools" / "testing" / "piqb_b1_review.py"

SPEC = importlib.util.spec_from_file_location("piqb_b1_review", REVIEW_PATH)
assert SPEC is not None and SPEC.loader is not None
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)


def _config(profile: RuntimeProfile) -> ProductRuntimeConfig:
    return ProductRuntimeConfig(
        profile=profile,
        product_build_version="0.0.0",
        authority_root=ROOT / "baseline" / "CB-1.4.0" / "canonical",
        m1_fixture_root=ROOT / "tests" / "fixtures" / "m1",
    )


def test_b1_machine_admission_evidence_matches_runtime_resolver() -> None:
    manifest = json.loads(
        (
            ROOT
            / "docs"
            / "baseline"
            / "PIQB-1.0"
            / "B1_RUNTIME_ADMISSION_EVIDENCE.json"
        ).read_text(encoding="utf-8")
    )
    resolver = ProductAdmissionResolver()
    records = manifest["records"]
    assert [record["phase"] for record in records] == [
        "P1", "P2", "P3", "P4", "P5", "P6"
    ]
    for expected in records:
        actual = resolver.record(expected["phase"])
        assert actual.qualification == expected["qualification"]
        assert actual.source_revision == expected["source_revision"]
        assert actual.run_number == expected["run_number"]
        assert actual.actions_run_id == expected["actions_run_id"]
        assert actual.exact is True


def test_b1_admission_resolver_uses_exact_protected_main_evidence() -> None:
    resolver = ProductAdmissionResolver()
    assert [resolver.record(phase).qualification for phase in (
        "P1", "P2", "P3", "P4", "P5", "P6"
    )] == [
        "P1_M5_QUALIFIED",
        "P2_M6_QUALIFIED",
        "P3_M7_QUALIFIED",
        "P4_P5_M8_QUALIFIED",
        "P4_P5_M8_QUALIFIED",
        "P6_M9_QUALIFIED",
    ]
    assert all(resolver.admitted(phase) for phase in (
        "P1", "P2", "P3", "P4", "P5", "P6"
    ))
    evidence = resolver.p6_evidence()
    assert evidence is not None
    assert evidence.source_revision == "06945127c86069918ffdfd415201d321d53aae4d"
    assert_p6_claim_allowed("P6", evidence=evidence)


def test_b1_feature_availability_states_are_all_reachable() -> None:
    resolver = ProductAdmissionResolver()
    assert resolver.feature_state(
        "P1",
        configured=True,
    ).value == "AVAILABLE"
    assert resolver.feature_state(
        "P1",
        configured=False,
    ).value == "NOT_CONFIGURED"
    assert resolver.feature_state(
        "P1",
        configured=True,
        dependency_ready=False,
    ).value == "DEPENDENCY_MISSING"
    assert resolver.feature_state(
        "P1",
        configured=True,
        supported_profile=False,
    ).value == "UNSUPPORTED_PROFILE"
    assert resolver.feature_state(
        "P1",
        configured=True,
        available=False,
    ).value == "UNAVAILABLE"


def test_b1_desktop_runtime_exposes_one_p1_p6_backend_surface() -> None:
    runtime = build_desktop_application(_config(RuntimeProfile.DESKTOP))
    app = create_full_desktop_app(runtime, bearer_token="b1-secret")
    route_paths = {
        route.path
        for route in app.routes
        if hasattr(route, "path")
    }
    for prefix in ("/m1/", "/m3/", "/m4/", "/m6/", "/m7/", "/m8/", "/m9/"):
        assert any(path.startswith(prefix) for path in route_paths)
    assert "/runtime/features" in route_paths
    assert "/jobs" in route_paths

    with TestClient(app) as client:
        unauthorized = client.get("/runtime/features")
        response = client.get(
            "/runtime/features",
            headers={"Authorization": "Bearer b1-secret"},
        )
        forbidden = client.get(
            "/outside-governed-surface",
            headers={"Authorization": "Bearer b1-secret"},
        )
    assert unauthorized.status_code == 401
    assert response.status_code == 200
    payload = response.json()
    assert payload["schema"] == "TPAA_PRODUCT_FEATURE_AVAILABILITY_V1"
    assert [item["state"] for item in payload["items"]] == ["AVAILABLE"] * 6
    assert forbidden.status_code == 404
    assert forbidden.json() == {"detail": "PATH_NOT_ALLOWED"}


def test_b1_service_runtime_uses_same_application_composition() -> None:
    runtime = build_service_application(_config(RuntimeProfile.SERVICE))

    def denied_m8(_request):
        raise PermissionError("identity provider belongs to B4")

    def denied_m9(_request):
        raise PermissionError("identity provider belongs to B4")

    app = create_full_service_app(
        runtime,
        m8_principal_resolver=denied_m8,
        m9_principal_resolver=denied_m9,
    )
    route_paths = {
        route.path
        for route in app.routes
        if hasattr(route, "path")
    }
    for prefix in ("/m1/", "/m3/", "/m4/", "/m6/", "/m7/", "/m8/", "/m9/"):
        assert any(path.startswith(prefix) for path in route_paths)
    assert "/runtime/features" in route_paths


def test_b1_local_child_delegates_to_composition_root() -> None:
    source = (
        ROOT / "src" / "tpaa_api" / "local_backend_child.py"
    ).read_text(encoding="utf-8")
    assert "build_desktop_application" in source
    assert "create_full_desktop_app" in source
    assert "M1PublicationService" not in source
    assert "ApplicationService(" not in source


def test_b1_desktop_transport_is_generic_but_keeps_m1_compatibility() -> None:
    source = (
        ROOT / "src" / "tpaa_gui" / "local_backend.py"
    ).read_text(encoding="utf-8")
    assert "def request_json(" in source
    assert "def m1_request_json(" in source
    for prefix in (
        '"/m1/"',
        '"/m3/"',
        '"/m4/"',
        '"/m6/"',
        '"/m7/"',
        '"/m8/"',
        '"/m9/"',
    ):
        assert prefix in source


def test_b1_m9_runtime_has_no_naked_admission_boolean() -> None:
    source = (
        ROOT / "src" / "tpaa_application" / "m9_workspace.py"
    ).read_text(encoding="utf-8")
    assert "p6_admitted: bool" not in source
    assert "admission_evidence: P6AdmissionEvidence" in source
    assert 'assert_p6_claim_allowed("P6"' in source


def _review(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "expected_revision": "a" * 40,
        "checked_out_revision": "a" * 40,
        "event_name": "pull_request",
        "git_ref": "refs/pull/215/merge",
        "run_conclusion": "success",
        "required_jobs_success": 14,
        "required_jobs_total": 14,
    }
    values.update(overrides)
    return REVIEW.review(**values)


def test_b1_candidate_passes_but_requires_protected_main() -> None:
    result = _review()
    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["qualification"] == "PIQB_B1_CANDIDATE"
    assert result["runtime_composition_qualified"] is False


def test_b1_protected_main_exact_push_qualifies() -> None:
    result = _review(event_name="push", git_ref="refs/heads/main")
    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["failed_acceptance"] == []
    assert result["qualification"] == "PIQB_B1_QUALIFIED"
    assert result["runtime_composition_qualified"] is True


def test_b1_review_keeps_existing_fourteen_job_topology() -> None:
    workflow = (
        ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
    ).read_text(encoding="utf-8")
    assert "\n  piqb-b1-review:" not in workflow
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "Review PIQB B1 runtime composition closure" in workflow
    assert "piqb_b1_review.py" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
    assert "--output evidence/piqb-b1/review.json" in workflow
