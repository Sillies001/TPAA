#!/usr/bin/env python3
"""Machine-readable acceptance verifier for M0-CORE-005 architecture dependencies."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from dependency_policy import load_policy, scan_architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
POLICY_PATH = REPO_ROOT / "tools" / "architecture" / "ARCHITECTURE_POLICY.json"


def _head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNAVAILABLE"


def _policy_sha256() -> str:
    return hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()


def verify(src_root: Path = SRC_ROOT) -> dict[str, object]:
    policy = load_policy(POLICY_PATH)
    violations, scanned_files, import_count = scan_architecture(src_root, policy)
    reasons = {item.reason for item in violations}

    checks = [
        {
            "check_id": "LOWER-LAYER-NO-GUI-API",
            "status": "FAIL" if "LOWER_LAYER_TRANSPORT_DEPENDENCY" in reasons else "PASS",
            "detail": "lower governed layers do not import tpaa_gui/tpaa_api",
        },
        {
            "check_id": "BUSINESS-CORE-NO-PLATFORM-IMPL",
            "status": "FAIL"
            if "BUSINESS_CORE_PLATFORM_IMPLEMENTATION_DEPENDENCY" in reasons
            else "PASS",
            "detail": "business core does not import tpaa_platform implementation",
        },
        {
            "check_id": "APPENDIX-E-STATIC-IMPORT-RULES",
            "status": "PASS" if not violations else "FAIL",
            "detail": f"violations={len(violations)}",
        },
    ]
    status = "PASS" if not violations else "FAIL"
    return {
        "evidence_schema": "TPAA_M0_GATE_EVIDENCE_V1",
        "task_id": "M0-CORE-005",
        "gate_id": "M0-CORE-005.ARCHITECTURE_DEPENDENCIES",
        "workstream": "WS-CORE",
        "status": status,
        "source_revision": _head(),
        "policy_schema": policy.schema,
        "policy_authority": policy.authority,
        "policy_sha256": _policy_sha256(),
        "scanned_python_files": scanned_files,
        "observed_import_dependencies": import_count,
        "violation_count": len(violations),
        "violations": [item.as_dict() for item in violations],
        "checks": checks,
        "semantic_constraints_not_proven_by_import_scan": list(
            policy.semantic_constraints_not_proven_by_import_scan
        ),
        "execution_limitations": [
            "This gate proves statically observable Python import dependencies; semantic behavior not inferable from imports is explicitly not claimed.",
            "External CI-provider and Windows execution are not claimed by M0-CORE-005; later platform/CI evidence must invoke the same command.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--src-root", type=Path, default=SRC_ROOT)
    args = parser.parse_args()
    src_root = args.src_root if args.src_root.is_absolute() else REPO_ROOT / args.src_root
    evidence = verify(src_root)
    text = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.evidence is not None:
        target = args.evidence if args.evidence.is_absolute() else REPO_ROOT / args.evidence
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0 if evidence["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
