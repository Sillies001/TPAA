from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from tools.testing.prcb_c5_four_profile_equivalence import review


def _installed(profile: str, *, p2_release_id: str, suffix: str) -> dict[str, object]:
    desktop = "DESKTOP" in profile
    value: dict[str, object] = {
        "status": "PASS",
        "product_version": "1.0.1",
        "db_schema_version": "1.9.0",
        "canonical_baseline": "CB-1.4.0",
        "release_id": "11111111-1111-4111-8111-111111111111",
        "metric_count": 132,
        "catalog_definition_count": 116,
        "metric_code_count": 116,
        "capability_observation_count": 47,
        "system_observation_count": 80,
        "evidence_only_metric_instance_count": 5,
        "p2_job_status": "SUCCEEDED",
        "p2_release_id": p2_release_id,
        "p2_estimate_id": f"22222222-2222-4222-8222-2222222222{suffix}",
        "p2_estimate_status": "NOT_IDENTIFIABLE",
        "p2_source_observation_id": "33333333-3333-4333-8333-333333333333",
        "p2_source_knowledge_time_utc": f"2026-10-07T00:00:0{suffix}Z",
        "p2_reason_codes": ["INSUFFICIENT_EFFECTIVE_EVIDENCE"],
        "p2_claim_level": "ASSOCIATION_ONLY",
        "p2_adjusted_value": None,
        "p2_unit": "g",
        "p3_estimate_id": "44444444-4444-4444-8444-444444444444",
        "p4_revision_id": "55555555-5555-4555-8555-555555555555",
        "p5_revision_id": "66666666-6666-4666-8666-666666666666",
        "p6_forecast_result_id": "77777777-7777-4777-8777-777777777777",
        "p6_counterfactual_run_id": "88888888-8888-4888-8888-888888888888",
        "restart_exact_replay": True,
        "backup_restore_exact_replay": True,
        "api_exact_read_verified": True,
        "persistent_audit_verified": True,
        "tests_fixture_dependency": False,
        "formal_release_claimed": False,
    }
    if desktop:
        value.update(
            {
                "desktop_discovery_verified": True,
                "desktop_authentication_verified": True,
                "desktop_latest_alias_rejected": True,
                "api_exact_read_restart_replay": True,
                "desktop_discovery_restart_replay": True,
                "api_exact_read_backup_restore_replay": True,
                "desktop_discovery_backup_restore_replay": True,
            }
        )
    else:
        value.update(
            {
                "service_authentication_verified": True,
                "service_rbac_verified": True,
                "service_latest_alias_rejected": True,
                "api_exact_read_restart_replay": True,
                "api_exact_read_backup_restore_replay": True,
                "security_audit_verified": True,
                "model_reviewer_service_role_configured": False,
            }
        )
    return value


def _report(
    profile: str,
    *,
    revision: str,
    p2_release_id: str,
    suffix: str,
) -> dict[str, object]:
    service = "SERVICE" in profile
    value: dict[str, object] = {
        "status": "PASS",
        "profile_id": profile,
        "source_revision": revision,
        "product_version": "1.0.1",
        "formal_release_claimed": False,
        "tests_packaged": False,
        "fixtures_packaged": False,
        "package_sha256": suffix * 64,
        "installed_runtime": _installed(
            profile,
            p2_release_id=p2_release_id,
            suffix=suffix,
        ),
    }
    if service:
        value.update(
            {
                "real_postgresql_executed": True,
                "pg_dump_restore_executed": True,
                "postgres_server_version": (
                    "17.11" if profile.startswith("WINDOWS") else "16.10"
                ),
            }
        )
    return value


def _write(path: Path, value: dict[str, object]) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path, str]:
    revision = "a" * 40
    linux_desktop = _write(
        tmp_path / "linux-desktop.json",
        _report(
            "LINUX_DESKTOP_X64",
            revision=revision,
            p2_release_id="99999999-9999-4999-8999-999999999999",
            suffix="1",
        ),
    )
    windows_desktop = _write(
        tmp_path / "windows-desktop.json",
        _report(
            "WINDOWS_DESKTOP_X64",
            revision=revision,
            p2_release_id="99999999-9999-4999-8999-999999999999",
            suffix="2",
        ),
    )
    linux_service = _write(
        tmp_path / "linux-service.json",
        _report(
            "LINUX_SERVICE_X64",
            revision=revision,
            p2_release_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            suffix="3",
        ),
    )
    windows_service = _write(
        tmp_path / "windows-service.json",
        _report(
            "WINDOWS_SERVICE_X64",
            revision=revision,
            p2_release_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            suffix="4",
        ),
    )
    return (
        linux_desktop,
        windows_desktop,
        linux_service,
        windows_service,
        revision,
    )


def test_prcb_c5_four_profile_review_preserves_p2_provenance_but_compares_semantics(
    tmp_path: Path,
) -> None:
    linux_desktop, windows_desktop, linux_service, windows_service, revision = (
        _inputs(tmp_path)
    )
    payload = review(
        linux_desktop=linux_desktop,
        windows_desktop=windows_desktop,
        linux_service=linux_service,
        windows_service=windows_service,
        expected_revision=revision,
    )
    assert payload["status"] == "PASS"
    assert payload["failed_acceptance"] == []
    evidence_hashes_raw = payload["installed_evidence_sha256_by_profile"]
    assert isinstance(evidence_hashes_raw, dict)
    evidence_hashes = cast(dict[str, str], evidence_hashes_raw)
    assert set(evidence_hashes) == {
        "LINUX_DESKTOP_X64",
        "LINUX_SERVICE_X64",
        "WINDOWS_DESKTOP_X64",
        "WINDOWS_SERVICE_X64",
    }
    assert all(len(value) == 64 for value in evidence_hashes.values())
    provenance_raw = payload["p2_runtime_provenance_by_profile"]
    assert isinstance(provenance_raw, dict)
    provenance = cast(dict[str, dict[str, object]], provenance_raw)
    assert (
        provenance["LINUX_DESKTOP_X64"]["estimate_id"]
        != provenance["WINDOWS_DESKTOP_X64"]["estimate_id"]
    )


def test_prcb_c5_four_profile_review_fails_on_p2_semantic_drift(
    tmp_path: Path,
) -> None:
    linux_desktop, windows_desktop, linux_service, windows_service, revision = (
        _inputs(tmp_path)
    )
    value = cast(
        dict[str, Any],
        json.loads(windows_service.read_text(encoding="utf-8")),
    )
    installed = cast(dict[str, Any], value["installed_runtime"])
    installed["p2_reason_codes"] = ["COHORT_NOT_COMPARABLE"]
    windows_service.write_text(json.dumps(value), encoding="utf-8")
    payload = review(
        linux_desktop=linux_desktop,
        windows_desktop=windows_desktop,
        linux_service=linux_service,
        windows_service=windows_service,
        expected_revision=revision,
    )
    assert payload["status"] == "FAIL"
    assert "service_windows_linux_p2_semantic_equivalence" in payload[
        "failed_acceptance"
    ]
