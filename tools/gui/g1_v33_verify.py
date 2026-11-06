#!/usr/bin/env python3
"""Verify and record every local G1 v33 exit gate without making a release claim."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
for import_root in (REPO_ROOT, SRC_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from tools.baseline.adopt_g1_successor import (  # noqa: E402
    _directory_digest,
    build_successor,
)
from tools.codegen.g1_generate import DEFAULT_OUTPUT  # noqa: E402
from tools.codegen.g1_generate import verify as verify_codegen  # noqa: E402
from tools.gui.g1_frontend_build import verify as verify_frontend  # noqa: E402
from tools.storage.g1_v33_migration import (  # noqa: E402
    bootstrap_source_sqlite,
    downgrade_sqlite,
    new_relation_names,
    upgrade_sqlite,
    verify_source_sqlite,
    verify_target_sqlite,
)
from tpaa_canonical import CanonicalArtifactLoader  # noqa: E402

CANDIDATE_ROOT = REPO_ROOT / "baseline" / "CB-1.6.0"
PREDECESSOR_LOCK = REPO_ROOT / "baseline" / "CB-1.5.0" / "BASELINE_LOCK.json"
CANDIDATE_LOCK = CANDIDATE_ROOT / "BASELINE_LOCK.json"
CANONICAL_ROOT = CANDIDATE_ROOT / "canonical"
WEBENGINE_EVIDENCE = REPO_ROOT / "evidence" / "gui-g1-v33-webengine-smoke.json"
OUTPUT = REPO_ROOT / "evidence" / "gui-g1-v33-closure.json"
EXPECTED_PREDECESSOR_LOCK = (
    "ecdb68d0aa17ad49b2b0b3bdbad0e82559cd455725a0eb2a2a4855feba99edab"
)
EXPECTED_RELATIONS = (
    "registry.batch_registration",
    "registry.batch_training_type_revision",
    "context.force_formation_context_revision",
    "context.force_formation_member",
)


class G1VerificationError(RuntimeError):
    """A G1 machine-authority or scaffold gate failed closed."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise G1VerificationError(f"cannot load JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise G1VerificationError(f"expected JSON object: {path}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise G1VerificationError(message)


def _verify_lock_and_loader() -> dict[str, Any]:
    _require(_sha256(PREDECESSOR_LOCK) == EXPECTED_PREDECESSOR_LOCK, "CB-1.5.0 lock drift")
    lock = _load(CANDIDATE_LOCK)
    baseline = lock.get("baseline")
    artifacts = lock.get("artifacts")
    if not isinstance(baseline, dict) or not isinstance(artifacts, list):
        raise G1VerificationError("candidate lock structure invalid")
    _require(baseline.get("core") == "CB-1.6.0", "candidate core version drift")
    _require(baseline.get("db_schema") == "1.10.0", "candidate DB version drift")
    _require(baseline.get("lock_lineage_sha256") == [EXPECTED_PREDECESSOR_LOCK], "lineage drift")
    _require(baseline.get("release_claim") is False, "G1 must not make a release claim")
    _require(len(artifacts) == 42, "candidate controlled artifact count drift")
    loader = CanonicalArtifactLoader(
        CANDIDATE_ROOT,
        expected_core_baseline="CB-1.6.0",
        trusted_lock_sha256=_sha256(CANDIDATE_LOCK),
        expected_controlled_artifact_count=len(artifacts),
    )
    loaded = [loader.load(artifact_id).filename for artifact_id in loader.artifact_ids]
    _require(len(loaded) == len(artifacts), "candidate loader coverage drift")
    return {
        "predecessor_lock_sha256": EXPECTED_PREDECESSOR_LOCK,
        "candidate_lock_sha256": _sha256(CANDIDATE_LOCK),
        "controlled_artifacts": len(loaded),
        "status": "PASS",
    }


def _verify_authorities() -> dict[str, Any]:
    admission = _load(CANONICAL_ROOT / "GUI_DOMAIN_ADMISSION_AUTHORITY.json")
    decisions = admission.get("decisions")
    if not isinstance(decisions, list):
        raise G1VerificationError("domain admission decisions missing")
    by_concept = {
        item.get("concept"): item for item in decisions if isinstance(item, dict)
    }
    expected_persistence: dict[str, object] = {
        "BatchWorkset": False,
        "BatchRegistration/BatchMetadata": True,
        "WeaponEvent": "VIA_EXISTING_EVENT",
        "AttackCluster": "VIA_EXISTING_RELATION",
        "EventWindowProjection": False,
        "PerspectiveProjection": False,
        "Force/Formation Context": True,
        "HistoricalOverview": False,
        "TaskMetricDefinition": False,
    }
    for concept, persistent in expected_persistence.items():
        _require(by_concept.get(concept, {}).get("persistent") == persistent, f"admission drift: {concept}")
    routes = _load(CANONICAL_ROOT / "API_ROUTE_AUTHORITY.json")
    reserved = routes.get("reserved_routes")
    if not isinstance(reserved, list) or not reserved:
        raise G1VerificationError("reserved GUI routes missing")
    _require(
        all(
            isinstance(item, dict)
            and item.get("implementation_status") == "RESERVED_G1_NOT_EXPOSED"
            and isinstance(item.get("permission_id"), str)
            and isinstance(item.get("audit_event"), str)
            for item in reserved
        ),
        "reserved route admission is incomplete",
    )
    openapi = _load(DEFAULT_OUTPUT / "api" / "openapi-gui-v33.json")
    openapi_paths = openapi.get("paths")
    if not isinstance(openapi_paths, Mapping):
        raise G1VerificationError("generated OpenAPI paths missing")
    exposed_reserved = [
        item["path"]
        for item in reserved
        if isinstance(item, dict) and item.get("path") in openapi_paths
    ]
    _require(not exposed_reserved, f"unimplemented reserved routes exposed: {exposed_reserved}")
    metric = _load(CANONICAL_ROOT / "GUI_TASK_METRIC_ADMISSION_AUTHORITY.json")
    _require(metric.get("approval_status") == "NOT_ADMITTED", "task metric gate was bypassed")
    compatibility = _load(CANONICAL_ROOT / "SCHEMA_COMPATIBILITY_AUTHORITY.json")
    _require(compatibility.get("current_db_schema") == "1.10.0", "compatibility DB drift")
    _require(compatibility.get("approval_status") == "APPROVED", "compatibility not approved")
    return {
        "domain_decisions": len(by_concept),
        "reserved_routes": len(reserved),
        "exposed_unimplemented_routes": 0,
        "task_metric_admission": "NOT_ADMITTED",
        "status": "PASS",
    }


def _verify_successor_reproducibility() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="tpaa-g1-closure-") as temporary:
        regenerated = Path(temporary) / "CB-1.6.0"
        build_successor(regenerated)
        expected = _directory_digest(regenerated)
        actual = _directory_digest(CANDIDATE_ROOT)
    _require(actual == expected, f"candidate successor drift: {actual} != {expected}")
    return {"directory_digest": actual, "status": "PASS"}


