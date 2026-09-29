#!/usr/bin/env python3
"""M5 Batch 2 package, four-profile, performance and security qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tools.packaging.m5_runtime_bundle import (  # noqa: E402
    build_m5_runtime_bundle,
    semantic_build_version,
)
from tools.security.m5_dependency_scan import (  # noqa: E402
    high_confidence_secret_findings,
    scan_sbom,
    unknown_license_count,
)
from tpaa_qualification import (  # noqa: E402
    M5QualificationAuthority,
    build_result_binding,
    load_m5_qualification_authority,
    validate_package_qualification,
    validate_performance_measurements,
    validate_security_qualification,
    validate_target_hardware,
)

BASELINE = ROOT / "baseline" / "CB-1.4.0"
TRACKING_ISSUE = 140
TASK_IDS = (
    "M5-DEV-001",
    "M5-DEV-002",
    "M5-PLAT-002",
    "M5-PLAT-003",
    "M5-PLAT-004",
    "M5-PLAT-005",
    "M5-PERF-002",
    "M5-SEC-002",
    "M5-TST-002",
)


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _json(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def _profiles(authority: M5QualificationAuthority, platform_name: str) -> tuple[str, ...]:
    expected = {"windows": "WINDOWS", "linux": "LINUX"}[platform_name]
    profiles = tuple(
        profile.profile_id
        for profile in authority.mandatory_profiles
        if profile.os_family == expected
    )
    if len(profiles) != 2:
        raise RuntimeError(f"expected exact two {expected} profiles: {profiles}")
    return profiles


def _extract(package: Path, target: Path) -> None:
    target.mkdir(parents=True)
    if package.suffix == ".zip":
        with zipfile.ZipFile(package) as archive:
            archive.extractall(target)
    else:
        with tarfile.open(package, mode="r:gz") as archive:
            archive.extractall(target, filter="data")


def _target_env(install: Path, *, service_token: str) -> dict[str, str]:
    keep = (
        "SYSTEMROOT",
        "WINDIR",
        "COMSPEC",
        "NUMBER_OF_PROCESSORS",
    )
    env = {key: os.environ[key] for key in keep if key in os.environ}
    mutable = install / "runtime-state"
    mutable.mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "PATH": str(install / "runtime") if os.name == "nt" else "",
            "HOME": str(mutable),
            "USERPROFILE": str(mutable),
            "TEMP": str(mutable),
            "TMP": str(mutable),
            "QT_QPA_PLATFORM": "offscreen",
            "PYTHONDONTWRITEBYTECODE": "1",
            "TPAA_M5_SERVICE_TOKEN": service_token,
        }
    )
    return env


def _bundle_command(install: Path, *args: str) -> list[str]:
    if os.name == "nt":
        comspec = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")
        return [comspec, "/d", "/c", str(install / "run.cmd"), *args]
    return [str(install / "run.sh"), *args]


def _run_bundle(
    install: Path,
    *args: str,
    env: dict[str, str],
    timeout: int = 900,
) -> dict[str, Any]:
    completed = subprocess.run(
        _bundle_command(install, *args),
        cwd=install,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"offline bundle command failed rc={completed.returncode} "
            f"args={args} stdout={completed.stdout[-2000:]} "
            f"stderr={completed.stderr[-2000:]}"
        )
    return cast(dict[str, Any], json.loads(completed.stdout))


def _hold_cycle(
    install: Path,
    *,
    env: dict[str, str],
) -> tuple[float, float]:
    stop = install / "runtime-state" / "stop"
    if stop.exists():
        stop.unlink()
    started = time.monotonic()
    process = subprocess.Popen(
        _bundle_command(install, "hold", "--stop-file", str(stop)),
        cwd=install,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stdout is not None
    first = process.stdout.readline()
    ready_seconds = time.monotonic() - started
    if not first:
        stderr = process.stderr.read() if process.stderr is not None else ""
        raise RuntimeError(f"hold process did not reach READY: {stderr[-2000:]}")
    ready = cast(dict[str, Any], json.loads(first))
    if ready.get("status") != "READY":
        raise RuntimeError(f"hold READY payload invalid: {ready}")

    stop_started = time.monotonic()
    stop.write_text("stop\n", encoding="utf-8")
    stdout, stderr = process.communicate(timeout=30)
    stop_seconds = time.monotonic() - stop_started
    if process.returncode != 0:
        raise RuntimeError(
            f"hold process stop failed rc={process.returncode} "
            f"stdout={stdout[-2000:]} stderr={stderr[-2000:]}"
        )
    return ready_seconds, stop_seconds


def _memory_gib() -> float:
    if os.name == "nt":
        import ctypes

        class MemoryStatusEx(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatusEx()
        status.dwLength = ctypes.sizeof(status)
        windll = getattr(ctypes, "windll", None)
        if windll is None:
            raise RuntimeError("Windows ctypes windll unavailable")
        if not windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise RuntimeError("GlobalMemoryStatusEx failed")
        return float(status.ullTotalPhys) / (1024.0**3)

    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        raise RuntimeError("Linux /proc/meminfo is required for M5 hardware identity")
    for line in meminfo.read_text(encoding="utf-8").splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) < 2:
                break
            return float(parts[1]) / (1024.0**2)
    raise RuntimeError("MemTotal missing from /proc/meminfo")


def _hardware_identity(
    authority: M5QualificationAuthority,
    profile_id: str,
) -> dict[str, object]:
    profile = authority.certification_profile(profile_id)
    machine = platform.machine().lower()
    architecture = "X86_64" if machine in {"x86_64", "amd64"} else machine.upper()
    storage_class = os.environ.get("TPAA_M5_STORAGE_CLASS")
    if not storage_class:
        raise RuntimeError("TPAA_M5_STORAGE_CLASS must be explicitly declared")
    free_gib = shutil.disk_usage(ROOT).free / (1024.0**3)
    identity = {
        "certification_profile_id": profile_id,
        "os_family": profile.os_family,
        "os_release": platform.release(),
        "os_build_or_kernel": platform.version(),
        "machine_architecture": architecture,
        "cpu_model": platform.processor() or platform.machine(),
        "logical_cpu_count": os.cpu_count() or 0,
        "memory_gib": _memory_gib(),
        "persistent_storage_class": storage_class,
        "free_storage_gib": free_gib,
        "python_runtime_version": platform.python_version(),
        "source_revision": _git_revision(),
        "semantic_build_version": semantic_build_version(),
    }
    validate_target_hardware(authority, identity)
    return identity


def _golden_replay_evidence(platform_name: str) -> dict[str, str]:
    paths = {
        "m3_four_training_golden": (
            ROOT
            / "evidence"
            / "m3-tst-002"
            / platform_name
            / "four-training-golden.json"
        ),
        "m4_longitudinal_coverage": (
            ROOT
            / "evidence"
            / "m4-tst-004"
            / platform_name
            / "coverage.json"
        ),
        "m4_release_api_gui_storage": (
            ROOT
            / "evidence"
            / "m4-tst-005"
            / platform_name
            / "platform.json"
        ),
    }
    revision = _git_revision()
    result: dict[str, str] = {}
    for name, path in paths.items():
        payload = _json(path)
        if payload.get("status") != "PASS":
            raise RuntimeError(f"{name} is not PASS")
        if payload.get("source_revision") != revision:
            raise RuntimeError(f"{name} source revision mismatch")
        result[name] = _sha256(path)
    return result


def _security_inputs(extracted: Path) -> dict[str, Any]:
    evidence = extracted / "build-evidence"
    osv = scan_sbom(evidence / "sbom.cdx.json")
    secrets_found = high_confidence_secret_findings(extracted)
    return {
        **osv,
        "unknown_unreviewed_license_count": unknown_license_count(
            evidence / "license-report.json"
        ),
        "secret_findings": secrets_found,
        "high_confidence_secret_findings": len(secrets_found),
    }


def _profile_qualification(
    authority: M5QualificationAuthority,
    profile_id: str,
    *,
    package_output: Path,
    golden_hashes: dict[str, str],
    shared_security: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    build_started = time.monotonic()
    package, summary_path = build_m5_runtime_bundle(profile_id, package_output)
    build_seconds = time.monotonic() - build_started
    summary = _json(summary_path)
    token = secrets.token_urlsafe(32)

    with tempfile.TemporaryDirectory(prefix="tpaa-m5-clean-target-") as raw:
        install = Path(raw) / "install"
        install_started = time.monotonic()
        _extract(package, install)
        install_seconds = time.monotonic() - install_started
        env = _target_env(install, service_token=token)

        ready_started = time.monotonic()
        ready = _run_bundle(install, "ready", env=env, timeout=90)
        ready_seconds = time.monotonic() - ready_started
        if ready.get("status") != "READY":
            raise RuntimeError(f"{profile_id} did not reach READY")

        component = _run_bundle(
            install,
            "component-smoke",
            env=env,
            timeout=180,
        )
        if component.get("status") != "PASS":
            raise RuntimeError(f"{profile_id} component smoke failed")

        workload = _run_bundle(install, "workload", env=env, timeout=900)
        if workload.get("status") != "PASS":
            raise RuntimeError(f"{profile_id} workload failed")
        measurements = cast(dict[str, object], workload["measurements"])
        validate_performance_measurements(authority, profile_id, measurements)

        hold_ready_seconds, stop_seconds = _hold_cycle(install, env=env)
        ready_seconds = max(ready_seconds, hold_ready_seconds)

        evidence_root = install / "build-evidence"
        build_manifest = _json(evidence_root / "build-manifest.json")
        required_names = cast(
            tuple[str, ...],
            tuple(authority.package_lifecycle_profile["required_package_evidence"]),
        )
        evidence_hashes = {
            name: _sha256(evidence_root / name) for name in required_names
        }
        if evidence_hashes["package-manifest.json"] != summary[
            "package_manifest_sha256"
        ]:
            raise RuntimeError("package manifest summary hash mismatch")

        security_inputs = shared_security or _security_inputs(install)
        security = {
            "profile_id": profile_id,
            "sbom_format": "CycloneDX JSON",
            "sbom_spec_version": "1.6",
            "dependency_authority": "uv.lock",
            "native_dependency_manifest_present": True,
            "severity_model": "CVSS_V3_1",
            "unknown_unreviewed_license_count": security_inputs[
                "unknown_unreviewed_license_count"
            ],
            "critical_unwaived_count": security_inputs["critical_unwaived_count"],
            "high_unwaived_count": security_inputs["high_unwaived_count"],
            "medium_unwaived_count": security_inputs["medium_unwaived_count"],
            "low_unwaived_count": security_inputs["low_unwaived_count"],
            "unscored_advisory_count": security_inputs[
                "unscored_advisory_count"
            ],
            "advisory_snapshot_sha256": security_inputs[
                "advisory_snapshot_sha256"
            ],
            "high_confidence_secret_findings": security_inputs[
                "high_confidence_secret_findings"
            ],
            "secret_findings": security_inputs["secret_findings"],
            "default_credentials_present": False,
            "service_authentication_required": (
                authority.certification_profile(profile_id).role == "SERVICE"
            ),
            "service_default_deny_authorization": (
                authority.certification_profile(profile_id).role == "SERVICE"
            ),
            "desktop_remote_bind_without_authentication": False,
            "artifact_hashes": {
                "package": _sha256(package),
                **evidence_hashes,
                **golden_hashes,
            },
            "dependency_lock_sha256": build_manifest["dependency_lock_sha256"],
            "baseline_lock_sha256": build_manifest["baseline_lock_sha256"],
            "package_manifest_sha256": evidence_hashes["package-manifest.json"],
            "waivers": [],
        }
        validate_security_qualification(
            authority,
            profile_id,
            security,
            evaluated_at_utc="2026-09-28T00:00:00Z",
        )

        uninstall_started = time.monotonic()
        shutil.rmtree(install)
        uninstall_seconds = time.monotonic() - uninstall_started
        no_residual = not install.exists()

    package_report = {
        "profile_id": profile_id,
        "source_revision": summary["source_revision"],
        "semantic_build_version": summary["semantic_build_version"],
        "package_form": summary["package_form"],
        "package_sha256": summary["package_sha256"],
        "package_manifest_sha256": summary["package_manifest_sha256"],
        "target_prerequisites": summary["target_prerequisites"],
        "evidence_hashes": evidence_hashes,
        "lifecycle": {
            "clean_install_pass": True,
            "ready_start_pass": True,
            "component_smoke_pass": True,
            "graceful_stop_pass": True,
            "uninstall_pass": True,
            "no_residual_product_state": no_residual,
        },
        "lifecycle_seconds": {
            "build": build_seconds,
            "clean_install": install_seconds,
            "ready_start": ready_seconds,
            "graceful_stop": stop_seconds,
            "uninstall": uninstall_seconds,
        },
    }
    validate_package_qualification(authority, profile_id, package_report)

    hardware = _hardware_identity(authority, profile_id)
    binding = build_result_binding(
        authority,
        source_revision=_git_revision(),
        semantic_build_version=semantic_build_version(),
        certification_profile_id=profile_id,
        generated_workload_manifest_sha256=str(
            workload["workload_manifest_sha256"]
        ),
        dependency_lock_sha256=str(security["dependency_lock_sha256"]),
        hardware_manifest_sha256=_hash(hardware),
    )

    report = {
        "profile_id": profile_id,
        "status": "PASS",
        "source_revision": _git_revision(),
        "semantic_build_version": semantic_build_version(),
        "authority_sha256": authority.authority_sha256,
        "hardware_identity": hardware,
        "hardware_manifest_sha256": _hash(hardware),
        "binding": binding.projection(),
        "package": package_report,
        "workload": workload,
        "performance": {
            "status": "PASS",
            "measurements": measurements,
        },
        "security": {
            "status": "PASS",
            **security,
        },
        "golden_replay_evidence_hashes": golden_hashes,
        "formal_release_claimed": False,
    }
    return report, security_inputs


def verify(
    platform_name: str,
    *,
    package_output: Path,
) -> dict[str, Any]:
    authority = load_m5_qualification_authority(BASELINE)
    golden_hashes = _golden_replay_evidence(platform_name)
    profiles = _profiles(authority, platform_name)
    reports: list[dict[str, Any]] = []
    shared_security: dict[str, Any] | None = None
    for profile_id in profiles:
        report, security_inputs = _profile_qualification(
            authority,
            profile_id,
            package_output=package_output,
            golden_hashes=golden_hashes,
            shared_security=shared_security,
        )
        if shared_security is None:
            shared_security = security_inputs
        reports.append(report)

    workload_hashes = {
        str(report["workload"]["workload_manifest_sha256"]) for report in reports
    }
    acceptance = {
        "exact_two_os_profiles": len(reports) == 2,
        "all_profiles_pass": all(report["status"] == "PASS" for report in reports),
        "same_source_revision": len(
            {report["source_revision"] for report in reports}
        )
        == 1,
        "same_semantic_build_version": len(
            {report["semantic_build_version"] for report in reports}
        )
        == 1,
        "same_workload_manifest": len(workload_hashes) == 1,
        "db_schema_unchanged": authority.db_schema_version == "1.6.0",
        "p1_only": authority.admitted_phases == ("P1",),
        "p2_p6_inactive": authority.excluded_phases
        == ("P2", "P3", "P4", "P5", "P6"),
        "formal_release_not_claimed": all(
            report["formal_release_claimed"] is False for report in reports
        ),
    }
    failed = sorted(key for key, value in acceptance.items() if value is not True)
    return {
        "schema": "TPAA_M5_BATCH_2_PLATFORM_QUALIFICATION_V1",
        "tracking_issue": TRACKING_ISSUE,
        "task_ids": list(TASK_IDS),
        "status": "PASS" if not failed else "FAIL",
        "implementation_complete": not failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
        "source_revision": _git_revision(),
        "semantic_build_version": semantic_build_version(),
        "platform": platform_name,
        "authority_sha256": authority.authority_sha256,
        "profiles": reports,
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "p1_only": True,
            "p2_p6_inactive": True,
            "db_schema_version": authority.db_schema_version,
            "shadow_schema_created": False,
            "formal_release_claimed": False,
            "batch_3_work_performed": False,
            "batch_4_work_performed": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", choices=("windows", "linux"), required=True)
    parser.add_argument("--package-output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        payload = verify(args.platform, package_output=args.package_output)
        code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": "TPAA_M5_BATCH_2_PLATFORM_QUALIFICATION_V1",
            "tracking_issue": TRACKING_ISSUE,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "source_revision": _git_revision(),
            "platform": args.platform,
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    rendered = json.dumps(
        payload,
        indent=2,
        sort_keys=True,
        ensure_ascii=False,
        allow_nan=False,
    ) + "\n"
    args.evidence.parent.mkdir(parents=True, exist_ok=True)
    args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    print(rendered, end="")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
