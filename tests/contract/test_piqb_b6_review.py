from __future__ import annotations

import importlib.util
import json
import tomllib
from pathlib import Path

from tpaa_api.unified import UnifiedPrincipal
from tpaa_runtime import (
    ProductRuntimeConfig,
    RuntimeProfile,
    build_desktop_application,
    build_service_application,
    create_full_desktop_app,
    create_full_service_app,
)

ROOT = Path(__file__).resolve().parents[2]
REVIEW_PATH = ROOT / "tools" / "testing" / "piqb_exit_review.py"
SPEC = importlib.util.spec_from_file_location("piqb_exit_review", REVIEW_PATH)
assert SPEC is not None and SPEC.loader is not None
REVIEW = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REVIEW)

REVISION = "a" * 40
LOGICAL_PRODUCT = {
    "schema": "TPAA_PIQB_B6_LOGICAL_PRODUCT_V1",
    "product_version": "1.0.0",
    "db_schema_version": "1.9.0",
    "canonical_baseline": "CB-1.4.0",
    "source_revision": REVISION,
    "roles": ["DESKTOP", "SERVICE"],
    "admitted_capabilities": ["P1", "P2", "P3", "P4", "P5", "P6"],
    "release_manifest_schema": "TPAA_PIQB_RELEASE_MANIFEST_V1",
    "build_manifest_schema": "TPAA_PIQB_BUILD_MANIFEST_V1",
    "sbom_schema": "SPDX-2.3",
    "workload_manifest_sha256": "w" * 64,
    "runtime_entry": "PIQB_PRODUCT",
    "historical_m5_workload_reused_as_measurement_substrate": True,
    "historical_m5_qualification_semantics_rewritten": False,
}


def _platform(platform: str) -> dict[str, object]:
    profiles = (
        ["WINDOWS_DESKTOP_X64", "WINDOWS_SERVICE_X64"]
        if platform == "windows"
        else ["LINUX_DESKTOP_X64", "LINUX_SERVICE_X64"]
    )
    return {
        "schema": "TPAA_PIQB_B6_PLATFORM_QUALIFICATION_V1",
        "status": "PASS",
        "source_revision": REVISION,
        "product_version": "1.0.0",
        "db_schema_version": "1.9.0",
        "failed_acceptance": [],
        "profiles": [
            {
                "profile_id": profile,
                "package_sha256": (profile[0].lower() * 64)[:64],
            }
            for profile in profiles
        ],
        "logical_product": LOGICAL_PRODUCT,
        "logical_product_hash": "f" * 64,
    }


def _postgres() -> dict[str, object]:
    return {
        "schema": "TPAA_PIQB_B2_POSTGRES_PRODUCT_PERSISTENCE_V1",
        "status": "PASS",
        "source_revision": REVISION,
        "failed_acceptance": [],
        "acceptance": {
            "sqlite_current_db_1_9": True,
            "postgres_current_db_1_9": True,
            "sqlite_restart_exact": True,
            "postgres_restart_exact": True,
            "sqlite_postgres_logical_parity": True,
            "orphan_recovery_preserves_registered_both_engines": True,
        },
        "scope": {"db_schema_version": "1.9.0"},
    }


def _b4() -> dict[str, object]:
    return {
        "schema": "TPAA_PIQB_B4_API_SECURITY_OBSERVABILITY_V1",
        "status": "PASS",
        "source_revision": REVISION,
        "failed_acceptance": [],
        "acceptance": {
            "sqlite_db_1_9": True,
            "postgres_db_1_9": True,
            "product_openapi_exact": True,
            "product_client_exact": True,
            "product_route_count_exact_10": True,
            "product_exact_id_only": True,
            "audit_semantic_parity": True,
            "observability_exact": True,
        },
        "scope": {"db_schema_version": "1.9.0"},
    }


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _review(tmp_path: Path, **overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "windows_path": _write(tmp_path / "windows.json", _platform("windows")),
        "linux_path": _write(tmp_path / "linux.json", _platform("linux")),
        "postgres_path": _write(tmp_path / "postgres.json", _postgres()),
        "b4_path": _write(tmp_path / "b4.json", _b4()),
        "expected_revision": REVISION,
        "checked_out_revision": REVISION,
        "event_name": "pull_request",
        "git_ref": "refs/pull/999/merge",
        "run_conclusion": "success",
        "required_jobs_success": 14,
        "required_jobs_total": 14,
    }
    values.update(overrides)
    return REVIEW.review(**values)


