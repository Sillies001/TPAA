#!/usr/bin/env python3
"""Verify the SDIB-1.0.1 M0-DEV-000 repository bootstrap substrate.

This verifier is intentionally repository-local and standard-library-only.
GitHub branch-protection enforcement is a hosting control and is reviewed from
GitHub evidence separately; this script verifies the source-controlled portion
of M0-DEV-000 on both governed platforms.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_PATHS = (
    "README.md",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".github/workflows/cross-platform-ci.yml",
)

EDITORCONFIG_REQUIRED = (
    "root = true",
    "[*]",
    "charset = utf-8",
    "end_of_line = lf",
    "insert_final_newline = true",
    "trim_trailing_whitespace = true",
    "[*.py]",
    "indent_style = space",
    "indent_size = 4",
)

WORKFLOW_REQUIRED = (
    "pull_request:",
    "branches:",
    "- main",
    "runner: ubuntu-24.04",
    "runner: windows-2025",
    "python tools/dev/tpaa_dev.py ci-check",
)


def _check(code: str, ok: bool, detail: str) -> dict[str, str]:
    return {"check": code, "status": "PASS" if ok else "FAIL", "detail": detail}


def _git_worktree_check() -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    value = completed.stdout.strip().lower()
    return completed.returncode == 0 and value == "true", value or completed.stderr.strip()


def verify() -> dict[str, object]:
    checks: list[dict[str, str]] = []

    git_ok, git_detail = _git_worktree_check()
    checks.append(_check("formal_git_repository", git_ok, git_detail))

    for relative in REQUIRED_PATHS:
        path = REPO_ROOT / relative
        checks.append(_check(f"repo_file:{relative}", path.is_file(), relative))

    readme = REPO_ROOT / "README.md"
    checks.append(
        _check(
            "readme_nonempty",
            readme.is_file() and bool(readme.read_text(encoding="utf-8").strip()),
            "README.md contains repository entry documentation",
        )
    )

    editorconfig = REPO_ROOT / ".editorconfig"
    editor_text = editorconfig.read_text(encoding="utf-8") if editorconfig.is_file() else ""
    for token in EDITORCONFIG_REQUIRED:
        checks.append(
            _check(
                "editorconfig:" + token.replace(" ", "_").replace("=", "eq"),
                token in editor_text,
                token,
            )
        )

    attributes = REPO_ROOT / ".gitattributes"
    attributes_text = attributes.read_text(encoding="utf-8") if attributes.is_file() else ""
    checks.append(
        _check(
            "editorconfig_lf_checkout",
            ".editorconfig text eol=lf" in attributes_text,
            ".editorconfig text eol=lf",
        )
    )

    workflow = REPO_ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
    workflow_text = workflow.read_text(encoding="utf-8") if workflow.is_file() else ""
    for token in WORKFLOW_REQUIRED:
        checks.append(
            _check(
                "workflow:" + token.lower().replace(" ", "_").replace(":", ""),
                token in workflow_text,
                token,
            )
        )

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {
        "schema": "TPAA_M0_DEV_000_REPOSITORY_BOOTSTRAP_EVIDENCE_V1",
        "task_ids": ["M0-DEV-000"],
        "status": status,
        "checks": checks,
        "external_controls": {
            "github_main_branch_protection": (
                "NOT_EVALUATED_BY_REPOSITORY_VERIFIER; review GitHub branch metadata/"
                "protection evidence separately"
            ),
            "required_status_checks": (
                "NOT_EVALUATED_BY_REPOSITORY_VERIFIER; hosting enforcement is external"
            ),
        },
    }


def main() -> int:
    evidence = verify()
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if evidence["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
