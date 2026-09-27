from __future__ import annotations

import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from tpaa_application import (
    InMemoryM3ReleasePublicationRepository,
    M3PublicationService,
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
CHECK = ROOT / "tools" / "testing" / "m3_idempotent_publication_check.py"
SESSION_ID = "10000000-0000-4000-8000-000000000001"


def _release() -> object:
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
            plugin_id=f"m3-obs-003-test:{definition.metric_code}:v1",
            plugin=probe,
        )
    inputs = {
        definition.metric_code: {"input_token": definition.metric_code}
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
            "metric_code": definition.metric_code,
            "training_type": "BASIC_FLIGHT",
        }
        for definition in plan.definitions
    }
    return build_m3_release_snapshot(
        session_id=SESSION_ID,
        request_hash="6" * 64,
        release_no=1,
        parent_release_id=None,
        plan=plan,
        routing=routing,
        batch=batch,
        evidence_by_metric=evidence,
        context_snapshot={
            "context_version": "BASIC_CONTEXT_V1",
            "training_type": "BASIC_FLIGHT",
        },
        world_snapshot={
            "episode_id": "20000000-0000-4000-8000-000000000001",
            "stage_id": "30000000-0000-4000-8000-000000000001",
            "stage_code": "EXECUTION",
        },
        identity_snapshot={
            "training_type": "BASIC_FLIGHT",
            "stage_profile_id": "BASIC_FLIGHT_V1",
        },
        provenance_snapshot={
            "source_revision": "test",
            "stage_profile_id": "BASIC_FLIGHT_V1",
        },
    )


def test_m3_obs_003_concurrent_exact_retry_is_idempotent() -> None:
    release = _release()
    repository = InMemoryM3ReleasePublicationRepository()
    service = M3PublicationService(repository)

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(
            executor.map(
                lambda _: service.publish(
                    release,  # type: ignore[arg-type]
                    idempotency_key="basic-first",
                    expected_version_token=0,
                ),
                range(4),
            )
        )

    assert sum(not result.reused for result in results) == 1
    assert sum(result.reused for result in results) == 3
    assert {result.published.version_token for result in results} == {1}
    assert repository.version_token(SESSION_ID) == 1


def test_m3_obs_003_evidence_and_cross_platform_contract(
    tmp_path: Path,
) -> None:
    source = tmp_path / "publication.json"
    checked = subprocess.run(
        [
            sys.executable,
            str(CHECK),
            "check",
            "--evidence",
            str(source),
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    payload = __import__("json").loads(source.read_text(encoding="utf-8"))
    assert payload["schema"] == (
        "TPAA_M3_OBS_003_IDEMPOTENT_PUBLICATION_REPLAY_EVIDENCE_V1"
    )
    assert payload["task_id"] == "M3-OBS-003"
    assert payload["tracking_issue"] == 116
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())
    assert payload["logical_product"]["training_order"] == [
        "BASIC",
        "WVR",
        "BVR",
        "STRIKE",
    ]

    revision = payload["source_revision"]
    windows = tmp_path / "windows.json"
    linux = tmp_path / "linux.json"
    rendered = __import__("json").dumps(payload)
    windows.write_text(rendered, encoding="utf-8")
    linux.write_text(rendered, encoding="utf-8")
    compared = tmp_path / "compared.json"
    result = subprocess.run(
        [
            sys.executable,
            str(CHECK),
            "compare",
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
        timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    evidence = __import__("json").loads(compared.read_text(encoding="utf-8"))
    assert evidence["schema"] == (
        "TPAA_M3_OBS_003_IDEMPOTENT_PUBLICATION_REPLAY_"
        "CROSS_PLATFORM_EVIDENCE_V1"
    )
    assert evidence["status"] == "PASS"
    assert evidence["task_complete"] is True
    assert evidence["implementation_complete"] is True
    assert evidence["failed_acceptance"] == []
    assert all(evidence["checks"].values())
