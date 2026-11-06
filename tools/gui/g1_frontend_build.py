#!/usr/bin/env python3
"""Verify the v33 Vite production build is offline and byte-deterministic."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend" / "gui-v33"
DIST = REPO_ROOT / "src" / "tpaa_gui" / "web_dist"
EVIDENCE = REPO_ROOT / "evidence" / "gui-g1-v33-frontend-build.json"
REMOTE_PATTERN = re.compile(rb"(?:https?:)?//(?!127\.0\.0\.1|localhost)", re.IGNORECASE)


class FrontendBuildError(RuntimeError):
    """The static product shell build gate failed."""


def _npm() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _run_build(output: Path) -> None:
    command = [_npm(), "run", "build", "--", "--outDir", str(output), "--emptyOutDir"]
    completed = subprocess.run(
        command,
        cwd=FRONTEND,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )
    if completed.returncode != 0:
        raise FrontendBuildError(completed.stdout + completed.stderr)


def _inventory(root: Path) -> list[dict[str, Any]]:
    items = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        if path.suffix.lower() in {".html", ".js", ".css", ".json"} and REMOTE_PATTERN.search(raw):
            raise FrontendBuildError(f"remote resource reference: {path}")
        items.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw),
            }
        )
    if not any(item["path"] == "index.html" for item in items):
        raise FrontendBuildError("index.html missing")
    if not any(
        re.fullmatch(r"assets/.+-[A-Za-z0-9_-]+\.js", str(item["path"]))
        for item in items
    ):
        raise FrontendBuildError("hashed JavaScript asset missing")
    return items


def verify() -> dict[str, Any]:
    if not (FRONTEND / "package-lock.json").is_file():
        raise FrontendBuildError("package-lock.json missing")
    with tempfile.TemporaryDirectory(prefix="tpaa-v33-vite-") as temporary:
        first = Path(temporary) / "first"
        second = Path(temporary) / "second"
        _run_build(first)
        _run_build(second)
        first_inventory = _inventory(first)
        second_inventory = _inventory(second)
        current_inventory = _inventory(DIST)
        if first_inventory != second_inventory:
            raise FrontendBuildError("two clean Vite builds differ")
        if current_inventory != first_inventory:
            raise FrontendBuildError("checked-in web_dist differs from clean build")
    return {
        "schema": "TPAA_G1_V33_FRONTEND_BUILD_EVIDENCE_V1",
        "status": "PASS",
        "package_lock_sha256": hashlib.sha256((FRONTEND / "package-lock.json").read_bytes()).hexdigest(),
        "files": current_inventory,
        "remote_resources": 0,
        "release_claim": False,
    }


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=EVIDENCE)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = verify()
    except (OSError, subprocess.SubprocessError, FrontendBuildError) as exc:
        print(f"G1_FRONTEND_BUILD_FAIL {exc}")
        return 2
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"G1_FRONTEND_BUILD_PASS files={len(result['files'])} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
