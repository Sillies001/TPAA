from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

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
    M2ImmutableReleaseSnapshot,
    build_m2_publication_routing_plan,
    build_m2_release_snapshot,
)

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"
SESSION_ID = "11111111-1111-4111-8111-111111111111"


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


def _snapshot(
    *,
    request_label: str,
    release_no: int,
    parent_release_id: str | None,
    context_version: str,
) -> M2ImmutableReleaseSnapshot:
    plan = build_m2_metric_execution_plan(AUTHORITY)
    routing = build_m2_publication_routing_plan(AUTHORITY)
    registry = MetricPluginRegistry()

    def probe(request: M2MetricPluginRequest) -> dict[str, object]:
        return {
            "metric_code": request.definition.metric_code,
            "input": request.input_payload["input"],
        }

    for definition in plan.definitions:
        registry.register(
            definition.algorithm_id,
            algorithm_version=definition.algorithm_version,
            plugin_id=f"m2-obs-003-test:{definition.metric_code}:v1",
            plugin=probe,
        )
    batch = CatalogMetricEngine(plan, registry).execute(
        {
            definition.metric_code: {"input": definition.metric_code}
            for definition in plan.definitions
        },
        validate_runtime_contract=False,
    )
    return build_m2_release_snapshot(
        session_id=SESSION_ID,
        request_hash=_hash(
            {
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
        world_snapshot={"world_hash": "3" * 64},
        identity_snapshot={"identity_hash": "4" * 64},
        provenance_snapshot={"source_hash": "5" * 64},
    )


def test_m2_obs_003_idempotent_publish_and_cas_history() -> None:
    repository = InMemoryM2ReleasePublicationRepository()
    service = M2PublicationService(repository)
    first = _snapshot(
        request_label="first",
        release_no=1,
        parent_release_id=None,
        context_version="V1",
    )

    installed = service.publish(
        first,
        idempotency_key="first-key",
        expected_version_token=0,
    )
    reused = service.publish(
        first,
        idempotency_key="first-key",
        expected_version_token=0,
    )
    assert installed.reused is False
    assert installed.published.version_token == 1
    assert reused.reused is True
    assert reused.published == installed.published

    second = _snapshot(
        request_label="second",
        release_no=2,
        parent_release_id=first.release_id,
        context_version="V2",
    )
    with pytest.raises(M2PublishCASConflict):
        service.publish(
            second,
            idempotency_key="second-stale",
            expected_version_token=0,
        )

    installed_second = service.publish(
        second,
        idempotency_key="second-key",
        expected_version_token=1,
    )
    assert installed_second.published.version_token == 2
    assert service.current(SESSION_ID) == installed_second.published
    assert service.historical_release(first.release_id) == installed.published

    with pytest.raises(M2PublishIdempotencyConflict):
        service.publish(
            second,
            idempotency_key="first-key",
            expected_version_token=2,
        )


def test_m2_obs_003_replay_uses_explicit_historical_release() -> None:
    repository = InMemoryM2ReleasePublicationRepository()
    service = M2PublicationService(repository)
    first = _snapshot(
        request_label="first",
        release_no=1,
        parent_release_id=None,
        context_version="V1",
    )
    service.publish(
        first,
        idempotency_key="first-key",
        expected_version_token=0,
    )

    exact = _snapshot(
        request_label="first",
        release_no=1,
        parent_release_id=None,
        context_version="V1",
    )
    changed = _snapshot(
        request_label="first",
        release_no=1,
        parent_release_id=None,
        context_version="CHANGED",
    )
    assert service.replay(
        first.release_id,
        exact,
    ).exact_logical_products_equal
    comparison = service.replay(first.release_id, changed)
    assert comparison.exact_logical_products_equal is False
    assert comparison.manifest_equal is False
    assert comparison.bindings_equal is False


def test_m2_obs_003_evidence_and_cross_platform_contract(tmp_path: Path) -> None:
    source = tmp_path / "publication-replay.json"
    checked = subprocess.run(
        [
            sys.executable,
            str(DEV),
            "m2-idempotent-publication-check",
            "--evidence",
            str(source),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    payload = json.loads(source.read_text(encoding="utf-8"))
    assert payload["schema"] == (
        "TPAA_M2_OBS_003_IDEMPOTENT_PUBLICATION_REPLAY_EVIDENCE_V1"
    )
    assert payload["task_id"] == "M2-OBS-003"
    assert payload["tracking_issue"] == 98
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())
    assert payload["scope"]["historical_reads_release_id_bound"] is True
    assert payload["scope"]["latest_authority_resolution_used"] is False

    revision = payload["source_revision"]
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    windows.write_text(json.dumps(payload), encoding="utf-8")
    linux.write_text(json.dumps(payload), encoding="utf-8")
    compared = tmp_path / "compared.json"
    result = subprocess.run(
        [
            sys.executable,
            str(DEV),
            "m2-idempotent-publication-compare",
            "--windows",
            str(windows),
            "--linux",
            str(linux),
            "--expected-revision",
            revision,
            "--evidence",
            str(compared),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = json.loads(compared.read_text(encoding="utf-8"))
    assert evidence["schema"] == (
        "TPAA_M2_OBS_003_IDEMPOTENT_PUBLICATION_REPLAY_"
        "CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["implementation_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
