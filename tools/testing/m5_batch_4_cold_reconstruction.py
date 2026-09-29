#!/usr/bin/env python3
"""M5-TST-006 per-platform clean formal package reconstruction."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tpaa_qualification import (  # noqa: E402
    load_m5_qualification_authority,
    validate_upgrade_rollback_qualification,
)

BASELINE = ROOT / "baseline" / "CB-1.4.0"
TRACKING_ISSUE = 142
TASK_ID = "M5-TST-006"


def _json(path: Path) -> dict[str, Any]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{path}: root must be object")
    return cast(dict[str, Any], value)


def _platform_profiles(platform_name: str) -> tuple[str, str]:
    if platform_name == "windows":
        return ("WINDOWS_DESKTOP_X64", "WINDOWS_SERVICE_X64")
    if platform_name == "linux":
        return ("LINUX_DESKTOP_X64", "LINUX_SERVICE_X64")
    raise ValueError(platform_name)


def _profile_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("profiles")
    if not isinstance(rows, list):
        raise RuntimeError("Batch 2 profile rows missing")
    result: dict[str, dict[str, Any]] = {}
    for raw in rows:
        if not isinstance(raw, dict):
            raise RuntimeError("Batch 2 profile row invalid")
        profile_id = raw.get("profile_id")
        if not isinstance(profile_id, str):
            raise RuntimeError("Batch 2 profile id invalid")
        result[profile_id] = cast(dict[str, Any], raw)
    return result


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
    raise RuntimeError(f"unsupported package form: {package.name}")


def _run_bundle(
    install: Path,
    *,
    platform_name: str,
    command: str,
    timeout: int,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["TPAA_M5_SERVICE_TOKEN"] = "m5-cold-reconstruction-service-token-0001"
    env["QT_QPA_PLATFORM"] = "offscreen"
    if platform_name == "windows":
        comspec = os.environ.get("COMSPEC", r"C:\\Windows\\System32\\cmd.exe")
        argv = [comspec, "/d", "/c", str(install / "run.cmd"), command]
    else:
        argv = [str(install / "run.sh"), command]
    completed = subprocess.run(
        argv,
        cwd=install,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"reconstructed bundle command failed rc={completed.returncode} "
            f"command={command} stdout={completed.stdout[-2000:]} "
            f"stderr={completed.stderr[-2000:]}"
        )
    payload: object = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("runtime command did not return object")
    return cast(dict[str, Any], payload)


def reconstruct(
    *,
    platform_name: str,
    batch2_path: Path,
    batch3_path: Path,
    cold_start_path: Path,
    expected_revision: str,
) -> dict[str, Any]:
    authority = load_m5_qualification_authority(BASELINE)
    batch2 = _json(batch2_path)
    batch3 = _json(batch3_path)
    cold_start = _json(cold_start_path)
    profiles = _profile_rows(batch2)
    expected_profiles = _platform_profiles(platform_name)

    if batch2.get("status") != "PASS" or batch3.get("status") != "PASS":
        raise RuntimeError("Batch 2/3 prerequisite is not PASS")
    if (
        batch2.get("source_revision") != expected_revision
        or batch3.get("source_revision") != expected_revision
    ):
        raise RuntimeError("Batch 2/3 source revision mismatch")
    if tuple(profiles) != expected_profiles:
        raise RuntimeError("platform profile order/inventory mismatch")

    cold_start_exact = (
        cold_start.get("schema") == "TPAA_M0_COLD_START_V2"
        and cold_start.get("status") == "PASS"
        and cold_start.get("source_revision") == expected_revision
        and cold_start.get("platform") == platform_name
        and cold_start.get("clean_clone") is True
        and cold_start.get("uv_sync_locked") is True
        and cold_start.get("m0_gates") == "PASS"
        and cold_start.get("worktree_clean") is True
    )
    if not cold_start_exact:
        raise RuntimeError("governed clean-source reconstruction prerequisite failed")

    batch3_rows = batch3.get("profiles")
    if not isinstance(batch3_rows, list):
        raise RuntimeError("Batch 3 profile rows missing")
    batch3_by_profile = {
        str(cast(dict[str, Any], row)["profile_id"]): cast(dict[str, Any], row)
        for row in batch3_rows
        if isinstance(row, dict)
    }

    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError("uv executable unavailable for locked reconstruction")

    with tempfile.TemporaryDirectory(prefix="tpaa-m5-cold-reconstruct-") as raw:
        temp = Path(raw)
        clone = temp / "repo"
        subprocess.run(
            [
                "git",
                "clone",
                "--local",
                "--no-hardlinks",
                "--no-checkout",
                str(ROOT),
                str(clone),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
        subprocess.run(
            ["git", "checkout", "--detach", expected_revision],
            cwd=clone,
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
        project_venv_absent_before_sync = not (clone / ".venv").exists()
        env = os.environ.copy()
        env["UV_OFFLINE"] = "1"
        env["UV_NO_PROGRESS"] = "1"
        subprocess.run(
            [uv, "sync", "--locked", "--offline", "--python", "3.13.5"],
            cwd=clone,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=300,
        )
        reconstructed: dict[str, dict[str, Any]] = {}
        for profile_id in expected_profiles:
            output_dir = clone / "dist" / "m5-reconstructed" / profile_id
            subprocess.run(
                [
                    uv,
                    "run",
                    "--locked",
                    "--offline",
                    "python",
                    "tools/packaging/m5_runtime_bundle.py",
                    "--profile",
                    profile_id,
                    "--output",
                    str(output_dir),
                ],
                cwd=clone,
                env=env,
                check=True,
                capture_output=True,
                text=True,
                timeout=600,
            )
            summaries = list(output_dir.glob("*.summary.json"))
            if len(summaries) != 1:
                raise RuntimeError(f"{profile_id}: reconstructed summary count")
            summary = _json(summaries[0])
            expected = profiles[profile_id]
            package_expected = cast(dict[str, Any], expected["package"])
            package_name = summary.get("package")
            if not isinstance(package_name, str):
                raise RuntimeError(f"{profile_id}: reconstructed package name")
            package = output_dir / package_name
            if not package.is_file():
                raise RuntimeError(f"{profile_id}: reconstructed package missing")
            if (
                summary.get("source_revision") != expected_revision
                or summary.get("semantic_build_version")
                != expected.get("semantic_build_version")
                or summary.get("profile_id") != profile_id
                or summary.get("package_form") != package_expected.get("package_form")
            ):
                raise RuntimeError(f"{profile_id}: reconstructed package summary identity mismatch")

            install = temp / "install" / profile_id
            _extract(package, install)
            package_manifest = _json(
                install / "build-evidence" / "package-manifest.json"
            )
            expected_security = cast(dict[str, Any], expected["security"])
            dependency_lock_sha256 = hashlib.sha256(
                (clone / "uv.lock").read_bytes()
            ).hexdigest()
            manifest_files = package_manifest.get("files")
            if not isinstance(manifest_files, list) or not manifest_files:
                raise RuntimeError(f"{profile_id}: reconstructed package inventory missing")
            manifest_paths = [
                str(cast(dict[str, Any], row).get("path"))
                for row in manifest_files
                if isinstance(row, dict)
            ]
            manifest_identity_exact = (
                package_manifest.get("schema") == "TPAA_M5_PACKAGE_MANIFEST_V1"
                and package_manifest.get("qualification")
                == "M5_CANDIDATE_NOT_FORMALLY_QUALIFIED"
                and package_manifest.get("formal_release_claimed") is False
                and package_manifest.get("source_revision") == expected_revision
                and package_manifest.get("semantic_build_version")
                == expected.get("semantic_build_version")
                and package_manifest.get("profile_id") == profile_id
                and package_manifest.get("package_form")
                == package_expected.get("package_form")
                and package_manifest.get("m5_authority_sha256")
                == authority.authority_sha256
                and package_manifest.get("baseline_lock_sha256")
                == authority.baseline_lock_sha256
                and package_manifest.get("dependency_lock_sha256")
                == dependency_lock_sha256
                and package_manifest.get("dependency_lock_sha256")
                == expected_security.get("dependency_lock_sha256")
                and len(manifest_paths) == len(manifest_files)
                and len(set(manifest_paths)) == len(manifest_paths)
            )
            if not manifest_identity_exact:
                raise RuntimeError(
                    f"{profile_id}: reconstructed package manifest logical identity mismatch"
                )

            ready = _run_bundle(
                install,
                platform_name=platform_name,
                command="ready",
                timeout=120,
            )
            component = _run_bundle(
                install,
                platform_name=platform_name,
                command="component-smoke",
                timeout=180,
            )
            workload = _run_bundle(
                install,
                platform_name=platform_name,
                command="workload",
                timeout=900,
            )
            expected_workload = cast(dict[str, Any], expected["workload"])
            if (
                ready.get("status") != "READY"
                or component.get("status") != "PASS"
                or workload.get("status") != "PASS"
                or workload.get("workload_manifest_sha256")
                != expected_workload.get("workload_manifest_sha256")
            ):
                raise RuntimeError(f"{profile_id}: reconstructed runtime smoke failed")
            required_products = workload.get("required_products")
            if not isinstance(required_products, dict) or not all(
                value is True for value in required_products.values()
            ):
                raise RuntimeError(f"{profile_id}: replay/product smoke incomplete")

            b3 = batch3_by_profile.get(profile_id)
            if not isinstance(b3, dict):
                raise RuntimeError(f"{profile_id}: Batch 3 recovery evidence missing")
            upgrade = cast(dict[str, object], b3.get("upgrade_rollback", {}))
            validate_upgrade_rollback_qualification(authority, profile_id, upgrade)
            local = b3.get("local_backup_restore")
            if not isinstance(local, dict) or not all(
                local.get(key) is expected_value
                for key, expected_value in (
                    ("clean_target_restore_verified", True),
                    ("exact_release_membership_and_replay_verified", True),
                    ("one_byte_corruption_detected_before_mutation", True),
                    ("target_mutated_before_corruption_detection", False),
                    ("partial_cross_store_restore_observed", False),
                )
            ):
                raise RuntimeError(f"{profile_id}: recovery smoke incomplete")

            reconstructed[profile_id] = {
                "package_sha256": summary["package_sha256"],
                "batch2_package_sha256": package_expected["package_sha256"],
                "archive_bytes_match_batch2": (
                    summary["package_sha256"] == package_expected["package_sha256"]
                ),
                "package_manifest_sha256": summary["package_manifest_sha256"],
                "batch2_package_manifest_sha256": package_expected[
                    "package_manifest_sha256"
                ],
                "package_manifest_bytes_match_batch2": (
                    summary["package_manifest_sha256"]
                    == package_expected["package_manifest_sha256"]
                ),
                "package_manifest_logical_identity_exact": manifest_identity_exact,
                "archive_rule": authority.package_lifecycle_profile["archive_rule"],
                "ready": "PASS",
                "component_smoke": "PASS",
                "replay_workload_smoke": "PASS",
                "workload_manifest_sha256": workload["workload_manifest_sha256"],
                "upgrade_rollback_smoke": "PASS",
                "recovery_smoke": "PASS",
            }

        acceptance = {
            "clean_clone_exact_revision": True,
            "project_venv_absent_before_sync": project_venv_absent_before_sync,
            "locked_dependency_sync_offline": True,
            "baseline_present_in_clean_clone": (
                clone / "baseline" / "CB-1.4.0" / "BASELINE_LOCK.json"
            ).is_file(),
            "exact_two_platform_profiles": tuple(reconstructed) == expected_profiles,
            "c3_archive_rule_exact": authority.package_lifecycle_profile["archive_rule"]
            == (
                "Archive bytes may differ by OS/profile; package manifest logical identities "
                "and governed source/dependency/baseline hashes must remain exact."
            ),
            "package_manifest_logical_identity_exact": all(
                row["package_manifest_logical_identity_exact"] is True
                for row in reconstructed.values()
            ),
            "clean_install_readiness_component_replay_pass": all(
                row["ready"] == row["component_smoke"] == row["replay_workload_smoke"]
                == "PASS"
                for row in reconstructed.values()
            ),
            "upgrade_recovery_smoke_pass": all(
                row["upgrade_rollback_smoke"] == row["recovery_smoke"] == "PASS"
                for row in reconstructed.values()
            ),
            "db_schema_1_6_0": authority.db_schema_version == "1.6.0",
            "p1_only": authority.admitted_phases == ("P1",),
            "formal_release_not_claimed": True,
        }
        failed = sorted(key for key, value in acceptance.items() if value is not True)
        return {
            "schema": "TPAA_M5_TST_006_PLATFORM_RECONSTRUCTION_V1",
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "PASS" if not failed else "FAIL",
            "implementation_complete": not failed,
            "task_complete": False,
            "source_revision": expected_revision,
            "semantic_build_version": batch2.get("semantic_build_version"),
            "platform": platform_name,
            "profiles": reconstructed,
            "acceptance": acceptance,
            "failed_acceptance": failed,
            "scope": {
                "clean_source_baseline_locked_dependency_reconstruction": True,
                "network_used_for_dependency_sync": False,
                "archive_byte_identity_used_as_release_gate": False,
                "package_manifest_logical_identity_gate": True,
                "p1_only": True,
                "p2_p6_inactive": True,
                "db_schema_version": authority.db_schema_version,
                "shadow_schema_created": False,
                "formal_release_claimed": False,
                "m5_exit_go_claimed": False,
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    parser.add_argument("--batch2", type=Path, required=True)
    parser.add_argument("--batch3", type=Path, required=True)
    parser.add_argument("--cold-start", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = reconstruct(
            platform_name=args.platform,
            batch2_path=args.batch2,
            batch3_path=args.batch3,
            cold_start_path=args.cold_start,
            expected_revision=args.expected_revision,
        )
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M5_TST_006_PLATFORM_RECONSTRUCTION_V1",
            "task_id": TASK_ID,
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "source_revision": args.expected_revision,
            "platform": args.platform,
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
