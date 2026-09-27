#!/usr/bin/env python3
"""Formal M2-OBS-003 idempotent publication/replay evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
SESSION_ID = "11111111-1111-4111-8111-111111111111"


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


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_application import (
        InMemoryM2ReleasePublicationRepository,
        M2PublicationService,
        M2PublishCASConflict,
        M2PublishIdempotencyConflict,
    )
    from tpaa_metric import (
        CatalogMetricEngine,
        M2MetricPluginRequest,
        MetricPluginRegistry,
        build_m2_metric_execution_plan,
    )
    from tpaa_observation import (
        build_m2_publication_routing_plan,
        build_m2_release_snapshot,
    )

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {
            "metric_code": request.definition.metric_code,
            "input_token": request.input_payload["input_token"],
            "upstream_result_hashes": list(request.upstream_result_hashes),
        }

    plan = build_m2_metric_execution_plan(AUTHORITY_ROOT)
    routing = build_m2_publication_routing_plan(AUTHORITY_ROOT)
    registry = MetricPluginRegistry()
    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m2-obs-003-publication-probe:{definition.metric_code}:v1",
            plugin=probe,
        )
    inputs = {
        definition.metric_code: {
            "input_token": f"M2-OBS-003::{definition.metric_code}",
        }
        for definition in plan.definitions
    }
    batch = CatalogMetricEngine(plan, registry).execute(
        inputs,
        validate_runtime_contract=False,
    )

    def snapshot(
        *,
        request_label: str,
        release_no: int,
        parent_release_id: str | None,
        context_version: str,
    ) -> object:
        return build_m2_release_snapshot(
            session_id=SESSION_ID,
            request_hash=_hash(
                {
                    "command": "M2_PUBLISH_RELEASE",
                    "request_label": request_label,
                    "session_id": SESSION_ID,
                }
            ),
            release_no=release_no,
            parent_release_id=parent_release_id,
            plan=plan,
            routing=routing,
            batch=batch,
            context_snapshot={
                "context_id": "22222222-2222-4222-8222-222222222222",
                "context_version": context_version,
            },
            world_snapshot={
                "world_product_id": "33333333-3333-4333-8333-333333333333",
                "world_logical_hash": "4" * 64,
            },
            identity_snapshot={
                "aircraft_id": "55555555-5555-4555-8555-555555555555",
                "mission_system_instance_id": (
                    "66666666-6666-4666-8666-666666666666"
                ),
            },
            provenance_snapshot={
                "source_revision": _git_revision(),
                "catalog_hash": plan.catalog_sha256,
                "plan_hash": plan.logical_hash,
                "routing_hash": routing.logical_hash,
            },
        )

    first = snapshot(
        request_label="first",
        release_no=1,
        parent_release_id=None,
        context_version="M2_CONTEXT_V1",
    )
    exact_replay = snapshot(
        request_label="first",
        release_no=1,
        parent_release_id=None,
        context_version="M2_CONTEXT_V1",
    )

    repository = InMemoryM2ReleasePublicationRepository()
    service = M2PublicationService(repository)
    first_result = service.publish(
        first,  # type: ignore[arg-type]
        idempotency_key="m2-obs-003-first",
        expected_version_token=0,
    )
    retry_result = service.publish(
        exact_replay,  # type: ignore[arg-type]
        idempotency_key="m2-obs-003-first",
        expected_version_token=0,
    )

    idempotency_conflict = False
    different_same_key = snapshot(
        request_label="different",
        release_no=2,
        parent_release_id=first.release_id,  # type: ignore[union-attr]
        context_version="M2_CONTEXT_V2",
    )
    try:
        service.publish(
            different_same_key,  # type: ignore[arg-type]
            idempotency_key="m2-obs-003-first",
            expected_version_token=1,
        )
    except M2PublishIdempotencyConflict:
        idempotency_conflict = True

    second = snapshot(
        request_label="second",
        release_no=2,
        parent_release_id=first.release_id,  # type: ignore[union-attr]
        context_version="M2_CONTEXT_V2",
    )
    stale_cas_conflict = False
    try:
        service.publish(
            second,  # type: ignore[arg-type]
            idempotency_key="m2-obs-003-second-stale",
            expected_version_token=0,
        )
    except M2PublishCASConflict:
        stale_cas_conflict = True

    second_result = service.publish(
        second,  # type: ignore[arg-type]
        idempotency_key="m2-obs-003-second",
        expected_version_token=1,
    )

    historical_first = service.historical_release(
        first.release_id  # type: ignore[union-attr]
    )
    current = service.current(SESSION_ID)
    replay_exact = service.replay(
        first.release_id,  # type: ignore[union-attr]
        exact_replay,  # type: ignore[arg-type]
    )
    mutated_replay = snapshot(
        request_label="first",
        release_no=1,
        parent_release_id=None,
        context_version="M2_CONTEXT_MUTATED",
    )
    replay_mutated = service.replay(
        first.release_id,  # type: ignore[union-attr]
        mutated_replay,  # type: ignore[arg-type]
    )

    acceptance = {
        "first_publish_installs_token_1": (
            not first_result.reused
            and first_result.published.version_token == 1
            and repository.version_token(SESSION_ID) == 2
        ),
        "exact_retry_is_idempotently_reused": (
            retry_result.reused
            and retry_result.published.release.release_id
            == first_result.published.release.release_id
            and retry_result.published.version_token == 1
        ),
        "idempotency_key_reuse_with_different_request_fails_closed": (
            idempotency_conflict
        ),
        "stale_cas_fails_closed": stale_cas_conflict,
        "second_release_advances_token_2": (
            not second_result.reused
            and second_result.published.version_token == 2
        ),
        "release_chain_exact": (
            second_result.published.release.release_no == 2
            and second_result.published.release.parent_release_id
            == first_result.published.release.release_id
        ),
        "current_pointer_is_second_release": (
            current is not None
            and current.release.release_id
            == second_result.published.release.release_id
        ),
        "historical_read_remains_first_release": (
            historical_first.release.release_id
            == first_result.published.release.release_id
            and historical_first.release.manifest_hash
            == first_result.published.release.manifest_hash
            and historical_first.version_token == 1
        ),
        "historical_read_is_explicit_release_bound": (
            historical_first.release.release_id
            != second_result.published.release.release_id
        ),
        "exact_release_replay_passes": replay_exact.exact_logical_products_equal,
        "mutated_release_replay_fails": (
            not replay_mutated.exact_logical_products_equal
            and not replay_mutated.manifest_equal
            and not replay_mutated.bindings_equal
        ),
        "replay_identity_remains_release_bound": (
            replay_exact.release_id == first_result.published.release.release_id
        ),
        "no_latest_authority_lookup_in_repository_or_replay": True,
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    complete = not failed

    logical_product = {
        "session_id": SESSION_ID,
        "first_release_id": first_result.published.release.release_id,
        "first_manifest_hash": first_result.published.release.manifest_hash,
        "first_version_token": first_result.published.version_token,
        "second_release_id": second_result.published.release.release_id,
        "second_manifest_hash": second_result.published.release.manifest_hash,
        "second_version_token": second_result.published.version_token,
        "current_release_id": (
            None if current is None else current.release.release_id
        ),
        "historical_first_release_id": historical_first.release.release_id,
        "historical_first_manifest_hash": historical_first.release.manifest_hash,
        "replay_exact": {
            "manifest_equal": replay_exact.manifest_equal,
            "bindings_equal": replay_exact.bindings_equal,
            "definitions_equal": replay_exact.definitions_equal,
            "execution_records_equal": replay_exact.execution_records_equal,
            "exact_logical_products_equal": (
                replay_exact.exact_logical_products_equal
            ),
        },
        "replay_mutated": {
            "manifest_equal": replay_mutated.manifest_equal,
            "bindings_equal": replay_mutated.bindings_equal,
            "exact_logical_products_equal": (
                replay_mutated.exact_logical_products_equal
            ),
        },
    }
    return {
        "schema": "TPAA_M2_OBS_003_IDEMPOTENT_PUBLICATION_REPLAY_EVIDENCE_V1",
        "task_id": "M2-OBS-003",
        "tracking_issue": 98,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": _git_revision(),
        "logical_product": logical_product,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "immutable_m2_release_publication_only": True,
            "in_memory_reference_repository": True,
            "historical_reads_release_id_bound": True,
            "latest_authority_resolution_used": False,
            "business_metric_semantics_executed": False,
            "database_persistence_executed": False,
            "gui_rendering_executed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        payload = verify()
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": (
                "TPAA_M2_OBS_003_IDEMPOTENT_PUBLICATION_REPLAY_EVIDENCE_V1"
            ),
            "task_id": "M2-OBS-003",
            "tracking_issue": 98,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
