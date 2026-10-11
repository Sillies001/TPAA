from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

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
        "world_product_count": 4,
        "stage_count": 4,
        "world_relation_count": 3,
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
    assert payload["ed2_b3_upper_projection_by_profile"] == {}
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


def test_prcb_c5_four_profile_review_rejects_partial_ed2_b3_evidence(
    tmp_path: Path,
) -> None:
    linux_desktop, windows_desktop, linux_service, windows_service, revision = (
        _inputs(tmp_path)
    )
    value = cast(
        dict[str, Any],
        json.loads(linux_desktop.read_text(encoding="utf-8")),
    )
    value["ed2_b3_upper_runtime"] = {}
    linux_desktop.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(
        RuntimeError,
        match="ED2 B3 installed upper evidence incomplete across profiles",
    ):
        review(
            linux_desktop=linux_desktop,
            windows_desktop=windows_desktop,
            linux_service=linux_service,
            windows_service=windows_service,
            expected_revision=revision,
        )


def _attach_ed2_b3(
    path: Path,
    *,
    suffix: str,
    stable_plugin_id: str = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
) -> None:
    report = cast(
        dict[str, Any],
        json.loads(path.read_text(encoding="utf-8")),
    )
    p4_drafts = [f"p4-draft-{suffix}-{index}" for index in range(4)]
    p4_approved = [f"p4-approved-{suffix}-{index}" for index in range(4)]
    p5_draft = f"p5-draft-{suffix}"
    p5_approved = f"p5-approved-{suffix}"
    b2 = {
        "schema": "TPAA_ED2_B2_CONTINUOUS_QUALIFICATION_RESULT_V1",
        "status": "PASS",
        "p4_draft_revision_ids": p4_drafts,
        "p4_approved_revision_ids": p4_approved,
        "p5_draft_revision_id": p5_draft,
        "p5_approved_revision_id": p5_approved,
    }
    p4_refs = tuple(p4_drafts + p4_approved)
    p5_refs = (p5_draft, p5_approved)
    authority = hashlib.sha256(
        json.dumps(
            {
                "p4_revision_refs": list(p4_refs),
                "p5_revision_refs": list(p5_refs),
            },
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    report["ed2_b2_continuous_runtime"] = b2
    report["ed2_b3_upper_runtime"] = {
        "schema": "TPAA_ED2_B3_UPPER_QUALIFICATION_RESULT_V1",
        "status": "PASS",
        "snapshot_count": 8,
        "snapshot_ids": {
            "event_relation_root_cause": (
                "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            ),
            "human_longitudinal": f"human-{suffix}",
            "team_longitudinal": f"team-{suffix}",
            "course_analytics": f"course-{suffix}",
            "unit_analytics": f"unit-{suffix}",
            "training_plugin": stable_plugin_id,
            "joint_lvc_gateway": (
                "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
            ),
            "media_debrief": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        },
        "source_release_ids": [
            "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
        ],
        "event_availability": "UNAVAILABLE",
        "objective_availability": "UNAVAILABLE",
        "assessment_authority_mode": "ED2_B2_EXACT_REVISION_OUTPUT",
        "assessment_authority_sha256": authority,
        "p4_revision_ref_count": 12,
        "p5_revision_ref_count": 3,
        "semantic_layers": ["W", "P", "A", "J", "M"],
        "media_uri": "tpaa-object://ed2-b3/media/qualification-media.txt",
        "media_sha256": "a" * 64,
        "transcript_uri": (
            "tpaa-object://ed2-b3/media/qualification-transcript.txt"
        ),
        "transcript_sha256": "b" * 64,
        "verification_ids": [
            "V-SAFE-002",
            "V-COHORT-001",
            "V-PLUGIN-001",
            "V-KNOW-001",
            "V-VIS-001",
        ],
        "restart_exact_replay": True,
        "backup_restore_exact_replay": True,
        "api_exact_read_verified": True,
        "api_latest_alias_rejected": True,
        "privacy_boundaries_verified": True,
        "training_plugin_contracts_verified": True,
        "joint_lvc_boundary_verified": True,
        "mutable_latest_fallback_used": False,
        "formal_release_claimed": False,
    }
    path.write_text(json.dumps(report), encoding="utf-8")


def test_prcb_c5_b3_compares_longitudinal_semantics_not_profile_local_ids(
    tmp_path: Path,
) -> None:
    linux_desktop, windows_desktop, linux_service, windows_service, revision = (
        _inputs(tmp_path)
    )
    for suffix, path in (
        ("1", linux_desktop),
        ("2", windows_desktop),
        ("3", linux_service),
        ("4", windows_service),
    ):
        _attach_ed2_b3(path, suffix=suffix)

    payload = review(
        linux_desktop=linux_desktop,
        windows_desktop=windows_desktop,
        linux_service=linux_service,
        windows_service=windows_service,
        expected_revision=revision,
    )
    assert payload["status"] == "PASS"
    acceptance = cast(dict[str, object], payload["acceptance"])
    assert acceptance["ed2_b3_upper_logical_equivalence_all_profiles"] is True
    local_ids = cast(
        dict[str, dict[str, str]],
        payload["ed2_b3_profile_local_snapshot_ids"],
    )
    assert (
        local_ids["LINUX_DESKTOP_X64"]["human_longitudinal"]
        != local_ids["WINDOWS_DESKTOP_X64"]["human_longitudinal"]
    )


def test_prcb_c5_b3_fails_on_stable_upper_identity_drift(
    tmp_path: Path,
) -> None:
    linux_desktop, windows_desktop, linux_service, windows_service, revision = (
        _inputs(tmp_path)
    )
    for suffix, path in (
        ("1", linux_desktop),
        ("2", windows_desktop),
        ("3", linux_service),
        ("4", windows_service),
    ):
        _attach_ed2_b3(path, suffix=suffix)
    _attach_ed2_b3(
        windows_service,
        suffix="4",
        stable_plugin_id="ffffffff-ffff-4fff-8fff-ffffffffffff",
    )

    payload = review(
        linux_desktop=linux_desktop,
        windows_desktop=windows_desktop,
        linux_service=linux_service,
        windows_service=windows_service,
        expected_revision=revision,
    )
    assert payload["status"] == "FAIL"
    assert "ed2_b3_upper_logical_equivalence_all_profiles" in payload[
        "failed_acceptance"
    ]


def test_prcb_c5_b3_rejects_authority_hash_not_bound_to_b2(
    tmp_path: Path,
) -> None:
    linux_desktop, windows_desktop, linux_service, windows_service, revision = (
        _inputs(tmp_path)
    )
    for suffix, path in (
        ("1", linux_desktop),
        ("2", windows_desktop),
        ("3", linux_service),
        ("4", windows_service),
    ):
        _attach_ed2_b3(path, suffix=suffix)

    value = cast(
        dict[str, Any],
        json.loads(windows_service.read_text(encoding="utf-8")),
    )
    b3 = cast(dict[str, Any], value["ed2_b3_upper_runtime"])
    b3["assessment_authority_sha256"] = "0" * 64
    windows_service.write_text(json.dumps(value), encoding="utf-8")

    with pytest.raises(
        RuntimeError,
        match="ED2 B3 installed upper evidence invalid",
    ):
        review(
            linux_desktop=linux_desktop,
            windows_desktop=windows_desktop,
            linux_service=linux_service,
            windows_service=windows_service,
            expected_revision=revision,
        )

