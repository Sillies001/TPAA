"""Consolidated executable evidence for M1 Batch 2 backend acceptance."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Never
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from tpaa_api import create_m1_app  # noqa: E402
from tpaa_application import (  # noqa: E402
    ApplicationService,
    M1PublicationService,
    M1PublishSessionCommand,
    M1PublishSessionResult,
)
from tpaa_application.m1_repository import (  # noqa: E402
    InMemorySessionPublicationRepository,
)

FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY_ROOT = ROOT / "baseline" / "CB-1.4.0" / "canonical"
SCHEMA = "TPAA_M1_BATCH_2_BACKEND_EVIDENCE_V1"
TASK_IDS = (
    "M1-OBS-001",
    "M1-OBS-002",
    "M1-OBS-003",
    "M1-OBS-004",
    "M1-OBS-005",
    "M1-STO-001",
    "M1-STO-002",
    "M1-API-001",
    "M1-API-002",
    "M1-API-003",
    "M1-API-004",
    "M1-API-005",
    "M1-TST-004",
    "M1-TST-005",
    "M1-TST-006",
    "M1-TST-007",
)
DECIMAL_STRING = re.compile(r"^-?[0-9]+$")


def _platform_matches(expected: str) -> bool:
    if expected == "windows":
        return sys.platform == "win32"
    return sys.platform.startswith("linux")


def _command(token: int, capability_type: str) -> M1PublishSessionCommand:
    return M1PublishSessionCommand(
        fixture_id="BF_M1_NOMINAL_V1",
        aircraft_model_id=str(uuid5(NAMESPACE_URL, "m1-batch-2-backend-model")),
        aircraft_instance_id=str(uuid5(NAMESPACE_URL, "m1-batch-2-backend-instance")),
        subject_entity_id=str(uuid5(NAMESPACE_URL, "m1-batch-2-backend-entity")),
        capability_dimension="TEST_EXPLICIT_CAPABILITY_DIMENSION",
        capability_type=capability_type,
        expected_version_token=token,
    )


def _service() -> tuple[M1PublicationService, InMemorySessionPublicationRepository]:
    repository = InMemorySessionPublicationRepository()
    service = M1PublicationService(
        fixture_root=FIXTURE_ROOT,
        authority_root=AUTHORITY_ROOT,
        repository=repository,
    )
    return service, repository


def _api_client() -> tuple[
    TestClient,
    M1PublicationService,
    InMemorySessionPublicationRepository,
]:
    service, repository = _service()

    class _UnusedStorageBaseline:
        def execute(self) -> Never:
            raise AssertionError("Batch 2 backend evidence must not use M0 storage baseline")

    application = ApplicationService(
        get_storage_baseline_status=_UnusedStorageBaseline(),
        m1_publication=service,
    )
    return TestClient(create_m1_app(application)), service, repository


def _authority_json(name: str) -> dict[str, object]:
    raw = json.loads((AUTHORITY_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"authority object expected: {name}")
    return raw


def _object_seal_ok() -> bool:
    from tpaa_storage.object_seal import LocalSealedObjectFlow
    from tpaa_storage.object_store import LocalObjectStore

    with tempfile.TemporaryDirectory(prefix="tpaa-m1-batch2-seal-") as tmp:
        store = LocalObjectStore(Path(tmp))
        flow = LocalSealedObjectFlow(store)
        sealed_uri = "tpaa-object://m1-batch-2/evidence.bin"

        cancelled = flow.stage(
            sealed_uri=sealed_uri,
            data=b"cancelled-staging-bytes",
            operation_id="cancelled-op",
        )
        cancelled_path = store.physical_path(cancelled.staging.logical_uri)
        sealed_path = store.physical_path(sealed_uri)
        if not cancelled_path.exists() or sealed_path.exists():
            return False
        if not flow.cleanup(cancelled) or cancelled_path.exists() or sealed_path.exists():
            return False

        orphan = flow.stage(
            sealed_uri=sealed_uri,
            data=b"orphan-staging-bytes",
            operation_id="orphan-op",
        )
        if not flow.cleanup(orphan):
            return False
        if flow.cleanup(orphan):
            return False

        staged = flow.stage(
            sealed_uri=sealed_uri,
            data=b"sealed-publication-bytes",
            operation_id="seal-op",
        )
        sealed = flow.seal(staged)
        return (
            sealed.logical_uri == sealed_uri
            and store.verify(sealed)
            and store.read_bytes(sealed_uri) == b"sealed-publication-bytes"
            and not store.physical_path(staged.staging.logical_uri).exists()
        )


def _race_ok() -> bool:
    service, repository = _service()
    command = _command(0, "TEST_RACE_CAPABILITY")

    def publish(_index: int) -> M1PublishSessionResult:
        return service.publish_session(
            command,
            idempotency_key="m1-batch-2-backend-race",
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(publish, range(8)))

    release_ids = {item.release_id for item in results}
    session_ids = {item.session_id for item in results}
    if len(release_ids) != 1 or len(session_ids) != 1:
        return False
    if sum(item.reused is False for item in results) != 1:
        return False
    if sum(item.reused is True for item in results) != 7:
        return False
    session_id = next(iter(session_ids))
    current = repository.current(session_id)
    return (
        repository.version_token(session_id) == 1
        and current is not None
        and current.release.release_id == next(iter(release_ids))
    )


def run(*, platform: str, source_revision: str, evidence: Path) -> int:
    from tpaa_application.m1_publication import to_core_publication_bundle

    failures: list[str] = []
    acceptance: dict[str, bool] = {task_id: False for task_id in TASK_IDS}

    try:
        service, repository = _service()
        first = service.publish_session(
            _command(0, "TEST_CAPABILITY_A"),
            idempotency_key="m1-batch-2-backend-first",
        )
        retry = service.publish_session(
            _command(0, "TEST_CAPABILITY_A"),
            idempotency_key="m1-batch-2-backend-first",
        )
        stored = repository.get_release(first.release_id).release

        first_summary = service.release_summary(first.release_id)
        first_context = service.context_projection(first.release_id)
        first_metric = service.metric_detail(first.release_id, "P1-AIR-007")
        first_evidence = service.metric_evidence(first.release_id, "P1-AIR-007")
        first_replay = service.replay(first.release_id)

        acceptance["M1-OBS-001"] = (
            len(stored.observations) == 5
            and len(stored.definitions) == 5
            and all(
                definition.publication_route == "CAPABILITY_OBSERVATION"
                for definition in stored.definitions
            )
            and all(
                observation.release_id == stored.release_id
                for observation in stored.observations
            )
        )
        acceptance["M1-OBS-002"] = (
            stored.session_id == first.session_id
            and stored.context_dto()["context_id"] == stored.context_id
            and len(stored.catalog_hash) == 64
            and len(stored.world_logical_hash) == 64
            and len(stored.definitions) == 5
            and len(stored.evidence_sets) == 5
            and len(stored.metric_instances) == 5
            and stored.logical_membership()["manifest_hash"] == stored.manifest_hash
        )
        acceptance["M1-OBS-003"] = (
            first.reused is False
            and retry.reused is True
            and retry.release_id == first.release_id
            and retry.manifest_hash == first.manifest_hash
            and repository.version_token(first.session_id) == 1
        )
        acceptance["M1-OBS-005"] = (
            first_replay["status"] == "PASS"
            and first_replay["exact_logical_products_equal"] is True
            and first_replay["current_latest_fallback_used"] is False
        )

        core_bundle = to_core_publication_bundle(stored)
        acceptance["M1-STO-001"] = (
            core_bundle.release_id == stored.release_id
            and core_bundle.session_id == stored.session_id
            and core_bundle.context_id == stored.context_id
            and len(core_bundle.definitions) == 5
            and len(core_bundle.evidence_sets) == 5
            and len(core_bundle.metric_instances) == 5
            and len(core_bundle.observations) == 5
            and all(
                reference.definition_hash
                == next(
                    item.definition_hash
                    for item in stored.definitions
                    if item.metric_definition_id == reference.metric_definition_id
                )
                for reference in core_bundle.definitions
            )
        )
        acceptance["M1-STO-002"] = _object_seal_ok()

        second = service.publish_session(
            _command(1, "TEST_CAPABILITY_B"),
            idempotency_key="m1-batch-2-backend-second",
        )
        current = repository.current(first.session_id)
        acceptance["M1-OBS-004"] = (
            second.release_id != first.release_id
            and current is not None
            and current.release.release_id == second.release_id
            and service.release_summary(first.release_id) == first_summary
            and service.context_projection(first.release_id) == first_context
            and service.metric_detail(first.release_id, "P1-AIR-007") == first_metric
            and service.metric_evidence(first.release_id, "P1-AIR-007") == first_evidence
        )
        acceptance["M1-TST-006"] = (
            acceptance["M1-OBS-004"]
            and service.replay(first.release_id) == first_replay
            and first_replay["release_status"] == "PUBLISHED"
        )

        immutable_ok = True
        manifest_field = "manifest_hash"
        algorithm_field = "algorithm_version"
        try:
            setattr(stored, manifest_field, "0" * 64)
            immutable_ok = False
        except FrozenInstanceError:
            pass
        try:
            setattr(stored.definitions[0], algorithm_field, "tampered")
            immutable_ok = False
        except FrozenInstanceError:
            pass
        context_copy = service.context_projection(first.release_id)
        original_context_status = context_copy["status"]
        context_copy["status"] = "TAMPERED"
        immutable_ok = immutable_ok and (
            service.context_projection(first.release_id)["status"]
            == original_context_status
        )
        acceptance["M1-TST-004"] = immutable_ok
        acceptance["M1-TST-005"] = _race_ok()

        client, _, _ = _api_client()
        import_response = client.post(
            "/m1/commands/import-session",
            headers={"Idempotency-Key": "backend-api-import"},
            json={"fixture_id": "BF_M1_NOMINAL_V1"},
        )
        import_retry = client.post(
            "/m1/commands/import-session",
            headers={"Idempotency-Key": "backend-api-import"},
            json={"fixture_id": "BF_M1_NOMINAL_V1"},
        )
        compute_response = client.post(
            "/m1/commands/compute-session",
            headers={"Idempotency-Key": "backend-api-compute"},
            json={"fixture_id": "BF_M1_NOMINAL_V1"},
        )
        compute_retry = client.post(
            "/m1/commands/compute-session",
            headers={"Idempotency-Key": "backend-api-compute"},
            json={"fixture_id": "BF_M1_NOMINAL_V1"},
        )
        publish_response = client.post(
            "/m1/commands/publish-session",
            headers={"Idempotency-Key": "backend-api-publish"},
            json={
                "fixture_id": "BF_M1_NOMINAL_V1",
                "aircraft_model_id": str(uuid5(NAMESPACE_URL, "backend-api-model")),
                "aircraft_instance_id": str(uuid5(NAMESPACE_URL, "backend-api-instance")),
                "subject_entity_id": str(uuid5(NAMESPACE_URL, "backend-api-entity")),
                "capability_dimension": "TEST_EXPLICIT_CAPABILITY_DIMENSION",
                "capability_type": "TEST_EXPLICIT_CAPABILITY_TYPE",
                "expected_version_token": 0,
            },
        )
        publish_retry = client.post(
            "/m1/commands/publish-session",
            headers={"Idempotency-Key": "backend-api-publish"},
            json={
                "fixture_id": "BF_M1_NOMINAL_V1",
                "aircraft_model_id": str(uuid5(NAMESPACE_URL, "backend-api-model")),
                "aircraft_instance_id": str(uuid5(NAMESPACE_URL, "backend-api-instance")),
                "subject_entity_id": str(uuid5(NAMESPACE_URL, "backend-api-entity")),
                "capability_dimension": "TEST_EXPLICIT_CAPABILITY_DIMENSION",
                "capability_type": "TEST_EXPLICIT_CAPABILITY_TYPE",
                "expected_version_token": 0,
            },
        )
        import_json = import_response.json()
        import_retry_json = import_retry.json()
        compute_json = compute_response.json()
        compute_retry_json = compute_retry.json()
        publish_json = publish_response.json()
        publish_retry_json = publish_retry.json()
        acceptance["M1-API-001"] = (
            import_response.status_code == 200
            and import_retry.status_code == 200
            and import_json.get("reused") is False
            and import_retry_json.get("reused") is True
            and len(str(import_json.get("request_hash", ""))) == 64
            and compute_response.status_code == 200
            and compute_retry.status_code == 200
            and compute_json.get("reused") is False
            and compute_retry_json.get("reused") is True
            and len(str(compute_json.get("request_hash", ""))) == 64
            and publish_response.status_code == 201
            and publish_retry.status_code == 200
            and publish_json.get("reused") is False
            and publish_retry_json.get("reused") is True
            and len(str(publish_json.get("request_hash", ""))) == 64
        )

        api_release_id = str(publish_json["release_id"])
        context_response = client.get(f"/m1/releases/{api_release_id}/context")
        topology_response = client.get(f"/m1/releases/{api_release_id}/topology")
        metrics_response = client.get(f"/m1/releases/{api_release_id}/metrics")
        metric_response = client.get(
            f"/m1/releases/{api_release_id}/metrics/P1-AIR-007"
        )
        evidence_response = client.get(
            f"/m1/releases/{api_release_id}/metrics/P1-AIR-007/evidence"
        )
        release_response = client.get(f"/m1/releases/{api_release_id}")
        replay_response = client.post(f"/m1/releases/{api_release_id}/replay")
        observations_response = client.get(
            f"/m1/releases/{api_release_id}/observations"
        )

        context_json = context_response.json()
        topology_json = topology_response.json()
        metrics_json = metrics_response.json()
        metric_json = metric_response.json()
        evidence_json = evidence_response.json()
        release_json = release_response.json()
        replay_json = replay_response.json()
        observations_json = observations_response.json()

        acceptance["M1-API-002"] = (
            context_response.status_code == 200
            and topology_response.status_code == 200
            and set(topology_json) == {"release_id", "session", "episode", "stages"}
            and isinstance(topology_json["session"]["start_session_time_us"], str)
            and isinstance(topology_json["session"]["end_session_time_us"], str)
            and len(topology_json["stages"]) == 4
        )
        acceptance["M1-API-003"] = (
            metrics_response.status_code == 200
            and metric_response.status_code == 200
            and evidence_response.status_code == 200
            and [item["metric_code"] for item in metrics_json["items"]]
            == ["P1-AIR-001", "P1-AIR-002", "P1-AIR-003", "P1-AIR-004", "P1-AIR-007"]
            and metric_json["release_id"] == api_release_id
            and evidence_json["release_id"] == api_release_id
            and metric_json["definition"]["definition_hash"]
            == evidence_json["definition_hash"]
            and metric_json["evidence"]["logical_hash"]
            == evidence_json["logical_hash"]
        )
        acceptance["M1-API-004"] = (
            release_response.status_code == 200
            and replay_response.status_code == 200
            and release_json["release_id"] == api_release_id
            and release_json["status"] == "PUBLISHED"
            and isinstance(release_json["identity"], dict)
            and isinstance(release_json["provenance"], dict)
            and replay_json["release_id"] == api_release_id
            and replay_json["release_status"] == "PUBLISHED"
            and replay_json["status"] == "PASS"
            and replay_json["provenance"] == release_json["provenance"]
        )

        start_us = topology_json["session"]["start_session_time_us"]
        end_us = topology_json["session"]["end_session_time_us"]
        series_response = client.get(
            f"/m1/releases/{api_release_id}/series",
            params={
                "start_session_time_us": start_us,
                "end_session_time_us": end_us,
                "limit": 2,
            },
        )
        series_json = series_response.json()
        acceptance["M1-API-005"] = (
            series_response.status_code == 200
            and series_json["limit"] == 2
            and series_json["returned"] <= 2
            and len(series_json["rows"]) == series_json["returned"]
            and "rows" not in metric_json
            and "series" not in metric_json
            and "canonical_rows" not in metric_json
        )

        dto_authority = _authority_json("CROSS_LAYER_DTO_CONTRACTS.json")
        catalog = _authority_json("P1_METRIC_CATALOG.json")
        contracts = dto_authority["contracts"]
        registry = catalog["structured_output_schema_registry"]
        if not isinstance(contracts, dict) or not isinstance(registry, dict):
            raise TypeError("frozen DTO/structured registry shape invalid")

        context_contract = contracts["EvaluationContextDTO"]
        observation_contract = contracts["CapabilityObservationDTO"]
        if not isinstance(context_contract, dict) or not isinstance(observation_contract, dict):
            raise TypeError("frozen DTO contract missing")
        context_fields = context_contract["fields"]
        observation_fields = observation_contract["fields"]
        if not isinstance(context_fields, list) or not isinstance(observation_fields, list):
            raise TypeError("frozen DTO field list invalid")

        required_context = {
            item["field"]
            for item in context_fields
            if isinstance(item, dict) and item.get("required") is True
        }
        required_observation = {
            item["field"]
            for item in observation_fields
            if isinstance(item, dict) and item.get("required") is True
        }
        air_007 = next(
            item
            for item in observations_json["items"]
            if item["metric_code"] == "P1-AIR-007"
        )
        schema_entry = registry["STRUCT_P1_AIR_007_V1"]
        if not isinstance(schema_entry, dict):
            raise TypeError("AIR-007 structured schema missing")
        structured_schema = schema_entry["json_schema"]
        if not isinstance(structured_schema, dict):
            raise TypeError("AIR-007 JSON schema invalid")
        structured_value = air_007["value"]
        if not isinstance(structured_value, dict):
            raise TypeError("AIR-007 value must be object")

        expected_observation = required_observation | {
            "structured_output_schema_id",
            "value",
        }
        acceptance["M1-TST-007"] = (
            set(context_json) == required_context
            and set(air_007) == expected_observation
            and air_007["structured_output_schema_id"] == "STRUCT_P1_AIR_007_V1"
            and DECIMAL_STRING.fullmatch(air_007["observation_start_session_time_us"])
            is not None
            and DECIMAL_STRING.fullmatch(air_007["observation_end_session_time_us"])
            is not None
            and set(structured_value) == set(structured_schema["required"])
            and set(structured_value["tas"])
            == {
                "status",
                "n",
                "min_mps",
                "max_mps",
                "p05_mps",
                "p50_mps",
                "p95_mps",
            }
            and set(structured_value["mach"])
            == {"status", "n", "min", "max", "p05", "p50", "p95"}
        )

    except Exception as exc:  # noqa: BLE001 - evidence captures full fail-closed state
        failures.append(f"{type(exc).__name__}:{exc}")

    failed_acceptance = sorted(
        task_id for task_id, passed in acceptance.items() if not passed
    )
    platform_ok = _platform_matches(platform)
    if not platform_ok:
        failures.append(f"PLATFORM_MISMATCH expected={platform} actual={sys.platform}")

    status = "PASS" if not failures and not failed_acceptance else "FAIL"
    payload: dict[str, object] = {
        "schema": SCHEMA,
        "tracking_issue": 87,
        "task_ids": list(TASK_IDS),
        "source_revision": source_revision,
        "platform": platform,
        "platform_matches_expected": platform_ok,
        "status": status,
        "acceptance": acceptance,
        "failed_acceptance": failed_acceptance,
        "failures": failures,
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
    parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(
        platform=args.platform,
        source_revision=args.source_revision,
        evidence=args.evidence,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
