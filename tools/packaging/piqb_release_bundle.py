#!/usr/bin/env python3
"""Build the PIQB-1.0 final-product release envelope for one governed profile."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import shutil
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.manifest.build_artifacts import git_revision, project_version, sha256_file  # noqa: E402
from tools.packaging.m5_runtime_bundle import (  # noqa: E402
    LINUX_PROFILES,
    WINDOWS_PROFILES,
    build_m5_runtime_bundle,
)

RELEASE_CONTRACT = REPO_ROOT / "docs" / "baseline" / "PIQB-1.0" / "B6_RELEASE_CONTRACT.json"
PIQB_RUNTIME_ENTRY = REPO_ROOT / "tools" / "packaging" / "piqb_runtime_entry.py"


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _extract(package: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    if package.suffix.lower() == ".zip":
        with zipfile.ZipFile(package) as archive:
            archive.extractall(target)
        return
    if package.name.endswith(".tar.gz"):
        with tarfile.open(package, mode="r:gz") as archive:
            archive.extractall(target, filter="data")
        return
    raise RuntimeError(f"unsupported base package: {package.name}")


def _archive_mode(relative: str) -> int:
    if relative in {"run.sh", "runtime/bin/python"}:
        return 0o755
    return 0o644


def _zip(stage: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in stage.rglob("*") if item.is_file()):
            relative = path.relative_to(stage).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100000 | _archive_mode(relative)) << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _tar_gz(stage: Path, output: Path) -> None:
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in sorted(item for item in stage.rglob("*") if item.is_file()):
                    relative = path.relative_to(stage).as_posix()
                    data = path.read_bytes()
                    info = tarfile.TarInfo(relative)
                    info.size = len(data)
                    info.mode = _archive_mode(relative)
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    archive.addfile(info, io.BytesIO(data))


def _install_piqb_runtime(stage: Path, profile: str) -> None:
    """Overlay the qualified M5 runtime substrate with the current PIQB product entry."""

    target_entry = stage / "app" / "tools" / "packaging" / PIQB_RUNTIME_ENTRY.name
    target_entry.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(PIQB_RUNTIME_ENTRY, target_entry)

    fixture_source = REPO_ROOT / "tests" / "fixtures" / "m1"
    if not fixture_source.is_dir():
        raise RuntimeError("M1 qualification fixture source missing")
    shutil.copytree(
        fixture_source,
        stage / "app" / "tests" / "fixtures" / "m1",
        dirs_exist_ok=True,
    )

    default_command = "desktop" if profile.endswith("_DESKTOP_X64") else "service"
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
            "\"%ROOT%app\\tools\\packaging\\piqb_runtime_entry.py\" "
            f"--profile {profile} %*\r\n"
            "exit /b %ERRORLEVEL%\r\n"
            ":default\r\n"
            "\"%ROOT%runtime\\python.exe\" "
            "\"%ROOT%app\\tools\\packaging\\piqb_runtime_entry.py\" "
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
            "\"$ROOT/app/tools/packaging/piqb_runtime_entry.py\" "
            f"--profile {profile} \"$@\"\n",
            encoding="utf-8",
            newline="\n",
        )
        launcher.chmod(0o755)


def _canonical_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _file_inventory(stage: Path) -> list[dict[str, object]]:
    ignored = {"piqb-release/release-manifest.json", "piqb-release/build-manifest.json"}
    return [
        {
            "path": path.relative_to(stage).as_posix(),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in sorted(item for item in stage.rglob("*") if item.is_file())
        if path.relative_to(stage).as_posix() not in ignored
    ]


def _spdx(stage: Path, *, profile: str, version: str, revision: str) -> dict[str, object]:
    dependency_manifest = _json(stage / "build-evidence" / "third-party-dependencies.json")
    raw_packages = dependency_manifest.get("packages")
    if not isinstance(raw_packages, list):
        raise RuntimeError("base dependency inventory missing")
    packages: list[dict[str, object]] = [
        {
            "SPDXID": "SPDXRef-Package-TPAA",
            "name": "tpaa",
            "versionInfo": version,
            "downloadLocation": "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": "NOASSERTION",
            "licenseDeclared": "NOASSERTION",
            "copyrightText": "NOASSERTION",
            "comment": "Project metadata declares a proprietary license.",
        }
    ]
    for index, row in enumerate(raw_packages, start=1):
        if not isinstance(row, dict):
            raise RuntimeError("base dependency inventory row invalid")
        name = row.get("name")
        package_version = row.get("version")
        if not isinstance(name, str) or not isinstance(package_version, str):
            raise RuntimeError("base dependency identity invalid")
        packages.append(
            {
                "SPDXID": f"SPDXRef-Package-{index:04d}",
                "name": name,
                "versionInfo": package_version,
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": "NOASSERTION",
                "licenseDeclared": "NOASSERTION",
                "copyrightText": "NOASSERTION",
            }
        )
    return {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": f"TPAA-{version}-{profile}",
        "documentNamespace": f"https://tpaa.invalid/spdx/{version}/{revision}/{profile}",
        "creationInfo": {
            "created": "1970-01-01T00:00:00Z",
            "creators": ["Tool: TPAA PIQB B6 deterministic packager"],
            "comment": "Timestamp is a deterministic archive metadata epoch, not release time.",
        },
        "packages": packages,
    }


def build_piqb_release_bundle(profile: str, output_dir: Path) -> tuple[Path, Path]:
    contract = _json(RELEASE_CONTRACT)
    profiles = contract.get("mandatory_profiles")
    if not isinstance(profiles, list) or profile not in profiles:
        raise ValueError(f"unsupported PIQB release profile: {profile}")
    version = project_version()
    if version != contract.get("product_version"):
        raise RuntimeError("project version does not match B6 release contract")
    if contract.get("db_schema_version") != "1.9.0":
        raise RuntimeError("B6 release contract DB schema drift")

    revision = git_revision()
    output_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="tpaa-piqb-base-") as base_raw:
        base_dir = Path(base_raw)
        base_package, _ = build_m5_runtime_bundle(profile, base_dir)
        with tempfile.TemporaryDirectory(prefix="tpaa-piqb-release-stage-") as stage_raw:
            stage = Path(stage_raw)
            _extract(base_package, stage)
            _install_piqb_runtime(stage, profile)

            m5_manifest_path = stage / "build-evidence" / "package-manifest.json"
            m5_manifest = _json(m5_manifest_path)
            if m5_manifest.get("source_revision") != revision or m5_manifest.get("profile_id") != profile:
                raise RuntimeError("retained M5 runtime substrate is not exact-head/profile")

            release_root = stage / "piqb-release"
            spdx = _spdx(stage, profile=profile, version=version, revision=revision)
            spdx_path = release_root / "sbom.spdx.json"
            _write_json(spdx_path, spdx)
            inventory = _file_inventory(stage)
            inventory_hash = _canonical_hash(inventory)

            base_build = _json(stage / "build-evidence" / "build-manifest.json")
            dependency_lock_hash = base_build.get("dependency_lock_sha256")
            if not isinstance(dependency_lock_hash, str):
                raise RuntimeError("dependency lock identity missing from retained substrate")

            common = {
                "product_name": "TPAA",
                "product_version": version,
                "source_revision": revision,
                "profile_id": profile,
                "db_schema_version": "1.9.0",
                "canonical_baseline": "CB-1.4.0",
                "dependency_lock_sha256": dependency_lock_hash,
                "sbom_sha256": sha256_file(spdx_path),
                "file_inventory_sha256": inventory_hash,
                "retained_m5_substrate_manifest_sha256": sha256_file(m5_manifest_path),
                "admitted_capabilities": ["P1", "P2", "P3", "P4", "P5", "P6"],
            }
            build_manifest = {
                "schema": "TPAA_PIQB_BUILD_MANIFEST_V1",
                "qualification": "PIQB_B6_CANDIDATE",
                "formal_release_claimed": False,
                **common,
                "runtime_substrate": "M5_OFFLINE_RUNTIME_BUNDLE",
                "historical_m5_qualification_semantics_rewritten": False,
                "m5_substrate_manifest_is_final_package_manifest": False,
            }
            _write_json(release_root / "build-manifest.json", build_manifest)
            release_manifest = {
                "schema": "TPAA_PIQB_RELEASE_MANIFEST_V1",
                "qualification": "PIQB_B6_CANDIDATE",
                "formal_release_claimed": False,
                **common,
                "release_contract_sha256": sha256_file(RELEASE_CONTRACT),
                "file_inventory": inventory,
            }
            _write_json(release_root / "release-manifest.json", release_manifest)

            semantic = f"{version}+piqb.{revision[:12]}"
            if profile in WINDOWS_PROFILES:
                package = output_dir / f"tpaa-{semantic}-{profile}.zip"
                _zip(stage, package)
            elif profile in LINUX_PROFILES:
                package = output_dir / f"tpaa-{semantic}-{profile}.tar.gz"
                _tar_gz(stage, package)
            else:
                raise ValueError(f"unsupported PIQB release profile: {profile}")

    summary = output_dir / f"{package.name}.summary.json"
    _write_json(
        summary,
        {
            "schema": "TPAA_PIQB_RELEASE_BUNDLE_SUMMARY_V1",
            "status": "PASS",
            "qualification": "PIQB_B6_CANDIDATE",
            "formal_release_claimed": False,
            "product_version": version,
            "source_revision": revision,
            "profile_id": profile,
            "db_schema_version": "1.9.0",
            "package": package.name,
            "package_sha256": sha256_file(package),
            "package_bytes": package.stat().st_size,
        },
    )
    return package, summary


def main() -> int:
    contract = _json(RELEASE_CONTRACT)
    profiles = contract.get("mandatory_profiles")
    if not isinstance(profiles, list) or not all(isinstance(item, str) for item in profiles):
        raise RuntimeError("B6 mandatory profile inventory invalid")
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(cast(list[str], profiles)))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package, summary = build_piqb_release_bundle(args.profile, args.output)
    print(
        json.dumps(
            {
                "schema": "TPAA_PIQB_RELEASE_BUILD_V1",
                "status": "PASS",
                "profile_id": args.profile,
                "product_version": project_version(),
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
