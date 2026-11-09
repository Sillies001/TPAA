#!/usr/bin/env python3
"""Verify the immutable CB-1.17.0 parent and the F1 CB-1.18.0 candidate successor."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from tpaa_canonical.loader import (
    F1_CANDIDATE_BASELINE_LOCK_SHA256,
    F1_CANDIDATE_CONTROLLED_ARTIFACT_COUNT,
    F1_CANDIDATE_CORE_BASELINE,
    G12_LOCAL_BASELINE_LOCK_SHA256,
    G12_LOCAL_CORE_BASELINE,
    trusted_loader_for_baseline,
)

ROOT = Path(__file__).resolve().parents[2]
PARENT_TREE_SHA256 = "fddf6e0b5af15cdc2c81aaea60a5c754b078e71b"
REQUIRED_TABLES = {
    "assessment.task_metric_definition",
    "assessment.task_metric_result",
    "assessment.mission_objective_plan",
    "assessment.adjudicated_loss",
    "assessment.engagement_episode",
}
REQUIRED_METRICS = ("KILL_RATIO", "EXCHANGE_RATIO", "MISSION_COMPLETION_RATE")
REQUIRED_RELATIONS = {
    "MANEUVER_SEGMENT",
    "BASIC_FLIGHT_DEVIATION",
    "FORMATION_RELATION",
    "PERCEPTION_EVENT",
    "SENSOR_TRACK_ASSOCIATION",
    "ENGAGEMENT_GEOMETRY",
    "ATTACK_SUPPORT_RELATION",
    "WEAPON_EVENT",
    "ATTACK_CLUSTER",
    "WEAPON_EVENT_SUPERSESSION",
}


class SuccessorError(RuntimeError):
    """The F1 successor is not reproducible or does not match its pinned authority."""


def _git_tree_sha(path: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", f"HEAD:{path}"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SuccessorError(f"cannot verify immutable parent tree {path}: {exc}") from exc
    return result.stdout.strip()


def _definition_sha256(definition: dict[str, Any]) -> str:
    payload = dict(definition)
    payload.pop("definition_sha256", None)
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def check() -> None:
    parent_tree = _git_tree_sha("baseline/CB-1.17.0")
    if parent_tree != PARENT_TREE_SHA256:
        raise SuccessorError(
            "CB-1.17.0 immutable parent tree changed: "
            f"expected={PARENT_TREE_SHA256} actual={parent_tree}"
        )

    candidate_root = ROOT / "baseline" / F1_CANDIDATE_CORE_BASELINE
    loader = trusted_loader_for_baseline(candidate_root)
    artifacts = loader.load_all()
    if len(artifacts) != F1_CANDIDATE_CONTROLLED_ARTIFACT_COUNT:
        raise SuccessorError(
            "candidate controlled artifact count mismatch: "
            f"expected={F1_CANDIDATE_CONTROLLED_ARTIFACT_COUNT} actual={len(artifacts)}"
        )
    if loader.trusted_lock_sha256 != F1_CANDIDATE_BASELINE_LOCK_SHA256:
        raise SuccessorError("candidate BASELINE_LOCK does not match the code-pinned SHA-256")

    lock = json.loads((candidate_root / "BASELINE_LOCK.json").read_text(encoding="utf-8"))
    metadata = lock.get("baseline")
    if not isinstance(metadata, dict):
        raise SuccessorError("candidate BASELINE_LOCK baseline metadata is missing")
    if metadata.get("core") != F1_CANDIDATE_CORE_BASELINE:
        raise SuccessorError("candidate Core identity mismatch")
    if metadata.get("db_schema") != "1.11.0":
        raise SuccessorError("candidate DB schema must be 1.11.0")
    if metadata.get("lock_lineage_sha256") != [G12_LOCAL_BASELINE_LOCK_SHA256]:
        raise SuccessorError("candidate lock lineage must point only to immutable CB-1.17.0")
    if metadata.get("activation_status") != "CANDIDATE_NOT_ACTIVE":
        raise SuccessorError("candidate must remain inactive")
    if metadata.get("release_claim") is not False:
        raise SuccessorError("candidate cannot make a release claim")

    core = dict(loader.load("CORE_LOGICAL_MODEL").payload)
    tables = core.get("tables")
    if not isinstance(tables, dict) or not REQUIRED_TABLES.issubset(tables):
        raise SuccessorError("candidate CORE_LOGICAL_MODEL is missing F1 Assessment tables")
    if len(tables) != 104 or core.get("db_schema_version") != "1.11.0":
        raise SuccessorError("candidate logical model table count or DB version mismatch")

    for metric_id in REQUIRED_METRICS:
        definition = dict(loader.load(metric_id).payload)
        if definition.get("semantic_id") != metric_id:
            raise SuccessorError(f"{metric_id} semantic identity mismatch")
        if definition.get("definition_version") != "1.0.0":
            raise SuccessorError(f"{metric_id} definition version mismatch")
        if definition.get("admission_status") != "CANDIDATE_TEST_ONLY":
            raise SuccessorError(f"{metric_id} must remain CANDIDATE_TEST_ONLY")
        if definition.get("definition_sha256") != _definition_sha256(definition):
            raise SuccessorError(f"{metric_id} definition self-hash mismatch")

    catalog = dict(loader.load("TASK_METRIC_CATALOG").payload)
    catalog_ids = {
        item.get("semantic_id") for item in catalog.get("metrics", [])
        if isinstance(item, dict)
    }
    if catalog_ids != set(REQUIRED_METRICS):
        raise SuccessorError("TASK_METRIC_CATALOG does not reference exactly the three candidates")

    admission = dict(loader.load("GUI_TASK_METRIC_ADMISSION_AUTHORITY").payload)
    if admission.get("approval_status") != "CANDIDATE_TEST_ONLY":
        raise SuccessorError("task metric admission authority must remain test-only")
    if any(
        item.get("admission_status") == "ADMITTED"
        for item in admission.get("candidates", [])
        if isinstance(item, dict)
    ):
        raise SuccessorError("automated work cannot admit a business metric")

    world = dict(loader.load("WORLD_RELATION_TYPE_AUTHORITY").payload)
    relation_types = {
        item.get("relation_type")
        for item in world.get("relation_types", [])
        if isinstance(item, dict)
    }
    if relation_types != REQUIRED_RELATIONS:
        raise SuccessorError("WORLD_RELATION_TYPE_AUTHORITY relation set mismatch")
    distinctions = world.get("semantic_distinctions")
    if not isinstance(distinctions, dict) or not {
        "COOPERATIVE_PASSIVE_LOCALIZATION",
        "PASSIVE_DETECTION_DATA_LINK_SHARE",
    }.issubset(distinctions):
        raise SuccessorError("passive localization and data-link sharing must remain distinct")

    dto = dict(loader.load("CROSS_LAYER_DTO_CONTRACTS").payload)
    contracts = dto.get("contracts")
    if not isinstance(contracts, dict) or not {
        "TaskMetricDefinitionDTO",
        "TaskMetricResultDTO",
        "TaskMetricCompareRequestDTO",
        "TaskMetricEvidenceDTO",
    }.issubset(contracts):
        raise SuccessorError("candidate DTO contract set is incomplete")

    vectors = dict(loader.load("TASK_METRIC_ALGORITHM_TEST_VECTORS").payload)
    if len(vectors.get("vectors", [])) < 10:
        raise SuccessorError("metric algorithm test vectors do not cover required edge cases")

    parent_loader = trusted_loader_for_baseline(ROOT / "baseline" / G12_LOCAL_CORE_BASELINE)
    if loader.load("P1_METRIC_CATALOG").sha256 != parent_loader.load("P1_METRIC_CATALOG").sha256:
        raise SuccessorError("F1 candidate must not modify or replace the P1 metric catalog")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", required=True)
    parser.parse_args()
    check()
    print("CB118_F1_SUCCESSOR_CHECK_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
