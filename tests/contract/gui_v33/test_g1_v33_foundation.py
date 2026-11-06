from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tpaa_canonical import CanonicalArtifactLoader

REPO_ROOT = Path(__file__).resolve().parents[3]
CANDIDATE = REPO_ROOT / "baseline" / "CB-1.6.0"
LOCK = CANDIDATE / "BASELINE_LOCK.json"
CANONICAL = CANDIDATE / "canonical"


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_g1_candidate_lock_and_all_42_artifacts_validate() -> None:
    lock = _load(LOCK)
    assert lock["baseline"]["core"] == "CB-1.6.0"
    assert lock["baseline"]["db_schema"] == "1.10.0"
    assert lock["baseline"]["release_claim"] is False
    assert len(lock["artifacts"]) == 42
    loader = CanonicalArtifactLoader(
        CANDIDATE,
        expected_core_baseline="CB-1.6.0",
        trusted_lock_sha256=_sha256(LOCK),
        expected_controlled_artifact_count=42,
    )
    assert len(loader.artifact_ids) == 42
    assert all(loader.load(artifact_id).byte_size > 0 for artifact_id in loader.artifact_ids)


def test_g1_persistence_decisions_are_explicit_and_minimal() -> None:
    authority = _load(CANONICAL / "GUI_DOMAIN_ADMISSION_AUTHORITY.json")
    decisions = {item["concept"]: item for item in authority["decisions"]}
    assert decisions["BatchWorkset"]["persistent"] is False
    assert decisions["BatchRegistration/BatchMetadata"]["persistent"] is True
    assert decisions["WeaponEvent"]["persistent"] == "VIA_EXISTING_EVENT"
    assert decisions["AttackCluster"]["persistent"] == "VIA_EXISTING_RELATION"
    assert decisions["EventWindowProjection"]["persistent"] is False
    assert decisions["PerspectiveProjection"]["persistent"] is False
    assert decisions["Force/Formation Context"]["persistent"] is True
    assert decisions["TaskMetricDefinition"]["lifecycle"] == "SEPARATE_METRIC_ADMISSION"


def test_g1_routes_are_governed_but_not_falsely_exposed() -> None:
    authority = _load(CANONICAL / "API_ROUTE_AUTHORITY.json")
    reserved = authority["reserved_routes"]
    assert len(reserved) == 14
    assert all(item["implementation_status"] == "RESERVED_G1_NOT_EXPOSED" for item in reserved)
    assert all(item["permission_id"] and item["audit_event"] for item in reserved)
    openapi = _load(REPO_ROOT / "generated" / "g1-cb-1.6.0" / "api" / "openapi-gui-v33.json")
    assert not ({item["path"] for item in reserved} & set(openapi["paths"]))


def test_g1_webengine_evidence_is_fail_closed_and_non_release() -> None:
    evidence = _load(REPO_ROOT / "evidence" / "gui-g1-v33-webengine-smoke.json")
    assert evidence["status"] == "PASS"
    assert evidence["exact_origin"].startswith("http://127.0.0.1:")
    assert evidence["off_the_record"] is True
    assert evidence["backend_degraded_state"] == "PASS"
    assert evidence["shutdown_state"] == "EXITED"
    assert evidence["release_claim"] is False
