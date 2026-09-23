#!/usr/bin/env python3
"""Build, clean-extract, install, start and stop M0 Desktop/Service development bundles."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.packaging.development_package import build_package  # noqa: E402


def _profiles() -> tuple[str, str]:
    if os.name == "nt":
        return ("WINDOWS_DESKTOP_X64", "WINDOWS_SERVICE_X64")
    if sys.platform.startswith("linux"):
        return ("LINUX_DESKTOP_X64", "LINUX_SERVICE_X64")
    raise RuntimeError(f"unsupported packaging smoke platform: {sys.platform}")


def _extract(package: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    if package.suffix == ".zip":
        with zipfile.ZipFile(package) as archive:
            archive.extractall(destination)
    else:
        with tarfile.open(package, mode="r:gz") as archive:
            archive.extractall(destination, filter="data")


def _run(args: list[str], cwd: Path, *, timeout: int = 240) -> None:
    completed = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"package smoke command failed rc={completed.returncode}: {args}")


def run() -> dict[str, object]:
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv is required for package smoke")
    results: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="tpaa-package-smoke-") as raw:
        root = Path(raw)
        for profile in _profiles():
            out = root / "out"
            package, _ = build_package(profile, out)
            install = root / f"install-{profile}"
            _extract(package, install)
            _run([uv, "sync", "--locked"], install)
            python = [uv, "run", "--frozen", "python", "tools/dev/tpaa_dev.py"]
            _run([*python, "verify-baseline"], install)
            _run([*python, "verify-generated"], install)
            _run([*python, "platform-smoke"], install)
            if "DESKTOP" in profile:
                _run([*python, "gui-smoke", "--headless"], install)
                _run([*python, "desktop-backend-smoke"], install)
            else:
                _run([*python, "api-smoke"], install)
            results[profile] = {
                "package": package.name,
                "clean_install": "PASS",
                "start_stop": "PASS",
            }
    return {
        "schema": "TPAA_M0_PACKAGE_SMOKE_V1",
        "status": "PASS",
        "profiles": results,
    }


def main() -> int:
    try:
        result = run()
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema": "TPAA_M0_PACKAGE_SMOKE_V1",
                    "status": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
