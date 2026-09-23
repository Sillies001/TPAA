#!/usr/bin/env python3
"""Build deterministic M0 development bundles frozen by ADR-M0-006."""

from __future__ import annotations

import argparse
import gzip
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.manifest.build_artifacts import (  # noqa: E402
    VALID_PROFILES,
    git_revision,
    project_version,
    sha256_file,
    write_evidence,
)

WINDOWS_PROFILES = {"WINDOWS_DESKTOP_X64", "WINDOWS_SERVICE_X64"}
LINUX_PROFILES = {"LINUX_DESKTOP_X64", "LINUX_SERVICE_X64"}


def _require_clean_tracked_tree() -> None:
    for args in (["git", "diff", "--quiet"], ["git", "diff", "--cached", "--quiet"]):
        completed = subprocess.run(args, cwd=REPO_ROOT, check=False)
        if completed.returncode != 0:
            raise RuntimeError("development package requires a clean tracked worktree")


def _tracked_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return sorted(
        part.decode("utf-8")
        for part in completed.stdout.split(b"\0")
        if part
    )


def _stage_source(stage: Path) -> None:
    for relative in _tracked_files():
        source = REPO_ROOT / relative
        if not source.is_file():
            continue
        target = stage / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _package_manifest(stage: Path, profile: str) -> None:
    files = []
    for path in sorted(p for p in stage.rglob("*") if p.is_file()):
        relative = path.relative_to(stage).as_posix()
        if relative == "build-evidence/package-manifest.json":
            continue
        files.append(
            {
                "path": relative,
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    payload = {
        "schema": "TPAA_M0_PACKAGE_MANIFEST_V1",
        "qualification": "DEVELOPMENT_NOT_M5_QUALIFIED",
        "source_revision": git_revision(),
        "product_version": project_version(),
        "platform_profile": profile,
        "files": files,
    }
    target = stage / "build-evidence" / "package-manifest.json"
    target.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _zip(stage: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in stage.rglob("*") if p.is_file()):
            relative = path.relative_to(stage).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _tar_gz(stage: Path, output: Path) -> None:
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in sorted(p for p in stage.rglob("*") if p.is_file()):
                    relative = path.relative_to(stage).as_posix()
                    info = tarfile.TarInfo(relative)
                    data = path.read_bytes()
                    info.size = len(data)
                    info.mode = 0o644
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    archive.addfile(info, fileobj=__import__("io").BytesIO(data))


def build_package(profile: str, output_dir: Path) -> tuple[Path, Path]:
    if profile not in VALID_PROFILES:
        raise ValueError(f"unsupported profile: {profile}")
    _require_clean_tracked_tree()
    output_dir.mkdir(parents=True, exist_ok=True)
    version = project_version()
    extension = ".zip" if profile in WINDOWS_PROFILES else ".tar.gz"
    package = output_dir / f"tpaa-{version}-{profile}{extension}"

    with tempfile.TemporaryDirectory(prefix="tpaa-package-stage-") as raw:
        stage = Path(raw)
        _stage_source(stage)
        write_evidence(profile, stage / "build-evidence")
        _package_manifest(stage, profile)
        if profile in WINDOWS_PROFILES:
            _zip(stage, package)
        else:
            _tar_gz(stage, package)

    summary = output_dir / f"{package.name}.summary.json"
    summary_payload = {
        "schema": "TPAA_M0_PACKAGE_ARTIFACT_SUMMARY_V1",
        "qualification": "DEVELOPMENT_NOT_M5_QUALIFIED",
        "source_revision": git_revision(),
        "platform_profile": profile,
        "package": package.name,
        "package_sha256": sha256_file(package),
        "package_bytes": package.stat().st_size,
    }
    summary.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return package, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(VALID_PROFILES))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package, summary = build_package(args.profile, args.output)
    print(
        json.dumps(
            {
                "schema": "TPAA_M0_PACKAGE_BUILD_V1",
                "status": "PASS",
                "profile": args.profile,
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