def test_b6_baseline_and_product_identity_are_exact() -> None:
    baseline = json.loads(
        (ROOT / "docs" / "baseline" / "PIQB-1.0" / "B6_TASK_BASELINE.json").read_text(
            encoding="utf-8"
        )
    )
    assert baseline["task_count"] == 8
    assert [row["task_id"] for row in baseline["tasks"]] == [
        f"PIQB-B6-{index:03d}" for index in range(1, 9)
    ]
    assert baseline["product_version"] == "1.0.0"
    assert baseline["db_schema_version"] == "1.9.0"
    assert baseline["scope"]["no_m10_p7"] is True
    assert baseline["scope"]["four_profiles"] == [
        "WINDOWS_DESKTOP_X64",
        "WINDOWS_SERVICE_X64",
        "LINUX_DESKTOP_X64",
        "LINUX_SERVICE_X64",
    ]

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["version"] == "1.0.0"
    uv_lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    tpaa = [row for row in uv_lock["package"] if row["name"] == "tpaa"]
    assert len(tpaa) == 1
    assert tpaa[0]["version"] == "1.0.0"


def test_full_product_apps_use_runtime_product_version() -> None:
    authority_root = ROOT / "baseline" / "CB-1.4.0" / "canonical"
    fixture_root = ROOT / "tests" / "fixtures" / "m1"

    desktop = build_desktop_application(
        ProductRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.0",
            authority_root=authority_root,
            m1_fixture_root=fixture_root,
        )
    )
    desktop_app = create_full_desktop_app(
        desktop,
        bearer_token="contract-test-desktop-token",
    )
    assert desktop_app.version == "1.0.0"

    service = build_service_application(
        ProductRuntimeConfig(
            profile=RuntimeProfile.SERVICE,
            product_build_version="1.0.0",
            authority_root=authority_root,
            m1_fixture_root=fixture_root,
        )
    )
    service_app = create_full_service_app(
        service,
        principal_resolver=lambda _request: UnifiedPrincipal(
            role="SYSTEM",
            actor_id="CONTRACT_TEST",
            scope_match=True,
        ),
    )
    assert service_app.version == "1.0.0"


def test_piqb_exit_candidate_waits_for_protected_main(tmp_path: Path) -> None:
    result = _review(tmp_path)

    assert result["status"] == "PASS"
    assert result["decision"] == "PENDING_PROTECTED_MAIN"
    assert result["qualification"] == "PIQB_B6_CANDIDATE"
    assert result["implementation_complete"] is True
    assert result["formal_release_claimed"] is False
    assert result["formal_completion_blocked_by_protected_main"] is True
    assert result["failed_acceptance"] == []


def test_piqb_exit_protected_main_qualifies_release(tmp_path: Path) -> None:
    result = _review(
        tmp_path,
        event_name="push",
        git_ref="refs/heads/main",
    )

    assert result["status"] == "PASS"
    assert result["decision"] == "GO"
    assert result["qualification"] == "PIQB_1_0_QUALIFIED"
    assert result["formal_release_claimed"] is True
    assert result["formal_completion_blocked_by_protected_main"] is False
    assert len(result["package_sha256_by_profile"]) == 4


def test_piqb_exit_rejects_stale_head_jobs_and_db_recovery(tmp_path: Path) -> None:
    stale = _review(tmp_path, checked_out_revision="b" * 40)
    assert "candidate_revision_exact" in stale["failed_acceptance"]

    jobs = _review(tmp_path, required_jobs_success=13)
    assert "required_jobs_exact" in jobs["failed_acceptance"]

    postgres = _postgres()
    acceptance = postgres["acceptance"]
    assert isinstance(acceptance, dict)
    acceptance["postgres_restart_exact"] = False
    failed_pg = _review(
        tmp_path,
        postgres_path=_write(tmp_path / "failed-postgres.json", postgres),
    )
    assert "current_db_restart_recovery_pass" in failed_pg["failed_acceptance"]


    b4 = _b4()
    b4_acceptance = b4["acceptance"]
    assert isinstance(b4_acceptance, dict)
    b4_acceptance["product_exact_id_only"] = False
    failed_b4 = _review(
        tmp_path,
        b4_path=_write(tmp_path / "failed-b4.json", b4),
    )
    assert (
        "same_run_product_api_security_observability_pass"
        in failed_b4["failed_acceptance"]
    )


def test_b6_workflow_reuses_existing_fourteen_check_topology() -> None:
    workflow = (ROOT / ".github" / "workflows" / "cross-platform-ci.yml").read_text(
        encoding="utf-8"
    )
    assert workflow.count("\n  m0-cross-platform:") == 1
    assert "\n  piqb-b6" not in workflow
    assert "Execute PIQB B6 final product qualification" in workflow
    assert "Upload PIQB B6 release packages" in workflow
    assert "Review PIQB B6 final product and release qualification" in workflow
    assert "piqb_b6_final_product_qualification.py" in workflow
    assert "piqb_exit_review.py" in workflow
    assert "--b4-qualification downloaded/piqb-b4/postgres-api-security-observability.json" in workflow
    assert "--required-jobs-success 14" in workflow
    assert "--required-jobs-total 14" in workflow
