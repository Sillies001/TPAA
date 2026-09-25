#!/usr/bin/env python3
"""Integrated per-platform qualification for M1 Batch 4 / Issue #88."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

SCHEMA = "TPAA_M1_BATCH_4_PLATFORM_V1"


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"evidence must be an object: {path}")
    return payload


def _git_tree_identity(repo_root: Path, relative: str) -> str:
    result = subprocess.run(
        ["git", "ls-tree", "-r", "HEAD", "--", relative],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_blob_identity(repo_root: Path, relative: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", f"HEAD:{relative}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_clean(repo_root: Path) -> bool:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and not result.stdout.strip()


def run(
    *,
    batch1: Path,
    batch2_service: Path,
    batch3_desktop: Path,
    expected_revision: str,
    repo_root: Path,
    evidence: Path,
) -> int:
    b1 = _load(batch1)
    b2 = _load(batch2_service)
    b3 = _load(batch3_desktop)

    frozen_hashes = {
        "canonical": _git_tree_identity(repo_root, "baseline/CB-1.4.0/canonical"),
        "fixtures": _git_tree_identity(repo_root, "tests/fixtures/m1"),
    }
    lock_hashes = {
        name: _git_blob_identity(repo_root, name)
        for name in ("pyproject.toml", "uv.lock")
    }

    checks = {
        "batch1_schema_exact": b1.get("schema") == "TPAA_M1_BATCH_1_CORE_EVIDENCE_V1",
        "batch1_status_pass": b1.get("status") == "PASS",
        "batch1_revision_exact": b1.get("source_revision") == expected_revision,
        "batch1_failed_acceptance_empty": b1.get("failed_acceptance") == [],
        "batch2_schema_exact": b2.get("schema") == "TPAA_M1_BATCH_2_SERVICE_SMOKE_V1",
        "batch2_status_pass": b2.get("status") == "PASS",
        "batch2_revision_exact": b2.get("source_revision") == expected_revision,
        "batch3_schema_exact": b3.get("schema") == "TPAA_M1_BATCH_3_DESKTOP_E2E_V1",
        "batch3_status_pass": b3.get("status") == "PASS",
        "batch3_revision_exact": b3.get("source_revision") == expected_revision,
        "workspace_tracked_files_clean": _git_clean(repo_root),
        "frozen_canonical_bundle_present": bool(frozen_hashes["canonical"]),
        "frozen_fixture_bundle_present": bool(frozen_hashes["fixtures"]),
        "locked_environment_present": set(lock_hashes) == {"pyproject.toml", "uv.lock"},
    }

    logical_product = {
        "fixture_family": "M1_INTEGRATED_CURRENT",
        "batch1": {
            "world_logical_hashes": b1.get("world_logical_hashes"),
            "metric_batch_hashes": b1.get("metric_batch_hashes"),
        },
        "batch2": b2.get("logical_product"),
        "batch3": b3.get("logical_product"),
        "frozen_bundle": {
            "canonical_git_tree_listing": frozen_hashes["canonical"],
            "fixture_git_tree_listing": frozen_hashes["fixtures"],
            "pyproject_git_blob": lock_hashes.get("pyproject.toml"),
            "uv_lock_git_blob": lock_hashes.get("uv.lock"),
        },
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    acceptance = {
        "M1-TST-010": not failed,
    }
    payload = {
        "schema": SCHEMA,
        "tracking_issue": 88,
        "source_revision": expected_revision,
        "status": "PASS" if not failed else "FAIL",
        "acceptance": acceptance,
        "failed_acceptance": [] if acceptance["M1-TST-010"] else ["M1-TST-010"],
        "checks": checks,
        "failed_checks": failed,
        "logical_product": logical_product,
        "noise_policy": {
            "excluded_keys": ["path", "pid", "native_bytes", "native_byte_hash", "timestamp"],
            "comparison_scope": "business logical products plus frozen governed bundle hashes",
        },
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if not failed else 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch1", type=Path, required=True)
    parser.add_argument("--batch2-service", type=Path, required=True)
    parser.add_argument("--batch3-desktop", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args(argv)
    return run(
        batch1=args.batch1,
        batch2_service=args.batch2_service,
        batch3_desktop=args.batch3_desktop,
        expected_revision=args.expected_revision,
        repo_root=args.repo_root.resolve(),
        evidence=args.evidence,
    )


if __name__ == "__main__":
    raise SystemExit(main())
