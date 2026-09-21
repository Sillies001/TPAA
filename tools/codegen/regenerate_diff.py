#!/usr/bin/env python3
"""CI-vendor-neutral regenerate-diff gate for governed generated source."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_canonical import CanonicalArtifactLoader  # noqa: E402
from tpaa_codegen import GenerationCoordinator, default_generators  # noqa: E402
from tpaa_codegen.governance import verify_generated_tree  # noqa: E402

GENERATED_PATHSPEC = "src/tpaa_generated"


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )


def main() -> int:
    if shutil.which("git") is None:
        print("REGENERATE_DIFF_FAIL reason=GIT_UNAVAILABLE", file=sys.stderr)
        return 2

    status = _git("status", "--porcelain", "--", GENERATED_PATHSPEC)
    if status.returncode != 0:
        print(
            "REGENERATE_DIFF_FAIL reason=GIT_UNAVAILABLE detail=" + (status.stderr.strip() or "git status failed"),
            file=sys.stderr,
        )
        return 2
    if status.stdout.strip():
        print(
            "REGENERATE_DIFF_FAIL reason=GENERATED_TREE_DIRTY detail=pre-existing-uncommitted-change",
            file=sys.stderr,
        )
        return 2

    loader = CanonicalArtifactLoader()
    coordinator = GenerationCoordinator(loader, default_generators())
    summary = coordinator.write(REPO_ROOT)

    try:
        verify_generated_tree(REPO_ROOT, summary.files)
    except Exception as exc:
        print(f"REGENERATE_DIFF_FAIL reason=GENERATED_TREE_VERIFY detail={exc}", file=sys.stderr)
        return 2

    diff = _git("diff", "--exit-code", "--", GENERATED_PATHSPEC)
    if diff.returncode != 0:
        detail = diff.stdout.strip() or diff.stderr.strip() or "generated diff is non-zero"
        print("REGENERATE_DIFF_FAIL reason=REGENERATE_DIFF_FAILED", file=sys.stderr)
        if detail:
            print(detail, file=sys.stderr)
        return 2

    print(f"REGENERATE_DIFF_PASS files={len(summary.files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
