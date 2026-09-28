from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

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

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"


class _UnusedStorageBaseline:
    def execute(self) -> StorageBaselineStatus:
        raise AssertionError("M3 API-002 workspace must not access persistence")


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


def _client(training_key: str) -> tuple[TestClient, str, str, str]:
    catalog = json.loads(
        (AUTHORITY / "P1_METRIC_CATALOG.json").read_text(encoding="utf-8")
    )
    stage_registry = json.loads(
        (AUTHORITY / "STAGE_REGISTRY.json").read_text(encoding="utf-8")
    )
    training = {
        "BASIC": ("BASIC_FLIGHT", "BASIC_FLIGHT_V1", "EXECUTION"),
        "WVR": ("WVR_ENGAGEMENT", "WVR_ENGAGEMENT_V1", "MANEUVER"),
        "BVR": ("BVR_KILL_CHAIN", "BVR_KILL_CHAIN_V1", "TRACK"),
        "STRIKE": (
            "STRIKE_MISSION",
            "STRIKE_MISSION_V1",
            "ROUTE_TASK_EXECUTION",
        ),
    }
    episode_type, profile_id, stage_code = training[training_key]
    assert stage_registry["profiles"][profile_id]["episode_type"] == episode_type
    assert stage_code in stage_registry["profiles"][profile_id]["ordered_stages"]

    plan = build_m3_metric_execution_plan(AUTHORITY)
    routing = build_m3_publication_routing_plan(AUTHORITY)
    registry = MetricPluginRegistry()

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {"metric_code": request.definition.metric_code}

    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m3-api-002-test:{definition.metric_code}:v1",
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

    session_id = str(uuid5(NAMESPACE_URL, f"api-002:{training_key}:session"))
    episode_id = str(uuid5(NAMESPACE_URL, f"api-002:{training_key}:episode"))
    stage_id = str(uuid5(NAMESPACE_URL, f"api-002:{training_key}:stage"))
    system_type = {
        "BASIC": "RADAR",
        "WVR": "IRST",
        "BVR": "DATALINK",
        "STRIKE": "FUSION",
    }[training_key]
    product_semantics = {
        "LOCAL_TRACK_PRODUCT",
        "ASSOCIATION_IDENTIFICATION_PRODUCT",
    }
    contracts = catalog["family_applicability_contracts"]

    evidence: dict[str, dict[str, object]] = {}
    for index, definition in enumerate(plan.definitions):
        family_code = f"P1-{definition.metric_code.split('-')[1]}-*"
        contract = contracts[family_code]
        mode = contract["applicability_mode"]
        if mode in {"SUBJECT_TYPE", "QUALITY_FOUNDATION"}:
            applicable = True
            reason = f"APPLICABLE_{mode}"
        elif mode in {"SYSTEM_TYPE_EXACT", "SYSTEM_TYPE_SET"}:
            applicable = system_type in contract["allowed_system_types"]
            reason = (
                "APPLICABLE_SYSTEM_TYPE"
                if applicable
                else "NOT_APPLICABLE_SYSTEM_TYPE"
            )
        else:
            required = contract["required_product_semantics"]
            applicable = required in product_semantics
            reason = (
                "APPLICABLE_PRODUCT_CAPABILITY"
                if applicable
                else "NOT_APPLICABLE_PRODUCT_CAPABILITY"
            )
        if applicable:
            statuses = (
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
            instances = [
                {
                    "status": statuses[0],
                    "reason_codes": statuses[1],
                }
            ]
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
        context_snapshot={"training_key": training_key, "profile_id": profile_id},
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
            "source_revision": "test",
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
        get_storage_baseline_status=_UnusedStorageBaseline(),
        m3_publication=publication,
    )
    return TestClient(create_m3_app(application)), release.release_id, episode_id, stage_id


def test_m3_api_002_preserves_four_training_workspace_identity_and_states() -> None:
    for training_key in ("BASIC", "WVR", "BVR", "STRIKE"):
        client, release_id, episode_id, stage_id = _client(training_key)
        response = client.get(f"/m3/releases/{release_id}/workspace")
        assert response.status_code == 200
        payload = response.json()
        assert payload["release_id"] == release_id
        assert payload["training"]["training_key"] == training_key
        assert payload["training"]["episode_id"] == episode_id
        assert payload["training"]["stage_id"] == stage_id
        assert len(payload["metrics"]) == 116
        assert sum(item["metric_count"] for item in payload["families"]) == 116
        assert len(payload["release_provenance"]["provenance_hash"]) == 64
        for metric in payload["metrics"]:
            assert metric["release_id"] == release_id
            if metric["applicability"]["applicable"] is False:
                assert metric["instances"] == []
                assert metric["applicability"]["reason_codes"]
            else:
                assert metric["instances"]
                for instance in metric["instances"]:
                    if instance["status"] != "VALID":
                        assert instance["reason_codes"]
