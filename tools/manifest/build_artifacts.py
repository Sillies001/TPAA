#!/usr/bin/env python3
"""M0 build-manifest, CycloneDX SBOM, license and native-dependency evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_LOCK = REPO_ROOT / "baseline" / "CB-1.4.0" / "BASELINE_LOCK.json"
UV_LOCK = REPO_ROOT / "uv.lock"
PYPROJECT = REPO_ROOT / "pyproject.toml"

VALID_PROFILES = {
    "WINDOWS_DESKTOP_X64",
    "WINDOWS_SERVICE_X64",
    "LINUX_DESKTOP_X64",
    "LINUX_SERVICE_X64",
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    value = completed.stdout.strip()
    if completed.returncode != 0 or len(value) != 40:
        raise RuntimeError("source revision unavailable")
    return value


def project_version() -> str:
    raw = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    project = raw.get("project")
    if not isinstance(project, dict):
        raise RuntimeError("project metadata unavailable")
    version = project.get("version")
    if not isinstance(version, str):
        raise RuntimeError("project version unavailable")
    return version


def _locked_packages() -> list[dict[str, object]]:
    raw = tomllib.loads(UV_LOCK.read_text(encoding="utf-8"))
    packages = raw.get("package")
    if not isinstance(packages, list):
        raise RuntimeError("uv.lock package array unavailable")
    result: list[dict[str, object]] = []
    for item in packages:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        version = item.get("version")
        source = item.get("source")
        if (
            isinstance(name, str)
            and isinstance(version, str)
            and name != "tpaa"
            and isinstance(source, dict)
            and "registry" in source
        ):
            result.append(item)
    return sorted(result, key=lambda item: str(item["name"]))


def _license_for(name: str) -> str:
    try:
        metadata = importlib.metadata.metadata(name)
    except importlib.metadata.PackageNotFoundError:
        return "UNKNOWN_REQUIRES_REVIEW"
    value = metadata.get("License-Expression") or metadata.get("License")
    if value is None or not value.strip() or value.strip().upper() == "UNKNOWN":
        return "UNKNOWN_REQUIRES_REVIEW"
    return value.strip()


def _component(item: dict[str, object]) -> dict[str, object]:
    name = str(item["name"])
    version = str(item["version"])
    hashes: list[dict[str, str]] = []
    sdist = item.get("sdist")
    if isinstance(sdist, dict):
        digest = sdist.get("hash")
        if isinstance(digest, str) and digest.startswith("sha256:"):
            hashes.append({"alg": "SHA-256", "content": digest.removeprefix("sha256:")})
    result: dict[str, object] = {
        "type": "library",
        "name": name,
        "version": version,
        "purl": f"pkg:pypi/{name}@{version}",
    }
    if hashes:
        result["hashes"] = hashes
    return result


def build_evidence(profile: str) -> dict[str, dict[str, object]]:
    if profile not in VALID_PROFILES:
        raise ValueError(f"unsupported platform profile: {profile}")
    lock = json.loads(BASELINE_LOCK.read_text(encoding="utf-8"))
    baseline = lock.get("baseline")
    artifacts = lock.get("artifacts")
    if not isinstance(baseline, dict) or not isinstance(artifacts, list):
        raise RuntimeError("baseline lock shape invalid")
    canonical_hashes = {
        str(item["file"]): str(item["sha256"])
        for item in artifacts
        if isinstance(item, dict)
        and isinstance(item.get("file"), str)
        and isinstance(item.get("sha256"), str)
    }
    packages = _locked_packages()
    revision = git_revision()
    version = project_version()
    lock_hash = sha256_file(UV_LOCK)
    baseline_hash = sha256_file(BASELINE_LOCK)

    build_manifest: dict[str, object] = {
        "schema": "TPAA_M0_BUILD_MANIFEST_V1",
        "qualification": "DEVELOPMENT_NOT_M5_QUALIFIED",
        "product_version": version,
        "source_revision": revision,
        "platform_profile": profile,
        "core_baseline": baseline.get("core"),
        "db_schema_version": baseline.get("db_schema"),
        "baseline_lock_sha256": baseline_hash,
        "dependency_lock_sha256": lock_hash,
        "canonical_artifact_hashes": canonical_hashes,
        "python": {
            "implementation": platform.python_implementation(),
            "version": platform.python_version(),
            "machine": platform.machine(),
            "system": platform.system(),
        },
    }

    sbom: dict[str, object] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": "tpaa",
                "version": version,
            },
            "properties": [
                {"name": "tpaa:source_revision", "value": revision},
                {"name": "tpaa:platform_profile", "value": profile},
                {"name": "tpaa:dependency_lock_sha256", "value": lock_hash},
            ],
        },
        "components": [_component(item) for item in packages],
    }

    license_report: dict[str, object] = {
        "schema": "TPAA_M0_LICENSE_REPORT_V1",
        "qualification": "ENGINEERING_INVENTORY_NOT_LEGAL_APPROVAL",
        "source_revision": revision,
        "platform_profile": profile,
        "dependency_lock_sha256": lock_hash,
        "packages": [
            {
                "name": str(item["name"]),
                "version": str(item["version"]),
                "declared_license": _license_for(str(item["name"])),
            }
            for item in packages
        ],
    }

    native_names = {
        "pyside6",
        "pyside6-addons",
        "pyside6-essentials",
        "shiboken6",
        "psycopg-binary",
    }
    native_dependencies: dict[str, object] = {
        "schema": "TPAA_M0_NATIVE_DEPENDENCIES_V1",
        "source_revision": revision,
        "platform_profile": profile,
        "dependencies": [
            {
                "name": str(item["name"]),
                "version": str(item["version"]),
                "kind": "PYTHON_NATIVE_OR_RUNTIME",
            }
            for item in packages
            if str(item["name"]).lower() in native_names
        ],
    }

    third_party_manifest: dict[str, object] = {
        "schema": "TPAA_M0_THIRD_PARTY_DEPENDENCIES_V1",
        "source_revision": revision,
        "platform_profile": profile,
        "dependency_lock_sha256": lock_hash,
        "packages": [
            {"name": str(item["name"]), "version": str(item["version"])}
            for item in packages
        ],
    }
    return {
        "build-manifest.json": build_manifest,
        "sbom.cdx.json": sbom,
        "license-report.json": license_report,
        "native-dependencies.json": native_dependencies,
        "third-party-dependencies.json": third_party_manifest,
    }


def write_evidence(profile: str, output: Path) -> dict[str, str]:
    output.mkdir(parents=True, exist_ok=True)
    written: dict[str, str] = {}
    for name, payload in build_evidence(profile).items():
        path = output / name
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        written[name] = sha256_file(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(VALID_PROFILES))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    written = write_evidence(args.profile, args.output)
    print(
        json.dumps(
            {
                "schema": "TPAA_M0_MANIFEST_GENERATION_V1",
                "status": "PASS",
                "profile": args.profile,
                "files": written,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
