"""Cross-platform M1 Batch 2 service smoke for M1-PLAT-003."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Never
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY_ROOT = ROOT / "baseline" / "CB-1.4.0" / "canonical"
SCHEMA = "TPAA_M1_BATCH_2_SERVICE_SMOKE_V1"


def _ensure_project_src() -> None:
    src_root = str(ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)


def _platform_matches(expected_platform: str) -> bool:
    if expected_platform == "windows":
        return sys.platform == "win32"
    if expected_platform == "linux":
        return sys.platform.startswith("linux")
    return False


def run(*, expected_platform: str, source_revision: str, evidence: Path) -> int:
    _ensure_project_src()

    from fastapi.testclient import TestClient

    from tpaa_api import create_m1_app
    from tpaa_application import ApplicationService, M1PublicationService
    from tpaa_application.m1_repository import InMemorySessionPublicationRepository

    class _UnusedStorageBaseline:
        def execute(self) -> Never:
            raise AssertionError("M1 Batch 2 service smoke must not use M0 storage baseline")

    repository = InMemorySessionPublicationRepository()
    publication = M1PublicationService(
        fixture_root=FIXTURE_ROOT,
        authority_root=AUTHORITY_ROOT,
        repository=repository,
    )
    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorageBaseline(),
        m1_publication=publication,
    )
    client = TestClient(create_m1_app(application))

    fixture_id = "BF_M1_NOMINAL_V1"
    import_body = {"fixture_id": fixture_id}
    imported = client.post(
        "/m1/commands/import-session",
        headers={"Idempotency-Key": "m1-batch-2-service-import"},
        json=import_body,
    )
    imported_retry = client.post(
        "/m1/commands/import-session",
        headers={"Idempotency-Key": "m1-batch-2-service-import"},
        json=import_body,
    )

    computed = client.post(
        "/m1/commands/compute-session",
        headers={"Idempotency-Key": "m1-batch-2-service-compute"},
        json={"fixture_id": fixture_id},
    )
    computed_retry = client.post(
        "/m1/commands/compute-session",
        headers={"Idempotency-Key": "m1-batch-2-service-compute"},
        json={"fixture_id": fixture_id},
    )

    publish_body = {
        "fixture_id": fixture_id,
        "aircraft_model_id": str(uuid5(NAMESPACE_URL, "m1-batch-2-service-model")),
        "aircraft_instance_id": str(uuid5(NAMESPACE_URL, "m1-batch-2-service-instance")),
        "subject_entity_id": str(uuid5(NAMESPACE_URL, "m1-batch-2-service-entity")),
        "capability_dimension": "TEST_EXPLICIT_CAPABILITY_DIMENSION",
        "capability_type": "TEST_EXPLICIT_CAPABILITY_TYPE",
        "expected_version_token": 0,
    }
    published = client.post(
        "/m1/commands/publish-session",
        headers={"Idempotency-Key": "m1-batch-2-service-publish"},
        json=publish_body,
    )
    published_retry = client.post(
        "/m1/commands/publish-session",
        headers={"Idempotency-Key": "m1-batch-2-service-publish"},
        json=publish_body,
    )

    failures: list[str] = []
    if published.status_code != 201:
        failures.append(f"publish_status={published.status_code}")
        release_id = ""
    else:
        release_id = str(published.json()["release_id"])

    release = client.get(f"/m1/releases/{release_id}") if release_id else None
    context = client.get(f"/m1/releases/{release_id}/context") if release_id else None
    topology = client.get(f"/m1/releases/{release_id}/topology") if release_id else None
    metrics = client.get(f"/m1/releases/{release_id}/metrics") if release_id else None
    observations = client.get(f"/m1/releases/{release_id}/observations") if release_id else None
    replay = client.post(f"/m1/releases/{release_id}/replay") if release_id else None

    metric_codes = [
        "P1-AIR-001",
        "P1-AIR-002",
        "P1-AIR-003",
        "P1-AIR-004",
        "P1-AIR-007",
    ]
    details: dict[str, dict[str, object]] = {}
    evidences: dict[str, dict[str, object]] = {}
    if release_id:
        for metric_code in metric_codes:
            detail_response = client.get(
                f"/m1/releases/{release_id}/metrics/{metric_code}"
            )
            evidence_response = client.get(
                f"/m1/releases/{release_id}/metrics/{metric_code}/evidence"
            )
            if detail_response.status_code == 200:
                details[metric_code] = detail_response.json()
            else:
                failures.append(
                    f"metric_detail:{metric_code}:status={detail_response.status_code}"
                )
            if evidence_response.status_code == 200:
                evidences[metric_code] = evidence_response.json()
            else:
                failures.append(
                    f"metric_evidence:{metric_code}:status={evidence_response.status_code}"
                )

    series_payload: dict[str, object] = {}
    if topology is not None and topology.status_code == 200 and release_id:
        topology_payload = topology.json()
        start_us = topology_payload["session"]["start_session_time_us"]
        end_us = topology_payload["session"]["end_session_time_us"]
        series = client.get(
            f"/m1/releases/{release_id}/series",
            params={
                "start_session_time_us": start_us,
                "end_session_time_us": end_us,
                "limit": 3,
            },
        )
        if series.status_code == 200:
            series_payload = series.json()
        else:
            failures.append(f"series_status={series.status_code}")

    import_payload = imported.json() if imported.status_code == 200 else {}
    import_retry_payload = imported_retry.json() if imported_retry.status_code == 200 else {}
    compute_payload = computed.json() if computed.status_code == 200 else {}
    compute_retry_payload = computed_retry.json() if computed_retry.status_code == 200 else {}
    publish_payload = published.json() if published.status_code == 201 else {}
    publish_retry_payload = published_retry.json() if published_retry.status_code == 200 else {}
    release_payload = release.json() if release is not None and release.status_code == 200 else {}
    context_payload = context.json() if context is not None and context.status_code == 200 else {}
    topology_payload = topology.json() if topology is not None and topology.status_code == 200 else {}
    metrics_payload = metrics.json() if metrics is not None and metrics.status_code == 200 else {}
    observations_payload = (
        observations.json()
        if observations is not None and observations.status_code == 200
        else {}
    )
    replay_payload = replay.json() if replay is not None and replay.status_code == 200 else {}

    series_rows = series_payload.get("rows")

    acceptance = {
        "platform_matches_expected": _platform_matches(expected_platform),
        "import_command_idempotent": (
            imported.status_code == 200
            and imported_retry.status_code == 200
            and import_payload.get("reused") is False
            and import_retry_payload.get("reused") is True
            and import_payload.get("request_hash") == import_retry_payload.get("request_hash")
        ),
        "compute_command_idempotent_and_unpublished": (
            computed.status_code == 200
            and computed_retry.status_code == 200
            and compute_payload.get("reused") is False
            and compute_retry_payload.get("reused") is True
            and compute_payload.get("metric_batch_hash")
            == compute_retry_payload.get("metric_batch_hash")
            and compute_payload.get("database_persistence_executed") is False
            and compute_payload.get("publication_executed") is False
        ),
        "publish_command_idempotent": (
            published.status_code == 201
            and published_retry.status_code == 200
            and publish_payload.get("reused") is False
            and publish_retry_payload.get("reused") is True
            and publish_payload.get("release_id") == publish_retry_payload.get("release_id")
            and publish_payload.get("manifest_hash") == publish_retry_payload.get("manifest_hash")
        ),
        "release_identity_provenance_status": (
            release is not None
            and release.status_code == 200
            and release_payload.get("release_id") == release_id
            and release_payload.get("status") == "PUBLISHED"
            and isinstance(release_payload.get("identity"), dict)
            and isinstance(release_payload.get("provenance"), dict)
        ),
        "generated_context_and_explicit_topology": (
            context is not None
            and context.status_code == 200
            and topology is not None
            and topology.status_code == 200
            and context_payload.get("context_id") == release_payload.get("context_id")
            and topology_payload.get("release_id") == release_id
            and len(topology_payload.get("stages", [])) == 4
        ),
        "metric_definition_and_evidence_release_bound": (
            metrics is not None
            and metrics.status_code == 200
            and [item.get("metric_code") for item in metrics_payload.get("items", [])]
            == metric_codes
            and set(details) == set(metric_codes)
            and set(evidences) == set(metric_codes)
            and all(item.get("release_id") == release_id for item in details.values())
            and all(item.get("release_id") == release_id for item in evidences.values())
        ),
        "observation_dto_projection": (
            observations is not None
            and observations.status_code == 200
            and len(observations_payload.get("items", [])) == 5
            and all(
                isinstance(item.get("observation_start_session_time_us"), str)
                and isinstance(item.get("observation_end_session_time_us"), str)
                for item in observations_payload.get("items", [])
            )
        ),
        "historical_replay_exact": (
            replay is not None
            and replay.status_code == 200
            and replay_payload.get("release_id") == release_id
            and replay_payload.get("release_status") == "PUBLISHED"
            and replay_payload.get("status") == "PASS"
            and replay_payload.get("exact_logical_products_equal") is True
            and replay_payload.get("current_latest_fallback_used") is False
        ),
        "bounded_series_query": (
            series_payload.get("release_id") == release_id
            and series_payload.get("limit") == 3
            and isinstance(series_rows, list)
            and len(series_rows) <= 3
        ),
    }

    failed_acceptance = sorted(
        name for name, passed in acceptance.items() if not passed
    )
    status = "PASS" if not failures and not failed_acceptance else "FAIL"

    def definition_hash(code: str) -> str | None:
        detail = details.get(code)
        if detail is None:
            return None
        definition = detail.get("definition")
        if not isinstance(definition, dict):
            return None
        value = definition.get("definition_hash")
        return value if isinstance(value, str) else None

    logical_product: dict[str, object] = {
        "fixture_id": fixture_id,
        "import_request_hash": import_payload.get("request_hash"),
        "compute_request_hash": compute_payload.get("request_hash"),
        "metric_batch_hash": compute_payload.get("metric_batch_hash"),
        "release_id": release_id,
        "publish_request_hash": publish_payload.get("request_hash"),
        "manifest_hash": publish_payload.get("manifest_hash"),
        "context_binding_hash": release_payload.get("context_binding_hash"),
        "catalog_hash": release_payload.get("catalog_hash"),
        "world_logical_hash": release_payload.get("world_logical_hash"),
        "metric_codes": metric_codes,
        "definition_hashes": {
            code: definition_hash(code)
            for code in metric_codes
            if code in details
        },
        "evidence_hashes": {
            code: evidences[code]["logical_hash"]
            for code in metric_codes
            if code in evidences
        },
        "observation_ids": {
            item["metric_code"]: item["observation_id"]
            for item in observations_payload.get("items", [])
            if isinstance(item, dict)
        },
    }

    payload: dict[str, object] = {
        "schema": SCHEMA,
        "tracking_issue": 87,
        "task_ids": ["M1-PLAT-003"],
        "source_revision": source_revision,
        "platform": expected_platform,
        "status": status,
        "acceptance": acceptance,
        "failed_acceptance": failed_acceptance,
        "failures": failures,
        "logical_product": logical_product,
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if status == "PASS" else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-platform", choices=("windows", "linux"), required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(
        expected_platform=args.expected_platform,
        source_revision=args.source_revision,
        evidence=args.evidence,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
