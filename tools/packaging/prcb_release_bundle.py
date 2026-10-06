#!/usr/bin/env python3
"""Build deterministic PRCB C5 TPAA 1.0.1 production candidate packages."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.manifest.build_artifacts import git_revision, sha256_file  # noqa: E402
from tools.packaging.m5_runtime_bundle import (  # noqa: E402
    LINUX_PROFILES,
    WINDOWS_PROFILES,
    _copy_app,
    _copy_runtime,
    _tar_gz,
    _write_json,
    _zip,
)

CONTRACT = REPO_ROOT / "docs" / "baseline" / "PRCB-1.0" / "C5_RELEASE_CONTRACT.json"
RUNTIME_ENTRY = REPO_ROOT / "tools" / "packaging" / "prcb_runtime_entry.py"
QUALIFICATION_SOURCE = (
    REPO_ROOT
    / "docs"
    / "baseline"
    / "PRCB-1.0"
    / "qualification"
    / "PRCB_C2_NOMINAL_FLIGHT.json"
)
TARGET_VERSION = "1.0.1"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return cast(dict[str, Any], value)


def _rewrite_staged_version(stage: Path) -> None:
    pyproject = stage / "app" / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    old = 'version = "1.0.0"'
    if text.count(old) != 1:
        raise RuntimeError("staged project version identity is unexpected")
    pyproject.write_text(text.replace(old, f'version = "{TARGET_VERSION}"'), encoding="utf-8")


def _install_runtime_entry(stage: Path, profile: str) -> None:
    app_packaging = stage / "app" / "tools" / "packaging"
    app_packaging.mkdir(parents=True, exist_ok=True)
    (app_packaging / "m5_runtime_entry.py").unlink(missing_ok=True)
    shutil.copy2(RUNTIME_ENTRY, app_packaging / RUNTIME_ENTRY.name)
    qualification_root = stage / "app" / "qualification"
    qualification_root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        QUALIFICATION_SOURCE,
        qualification_root / QUALIFICATION_SOURCE.name,
    )
    default_command = "ready"
    if profile in WINDOWS_PROFILES:
        launcher = stage / "run.cmd"
        launcher.write_text(
            "@echo off\r\n"
            "setlocal\r\n"
            "set \"ROOT=%~dp0\"\r\n"
            "set \"PYTHONHOME=%ROOT%runtime\"\r\n"
            "set \"PYTHONPATH=%ROOT%app\\src\"\r\n"
            "if \"%~1\"==\"\" goto default\r\n"
            "\"%ROOT%runtime\\python.exe\" "
            "\"%ROOT%app\\tools\\packaging\\prcb_runtime_entry.py\" "
            f"--profile {profile} %*\r\n"
            "exit /b %ERRORLEVEL%\r\n"
            ":default\r\n"
            "\"%ROOT%runtime\\python.exe\" "
            "\"%ROOT%app\\tools\\packaging\\prcb_runtime_entry.py\" "
            f"--profile {profile} {default_command}\r\n"
            "exit /b %ERRORLEVEL%\r\n",
            encoding="utf-8",
            newline="",
        )
    else:
        launcher = stage / "run.sh"
        launcher.write_text(
            "#!/bin/sh\n"
            "SCRIPT=$0\n"
            "case \"$SCRIPT\" in /*) ;; *) SCRIPT=\"$PWD/$SCRIPT\" ;; esac\n"
            "ROOT=${SCRIPT%/*}\n"
            "export PYTHONHOME=\"$ROOT/runtime\"\n"
            "export PYTHONPATH=\"$ROOT/app/src\"\n"
            "export LD_LIBRARY_PATH=\"$ROOT/runtime/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\"\n"
            f"if [ \"$#\" -eq 0 ]; then set -- {default_command}; fi\n"
            "exec \"$ROOT/runtime/bin/python\" "
            "\"$ROOT/app/tools/packaging/prcb_runtime_entry.py\" "
            f"--profile {profile} \"$@\"\n",
            encoding="utf-8",
            newline="\n",
        )
        launcher.chmod(0o755)


def _inventory(stage: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted(item for item in stage.rglob("*") if item.is_file()):
        relative = path.relative_to(stage).as_posix()
        if relative.startswith("app/tests/") or "/fixtures/" in f"/{relative}/":
            raise RuntimeError(f"production package contains forbidden test material: {relative}")
        rows.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return rows


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def build_prcb_release_bundle(profile: str, output_dir: Path) -> tuple[Path, Path]:
    contract = _json(CONTRACT)
    profiles = contract.get("mandatory_profiles")
    if not isinstance(profiles, list) or profile not in profiles:
        raise ValueError(f"unsupported PRCB release profile: {profile}")
    if contract.get("target_product_version") != TARGET_VERSION:
        raise RuntimeError("PRCB C5 target version drift")

    output_dir.mkdir(parents=True, exist_ok=True)
    revision = git_revision()
    with tempfile.TemporaryDirectory(prefix="tpaa-prcb-c5-stage-") as raw:
        stage = Path(raw)
        _copy_runtime(stage)
        _copy_app(stage)
        _rewrite_staged_version(stage)
        _install_runtime_entry(stage, profile)
        inventory = _inventory(stage)
        release_root = stage / "prcb-release"
        build_manifest = {
            "schema": "TPAA_PRCB_C5_BUILD_MANIFEST_V1",
            "qualification": "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED",
            "formal_release_claimed": False,
            "product_version": TARGET_VERSION,
            "source_revision": revision,
            "profile_id": profile,
            "canonical_baseline": "CB-1.4.0",
            "db_schema_version": "1.9.0",
            "tests_packaged": False,
            "fixtures_packaged": False,
            "runtime_entry": "tools/packaging/prcb_runtime_entry.py",
            "production_qualification_source": (
                "qualification/PRCB_C2_NOMINAL_FLIGHT.json"
            ),
            "file_inventory_sha256": _canonical_hash(inventory),
        }
        _write_json(release_root / "build-manifest.json", build_manifest)
        release_manifest = {
            **build_manifest,
            "schema": "TPAA_PRCB_C5_RELEASE_MANIFEST_V1",
            "file_inventory": inventory,
            "release_contract_sha256": sha256_file(CONTRACT),
        }
        _write_json(release_root / "release-manifest.json", release_manifest)

        semantic = f"{TARGET_VERSION}+prcb.{revision[:12]}"
        if profile in WINDOWS_PROFILES:
            package = output_dir / f"tpaa-{semantic}-{profile}.zip"
            _zip(stage, package)
        elif profile in LINUX_PROFILES:
            package = output_dir / f"tpaa-{semantic}-{profile}.tar.gz"
            _tar_gz(stage, package)
        else:
            raise ValueError(f"unsupported PRCB release profile: {profile}")

    summary = output_dir / f"{package.name}.summary.json"
    _write_json(
        summary,
        {
            "schema": "TPAA_PRCB_C5_RELEASE_BUNDLE_SUMMARY_V1",
            "status": "PASS",
            "qualification": "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED",
            "formal_release_claimed": False,
            "product_version": TARGET_VERSION,
            "source_revision": revision,
            "profile_id": profile,
            "package": package.name,
            "package_sha256": sha256_file(package),
            "package_bytes": package.stat().st_size,
        },
    )
    return package, summary


def main() -> int:
    contract = _json(CONTRACT)
    profiles = contract.get("mandatory_profiles")
    if not isinstance(profiles, list) or not all(isinstance(item, str) for item in profiles):
        raise RuntimeError("PRCB C5 mandatory profile inventory invalid")
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(cast(list[str], profiles)))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package, summary = build_prcb_release_bundle(args.profile, args.output)
    print(
        json.dumps(
            {
                "schema": "TPAA_PRCB_C5_RELEASE_BUILD_V1",
                "status": "PASS",
                "profile_id": args.profile,
                "product_version": TARGET_VERSION,
                "package": str(package),
                "package_sha256": sha256_file(package),
                "summary": str(summary),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
