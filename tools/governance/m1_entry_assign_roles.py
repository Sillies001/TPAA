#!/usr/bin/env python3
"""Render explicit M1 role assignments into an admission-candidate review.

The renderer never emits M1_ADMITTED. It transforms the 9/10 blocked review
into an assigned admission candidate whose condition 6 must be re-verified by
the exact PR/merged-main runtime manifests.
"""

from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROLES = REPO_ROOT / "docs" / "governance" / "M1_ROLE_ASSIGNMENTS.json"
DEFAULT_REVIEW = REPO_ROOT / "docs" / "reviews" / "M1_ENTRY_GATE_REVIEW.json"


def _load(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise RuntimeError(f"JSON root must be object: {path}")
    return raw


def _identity(value: str, field: str) -> str:
    result = value.strip()
    if not result or result.startswith("<") or result.endswith(">"):
        raise ValueError(f"{field} must be an explicit human identity")
    return result


def render(
    *,
    roles: dict[str, object],
    review: dict[str, object],
    primary_ws_owner: str,
    golden_independent_reviewer: str,
    m1_exit_reviewer: str,
    golden_independence_attestation: str,
) -> tuple[dict[str, object], dict[str, object]]:
    if roles.get("schema") != "TPAA_M1_ROLE_ASSIGNMENTS_V1":
        raise ValueError("unexpected role-assignment schema")
    if review.get("schema") != "TPAA_M1_ENTRY_GATE_REVIEW_V1":
        raise ValueError("unexpected Entry Gate review schema")

    primary = _identity(primary_ws_owner, "primary_ws_owner")
    golden = _identity(golden_independent_reviewer, "golden_independent_reviewer")
    exit_reviewer = _identity(m1_exit_reviewer, "m1_exit_reviewer")
    attestation = golden_independence_attestation.strip()
    if not attestation or attestation.startswith("<") or attestation.endswith(">"):
        raise ValueError("golden_independence_attestation must be explicit")

    assigned = deepcopy(roles)
    assigned.update(
        {
            "status": "ASSIGNED",
            "primary_ws_owner": primary,
            "golden_independent_reviewer": golden,
            "m1_exit_reviewer": exit_reviewer,
            "golden_independence_attestation": attestation,
            "assignment_source": "EXPLICIT_HUMAN_ASSIGNMENT",
        }
    )

    candidate = deepcopy(review)
    raw_conditions = candidate.get("conditions")
    if not isinstance(raw_conditions, list):
        raise ValueError("Entry Gate review conditions missing")
    seen: set[int] = set()
    for item in raw_conditions:
        if not isinstance(item, dict) or not isinstance(item.get("id"), int):
            raise ValueError("invalid Entry Gate condition record")
        condition_id = int(item["id"])
        seen.add(condition_id)
        if condition_id == 6:
            item["status"] = "RUNTIME_VERIFY_REQUIRED"
            item["evidence"] = (
                "Role-assignment change creates a new source revision. "
                "Windows/Linux M1 Entry manifests must match the exact PR/merged-main "
                "revision through M1_ENTRY_ACTIVATION_POLICY."
            )
        elif condition_id == 8:
            item["status"] = "PASS"
            item["evidence"] = (
                "Explicit human role assignments and Golden independence attestation "
                "are frozen in docs/governance/M1_ROLE_ASSIGNMENTS.json."
            )
        elif item.get("status") != "PASS":
            raise ValueError(
                f"condition {condition_id} must already be PASS before role assignment"
            )
    if seen != set(range(1, 11)):
        raise ValueError(f"expected conditions 1..10, actual={sorted(seen)}")

    candidate.update(
        {
            "pass_count": 9,
            "condition_count": 10,
            "decision": "M1_ADMISSION_CANDIDATE",
            "blocking_conditions": ["MERGED_MAIN_RUNTIME_EVIDENCE"],
            "implementation_authorized": False,
            "next_action": (
                "Verify the admission candidate on the PR synthetic merge revision, "
                "merge once, then require the protected-main activation artifact to "
                "state M1_ADMITTED before implementation begins."
            ),
        }
    )
    return assigned, candidate


def _write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-ws-owner", required=True)
    parser.add_argument("--golden-independent-reviewer", required=True)
    parser.add_argument("--m1-exit-reviewer", required=True)
    parser.add_argument("--golden-independence-attestation", required=True)
    parser.add_argument("--roles-input", type=Path, default=DEFAULT_ROLES)
    parser.add_argument("--review-input", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--roles-output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path, required=True)
    args = parser.parse_args()

    assigned, candidate = render(
        roles=_load(args.roles_input),
        review=_load(args.review_input),
        primary_ws_owner=args.primary_ws_owner,
        golden_independent_reviewer=args.golden_independent_reviewer,
        m1_exit_reviewer=args.m1_exit_reviewer,
        golden_independence_attestation=args.golden_independence_attestation,
    )
    _write(args.roles_output, assigned)
    _write(args.review_output, candidate)
    print(
        json.dumps(
            {
                "schema": "TPAA_M1_ROLE_ASSIGNMENT_RENDER_V1",
                "status": "PASS",
                "decision": candidate["decision"],
                "implementation_authorized": candidate["implementation_authorized"],
                "roles_output": str(args.roles_output),
                "review_output": str(args.review_output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
