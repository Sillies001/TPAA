#!/usr/bin/env python3
"""Build or verify the local G10 CB-1.15.0 view-closure successor baseline.

G10 adds no new security routes (103 stable).  It records the page-closure decision and
the explicit NOT_ADMITTED state of P3 profile / report revision / structured governance:
those panels render controlled-unavailable until their Metric/Report/Governance
authorities are admitted in a later phase.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "baseline" / "CB-1.14.0"
TARGET = ROOT / "baseline" / "CB-1.15.0"
CORE = "CB-1.15.0"
DECISION_ID = "G10-V33-VIEW-CLOSURE-2026-11-07"
APPROVAL_ID = "G10-CB-1.15.0-LOCAL-VIEW-CLOSURE-2026-11-07"


class G10SuccessorError(RuntimeError):
    pass


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise G10SuccessorError(f"expected JSON object: {path}")
    return value


def _clone(value: object) -> Any:
    return json.loads(json.dumps(value))


def _write(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _metadata(filename: str) -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / filename))
    value.update(
        core_baseline=CORE,
        parent_core_baseline="CB-1.14.0",
        decision_id=DECISION_ID,
        approval_id=APPROVAL_ID,
        approval_status="APPROVED_LOCAL",
        activation_status="ACTIVE",
        release_claim=False,
    )
    return cast(dict[str, Any], value)


def _not_admitted(authority_id: str, owner: str, reason: str) -> dict[str, Any]:
    return {
        "authority_id": authority_id,
        "authority_version": "1.0.0",
        "core_baseline": CORE,
        "parent_core_baseline": "CB-1.14.0",
        "decision_id": DECISION_ID,
        "approval_id": APPROVAL_ID,
        "admission_status": "NOT_ADMITTED",
        "rules": {
            "controlled_unavailable_only": True,
            "no_synthetic_profile": True,
            "no_synthetic_report_revision": True,
            "no_governance_mutation_without_authority": True,
        },
        "single_owner_rules": {"read_model_owner": owner},
        "not_admitted_reason": reason,
        "release_claim": False,
    }


def _schema_compatibility() -> dict[str, Any]:
    value = _clone(_load(PARENT / "canonical" / "SCHEMA_COMPATIBILITY_AUTHORITY.json"))
    value.update(
        authority_version="1.8.0",
        core_baseline=CORE,
        decision_id=DECISION_ID,
        approval_status="APPROVED",
        approval_date="2026-11-07",
        approval_basis="G10 local successor inherits unchanged CB-1.14.0 artifacts; no DB schema change.",
    )
    inherited: list[dict[str, str]] = []
    for path in sorted((PARENT / "canonical").glob("*.json"), key=lambda item: item.name):
        if path.name == "SCHEMA_COMPATIBILITY_AUTHORITY.json":
            continue
        payload = _load(path)
        declared = payload.get("core_baseline")
        if isinstance(declared, str) and declared != CORE:
            inherited.append(
                {
                    "file": path.name,
                    "declared_core_baseline": declared,
                    "compatible_core_baseline": CORE,
                    "approval_status": "APPROVED",
                }
            )
    value["core_inheritance"] = inherited
    entries = value.get("entries")
    if isinstance(entries, list):
        for entry in entries:
            if isinstance(entry, dict):
                entry["compatible_core_baseline"] = CORE
    return cast(dict[str, Any], value)


def build_successor(output: Path) -> None:
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(PARENT, output)
    canonical = output / "canonical"
    security = _clone(_load(PARENT / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json"))
    security.update(
        authority_version="1.8.0",
        core_baseline=CORE,
        parent_core_baseline="CB-1.14.0",
        decision_id=DECISION_ID,
        approval_id=APPROVAL_ID,
        approval_status="APPROVED_LOCAL",
        activation_status="ACTIVE",
        release_claim=False,
    )
    replacements = {
        "API_ROUTE_SECURITY_AUTHORITY.json": security,
        "GUI_PERMISSION_AUDIT_AUTHORITY.json": _metadata("GUI_PERMISSION_AUDIT_AUTHORITY.json"),
        "GUI_ROLE_VIEW_ACCESS_MATRIX.json": _metadata("GUI_ROLE_VIEW_ACCESS_MATRIX.json"),
        "GUI_VIEW_CONTRACT.json": _metadata("GUI_VIEW_CONTRACT.json"),
        "GUI_ASYNC_GATEWAY_AUTHORITY.json": _metadata("GUI_ASYNC_GATEWAY_AUTHORITY.json"),
        "GUI_BATCH_IMPORT_AUTHORITY.json": _metadata("GUI_BATCH_IMPORT_AUTHORITY.json"),
        "GUI_WEAPON_EVENT_AUTHORITY.json": _metadata("GUI_WEAPON_EVENT_AUTHORITY.json"),
        "GUI_HISTORICAL_OVERVIEW_AUTHORITY.json": _metadata("GUI_HISTORICAL_OVERVIEW_AUTHORITY.json"),
        "GUI_BATCH_EVENTS_AUTHORITY.json": _metadata("GUI_BATCH_EVENTS_AUTHORITY.json"),
        "GUI_CO_ATTACK_AUTHORITY.json": _metadata("GUI_CO_ATTACK_AUTHORITY.json"),
        "GUI_REPLAY_AUTHORITY.json": _metadata("GUI_REPLAY_AUTHORITY.json"),
        "SCHEMA_COMPATIBILITY_AUTHORITY.json": _schema_compatibility(),
        "GUI_P3_PROFILE_AUTHORITY.json": _not_admitted(
            "GUI_P3_PROFILE_AUTHORITY",
            "tpaa_application.p3_profile",
            "P3 Model Profile 读模型未准入：V10~V16 仅以受控不可用呈现，不合成 Profile。",
        ),
        "GUI_REPORT_REVISION_AUTHORITY.json": _not_admitted(
            "GUI_REPORT_REVISION_AUTHORITY",
            "tpaa_application.report_revision",
            "报告 revision 服务未准入：V18 仅以受控不可用呈现，不可变 revision 规则已在 authority 固化。",
        ),
        "GUI_GOVERNANCE_AUTHORITY.json": _not_admitted(
            "GUI_GOVERNANCE_AUTHORITY",
            "tpaa_application.governance",
            "结构化治理 mutation 未准入：V22 仅呈现审计只读入口说明，mutation 全部权限/审计在 authority 固化。",
        ),
        "G10_VIEW_CLOSURE_APPROVAL.json": {
            "schema": "TPAA_G10_VIEW_CLOSURE_APPROVAL_V1",
            "approval_id": APPROVAL_ID,
            "decision_id": DECISION_ID,
            "status": "APPROVED_LOCAL",
            "activation_status": "ACTIVE",
            "approved_core_baseline": CORE,
            "approved_at": "2026-11-07T00:00:00+08:00",
            "approver": "PROJECT_OWNER_G10_VIEW_CLOSURE_DIRECTIVE",
            "restrictions": {"push": False, "production_deployment": False, "release_claim": False},
        },
    }
    for name, document in replacements.items():
        _write(canonical / name, document)
    artifacts = [
        {"file": path.name, "sha256": _sha256(path), "bytes": path.stat().st_size}
        for path in sorted(canonical.glob("*.json"), key=lambda item: item.name)
    ]
    _write(
        output / "BASELINE_LOCK.json",
        {
            "baseline": {
                "overall": "TPAA V8.0",
                "engineering": "ED-2.1",
                "core": CORE,
                "db_schema": "1.10.0",
                "product": "P1_METRIC_CATALOG-1.14.0",
                "date": "2026-11-07",
                "rebaseline": "R4.0_G10_VIEW_CLOSURE",
                "decision_id": DECISION_ID,
                "approval_id": APPROVAL_ID,
                "approval_status": "APPROVED_LOCAL",
                "activation_status": "ACTIVE",
                "lock_lineage_sha256": [_sha256(PARENT / "BASELINE_LOCK.json")],
                "release_claim": False,
            },
            "artifacts": artifacts,
        },
    )
    _write(
        output / "IMPORT_PROVENANCE.json",
        {
            "record_type": "G10_SUCCESSOR_IMPORT_PROVENANCE",
            "authority": False,
            "decision_id": DECISION_ID,
            "source_baseline": "CB-1.14.0",
            "source_baseline_lock_sha256": _sha256(PARENT / "BASELINE_LOCK.json"),
            "core_baseline": CORE,
            "db_schema_target": "1.10.0",
            "controlled_artifact_count": len(artifacts),
            "release_claim": False,
        },
    )
    (output / "README.md").write_text(
        "# CB-1.15.0 G10 view-closure successor baseline\n\n"
        f"Decision: `{DECISION_ID}`. CB-1.14.0 remains the immutable parent. "
        "Route authority stays at 103; P3 profile / report revision / governance are recorded NOT_ADMITTED.\n",
        encoding="utf-8",
    )


def _digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()


def check_successor() -> None:
    if not TARGET.is_dir():
        raise G10SuccessorError(f"successor missing: {TARGET}")
    with tempfile.TemporaryDirectory(prefix="tpaa-g10-successor-") as temporary:
        expected = Path(temporary) / CORE
        build_successor(expected)
        expected_digest = _digest(expected)
    actual = _digest(TARGET)
    if actual != expected_digest:
        raise G10SuccessorError(f"successor drift: {actual} != {expected_digest}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        check_successor() if args.check else build_successor(TARGET)
        print(f"G10_SUCCESSOR_PASS core={CORE} digest={_digest(TARGET)}")
    except (OSError, ValueError, KeyError, G10SuccessorError) as exc:
        print(f"G10_SUCCESSOR_FAIL {exc}")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
