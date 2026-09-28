#!/usr/bin/env python3
"""Build deterministic M5 offline runtime bundles for one mandatory profile."""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import sysconfig
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
    build_evidence,
    git_revision,
    project_version,
    sha256_file,
)
from tpaa_qualification import load_m5_qualification_authority  # noqa: E402

BASELINE = REPO_ROOT / "baseline" / "CB-1.4.0"
RUNTIME_ENTRY = REPO_ROOT / "tools" / "packaging" / "m5_runtime_entry.py"
WINDOWS_PROFILES = {"WINDOWS_DESKTOP_X64", "WINDOWS_SERVICE_X64"}
LINUX_PROFILES = {"LINUX_DESKTOP_X64", "LINUX_SERVICE_X64"}


def semantic_build_version() -> str:
    return f"{project_version()}+m5.{git_revision()[:12]}"


def _clean_tree_ignore(
    directory: str,
    names: list[str],
    *,
    skip_site_packages: bool,
) -> set[str]:
    ignored = {
        name
        for name in names
        if name == "__pycache__"
        or name.endswith((".pyc", ".pyo", ".pth", ".egg-link"))
    }
    if skip_site_packages and Path(directory).name.startswith("python"):
        ignored.add("site-packages")
    return ignored


def _copy_tree(source: Path, target: Path, *, skip_site_packages: bool = False) -> None:
    if not source.is_dir():
        raise RuntimeError(f"runtime directory missing: {source}")
    shutil.copytree(
        source,
        target,
        dirs_exist_ok=True,
        symlinks=False,
        ignore=lambda directory, names: _clean_tree_ignore(
            directory,
            names,
            skip_site_packages=skip_site_packages,
        ),
    )


def _copy_runtime(stage: Path) -> Path:
    runtime = stage / "runtime"
    base = Path(sys.base_prefix).resolve()
    version_dir = f"python{sys.version_info.major}.{sys.version_info.minor}"

    if os.name == "nt":
        runtime.mkdir(parents=True, exist_ok=True)
        for path in sorted(base.iterdir()):
            if not path.is_file():
                continue
            lowered = path.name.lower()
            if (
                lowered.startswith("python")
                or lowered.startswith("vcruntime")
                or lowered.endswith(".dll")
            ):
                shutil.copy2(path, runtime / path.name)
        _copy_tree(base / "DLLs", runtime / "DLLs")
        _copy_tree(base / "Lib", runtime / "Lib", skip_site_packages=True)
        interpreter = runtime / "python.exe"
        site_target = runtime / "Lib" / "site-packages"
    elif sys.platform.startswith("linux"):
        (runtime / "bin").mkdir(parents=True, exist_ok=True)
        (runtime / "lib").mkdir(parents=True, exist_ok=True)
        interpreter = runtime / "bin" / "python"
        shutil.copy2(Path(sys.executable).resolve(), interpreter)
        interpreter.chmod(interpreter.stat().st_mode | stat.S_IXUSR)

        lib_root = base / "lib"
        for path in sorted(lib_root.glob("libpython*.so*")):
            if path.is_file():
                shutil.copy2(path.resolve(), runtime / "lib" / path.name)
        stdlib = Path(sysconfig.get_path("stdlib")).resolve()
        _copy_tree(
            stdlib,
            runtime / "lib" / version_dir,
            skip_site_packages=True,
        )
        site_target = runtime / "lib" / version_dir / "site-packages"
    else:
        raise RuntimeError(f"M5 offline runtime unsupported on {sys.platform}")

    purelib = Path(sysconfig.get_path("purelib")).resolve()
    _copy_tree(purelib, site_target)
    platlib = Path(sysconfig.get_path("platlib")).resolve()
    if platlib != purelib:
        _copy_tree(platlib, site_target)
    if not interpreter.is_file():
        raise RuntimeError(f"embedded interpreter missing: {interpreter}")
    return interpreter


