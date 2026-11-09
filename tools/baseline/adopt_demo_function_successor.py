#!/usr/bin/env python3
"""F0 scaffold for the Demo-v33 CB-1.18.0 candidate successor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tpaa_canonical import G12_LOCAL_BASELINE_LOCK_SHA256, trusted_loader_for_baseline

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "baseline" / "CB-1.17.0"
MANIFEST = ROOT / "generated" / "demo-function-cb-1.18.0" / "manifest.json"
DIFF = ROOT / "docs" / "compliance" / "CB_1_18_0_DEMO_FUNCTION_DIFF.json"


def _manifest() -> dict[str, object]:
    return {
        "schema": "TPAA_DEMO_FUNCTION_SUCCESSOR_SCAFFOLD_V1",
        "stage": "F0_SCAFFOLD_ONLY",
        "parent_core_baseline": "CB-1.17.0",
        "parent_lock_sha256": G12_LOCAL_BASELINE_LOCK_SHA256,
        "candidate_core_baseline": "CB-1.18.0-candidate",
        "candidate_db_schema": "1.11.0-candidate",
        "candidate_materialized": False,
        "activation_allowed": False,
        "release_claim": False,
        "next_stage": "F1",
    }


def _diff() -> dict[str, object]:
    return {
        "schema": "TPAA_CB_1_18_0_DEMO_FUNCTION_DIFF_V1",
        "status": "F0_SCAFFOLD_ONLY",
        "parent_core_baseline": "CB-1.17.0",
        "candidate_core_baseline": "CB-1.18.0-candidate",
        "parent_immutable": True,
        "candidate_materialized": False,
        "canonical_additions": [],
        "canonical_modifications": [],
        "db_schema_change": "PENDING_F1",
        "dto_codegen_change": "PENDING_F1",
        "admission_change": "NONE_F0",
        "release_claim": False,
    }


def _render(value: dict[str, object]) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _verify_parent() -> None:
    loader = trusted_loader_for_baseline(PARENT)
    artifacts = loader.load_all()
    if len(artifacts) != 69:
        raise RuntimeError(f"CB-1.17.0 artifact count drifted: {len(artifacts)}")
    if loader.trusted_lock_sha256 != G12_LOCAL_BASELINE_LOCK_SHA256:
        raise RuntimeError("CB-1.17.0 lock pin drifted")


def _check_file(path: Path, expected: bytes) -> None:
    if not path.is_file():
        raise RuntimeError(f"missing F0 scaffold output: {path.relative_to(ROOT)}")
    actual = path.read_bytes()
    if actual != expected:
        raise RuntimeError(f"F0 scaffold output drifted: {path.relative_to(ROOT)}")


def check() -> None:
    _verify_parent()
    if (ROOT / "baseline" / "CB-1.18.0-candidate").exists():
        raise RuntimeError("F0 scaffold forbids materialized CB-1.18.0-candidate before F1")
    _check_file(MANIFEST, _render(_manifest()))
    _check_file(DIFF, _render(_diff()))


def write() -> None:
    _verify_parent()
    for path, payload in ((MANIFEST, _manifest()), (DIFF, _diff())):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_render(payload))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
    else:
        write()
    print("DEMO_FUNCTION_SUCCESSOR_SCAFFOLD_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
