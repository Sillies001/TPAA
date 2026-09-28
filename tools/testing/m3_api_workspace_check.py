#!/usr/bin/env python3
"""M3-API-002 four-training release-bound workspace qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, uuid5

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
TRACKING_ISSUE = 116

TRAINING_CASES = {
    "BASIC": ("BASIC_FLIGHT", "BASIC_FLIGHT_V1", "EXECUTION", "RADAR"),
    "WVR": ("WVR_ENGAGEMENT", "WVR_ENGAGEMENT_V1", "MANEUVER", "IRST"),
    "BVR": ("BVR_KILL_CHAIN", "BVR_KILL_CHAIN_V1", "TRACK", "DATALINK"),
    "STRIKE": (
        "STRIKE_MISSION",
        "STRIKE_MISSION_V1",
        "ROUTE_TASK_EXECUTION",
        "FUSION",
    ),
}


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"{field} must be string-keyed object")
    return cast(dict[str, object], value)


def _load(path: Path) -> dict[str, object]:
    return _mapping(json.loads(path.read_text(encoding="utf-8")), field=str(path))


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from fastapi.testclient import TestClient

    from tpaa_api import create_m3_app
    from tpaa_application import (
        ApplicationService,
        InMemoryM3ReleasePublicationRepository,
        M3PublicationService,
        StorageBaselineStatus,
    )
    from tpaa_metric import (
        M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
        CatalogMetricEngine,
        M2MetricPluginRequest,
        MetricPluginRegistry,
        build_m3_metric_execution_plan,
    )
    from tpaa_observation import (
        build_m3_publication_routing_plan,
        build_m3_release_snapshot,
    )

    class UnusedStorageBaseline:
        def execute(self) -> StorageBaselineStatus:
            raise AssertionError("workspace query attempted persistence")

    catalog = _load(AUTHORITY_ROOT / "P1_METRIC_CATALOG.json")
    stage_registry = _load(AUTHORITY_ROOT / "STAGE_REGISTRY.json")
    profiles = _mapping(stage_registry.get("profiles"), field="stage profiles")
    contracts = _mapping(
        catalog.get("family_applicability_contracts"),
        field="family applicability contracts",
    )

    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    routing = build_m3_publication_routing_plan(AUTHORITY_ROOT)
    registry = MetricPluginRegistry()

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {"metric_code": request.definition.metric_code}

    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-api-002-probe:{definition.metric_code}:v1",
            plugin=probe,
        )
    batch = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    ).execute(
        {
            definition.metric_code: {"token": definition.metric_code}
            for definition in plan.definitions
        },
        validate_runtime_contract=False,
    )

    product: dict[str, object] = {}
    acceptance: dict[str, bool] = {}
    product_semantics = {
        "LOCAL_TRACK_PRODUCT",
        "ASSOCIATION_IDENTIFICATION_PRODUCT",
    }

    for training_key, (
        episode_type,
        profile_id,
        stage_code,
        system_type,
    ) in TRAINING_CASES.items():
        profile = _mapping(profiles.get(profile_id), field=profile_id)
        raw_stages = profile.get("ordered_stages")
        authority_exact = (
            profile.get("episode_type") == episode_type
            and isinstance(raw_stages, list)
            and stage_code in raw_stages
        )
        session_id = str(
            uuid5(NAMESPACE_URL, f"m3-api-002:{training_key}:session")
        )
        episode_id = str(
            uuid5(NAMESPACE_URL, f"m3-api-002:{training_key}:episode")
        )
        stage_id = str(
            uuid5(NAMESPACE_URL, f"m3-api-002:{training_key}:stage")
        )

        evidence: dict[str, dict[str, object]] = {}
        applicability_expected: dict[str, bool] = {}
        for index, definition in enumerate(plan.definitions):
            namespace = definition.metric_code.split("-")[1]
            family_code = f"P1-{namespace}-*"
            contract = _mapping(contracts.get(family_code), field=family_code)
            mode = contract.get("applicability_mode")
            if mode in {"SUBJECT_TYPE", "QUALITY_FOUNDATION"}:
                applicable = True
                reason = f"APPLICABLE_{mode}"
            elif mode in {"SYSTEM_TYPE_EXACT", "SYSTEM_TYPE_SET"}:
                allowed = contract.get("allowed_system_types")
                if not isinstance(allowed, list):
                    raise ValueError(f"{family_code}.allowed_system_types invalid")
                applicable = system_type in allowed
                reason = (
                    "APPLICABLE_SYSTEM_TYPE"
                    if applicable
                    else "NOT_APPLICABLE_SYSTEM_TYPE"
                )
            elif mode == "PRODUCT_CAPABILITY":
                required = contract.get("required_product_semantics")
                if not isinstance(required, str):
                    raise ValueError(
                        f"{family_code}.required_product_semantics invalid"
                    )
                applicable = required in product_semantics
                reason = (
                    "APPLICABLE_PRODUCT_CAPABILITY"
                    if applicable
                    else "NOT_APPLICABLE_PRODUCT_CAPABILITY"
                )
            else:
                raise ValueError(f"{family_code}.applicability_mode={mode!r}")

            applicability_expected[definition.metric_code] = applicable
            if applicable:
                status, reasons = (
                    ("N_A", ["SYNTHETIC_N_A"])
                    if index == 0
                    else ("INSUFFICIENT_DATA", ["SYNTHETIC_DATA_GAP"])
                    if index == 1
                    else ("REVIEW_REQUIRED", ["SYNTHETIC_REVIEW"])
                    if index == 2
                    else ("INVALID", ["SYNTHETIC_INVALID"])
                    if index == 3
                    else ("VALID", [])
                )
                instances = [{"status": status, "reason_codes": reasons}]
                applicability_reasons: list[str] = []
            else:
                instances = []
                applicability_reasons = [reason]

            evidence[definition.metric_code] = {
                "workspace_contract": "M3_API_002_WORKSPACE_EVIDENCE_V1",
                "training_key": training_key,
                "episode_type": episode_type,
                "stage_profile_id": profile_id,
                "episode_id": episode_id,
                "stage_id": stage_id,
                "stage_code": stage_code,
                "family_code": family_code,
                "system_type": system_type,
                "applicable": applicable,
                "applicability_reason_codes": applicability_reasons,
                "instances": instances,
            }

        release = build_m3_release_snapshot(
            session_id=session_id,
            request_hash=_hash({"training_key": training_key}),
            release_no=1,
            parent_release_id=None,
            plan=plan,
            routing=routing,
            batch=batch,
            evidence_by_metric=evidence,
            context_snapshot={
                "training_key": training_key,
                "profile_id": profile_id,
            },
            world_snapshot={
                "episode_id": episode_id,
                "stage_id": stage_id,
                "stage_code": stage_code,
            },
            identity_snapshot={
                "episode_id": episode_id,
                "stage_id": stage_id,
            },
            provenance_snapshot={
                "source_revision": _git_revision(),
                "training_key": training_key,
                "profile_id": profile_id,
            },
        )
        repository = InMemoryM3ReleasePublicationRepository()
        publication = M3PublicationService(repository)
        publication.publish(
            release,
            idempotency_key=f"m3-api-002-{training_key.lower()}",
            expected_version_token=0,
        )
        application = ApplicationService(
            get_storage_baseline_status=UnusedStorageBaseline(),
            m3_publication=publication,
        )
        response = TestClient(create_m3_app(application)).get(
            f"/m3/releases/{release.release_id}/workspace"
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"{training_key} workspace query failed {response.status_code}"
            )
        payload = _mapping(response.json(), field=f"{training_key}.workspace")
        metrics_raw = payload.get("metrics")
        families_raw = payload.get("families")
        if not isinstance(metrics_raw, list) or not isinstance(families_raw, list):
            raise ValueError(f"{training_key} workspace rows invalid")
        metrics = [
            _mapping(item, field=f"{training_key}.metric")
            for item in metrics_raw
        ]
        training = _mapping(payload.get("training"), field=f"{training_key}.training")
        provenance = _mapping(
            payload.get("release_provenance"),
            field=f"{training_key}.provenance",
        )

        identity_exact = (
            training.get("training_key") == training_key
            and training.get("episode_type") == episode_type
            and training.get("stage_profile_id") == profile_id
            and training.get("episode_id") == episode_id
            and training.get("stage_id") == stage_id
            and training.get("stage_code") == stage_code
        )
        applicability_exact = all(
            _mapping(
                metric.get("applicability"),
                field=f"{training_key}.applicability",
            ).get("applicable")
            == applicability_expected[cast(str, metric["metric_code"])]
            for metric in metrics
        )
        no_fake_non_applicable = all(
            bool(
                _mapping(
                    metric.get("applicability"),
                    field=f"{training_key}.applicability",
                ).get("applicable")
            )
            or metric.get("instances") == []
            for metric in metrics
        )
        status_reason_exact = all(
            isinstance(metric.get("instances"), list)
            and all(
                isinstance(instance, dict)
                and instance.get("status")
                in {
                    "VALID",
                    "N_A",
                    "INSUFFICIENT_DATA",
                    "INVALID",
                    "REVIEW_REQUIRED",
                }
                and (
                    instance.get("status") == "VALID"
                    or bool(instance.get("reason_codes"))
                )
                for instance in cast(list[object], metric["instances"])
            )
            for metric in metrics
        )
        provenance_exact = (
            payload.get("release_id") == release.release_id
            and payload.get("manifest_hash") == release.manifest_hash
            and provenance.get("catalog_hash") == release.catalog_hash
            and provenance.get("metric_execution_plan_hash")
            == release.metric_execution_plan_hash
            and provenance.get("publication_routing_plan_hash")
            == release.publication_routing_plan_hash
            and provenance.get("execution_batch_hash")
            == release.execution_batch_hash
            and provenance.get("provenance_hash")
            == release.bindings.provenance_hash
        )
        acceptance[f"{training_key.lower()}_stage_authority_exact"] = authority_exact
        acceptance[f"{training_key.lower()}_episode_stage_identity_exact"] = identity_exact
        acceptance[f"{training_key.lower()}_family_applicability_exact"] = (
            applicability_exact
        )
        acceptance[f"{training_key.lower()}_non_applicable_fail_closed"] = (
            no_fake_non_applicable
        )
        acceptance[f"{training_key.lower()}_status_reason_semantics_exact"] = (
            status_reason_exact
        )
        acceptance[f"{training_key.lower()}_release_provenance_exact"] = (
            provenance_exact
        )
        acceptance[f"{training_key.lower()}_metric_membership_exact_116"] = (
            len(metrics) == 116
            and tuple(
                cast(str, metric.get("metric_code"))
                for metric in metrics
            )
            == plan.metric_codes
            and sum(
                cast(int, _mapping(row, field="family").get("metric_count"))
                for row in cast(list[object], families_raw)
            )
            == 116
        )
        product[training_key] = {
            "release_id": release.release_id,
            "manifest_hash": release.manifest_hash,
            "training": training,
            "families": families_raw,
            "metrics": metrics,
            "release_provenance": provenance,
        }

    application_source = (
        REPO_ROOT / "src" / "tpaa_application" / "m3_workspace.py"
    ).read_text(encoding="utf-8")
    transport_source = (
        REPO_ROOT / "src" / "tpaa_api" / "m3_app.py"
    ).read_text(encoding="utf-8")
    acceptance["workspace_projector_has_no_current_authority_or_db_import"] = (
        "tpaa_world" not in application_source
        and "tpaa_metric" not in application_source
        and "tpaa_storage" not in application_source
        and "sqlalchemy" not in application_source
        and "sqlite3" not in application_source
        and "psycopg" not in application_source
    )
    acceptance["transport_delegates_without_recompute_or_db_access"] = (
        "tpaa_metric" not in transport_source
        and "tpaa_observation" not in transport_source
        and "tpaa_storage" not in transport_source
        and "CatalogMetricEngine" not in transport_source
    )
    failed = sorted(key for key, passed in acceptance.items() if not passed)

    return {
        "schema": "TPAA_M3_API_002_FOUR_TRAINING_WORKSPACE_EVIDENCE_V1",
        "task_id": "M3-API-002",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": _git_revision(),
        "logical_product": product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "workspace_projection_only": True,
            "four_training_types": True,
            "metric_membership_per_workspace": 116,
            "historical_release_id_explicit": True,
            "latest_authority_resolution_used": False,
            "database_access_executed": False,
            "business_metric_recomputation_executed": False,
            "gui_rendering_executed": False,
        },
    }


def compare_evidence(
    windows_path: Path,
    linux_path: Path,
    *,
    expected_revision: str,
) -> dict[str, object]:
    windows = _load(windows_path)
    linux = _load(linux_path)
    checks = {
        "windows_status_pass": windows.get("status") == "PASS",
        "linux_status_pass": linux.get("status") == "PASS",
        "windows_task_complete": windows.get("task_complete") is True,
        "linux_task_complete": linux.get("task_complete") is True,
        "windows_implementation_complete": (
            windows.get("implementation_complete") is True
        ),
        "linux_implementation_complete": linux.get("implementation_complete") is True,
        "windows_revision_exact": windows.get("source_revision") == expected_revision,
        "linux_revision_exact": linux.get("source_revision") == expected_revision,
        "logical_product_equal": (
            windows.get("logical_product") == linux.get("logical_product")
        ),
        "acceptance_equal": windows.get("acceptance") == linux.get("acceptance"),
        "failed_acceptance_empty": (
            windows.get("failed_acceptance") == []
            and linux.get("failed_acceptance") == []
        ),
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    return {
        "schema": (
            "TPAA_M3_API_002_FOUR_TRAINING_WORKSPACE_"
            "CROSS_PLATFORM_EVIDENCE_V1"
        ),
        "task_id": "M3-API-002",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": expected_revision,
        "windows_source_revision": windows.get("source_revision"),
        "linux_source_revision": linux.get("source_revision"),
        "logical_product": windows.get("logical_product"),
        "checks": checks,
        "failed_acceptance": failed,
    }


def _write(payload: dict[str, object], path: Path | None) -> None:
    rendered = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ) + "\n"
    print(rendered, end="")
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(rendered, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    check = sub.add_parser("check")
    check.add_argument("--evidence", type=Path)
    compare = sub.add_parser("compare")
    compare.add_argument("--windows", type=Path, required=True)
    compare.add_argument("--linux", type=Path, required=True)
    compare.add_argument("--expected-revision", required=True)
    compare.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()

    try:
        if args.mode == "check":
            payload = verify()
            evidence = args.evidence
        else:
            payload = compare_evidence(
                args.windows,
                args.linux,
                expected_revision=args.expected_revision,
            )
            evidence = args.evidence
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M3_API_002_FOUR_TRAINING_WORKSPACE_EVIDENCE_V1",
            "task_id": "M3-API-002",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        evidence = getattr(args, "evidence", None)
        code = 2
    _write(payload, evidence)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
