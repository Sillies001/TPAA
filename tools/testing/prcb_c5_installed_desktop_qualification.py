#!/usr/bin/env python3
"""PRCB C5 true installed Desktop candidate qualification for one OS profile."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any, cast

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.manifest.build_artifacts import git_revision, sha256_file  # noqa: E402
from tools.packaging.prcb_release_bundle import (  # noqa: E402
    build_prcb_release_bundle,
)

PROFILE_BY_PLATFORM = {
    "linux": "LINUX_DESKTOP_X64",
    "windows": "WINDOWS_DESKTOP_X64",
}


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
    raise RuntimeError(f"unsupported PRCB package form: {package.name}")


def _installed_command(stage: Path, platform_name: str, work_root: Path) -> list[str]:
    args = ["desktop-p1-e2e", "--work-root", str(work_root)]
    if platform_name == "windows":
        return [
            "cmd.exe",
            "/d",
            "/s",
            "/c",
            str(stage / "run.cmd"),
            *args,
        ]
    return [str(stage / "run.sh"), *args]


def _json_stdout(value: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(value):
        if char != "{":
            continue
        try:
            parsed, end = decoder.raw_decode(value[index:])
        except json.JSONDecodeError:
            continue
        if value[index + end :].strip():
            continue
        if isinstance(parsed, dict):
            return cast(dict[str, Any], parsed)
    raise RuntimeError("installed runtime did not emit one terminal JSON object")


def _forbidden_runtime_material(stage: Path) -> tuple[str, ...]:
    forbidden: list[str] = []
    for path in sorted(item for item in stage.rglob("*") if item.is_file()):
        relative = path.relative_to(stage).as_posix()
        if relative.startswith("app/tests/") or "/fixtures/" in f"/{relative}/":
            forbidden.append(relative)
    return tuple(forbidden)


def _logical_product(report: dict[str, Any]) -> tuple[dict[str, object], str]:
    product = {
        "schema": "TPAA_PRCB_C5_DESKTOP_P1_P2_LOGICAL_PRODUCT_V1",
        "product_version": report.get("product_version"),
        "db_schema_version": report.get("db_schema_version"),
        "canonical_baseline": report.get("canonical_baseline"),
        "release_id": report.get("release_id"),
        "metric_count": report.get("metric_count"),
        "job_status": report.get("job_status"),
        "p2_job_status": report.get("p2_job_status"),
        "p2_release_id": report.get("p2_release_id"),
        "p2_estimate_id": report.get("p2_estimate_id"),
        "p2_estimate_status": report.get("p2_estimate_status"),
        "restart_exact_replay": report.get("restart_exact_replay"),
        "backup_restore_exact_replay": report.get("backup_restore_exact_replay"),
        "persistent_audit_verified": report.get("persistent_audit_verified"),
        "production_source": report.get("production_source"),
    }
    encoded = json.dumps(
        product,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return product, hashlib.sha256(encoded).hexdigest()


def qualify(
    *,
    platform_name: str,
    expected_revision: str,
    package_output: Path,
    evidence: Path,
) -> dict[str, object]:
    revision = git_revision()
    if revision != expected_revision:
        raise RuntimeError(
            f"exact-head mismatch expected={expected_revision} observed={revision}"
        )
    profile = PROFILE_BY_PLATFORM[platform_name]
    package, summary_path = build_prcb_release_bundle(profile, package_output)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (
        not isinstance(summary, dict)
        or summary.get("status") != "PASS"
        or summary.get("product_version") != "1.0.1"
        or summary.get("source_revision") != revision
        or summary.get("profile_id") != profile
    ):
        raise RuntimeError("PRCB C5 package summary identity mismatch")

    with tempfile.TemporaryDirectory(prefix="tpaa-prcb-c5-installed-") as raw:
        stage = Path(raw) / "installed"
        _extract(package, stage)
        forbidden = _forbidden_runtime_material(stage)
        if forbidden:
            raise RuntimeError(
                "installed candidate contains forbidden test material: "
                + ",".join(forbidden)
            )
        release_manifest_path = stage / "prcb-release" / "release-manifest.json"
        release_manifest = json.loads(
            release_manifest_path.read_text(encoding="utf-8")
        )
        if (
            not isinstance(release_manifest, dict)
            or release_manifest.get("product_version") != "1.0.1"
            or release_manifest.get("source_revision") != revision
            or release_manifest.get("profile_id") != profile
            or release_manifest.get("tests_packaged") is not False
            or release_manifest.get("fixtures_packaged") is not False
            or release_manifest.get("formal_release_claimed") is not False
        ):
            raise RuntimeError("installed PRCB release manifest mismatch")

        work_root = Path(raw) / "work"
        completed = subprocess.run(
            _installed_command(stage, platform_name, work_root),
            cwd=stage,
            check=False,
            capture_output=True,
            text=True,
            env=dict(os.environ),
        )
        if completed.returncode != 0:
            raise RuntimeError(
                "installed Desktop P1 E2E failed "
                f"rc={completed.returncode} stderr={completed.stderr[-2000:]}"
            )
        installed = _json_stdout(completed.stdout)
        if (
            installed.get("schema")
            != "TPAA_PRCB_C5_INSTALLED_DESKTOP_P1_P2_E2E_V1"
            or installed.get("status") != "PASS"
            or installed.get("product_version") != "1.0.1"
            or installed.get("db_schema_version") != "1.9.0"
            or installed.get("metric_count") != 5
            or installed.get("p2_job_status") != "SUCCEEDED"
            or installed.get("p2_estimate_status") not in {
                "IDENTIFIABLE",
                "NOT_IDENTIFIABLE",
            }
            or installed.get("p2_restart_exact_replay") is not True
            or installed.get("p2_backup_restore_exact_replay") is not True
            or installed.get("restart_exact_replay") is not True
            or installed.get("backup_restore_exact_replay") is not True
            or installed.get("persistent_audit_verified") is not True
            or installed.get("tests_fixture_dependency") is not False
            or installed.get("formal_release_claimed") is not False
        ):
            raise RuntimeError(f"installed Desktop P1 E2E report invalid: {installed}")

        logical_product, logical_hash = _logical_product(installed)
        report: dict[str, object] = {
            "schema": "TPAA_PRCB_C5_INSTALLED_DESKTOP_QUALIFICATION_V1",
            "status": "PASS",
            "qualification": "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED",
            "formal_release_claimed": False,
            "platform": platform_name,
            "profile_id": profile,
            "source_revision": revision,
            "product_version": "1.0.1",
            "package": package.name,
            "package_sha256": sha256_file(package),
            "package_summary_sha256": sha256_file(summary_path),
            "release_manifest_sha256": sha256_file(release_manifest_path),
            "tests_packaged": False,
            "fixtures_packaged": False,
            "installed_runtime": installed,
            "logical_product": logical_product,
            "logical_product_sha256": logical_hash,
        }
    _write_json(evidence, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", required=True, choices=sorted(PROFILE_BY_PLATFORM))
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--package-output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    report = qualify(
        platform_name=args.platform,
        expected_revision=args.source_revision,
        package_output=args.package_output,
        evidence=args.evidence,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
