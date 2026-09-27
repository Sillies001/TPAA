#!/usr/bin/env python3
"""M3-API-001 exact release-bound 116-Metric/Evidence API qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
TRACKING_ISSUE = 116
SESSION_ID = "40000000-0000-4000-8000-000000000001"


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


def _list(value: object, *, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be list")
    return cast(list[object], value)


def _load(path: Path) -> dict[str, object]:
    return _mapping(json.loads(path.read_text(encoding="utf-8")), field=str(path))


def _has_db_leakage(value: object) -> bool:
    forbidden = {
        "db_row",
        "db_table",
        "table_name",
        "row_id",
        "sql",
        "repository",
        "connection",
        "cursor",
    }
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in forbidden or _has_db_leakage(item):
                return True
    elif isinstance(value, list):
        return any(_has_db_leakage(item) for item in value)
    return False


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
        M3PublishedRelease,
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
        M3ImmutableReleaseSnapshot,
        build_m3_publication_routing_plan,
        build_m3_release_snapshot,
    )

    class UnusedStorageBaseline:
        def execute(self) -> StorageBaselineStatus:
            raise AssertionError("M3 API query attempted storage baseline")

    class HistoricalOnlyRepository(InMemoryM3ReleasePublicationRepository):
        def current(self, session_id: str) -> M3PublishedRelease | None:
            del session_id
            raise AssertionError(
                "M3 API query attempted current/latest Release fallback"
            )

    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    routing = build_m3_publication_routing_plan(AUTHORITY_ROOT)
    registry = MetricPluginRegistry()

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {
            "metric_code": request.definition.metric_code,
            "input_token": request.input_payload["input_token"],
            "upstream_result_hashes": list(request.upstream_result_hashes),
        }

    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-api-001-probe:{definition.metric_code}:v1",
            plugin=probe,
        )
    inputs = {
        definition.metric_code: {
            "input_token": f"M3-API-001::{definition.metric_code}",
        }
        for definition in plan.definitions
    }
    batch = CatalogMetricEngine(
        plan,
        registry,
        operator_implementations=M3_RUNTIME_OPERATOR_IMPLEMENTATIONS,
    ).execute(
        inputs,
        validate_runtime_contract=False,
    )

    def snapshot(
        *,
        release_no: int,
        parent_release_id: str | None,
        request_label: str,
    ) -> M3ImmutableReleaseSnapshot:
        evidence = {
            definition.metric_code: {
                "evidence_contract": "M3_API_001_RELEASE_EVIDENCE_V1",
                "metric_code": definition.metric_code,
                "request_label": request_label,
                "source_artifact_hash": _hash(
                    {
                        "metric_code": definition.metric_code,
                        "request_label": request_label,
                    }
                ),
            }
            for definition in plan.definitions
        }
        return build_m3_release_snapshot(
            session_id=SESSION_ID,
            request_hash=_hash(
                {
                    "command": "M3_API_001_PUBLISH",
                    "request_label": request_label,
                }
            ),
            release_no=release_no,
            parent_release_id=parent_release_id,
            plan=plan,
            routing=routing,
            batch=batch,
            evidence_by_metric=evidence,
            context_snapshot={
                "context_id": "M3-API-001-CONTEXT",
                "context_version": request_label,
            },
            world_snapshot={
                "world_product_id": "M3-API-001-WORLD",
                "request_label": request_label,
            },
            identity_snapshot={
                "aircraft_identity_binding": "M3-API-001-AIRCRAFT",
                "mission_system_identity_binding": "M3-API-001-SYSTEM",
            },
            provenance_snapshot={
                "source_revision": _git_revision(),
                "request_label": request_label,
                "catalog_hash": plan.catalog_sha256,
                "plan_hash": plan.logical_hash,
                "routing_hash": routing.logical_hash,
            },
        )

    first = snapshot(
        release_no=1,
        parent_release_id=None,
        request_label="FIRST",
    )
    second = snapshot(
        release_no=2,
        parent_release_id=first.release_id,
        request_label="SECOND",
    )

    repository = HistoricalOnlyRepository()
    publication = M3PublicationService(repository)
    publication.publish(
        first,
        idempotency_key="m3-api-001-first",
        expected_version_token=0,
    )
    publication.publish(
        second,
        idempotency_key="m3-api-001-second",
        expected_version_token=1,
    )
    application = ApplicationService(
        get_storage_baseline_status=UnusedStorageBaseline(),
        m3_publication=publication,
    )
    client = TestClient(create_m3_app(application))

    release_response = client.get(f"/m3/releases/{first.release_id}")
    list_response = client.get(f"/m3/releases/{first.release_id}/metrics")
    if release_response.status_code != 200 or list_response.status_code != 200:
        raise RuntimeError(
            f"release/list query failed "
            f"{release_response.status_code}/{list_response.status_code}"
        )
    release_payload = _mapping(release_response.json(), field="release")
    list_payload = _mapping(list_response.json(), field="metric_list")
    items_raw = _list(list_payload.get("items"), field="metric_list.items")
    items = [_mapping(item, field="metric_list.item") for item in items_raw]

    first_code = plan.metric_codes[0]
    last_code = plan.metric_codes[-1]
    detail_payloads: dict[str, dict[str, object]] = {}
    evidence_payloads: dict[str, dict[str, object]] = {}
    for code in (first_code, last_code):
        detail_response = client.get(
            f"/m3/releases/{first.release_id}/metrics/{code}"
        )
        evidence_response = client.get(
            f"/m3/releases/{first.release_id}/metrics/{code}/evidence"
        )
        if detail_response.status_code != 200 or evidence_response.status_code != 200:
            raise RuntimeError(
                f"metric query failed {code}: "
                f"{detail_response.status_code}/{evidence_response.status_code}"
            )
        detail_payloads[code] = _mapping(
            detail_response.json(),
            field=f"detail[{code}]",
        )
        evidence_payloads[code] = _mapping(
            evidence_response.json(),
            field=f"evidence[{code}]",
        )

    missing_metric = client.get(
        f"/m3/releases/{first.release_id}/metrics/P1-AIR-999/evidence"
    )
    missing_release = client.get(
        "/m3/releases/00000000-0000-4000-8000-000000000000/metrics"
    )

    transport_source = (
        REPO_ROOT / "src" / "tpaa_api" / "m3_app.py"
    ).read_text(encoding="utf-8")
    application_source = (
        REPO_ROOT / "src" / "tpaa_application" / "m3_publication.py"
    ).read_text(encoding="utf-8")
    transport_forbidden = (
        "tpaa_storage",
        "tpaa_metric",
        "tpaa_observation",
        "sqlalchemy",
        "sqlite3",
        "psycopg",
        "CatalogMetricEngine",
    )
    application_query_forbidden = (
        "build_m3_metric_execution_plan",
        "CatalogMetricEngine(",
        "tpaa_storage",
        "sqlalchemy",
        "sqlite3",
        "psycopg",
    )

    metric_codes = tuple(
        cast(str, item.get("metric_code"))
        for item in items
    )
    release_bound_hashes = all(
        item.get("release_id") == first.release_id
        and isinstance(item.get("definition_hash"), str)
        and len(cast(str, item["definition_hash"])) == 64
        and isinstance(item.get("execution_record_hash"), str)
        and len(cast(str, item["execution_record_hash"])) == 64
        and isinstance(item.get("evidence_hash"), str)
        and len(cast(str, item["evidence_hash"])) == 64
        for item in items
    )
    detail_evidence_exact = all(
        detail_payloads[code].get("release_id") == first.release_id
        and evidence_payloads[code].get("release_id") == first.release_id
        and _mapping(
            detail_payloads[code].get("definition"),
            field=f"detail[{code}].definition",
        ).get("definition_hash")
        == evidence_payloads[code].get("definition_hash")
        and _mapping(
            detail_payloads[code].get("execution"),
            field=f"detail[{code}].execution",
        ).get("record_logical_hash")
        == evidence_payloads[code].get("execution_record_hash")
        and _mapping(
            detail_payloads[code].get("evidence"),
            field=f"detail[{code}].evidence",
        ).get("evidence_hash")
        == evidence_payloads[code].get("evidence_hash")
        for code in (first_code, last_code)
    )

    acceptance = {
        "release_query_exact_historical_identity": (
            release_payload.get("release_id") == first.release_id
            and release_payload.get("manifest_hash") == first.manifest_hash
            and release_payload.get("metric_count") == 116
            and first.release_id != second.release_id
        ),
        "metric_list_exact_116": (
            len(items) == 116
            and metric_codes == plan.metric_codes
        ),
        "all_116_metric_rows_release_bound": release_bound_hashes,
        "first_and_last_metric_detail_evidence_exact": detail_evidence_exact,
        "historical_query_does_not_use_current_latest_pointer": True,
        "transport_has_no_db_or_metric_engine_dependency": not any(
            token in transport_source for token in transport_forbidden
        ),
        "application_query_has_no_db_or_metric_recompute_dependency": not any(
            token in application_source for token in application_query_forbidden
        ),
        "response_has_no_db_leakage": not _has_db_leakage(
            {
                "release": release_payload,
                "items": items,
                "details": detail_payloads,
                "evidence": evidence_payloads,
            }
        ),
        "missing_metric_fails_closed_404": (
            missing_metric.status_code == 404
            and _mapping(
                missing_metric.json(),
                field="missing_metric",
            ).get("error")
            == {
                "code": "METRIC_NOT_FOUND",
                "detail": "P1-AIR-999",
            }
        ),
        "missing_release_fails_closed_404": (
            missing_release.status_code == 404
            and _mapping(
                missing_release.json(),
                field="missing_release",
            ).get("error")
            == {
                "code": "RELEASE_NOT_FOUND",
                "detail": "00000000-0000-4000-8000-000000000000",
            }
        ),
        "no_latest_authority_resolution": True,
        "no_transport_business_metric_recomputation": True,
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)

    return {
        "schema": "TPAA_M3_API_001_RELEASE_BOUND_METRIC_EVIDENCE_EVIDENCE_V1",
        "task_id": "M3-API-001",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": _git_revision(),
        "logical_product": {
            "release": release_payload,
            "metric_codes": list(metric_codes),
            "first_metric_detail": detail_payloads[first_code],
            "last_metric_detail": detail_payloads[last_code],
            "first_metric_evidence": evidence_payloads[first_code],
            "last_metric_evidence": evidence_payloads[last_code],
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "release_bound_query_only": True,
            "metric_count": 116,
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
            "TPAA_M3_API_001_RELEASE_BOUND_METRIC_EVIDENCE_"
            "CROSS_PLATFORM_EVIDENCE_V1"
        ),
        "task_id": "M3-API-001",
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
            "schema": "TPAA_M3_API_001_RELEASE_BOUND_METRIC_EVIDENCE_EVIDENCE_V1",
            "task_id": "M3-API-001",
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
