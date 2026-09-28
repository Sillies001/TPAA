from __future__ import annotations

import json
from pathlib import Path

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

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
SESSION_ID = "40000000-0000-4000-8000-000000000001"


class _UnusedStorageBaseline:
    def execute(self) -> StorageBaselineStatus:
        raise AssertionError("M3 API query must not call storage baseline")


class _HistoricalOnlyRepository(InMemoryM3ReleasePublicationRepository):
    def current(self, session_id: str) -> M3PublishedRelease | None:
        del session_id
        raise AssertionError("M3 release-bound query attempted current/latest fallback")


def _hash(value: object) -> str:
    import hashlib

    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _snapshot(
    *,
    release_no: int,
    parent_release_id: str | None,
    request_label: str,
) -> M3ImmutableReleaseSnapshot:
    plan = build_m3_metric_execution_plan(AUTHORITY)
    routing = build_m3_publication_routing_plan(AUTHORITY)
    registry = MetricPluginRegistry()

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {
            "metric_code": request.definition.metric_code,
            "input_token": request.input_payload["input_token"],
        }

    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-api-001-test:{definition.metric_code}:v1",
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
            "source_revision": "test",
            "request_label": request_label,
            "catalog_hash": plan.catalog_sha256,
            "plan_hash": plan.logical_hash,
            "routing_hash": routing.logical_hash,
        },
    )


def _client_with_history() -> tuple[TestClient, str, str]:
    first = _snapshot(
        release_no=1,
        parent_release_id=None,
        request_label="FIRST",
    )
    second = _snapshot(
        release_no=2,
        parent_release_id=first.release_id,
        request_label="SECOND",
    )
    repository = _HistoricalOnlyRepository()
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
        get_storage_baseline_status=_UnusedStorageBaseline(),
        m3_publication=publication,
    )
    return TestClient(create_m3_app(application)), first.release_id, second.release_id


def test_m3_api_001_exposes_exact_release_bound_116_metrics_and_evidence(
    monkeypatch,
) -> None:
    client, first_release_id, second_release_id = _client_with_history()

    def forbidden_execute(*args, **kwargs):
        del args, kwargs
        raise AssertionError("M3 API query attempted business Metric recomputation")

    monkeypatch.setattr(CatalogMetricEngine, "execute", forbidden_execute)

    listed = client.get(f"/m3/releases/{first_release_id}/metrics")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 116
    assert all(item["release_id"] == first_release_id for item in items)
    assert all(len(item["definition_hash"]) == 64 for item in items)
    assert all(len(item["execution_record_hash"]) == 64 for item in items)
    assert all(len(item["evidence_hash"]) == 64 for item in items)

    release = client.get(f"/m3/releases/{first_release_id}")
    assert release.status_code == 200
    assert release.json()["release_id"] == first_release_id
    assert release.json()["metric_count"] == 116
    assert first_release_id != second_release_id

    for metric_code in (items[0]["metric_code"], items[-1]["metric_code"]):
        detail = client.get(
            f"/m3/releases/{first_release_id}/metrics/{metric_code}"
        )
        assert detail.status_code == 200
        payload = detail.json()
        assert payload["release_id"] == first_release_id
        assert payload["metric_code"] == metric_code
        assert payload["definition"]["metric_code"] == metric_code
        assert len(payload["execution"]["record_logical_hash"]) == 64
        assert len(payload["evidence"]["evidence_hash"]) == 64
        assert payload["release_provenance"]["manifest_hash"] == (
            release.json()["manifest_hash"]
        )

        evidence = client.get(
            f"/m3/releases/{first_release_id}/metrics/{metric_code}/evidence"
        )
        assert evidence.status_code == 200
        evidence_payload = evidence.json()
        assert evidence_payload["release_id"] == first_release_id
        assert evidence_payload["metric_code"] == metric_code
        assert evidence_payload["definition_hash"] == (
            payload["definition"]["definition_hash"]
        )
        assert evidence_payload["execution_record_hash"] == (
            payload["execution"]["record_logical_hash"]
        )
        assert evidence_payload["evidence_hash"] == (
            payload["evidence"]["evidence_hash"]
        )


def test_m3_api_001_missing_metric_and_release_fail_closed() -> None:
    client, release_id, _ = _client_with_history()

    missing_metric = client.get(
        f"/m3/releases/{release_id}/metrics/P1-AIR-999/evidence"
    )
    assert missing_metric.status_code == 404
    assert missing_metric.json()["error"]["code"] == "METRIC_NOT_FOUND"

    missing_release = client.get(
        "/m3/releases/00000000-0000-4000-8000-000000000000/metrics"
    )
    assert missing_release.status_code == 404
    assert missing_release.json()["error"]["code"] == "RELEASE_NOT_FOUND"
