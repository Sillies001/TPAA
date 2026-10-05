#!/usr/bin/env python3
"""PIQB B6 per-platform final-product package and runtime qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.manifest.build_artifacts import git_revision, sha256_file  # noqa: E402
from tools.packaging.piqb_release_bundle import build_piqb_release_bundle  # noqa: E402
from tools.testing.m5_batch_2_qualification import (  # noqa: E402
    _extract,
    _hold_cycle,
    _profiles,
    _run_bundle,
    _target_env,
)
from tpaa_qualification import (  # noqa: E402
    load_m5_qualification_authority,
    validate_performance_measurements,
)
from tpaa_qualification.m5_recovery import exercise_failed_install_rollback  # noqa: E402

BASELINE = ROOT / "baseline" / "CB-1.4.0"
RELEASE_CONTRACT = ROOT / "docs" / "baseline" / "PIQB-1.0" / "B6_RELEASE_CONTRACT.json"
TASK_IDS = ("PIQB-B6-002", "PIQB-B6-003", "PIQB-B6-004", "PIQB-B6-005")


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return cast(dict[str, Any], payload)


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _embedded_python(install: Path) -> Path:
    if os.name == "nt":
        path = install / "runtime" / "python.exe"
    else:
        path = install / "runtime" / "bin" / "python"
    if not path.is_file():
        raise RuntimeError("embedded Python missing")
    return path


def _m5_workload(
    install: Path,
    profile_id: str,
    *,
    env: dict[str, str],
) -> dict[str, Any]:
    entry = install / "app" / "tools" / "packaging" / "m5_runtime_entry.py"
    if not entry.is_file():
        raise RuntimeError("retained M5 workload entry missing")
    workload_env = dict(env)
    runtime_root = install / "runtime"
    workload_env["PYTHONHOME"] = str(runtime_root)
    workload_env["PYTHONPATH"] = str(install / "app" / "src")
    if os.name != "nt":
        workload_env["LD_LIBRARY_PATH"] = str(runtime_root / "lib")
    completed = subprocess.run(
        [
            str(_embedded_python(install)),
            str(entry),
            "--profile",
            profile_id,
            "workload",
        ],
        cwd=install,
        env=workload_env,
        check=False,
        capture_output=True,
        text=True,
        timeout=900,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"retained workload failed rc={completed.returncode} "
            f"stdout={completed.stdout[-2000:]} stderr={completed.stderr[-2000:]}"
        )
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("retained workload payload invalid")
    return cast(dict[str, Any], payload)


def _profile(
    profile_id: str,
    *,
    package_output: Path,
) -> dict[str, Any]:
    authority = load_m5_qualification_authority(BASELINE)
    revision = git_revision()
    package, summary_path = build_piqb_release_bundle(profile_id, package_output)
    summary = _json(summary_path)
    if (
        summary.get("status") != "PASS"
        or summary.get("source_revision") != revision
        or summary.get("profile_id") != profile_id
        or summary.get("product_version") != "1.0.0"
        or summary.get("db_schema_version") != "1.9.0"
    ):
        raise RuntimeError("PIQB package summary identity mismatch")

    with tempfile.TemporaryDirectory(prefix="tpaa-piqb-b6-install-") as raw:
        install = Path(raw) / "install"
        _extract(package, install)

        release_manifest_path = install / "piqb-release" / "release-manifest.json"
        build_manifest_path = install / "piqb-release" / "build-manifest.json"
        sbom_path = install / "piqb-release" / "sbom.spdx.json"
        release = _json(release_manifest_path)
        build = _json(build_manifest_path)
        sbom = _json(sbom_path)

        if (
            release.get("schema") != "TPAA_PIQB_RELEASE_MANIFEST_V1"
            or build.get("schema") != "TPAA_PIQB_BUILD_MANIFEST_V1"
            or sbom.get("spdxVersion") != "SPDX-2.3"
            or release.get("source_revision") != revision
            or release.get("product_version") != "1.0.0"
            or release.get("db_schema_version") != "1.9.0"
            or release.get("profile_id") != profile_id
            or release.get("formal_release_claimed") is not False
            or release.get("qualification") != "PIQB_B6_CANDIDATE"
            or release.get("admitted_capabilities")
            != ["P1", "P2", "P3", "P4", "P5", "P6"]
        ):
            raise RuntimeError("PIQB release envelope invalid")

        token = "PIQB-B6-SERVICE-TOKEN-QUALIFICATION-0001"
        env = _target_env(install, service_token=token)
        env["TPAA_SERVICE_TOKEN"] = token

        first_ready = _run_bundle(install, "ready", env=env, timeout=120)
        component = _run_bundle(install, "component-smoke", env=env, timeout=240)
        product = _run_bundle(install, "product-smoke", env=env, timeout=240)
        if (
            first_ready.get("status") != "PASS"
            or component.get("status") != "PASS"
            or product.get("status") != "PASS"
        ):
            raise RuntimeError("PIQB packaged runtime smoke failed")

        hold_ready_seconds, stop_seconds = _hold_cycle(install, env=env)
        second_ready = _run_bundle(install, "ready", env=env, timeout=120)
        if second_ready.get("status") != "PASS":
            raise RuntimeError("PIQB packaged runtime restart failed")

        workload = _m5_workload(install, profile_id, env=env)
        if workload.get("status") != "PASS":
            raise RuntimeError("retained governed workload failed")
        measurements = cast(dict[str, object], workload.get("measurements", {}))
        validate_performance_measurements(authority, profile_id, measurements)

        rollback_target = Path(raw) / "committed-install"
        before, after = exercise_failed_install_rollback(
            candidate=install,
            target=rollback_target,
        )
        if before != after or rollback_target.exists():
            raise RuntimeError("failed-install rollback did not preserve prior state")

        role = "DESKTOP" if profile_id.endswith("_DESKTOP_X64") else "SERVICE"
        return {
            "profile_id": profile_id,
            "role": role,
            "status": "PASS",
            "source_revision": revision,
            "product_version": "1.0.0",
            "db_schema_version": "1.9.0",
            "package": package.name,
            "package_sha256": sha256_file(package),
            "release_manifest_sha256": sha256_file(release_manifest_path),
            "build_manifest_sha256": sha256_file(build_manifest_path),
            "sbom_sha256": sha256_file(sbom_path),
            "runtime_ready": "PASS",
            "component_smoke": "PASS",
            "product_p1_p6_smoke": "PASS",
            "restart_ready": "PASS",
            "hold_ready_seconds": hold_ready_seconds,
            "graceful_stop_seconds": stop_seconds,
            "performance_qualification": "PASS",
            "performance_measurements": measurements,
            "workload_manifest_sha256": workload["workload_manifest_sha256"],
            "failed_install_rollback": "PASS",
            "upgrade_result": "NOT_APPLICABLE_FIRST_PIQB_RELEASE",
            "formal_release_claimed": False,
        }


def qualify(platform_name: str, *, package_output: Path) -> dict[str, Any]:
    authority = load_m5_qualification_authority(BASELINE)
    contract = _json(RELEASE_CONTRACT)
    if contract.get("db_schema_version") != "1.9.0":
        raise RuntimeError("B6 release contract DB schema drift")
    profiles = _profiles(authority, platform_name)
    reports = [_profile(profile_id, package_output=package_output) for profile_id in profiles]

    workload_hashes = {str(report["workload_manifest_sha256"]) for report in reports}
    logical_product = {
        "schema": "TPAA_PIQB_B6_LOGICAL_PRODUCT_V1",
        "product_version": "1.0.0",
        "db_schema_version": "1.9.0",
        "canonical_baseline": "CB-1.4.0",
        "source_revision": git_revision(),
        "roles": ["DESKTOP", "SERVICE"],
        "admitted_capabilities": ["P1", "P2", "P3", "P4", "P5", "P6"],
        "release_manifest_schema": "TPAA_PIQB_RELEASE_MANIFEST_V1",
        "build_manifest_schema": "TPAA_PIQB_BUILD_MANIFEST_V1",
        "sbom_schema": "SPDX-2.3",
        "workload_manifest_sha256": next(iter(workload_hashes)) if len(workload_hashes) == 1 else None,
        "runtime_entry": "PIQB_PRODUCT",
        "historical_m5_workload_reused_as_measurement_substrate": True,
        "historical_m5_qualification_semantics_rewritten": False,
    }
    acceptance = {
        "exact_two_platform_profiles": len(reports) == 2,
        "roles_exact": [report["role"] for report in reports] == ["DESKTOP", "SERVICE"],
        "all_profiles_pass": all(report["status"] == "PASS" for report in reports),
        "product_version_1_0_0": all(report["product_version"] == "1.0.0" for report in reports),
        "db_schema_1_9_0": all(report["db_schema_version"] == "1.9.0" for report in reports),
        "full_product_smoke_pass": all(report["product_p1_p6_smoke"] == "PASS" for report in reports),
        "restart_pass": all(report["restart_ready"] == "PASS" for report in reports),
        "performance_pass": all(report["performance_qualification"] == "PASS" for report in reports),
        "failed_install_rollback_pass": all(report["failed_install_rollback"] == "PASS" for report in reports),
        "same_governed_workload": len(workload_hashes) == 1,
        "formal_release_not_claimed": all(report["formal_release_claimed"] is False for report in reports),
    }
    failed = sorted(key for key, value in acceptance.items() if value is not True)
    return {
        "schema": "TPAA_PIQB_B6_PLATFORM_QUALIFICATION_V1",
        "task_ids": list(TASK_IDS),
        "status": "PASS" if not failed else "FAIL",
        "platform": platform_name,
        "source_revision": git_revision(),
        "product_version": "1.0.0",
        "db_schema_version": "1.9.0",
        "profiles": reports,
        "logical_product": logical_product,
        "logical_product_hash": _hash(logical_product),
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "no_m10_p7": True,
            "historical_m5_authority_mutated": False,
            "current_db_1_9_authority_required": True,
            "formal_release_claimed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--package-output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.source_revision != git_revision():
            raise RuntimeError("B6 source revision is not exact checkout")
        payload = qualify(args.platform, package_output=args.package_output)
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_PIQB_B6_PLATFORM_QUALIFICATION_V1",
            "status": "FAIL",
            "platform": args.platform,
            "source_revision": args.source_revision,
            "error": f"{type(exc).__name__}: {exc}",
            "failed_acceptance": ["qualification_exception"],
        }
        code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    print(rendered, end="")
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
