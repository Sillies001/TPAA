#!/usr/bin/env python3
"""Verify all supported historical Canonical baselines with stable byte semantics."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tpaa_canonical import trusted_loader_for_baseline
from tpaa_canonical.byte_stability import governed_text_line_ending, governed_text_sha256
from tpaa_canonical.loader import G12_LOCAL_CORE_BASELINE

ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_BASELINES = (
    "CB-1.5.0",
    "CB-1.9.0",
    "CB-1.10.0",
    "CB-1.11.0",
    "CB-1.12.0",
    "CB-1.13.0",
    "CB-1.14.0",
    "CB-1.15.0",
    "CB-1.16.0",
    "CB-1.17.0",
)


class F0VerificationError(RuntimeError):
    """Historical baseline byte verification failed."""


def _source_revision() -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE"
    return completed.stdout.strip()


def verify() -> dict[str, Any]:
    baseline_results: list[dict[str, Any]] = []
    for baseline_id in SUPPORTED_BASELINES:
        baseline_root = ROOT / "baseline" / baseline_id
        if not baseline_root.is_dir():
            raise F0VerificationError(f"supported baseline directory is missing: {baseline_id}")

        loader = trusted_loader_for_baseline(baseline_root)
        artifacts = loader.load_all()
        lock_path = baseline_root / "BASELINE_LOCK.json"
        lock_bytes = lock_path.read_bytes()
        lock = json.loads(lock_bytes.decode("utf-8"))
        raw_entries = lock.get("artifacts")
        if not isinstance(raw_entries, list):
            raise F0VerificationError(f"{baseline_id} BASELINE_LOCK artifacts must be a list")
        entries = {
            entry["file"]: entry
            for entry in raw_entries
            if isinstance(entry, dict) and isinstance(entry.get("file"), str)
        }
        if len(entries) != len(raw_entries) or len(artifacts) != len(entries):
            raise F0VerificationError(f"{baseline_id} controlled artifact count is inconsistent")

        for artifact in artifacts:
            entry = entries.get(artifact.filename)
            if (
                entry is None
                or artifact.sha256 != entry.get("sha256")
                or artifact.byte_size != entry.get("bytes")
            ):
                raise F0VerificationError(
                    f"{baseline_id}/{artifact.filename} differs from its canonical lock entry"
                )

        controlled_paths = [
            lock_path,
            *(baseline_root / "canonical" / artifact.filename for artifact in artifacts),
        ]
        line_ending_counts = {"LF": 0, "CRLF": 0, "NONE": 0}
        for path in controlled_paths:
            style = governed_text_line_ending(path.read_bytes())
            line_ending_counts[style] += 1

        baseline_results.append(
            {
                "core_baseline": baseline_id,
                "baseline_lock_sha256": governed_text_sha256(lock_bytes),
                "controlled_artifact_count": len(artifacts),
                "verified_artifact_count": len(artifacts),
                "line_ending_counts": line_ending_counts,
                "status": "PASS",
            }
        )

    g12_root = ROOT / "baseline" / G12_LOCAL_CORE_BASELINE
    g12_lock = json.loads((g12_root / "BASELINE_LOCK.json").read_text(encoding="utf-8"))
    parent_lock_path = ROOT / "baseline" / "CB-1.16.0" / "BASELINE_LOCK.json"
    parent_digest = governed_text_sha256(parent_lock_path.read_bytes())
    lineage = g12_lock.get("baseline", {}).get("lock_lineage_sha256")
    if lineage != [parent_digest]:
        raise F0VerificationError(
            f"G12 parent lineage mismatch: expected={[parent_digest]!r} actual={lineage!r}"
        )

    return {
        "evidence_schema": "TPAA_F0_BASELINE_BYTE_STABILITY_EVIDENCE_V1",
        "status": "PASS",
        "recorded_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source_revision": _source_revision(),
        "host": {
            "os": platform.system(),
            "os_release": platform.release(),
            "machine": platform.machine(),
            "python": sys.version.split()[0],
        },
        "normalization": {
            "canonical_hash_representation": "CRLF",
            "accepted_checkout_line_endings": ["LF", "CRLF"],
            "mixed_or_bare_line_endings": "REJECT",
            "hash_and_byte_count": "computed over canonical CRLF bytes",
        },
        "supported_baselines": baseline_results,
        "g12_parent_lineage": {
            "parent_core_baseline": "CB-1.16.0",
            "parent_lock_sha256": parent_digest,
            "g12_lock_lineage": lineage,
            "status": "PASS",
        },
        "total_controlled_artifacts_verified": sum(
            item["verified_artifact_count"] for item in baseline_results
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args(argv)

    try:
        payload = verify()
        status = 0
    except (F0VerificationError, OSError, ValueError, RuntimeError) as exc:
        payload = {
            "evidence_schema": "TPAA_F0_BASELINE_BYTE_STABILITY_EVIDENCE_V1",
            "status": "FAIL",
            "recorded_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "source_revision": _source_revision(),
            "error": str(exc),
        }
        status = 2

    rendered = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_bytes(rendered.encode("utf-8"))
    print(rendered, end="")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
