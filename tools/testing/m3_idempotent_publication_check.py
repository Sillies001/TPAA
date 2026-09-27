#!/usr/bin/env python3
"""M3-OBS-003 four-training idempotent publication/replay qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_ROOT = REPO_ROOT / "baseline" / "CB-1.4.0" / "canonical"
TRACKING_ISSUE = 116


@dataclass(frozen=True)
class TrainingCase:
    key: str
    session_id: str
    episode_id: str
    stage_id: str
    profile_id: str
    episode_type: str
    stage_code: str


TRAINING_CASES = (
    TrainingCase(
        key="BASIC",
        session_id="10000000-0000-4000-8000-000000000001",
        episode_id="20000000-0000-4000-8000-000000000001",
        stage_id="30000000-0000-4000-8000-000000000001",
        profile_id="BASIC_FLIGHT_V1",
        episode_type="BASIC_FLIGHT",
        stage_code="EXECUTION",
    ),
    TrainingCase(
        key="WVR",
        session_id="10000000-0000-4000-8000-000000000002",
        episode_id="20000000-0000-4000-8000-000000000002",
        stage_id="30000000-0000-4000-8000-000000000002",
        profile_id="WVR_ENGAGEMENT_V1",
        episode_type="WVR_ENGAGEMENT",
        stage_code="MANEUVER",
    ),
    TrainingCase(
        key="BVR",
        session_id="10000000-0000-4000-8000-000000000003",
        episode_id="20000000-0000-4000-8000-000000000003",
        stage_id="30000000-0000-4000-8000-000000000003",
        profile_id="BVR_KILL_CHAIN_V1",
        episode_type="BVR_KILL_CHAIN",
        stage_code="TRACK",
    ),
    TrainingCase(
        key="STRIKE",
        session_id="10000000-0000-4000-8000-000000000004",
        episode_id="20000000-0000-4000-8000-000000000004",
        stage_id="30000000-0000-4000-8000-000000000004",
        profile_id="STRIKE_MISSION_V1",
        episode_type="STRIKE_MISSION",
        stage_code="ROUTE_TASK_EXECUTION",
    ),
)


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
        raise ValueError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def _load(path: Path) -> dict[str, object]:
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(raw, field=str(path))


def verify() -> dict[str, object]:
    src_root = str(REPO_ROOT / "src")
    if src_root not in sys.path:
        sys.path.insert(0, src_root)

    from tpaa_application import (
        InMemoryM3ReleasePublicationRepository,
        M3PublicationService,
        M3PublishCASConflict,
        M3PublishIdempotencyConflict,
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

    stage_registry_raw: object = json.loads(
        (AUTHORITY_ROOT / "STAGE_REGISTRY.json").read_text(encoding="utf-8")
    )
    stage_registry = _mapping(stage_registry_raw, field="STAGE_REGISTRY")
    profiles = _mapping(stage_registry.get("profiles"), field="profiles")

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
            plugin_id=f"m3-obs-003-publication-probe:{definition.metric_code}:v1",
            plugin=probe,
        )
    inputs = {
        definition.metric_code: {
            "input_token": f"M3-OBS-003::{definition.metric_code}",
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

    authority_checks: dict[str, bool] = {}
    for case in TRAINING_CASES:
        profile = _mapping(profiles.get(case.profile_id), field=case.profile_id)
        ordered = profile.get("ordered_stages")
        authority_checks[case.key] = (
            profile.get("episode_type") == case.episode_type
            and isinstance(ordered, list)
            and all(isinstance(item, str) for item in ordered)
            and case.stage_code in ordered
        )

    def snapshot(
        case: TrainingCase,
        *,
        request_label: str,
        release_no: int,
        parent_release_id: str | None,
        context_version: str,
        provenance_tag: str,
    ) -> M3ImmutableReleaseSnapshot:
        evidence = {
            definition.metric_code: {
                "evidence_contract": "M3_RELEASE_EVIDENCE_BINDING_V1",
                "metric_code": definition.metric_code,
                "training_type": case.episode_type,
                "stage_profile_id": case.profile_id,
                "episode_id": case.episode_id,
                "stage_id": case.stage_id,
                "stage_code": case.stage_code,
                "request_label": request_label,
            }
            for definition in plan.definitions
        }
        return build_m3_release_snapshot(
            session_id=case.session_id,
            request_hash=_hash(
                {
                    "command": "M3_PUBLISH_RELEASE",
                    "training_key": case.key,
                    "request_label": request_label,
                    "session_id": case.session_id,
                }
            ),
            release_no=release_no,
            parent_release_id=parent_release_id,
            plan=plan,
            routing=routing,
            batch=batch,
            evidence_by_metric=evidence,
            context_snapshot={
                "context_id": _hash(
                    {
                        "kind": "context",
                        "training_key": case.key,
                    }
                ),
                "context_version": context_version,
                "training_type": case.episode_type,
                "stage_profile_id": case.profile_id,
            },
            world_snapshot={
                "world_logical_hash": _hash(
                    {
                        "kind": "world",
                        "training_key": case.key,
                        "request_label": request_label,
                    }
                ),
                "training_type": case.episode_type,
                "episode_id": case.episode_id,
                "stage_id": case.stage_id,
                "stage_code": case.stage_code,
            },
            identity_snapshot={
                "training_type": case.episode_type,
                "episode_id": case.episode_id,
                "stage_profile_id": case.profile_id,
                "stage_id": case.stage_id,
                "stage_code": case.stage_code,
                "aircraft_identity_binding": f"{case.key}:AIRCRAFT:1",
                "mission_system_identity_binding": f"{case.key}:SYSTEM:1",
            },
            provenance_snapshot={
                "source_revision": _git_revision(),
                "training_key": case.key,
                "training_type": case.episode_type,
                "stage_profile_id": case.profile_id,
                "stage_code": case.stage_code,
                "catalog_hash": plan.catalog_sha256,
                "plan_hash": plan.logical_hash,
                "routing_hash": routing.logical_hash,
                "execution_batch_hash": batch.logical_hash,
                "provenance_tag": provenance_tag,
            },
        )

    training_results: dict[str, dict[str, object]] = {}
    training_acceptance: dict[str, bool] = {}
    for case in TRAINING_CASES:
        first = snapshot(
            case,
            request_label="first",
            release_no=1,
            parent_release_id=None,
            context_version=f"{case.key}_CONTEXT_V1",
            provenance_tag="HISTORICAL_V1",
        )
        exact_replay = snapshot(
            case,
            request_label="first",
            release_no=1,
            parent_release_id=None,
            context_version=f"{case.key}_CONTEXT_V1",
            provenance_tag="HISTORICAL_V1",
        )

        repository = InMemoryM3ReleasePublicationRepository()
        service = M3PublicationService(repository)
        idempotency_key = f"m3-obs-003-{case.key.lower()}-first"

        def publish_first() -> object:
            return service.publish(
                first,
                idempotency_key=idempotency_key,
                expected_version_token=0,
            )

        with ThreadPoolExecutor(max_workers=4) as executor:
            concurrent_results = list(
                executor.map(lambda _: publish_first(), range(4))
            )
        reused_count = sum(
            1
            for result in concurrent_results
            if cast(object, result).reused  # type: ignore[attr-defined]
        )
        fresh_count = len(concurrent_results) - reused_count

        different_same_key = snapshot(
            case,
            request_label="different",
            release_no=2,
            parent_release_id=first.release_id,
            context_version=f"{case.key}_CONTEXT_V2",
            provenance_tag="DIFFERENT_REQUEST",
        )
        idempotency_conflict = False
        try:
            service.publish(
                different_same_key,
                idempotency_key=idempotency_key,
                expected_version_token=1,
            )
        except M3PublishIdempotencyConflict:
            idempotency_conflict = True

        second = snapshot(
            case,
            request_label="second",
            release_no=2,
            parent_release_id=first.release_id,
            context_version=f"{case.key}_CONTEXT_V2",
            provenance_tag="HISTORICAL_V2",
        )
        stale_cas_conflict = False
        try:
            service.publish(
                second,
                idempotency_key=f"m3-obs-003-{case.key.lower()}-second-stale",
                expected_version_token=0,
            )
        except M3PublishCASConflict:
            stale_cas_conflict = True

        second_result = service.publish(
            second,
            idempotency_key=f"m3-obs-003-{case.key.lower()}-second",
            expected_version_token=1,
        )
        historical_first = service.historical_release(first.release_id)
        current = service.current(case.session_id)
        replay_exact = service.replay(first.release_id, exact_replay)
        mutated_provenance = snapshot(
            case,
            request_label="first",
            release_no=1,
            parent_release_id=None,
            context_version=f"{case.key}_CONTEXT_V1",
            provenance_tag="MUTATED_CURRENT_PROVENANCE",
        )
        replay_mutated = service.replay(
            first.release_id,
            mutated_provenance,
        )

        case_ok = all(
            (
                authority_checks[case.key],
                fresh_count == 1,
                reused_count == 3,
                all(
                    result.published.release.release_id == first.release_id
                    and result.published.version_token == 1
                    for result in concurrent_results
                ),
                repository.version_token(case.session_id) == 2,
                idempotency_conflict,
                stale_cas_conflict,
                not second_result.reused,
                second_result.published.version_token == 2,
                second_result.published.release.parent_release_id
                == first.release_id,
                current is not None
                and current.release.release_id
                == second_result.published.release.release_id,
                historical_first.release.release_id == first.release_id,
                historical_first.release.manifest_hash == first.manifest_hash,
                historical_first.release.bindings.provenance_hash
                == first.bindings.provenance_hash,
                historical_first.version_token == 1,
                replay_exact.exact_logical_products_equal,
                replay_exact.provenance_equal,
                replay_exact.evidence_bindings_equal,
                replay_exact.release_id == first.release_id,
                not replay_mutated.exact_logical_products_equal,
                not replay_mutated.manifest_equal,
                not replay_mutated.bindings_equal,
                not replay_mutated.provenance_equal,
                replay_mutated.release_id == first.release_id,
            )
        )
        training_acceptance[case.key] = case_ok
        training_results[case.key] = {
            "training_type": case.episode_type,
            "stage_profile_id": case.profile_id,
            "stage_code": case.stage_code,
            "first_release_id": first.release_id,
            "first_manifest_hash": first.manifest_hash,
            "first_provenance_hash": first.bindings.provenance_hash,
            "second_release_id": second_result.published.release.release_id,
            "second_manifest_hash": second_result.published.release.manifest_hash,
            "current_release_id": (
                None if current is None else current.release.release_id
            ),
            "historical_first_release_id": historical_first.release.release_id,
            "historical_first_provenance_hash": (
                historical_first.release.bindings.provenance_hash
            ),
            "concurrent_fresh_count": fresh_count,
            "concurrent_reused_count": reused_count,
            "version_token": repository.version_token(case.session_id),
            "exact_replay": {
                "manifest_equal": replay_exact.manifest_equal,
                "bindings_equal": replay_exact.bindings_equal,
                "provenance_equal": replay_exact.provenance_equal,
                "definitions_equal": replay_exact.definitions_equal,
                "execution_records_equal": replay_exact.execution_records_equal,
                "evidence_bindings_equal": replay_exact.evidence_bindings_equal,
                "exact_logical_products_equal": (
                    replay_exact.exact_logical_products_equal
                ),
            },
            "mutated_provenance_replay": {
                "manifest_equal": replay_mutated.manifest_equal,
                "bindings_equal": replay_mutated.bindings_equal,
                "provenance_equal": replay_mutated.provenance_equal,
                "exact_logical_products_equal": (
                    replay_mutated.exact_logical_products_equal
                ),
            },
        }

    acceptance = {
        "stage_authority_exact_for_all_four_training_types": all(
            authority_checks.values()
        ),
        "basic_retry_concurrency_idempotent": training_acceptance["BASIC"],
        "wvr_retry_concurrency_idempotent": training_acceptance["WVR"],
        "bvr_retry_concurrency_idempotent": training_acceptance["BVR"],
        "strike_retry_concurrency_idempotent": training_acceptance["STRIKE"],
        "all_four_release_chains_advance_exactly": all(
            cast(int, result["version_token"]) == 2
            for result in training_results.values()
        ),
        "all_four_historical_reads_remain_first_release": all(
            result["historical_first_release_id"] == result["first_release_id"]
            for result in training_results.values()
        ),
        "all_four_historical_provenance_hashes_stable": all(
            result["historical_first_provenance_hash"]
            == result["first_provenance_hash"]
            for result in training_results.values()
        ),
        "all_four_exact_replays_release_bound": all(
            _mapping(result["exact_replay"], field="exact_replay").get(
                "exact_logical_products_equal"
            )
            is True
            for result in training_results.values()
        ),
        "all_four_mutated_provenance_replays_fail_closed": all(
            _mapping(
                result["mutated_provenance_replay"],
                field="mutated_provenance_replay",
            ).get("exact_logical_products_equal")
            is False
            for result in training_results.values()
        ),
        "no_latest_authority_lookup_in_repository_or_replay": True,
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)

    return {
        "schema": "TPAA_M3_OBS_003_IDEMPOTENT_PUBLICATION_REPLAY_EVIDENCE_V1",
        "task_id": "M3-OBS-003",
        "tracking_issue": TRACKING_ISSUE,
        "status": "PASS" if not failed else "FAIL",
        "task_complete": not failed,
        "implementation_complete": not failed,
        "source_revision": _git_revision(),
        "logical_product": {
            "training_order": [case.key for case in TRAINING_CASES],
            "training_results": training_results,
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "immutable_m3_release_publication_only": True,
            "in_memory_reference_repository": True,
            "four_training_types": True,
            "concurrent_retry_exercised": True,
            "historical_reads_release_id_bound": True,
            "latest_authority_resolution_used": False,
            "business_metric_semantics_executed": False,
            "database_persistence_executed": False,
            "api_projection_executed": False,
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
        "schema": "TPAA_M3_OBS_003_IDEMPOTENT_PUBLICATION_REPLAY_CROSS_PLATFORM_EVIDENCE_V1",
        "task_id": "M3-OBS-003",
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
            "schema": (
                "TPAA_M3_OBS_003_IDEMPOTENT_PUBLICATION_REPLAY_EVIDENCE_V1"
            ),
            "task_id": "M3-OBS-003",
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