def _tracked_app_files() -> tuple[str, ...]:
    completed = subprocess.run(
        ["git", "ls-files", "-z", "src", "baseline", "uv.lock", "pyproject.toml"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    return tuple(
        sorted(
            part.decode("utf-8")
            for part in completed.stdout.split(b"\0")
            if part
        )
    )


def _copy_app(stage: Path) -> None:
    app = stage / "app"
    for relative in _tracked_app_files():
        source = REPO_ROOT / relative
        if not source.is_file():
            continue
        target = app / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

    target_entry = app / "tools" / "packaging" / RUNTIME_ENTRY.name
    target_entry.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RUNTIME_ENTRY, target_entry)


def _launcher(stage: Path, profile: str) -> None:
    if profile in WINDOWS_PROFILES:
        launcher = stage / "run.cmd"
        launcher.write_text(
            "@echo off\r\n"
            "setlocal\r\n"
            "set \"ROOT=%~dp0\"\r\n"
            "set \"PYTHONHOME=%ROOT%runtime\"\r\n"
            "set \"PYTHONPATH=%ROOT%app\\src\"\r\n"
            "\"%ROOT%runtime\\python.exe\" "
            "\"%ROOT%app\\tools\\packaging\\m5_runtime_entry.py\" "
            f"--profile {profile} %*\r\n",
            encoding="utf-8",
            newline="",
        )
    else:
        launcher = stage / "run.sh"
        launcher.write_text(
            "#!/bin/sh\n"
            "SCRIPT=$0\n"
            "case \"$SCRIPT\" in /*) ;; *) SCRIPT=\"$PWD/$SCRIPT\" ;; esac\n"
            "ROOT=$" "{SCRIPT%/*}\n"
            "export PYTHONHOME=\"$ROOT/runtime\"\n"
            "export PYTHONPATH=\"$ROOT/app/src\"\n"
            "export LD_LIBRARY_PATH=\"$ROOT/runtime/lib$" "{LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}\"\n"
            "exec \"$ROOT/runtime/bin/python\" "
            "\"$ROOT/app/tools/packaging/m5_runtime_entry.py\" "
            f"--profile {profile} \"$@\"\n",
            encoding="utf-8",
            newline="\n",
        )
        launcher.chmod(0o755)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _write_build_evidence(stage: Path, profile: str, package_form: str) -> None:
    authority = load_m5_qualification_authority(BASELINE)
    evidence = build_evidence(profile)
    semantic = semantic_build_version()
    for payload in evidence.values():
        payload["qualification"] = "M5_CANDIDATE_NOT_FORMALLY_QUALIFIED"
        payload["semantic_build_version"] = semantic
        payload["m5_authority_sha256"] = authority.authority_sha256
    build = evidence["build-manifest.json"]
    build["schema"] = "TPAA_M5_BUILD_MANIFEST_V1"
    build["package_form"] = package_form
    build["formal_release_claimed"] = False

    root = stage / "build-evidence"
    for name, payload in evidence.items():
        _write_json(root / name, payload)


def _file_inventory(stage: Path) -> list[dict[str, object]]:
    files: list[dict[str, object]] = []
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
    return files


def _write_package_manifest(stage: Path, profile: str, package_form: str) -> Path:
    authority = load_m5_qualification_authority(BASELINE)
    build = json.loads(
        (stage / "build-evidence" / "build-manifest.json").read_text(encoding="utf-8")
    )
    payload = {
        "schema": "TPAA_M5_PACKAGE_MANIFEST_V1",
        "qualification": "M5_CANDIDATE_NOT_FORMALLY_QUALIFIED",
        "formal_release_claimed": False,
        "source_revision": git_revision(),
        "semantic_build_version": semantic_build_version(),
        "profile_id": profile,
        "package_form": package_form,
        "m5_authority_sha256": authority.authority_sha256,
        "baseline_lock_sha256": build["baseline_lock_sha256"],
        "dependency_lock_sha256": build["dependency_lock_sha256"],
        "files": _file_inventory(stage),
    }
    target = stage / "build-evidence" / "package-manifest.json"
    _write_json(target, payload)
    return target


def _archive_mode(relative: str) -> int:
    if relative == "run.sh" or relative == "runtime/bin/python":
        return 0o755
    return 0o644


def _zip(stage: Path, output: Path) -> None:
    with zipfile.ZipFile(
        output,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(p for p in stage.rglob("*") if p.is_file()):
            relative = path.relative_to(stage).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (0o100000 | _archive_mode(relative)) << 16
            archive.writestr(
                info,
                path.read_bytes(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


def _tar_gz(stage: Path, output: Path) -> None:
    with output.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as archive:
                for path in sorted(p for p in stage.rglob("*") if p.is_file()):
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


def build_m5_runtime_bundle(
    profile: str,
    output_dir: Path,
) -> tuple[Path, Path]:
    authority = load_m5_qualification_authority(BASELINE)
    authority.certification_profile(profile)
    package_forms = authority.package_lifecycle_profile["package_forms"]
    package_form = str(package_forms[profile])

    if profile in WINDOWS_PROFILES:
        extension = ".zip"
    elif profile in LINUX_PROFILES:
        extension = ".tar.gz"
    else:
        raise ValueError(f"unsupported M5 package profile: {profile}")

    output_dir.mkdir(parents=True, exist_ok=True)
    semantic = semantic_build_version()
    package = output_dir / f"tpaa-{semantic}-{profile}{extension}"

    with tempfile.TemporaryDirectory(prefix="tpaa-m5-runtime-stage-") as raw:
        stage = Path(raw)
        _copy_runtime(stage)
        _copy_app(stage)
        _launcher(stage, profile)
        _write_build_evidence(stage, profile, package_form)
        manifest = _write_package_manifest(stage, profile, package_form)
        if profile in WINDOWS_PROFILES:
            _zip(stage, package)
        else:
            _tar_gz(stage, package)
        manifest_hash = sha256_file(manifest)

    summary = output_dir / f"{package.name}.summary.json"
    _write_json(
        summary,
        {
            "schema": "TPAA_M5_OFFLINE_RUNTIME_BUNDLE_SUMMARY_V1",
            "qualification": "M5_CANDIDATE_NOT_FORMALLY_QUALIFIED",
            "formal_release_claimed": False,
            "source_revision": git_revision(),
            "semantic_build_version": semantic,
            "profile_id": profile,
            "package_form": package_form,
            "package": package.name,
            "package_sha256": sha256_file(package),
            "package_bytes": package.stat().st_size,
            "package_manifest_sha256": manifest_hash,
            "target_prerequisites": dict(
                authority.package_lifecycle_profile["target_prerequisites"]
            ),
        },
    )
    return package, summary


def main() -> int:
    authority = load_m5_qualification_authority(BASELINE)
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        required=True,
        choices=sorted(authority.mandatory_profile_ids),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    package, summary = build_m5_runtime_bundle(args.profile, args.output)
    print(
        json.dumps(
            {
                "schema": "TPAA_M5_OFFLINE_RUNTIME_BUILD_V1",
                "status": "PASS",
                "profile_id": args.profile,
                "semantic_build_version": semantic_build_version(),
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