def _verify_migration() -> dict[str, Any]:
    _require(new_relation_names() == EXPECTED_RELATIONS, "migration relation set drift")
    with tempfile.TemporaryDirectory(prefix="tpaa-g1-migration-") as temporary:
        database = Path(temporary) / "g1.sqlite3"
        bootstrap_source_sqlite(database)
        _require(upgrade_sqlite(database).schema_version == "1.10.0", "upgrade failed")
        target = verify_target_sqlite(database)
        _require(downgrade_sqlite(database).schema_version == "1.9.0", "rollback failed")
        source = verify_source_sqlite(database)
    return {
        "from": source.schema_version,
        "to": target.schema_version,
        "relations": list(EXPECTED_RELATIONS),
        "empty_rollback": "PASS",
        "nonempty_rollback_policy": "REFUSE_FAIL_CLOSED",
        "status": "PASS",
    }


def _verify_webengine_evidence() -> dict[str, Any]:
    evidence = _load(WEBENGINE_EVIDENCE)
    _require(evidence.get("status") == "PASS", "WebEngine smoke did not pass")
    origin = evidence.get("exact_origin")
    _require(
        isinstance(origin, str) and origin.startswith("http://127.0.0.1:"),
        "WebEngine origin is not exact loopback",
    )
    _require(evidence.get("off_the_record") is True, "WebEngine profile is persistent")
    _require(evidence.get("backend_degraded_state") == "PASS", "degraded state missing")
    _require(evidence.get("shutdown_state") == "EXITED", "backend lifecycle did not close")
    _require(evidence.get("release_claim") is False, "smoke evidence made release claim")
    return {
        "exact_loopback_origin": True,
        "off_the_record": True,
        "backend_degraded_state": "PASS",
        "shutdown_state": "EXITED",
        "status": "PASS",
    }


def verify() -> dict[str, Any]:
    lock = _verify_lock_and_loader()
    authorities = _verify_authorities()
    successor = _verify_successor_reproducibility()
    migration = _verify_migration()
    codegen_digest = verify_codegen(DEFAULT_OUTPUT)
    frontend = verify_frontend()
    webengine = _verify_webengine_evidence()
    return {
        "schema": "TPAA_G1_V33_CLOSURE_EVIDENCE_V1",
        "status": "PASS",
        "verified_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "phase_status": "CLOSED_LOCAL_WITH_GATES",
        "machine_authority": lock,
        "authority_admission": authorities,
        "successor_reproducibility": successor,
        "migration": migration,
        "codegen": {"digest": codegen_digest, "zero_drift": True, "status": "PASS"},
        "frontend": frontend,
        "webengine": webengine,
        "open_gates": [
            "G2-G10 functional product implementation",
            "G11 target Windows/Linux GPU and software-rendering qualification",
            "G12 independent design-compliance and release approval",
        ],
        "release_claim": False,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = verify()
    except (OSError, ValueError, G1VerificationError) as exc:
        print(f"G1_V33_VERIFY_FAIL {exc}", file=sys.stderr)
        return 2
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"G1_V33_VERIFY_PASS output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
