#!/usr/bin/env python3
"""Build a fail-closed W9 local candidate identity from four development packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tpaa_qualification import W9_EVIDENCE_CATEGORIES  # noqa: E402

PROFILES = (
    "WINDOWS_DESKTOP_X64",
    "WINDOWS_SERVICE_X64",
    "LINUX_DESKTOP_X64",
    "LINUX_SERVICE_X64",
)


class W9CandidateError(RuntimeError):
    """Candidate package or evidence set is incomplete or inconsistent."""


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise W9CandidateError(f"W9_SUMMARY_UNREADABLE:{path}") from exc
    if not isinstance(payload, dict):
        raise W9CandidateError(f"W9_SUMMARY_ROOT_INVALID:{path}")
    return payload


def _head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _require_clean_tracked_tree() -> None:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if completed.stdout.strip():
        raise W9CandidateError("W9_TRACKED_WORKTREE_NOT_CLEAN")


def build_local_candidate_manifest(
    *,
    dist: Path,
    expected_revision: str,
    baseline_lock: Path,
    dependency_lock: Path,
    evidence_by_category: dict[str, Path],
) -> dict[str, object]:
    """Validate four exact package summaries and bind local evidence to one identity."""

    if tuple(evidence_by_category) != W9_EVIDENCE_CATEGORIES:
        raise W9CandidateError("W9_EVIDENCE_CATEGORY_SET_OR_ORDER_INVALID")
    if len(expected_revision) != 40 or any(
        character not in "0123456789abcdef" for character in expected_revision
    ):
        raise W9CandidateError("W9_EXPECTED_REVISION_INVALID")
    for required in (baseline_lock, dependency_lock, *evidence_by_category.values()):
        if not required.is_file():
            raise W9CandidateError(f"W9_REQUIRED_EVIDENCE_MISSING:{required}")

    package_records: list[dict[str, object]] = []
    package_hashes: dict[str, str] = {}
    for profile in PROFILES:
        summaries = sorted(dist.glob(f"tpaa-*-{profile}.*.summary.json"))
        if len(summaries) != 1:
            raise W9CandidateError(f"W9_PACKAGE_SUMMARY_COUNT_INVALID:{profile}")
        summary_path = summaries[0]
        summary = _load(summary_path)
        if summary.get("schema") != "TPAA_M0_PACKAGE_ARTIFACT_SUMMARY_V1":
            raise W9CandidateError(f"W9_PACKAGE_SUMMARY_SCHEMA_INVALID:{profile}")
        if summary.get("qualification") != "DEVELOPMENT_NOT_M5_QUALIFIED":
            raise W9CandidateError(f"W9_PACKAGE_QUALIFICATION_INVALID:{profile}")
        if summary.get("platform_profile") != profile:
            raise W9CandidateError(f"W9_PACKAGE_PROFILE_MISMATCH:{profile}")
        if summary.get("source_revision") != expected_revision:
            raise W9CandidateError(f"W9_PACKAGE_SOURCE_REVISION_MISMATCH:{profile}")
        package_name = summary.get("package")
        if not isinstance(package_name, str) or not package_name:
            raise W9CandidateError(f"W9_PACKAGE_NAME_INVALID:{profile}")
        package_path = dist / package_name
        if not package_path.is_file():
            raise W9CandidateError(f"W9_PACKAGE_MISSING:{profile}")
        actual_hash = _file_hash(package_path)
        if summary.get("package_sha256") != actual_hash:
            raise W9CandidateError(f"W9_PACKAGE_HASH_MISMATCH:{profile}")
        if summary.get("package_bytes") != package_path.stat().st_size:
            raise W9CandidateError(f"W9_PACKAGE_SIZE_MISMATCH:{profile}")
        package_hashes[profile] = actual_hash
        package_records.append(
            {
                "platform_profile": profile,
                "package": package_name,
                "package_bytes": package_path.stat().st_size,
                "package_sha256": actual_hash,
                "summary_sha256": _file_hash(summary_path),
            }
        )
    if len(set(package_hashes.values())) != len(PROFILES):
        raise W9CandidateError("W9_PACKAGE_HASHES_NOT_PROFILE_DISTINCT")

    candidate_core = {
        "source_revision": expected_revision,
        "baseline_lock_sha256": _file_hash(baseline_lock),
        "dependency_lock_sha256": _file_hash(dependency_lock),
        "package_sha256_by_profile": package_hashes,
    }
    candidate_identity = _canonical_hash(candidate_core)
    evidence_bindings = [
        {
            "category": category,
            "local_state": (
                "LOCAL_EVIDENCE_COMPLETE"
                if category == "AUTHORITY_ARCHITECTURE_DTO_OPENAPI_MIGRATION_REPLAY"
                else "PARTIAL_LOCAL_EVIDENCE"
            ),
            "candidate_identity_sha256": candidate_identity,
            "evidence_sha256": _file_hash(path),
            "evidence_path": path.as_posix(),
            "formal_acceptance": False,
        }
        for category, path in evidence_by_category.items()
    ]
    return {
        "schema": "TPAA_W9_LOCAL_CANDIDATE_MANIFEST_V1",
        "stage_status": "CLOSED_LOCAL_WITH_RELEASE_GATES",
        "decision": "NO_GO",
        "qualification": "LOCAL_CANDIDATE_NOT_FORMALLY_QUALIFIED",
        "candidate_identity_sha256": candidate_identity,
        "candidate_core": candidate_core,
        "packages": package_records,
        "evidence_bindings": evidence_bindings,
        "all_local_evidence_bound_to_one_candidate": True,
        "formal_release_allowed": False,
        "formal_release_claimed": False,
        "pending_formal_gates": [
            "INSTALLED_TARGET_E2E_AND_REAL_EXTERNAL_SYSTEMS",
            "FOUR_PROFILE_WORKLOAD_RECOVERY_AND_UPGRADE_ACCEPTANCE",
            "HUMAN_ROLE_TASK_SIGNOFF",
            "SBOM_PROVENANCE_AND_APPROVED_SIGNATURE",
            "ZERO_UNWAIVED_BLOCKER_OR_HIGH_FINDINGS",
            "PROTECTED_MAIN_EXACT_SHA_AND_HOSTED_CI",
            "INDEPENDENT_RELEASE_APPROVAL",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--expected-revision", default=None)
    parser.add_argument("--baseline-lock", type=Path, required=True)
    parser.add_argument("--dependency-lock", type=Path, required=True)
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        metavar="CATEGORY=PATH",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        _require_clean_tracked_tree()
        revision = args.expected_revision or _head()
        if revision != _head():
            raise W9CandidateError("W9_EXPECTED_REVISION_NOT_HEAD")
        evidence: dict[str, Path] = {}
        for item in args.evidence:
            category, separator, raw_path = item.partition("=")
            if not separator or category in evidence:
                raise W9CandidateError("W9_EVIDENCE_ARGUMENT_INVALID")
            evidence[category] = Path(raw_path)
        result = build_local_candidate_manifest(
            dist=args.dist,
            expected_revision=revision,
            baseline_lock=args.baseline_lock,
            dependency_lock=args.dependency_lock,
            evidence_by_category=evidence,
        )
        code = 0
    except (OSError, subprocess.SubprocessError, W9CandidateError, ValueError) as exc:
        result = {
            "schema": "TPAA_W9_LOCAL_CANDIDATE_MANIFEST_V1",
            "stage_status": "OPEN",
            "decision": "NO_GO",
            "formal_release_allowed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    args.output.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
