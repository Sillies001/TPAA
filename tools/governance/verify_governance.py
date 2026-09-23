#!/usr/bin/env python3
"""Verify M0 governance repository contracts without becoming policy authority."""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_DIR = REPO_ROOT / "docs" / "adr"
REQUIRED_ADRS = {
    "ADR-M0-001": "ADR-M0-001-python-runtime-baseline.md",
    "ADR-M0-002": "ADR-M0-002-dependency-resolver-lock.md",
    "ADR-M0-003": "ADR-M0-003-static-quality-toolchain.md",
    "ADR-M0-004": "ADR-M0-004-repository-db-access-implementation.md",
    "ADR-M0-005": "ADR-M0-005-desktop-backend-lifecycle-ipc.md",
    "ADR-M0-006": "ADR-M0-006-packaging.md",
    "ADR-M0-007": "ADR-M0-007-generated-source-policy.md",
    "ADR-M0-008": "ADR-M0-008-structured-logging-telemetry.md",
    "ADR-M0-009": "ADR-M0-009-local-object-parquet-layout.md",
    "ADR-M0-010": "ADR-M0-010-sbom-license-tooling.md",
}
REQUIRED_REPO_FILES = (
    ".github/ISSUE_TEMPLATE/feature.yml",
    ".github/ISSUE_TEMPLATE/baseline-change.yml",
    ".github/pull_request_template.md",
    "docs/governance/BASELINE_CHANGE.md",
    "docs/governance/DEFINITION_OF_DONE.md",
)
REQUIRED_MACHINE_POLICIES = (
    "tools/manifest/PACKAGING_POLICY.json",
    "tools/security/OBSERVABILITY_POLICY.json",
    "tools/storage/OBJECT_LAYOUT_POLICY.json",
    "tools/manifest/SBOM_POLICY.json",
)


def _check(code: str, ok: bool, detail: str) -> dict[str, str]:
    return {"check": code, "status": "PASS" if ok else "FAIL", "detail": detail}


def verify() -> dict[str, object]:
    checks: list[dict[str, str]] = []

    for adr_id, filename in REQUIRED_ADRS.items():
        path = ADR_DIR / filename
        if not path.is_file():
            checks.append(_check(f"{adr_id}.exists", False, filename))
            continue
        text = path.read_text(encoding="utf-8")
        checks.append(_check(f"{adr_id}.exists", True, filename))
        checks.append(
            _check(
                f"{adr_id}.closed",
                "- **Status:** CLOSED" in text,
                "status must be CLOSED before M0 Exit",
            )
        )
        checks.append(
            _check(
                f"{adr_id}.owner",
                "- **Owner role:**" in text,
                "owner role must be explicit",
            )
        )
        checks.append(
            _check(
                f"{adr_id}.decision",
                "## Decision" in text,
                "decision section must be explicit",
            )
        )
        checks.append(
            _check(
                f"{adr_id}.evidence",
                "evidence" in text.lower(),
                "ADR must reference verification/evidence",
            )
        )

    for relative in REQUIRED_REPO_FILES:
        path = REPO_ROOT / relative
        checks.append(_check(f"repo_file:{relative}", path.is_file(), relative))

    for relative in REQUIRED_MACHINE_POLICIES:
        path = REPO_ROOT / relative
        if not path.is_file():
            checks.append(_check(f"policy:{relative}", False, "missing"))
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            checks.append(_check(f"policy:{relative}", False, str(exc)))
            continue
        frozen = isinstance(payload, dict) and payload.get("status") == "FROZEN"
        checks.append(_check(f"policy:{relative}", frozen, "status=FROZEN"))

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {
        "schema": "TPAA_M0_GOVERNANCE_EVIDENCE_V1",
        "task_ids": ["M0-GOV-001", "M0-GOV-002", "M0-GOV-003", "M0-GOV-004"],
        "status": status,
        "checks": checks,
    }


def main() -> int:
    evidence = verify()
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
