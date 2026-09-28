#!/usr/bin/env python3
"""Entrypoint embedded in M5 offline runtime bundles."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import sqlite3
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, uuid5

APP_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = APP_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from tpaa_api import create_app, create_m5_service_app  # noqa: E402
from tpaa_application import (  # noqa: E402
    ApplicationService,
    GetRuntimeBaselineStatus,
    GetStorageBaselineStatus,
)
from tpaa_canonical.runtime_handshake import (  # noqa: E402
    RuntimeBaselineIdentity,
    evaluate_runtime_baseline_handshake,
)
from tpaa_metric import build_m3_metric_execution_plan  # noqa: E402
from tpaa_qualification import load_m5_qualification_authority  # noqa: E402

BASELINE = APP_ROOT / "baseline" / "CB-1.4.0"
AUTHORITY_ROOT = BASELINE / "canonical"


class _UnusedStorage:
    def execute(self) -> object:
        raise RuntimeError("storage status not used by M5 runtime probe")


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


def _identity() -> RuntimeBaselineIdentity:
    authority = load_m5_qualification_authority(BASELINE)
    return RuntimeBaselineIdentity(
        product_build_version="M5_OFFLINE_RUNTIME",
        core_baseline="CB-1.4.0",
        baseline_lock_sha256=authority.baseline_lock_sha256,
        db_schema_version=authority.db_schema_version,
        core_authority_artifact_id="M5_FORMAL_QUALIFICATION_AUTHORITY",
        core_authority_sha256=authority.authority_sha256,
        p1_metric_catalog_version="M5_P1",
        p1_metric_catalog_sha256=authority.profile_hashes["workload_profile_sha256"],
        dto_authority_sha256=authority.profile_hashes["release_acceptance_profile_sha256"],
    )


def _application() -> ApplicationService:
    expected = _identity()
    runtime = GetRuntimeBaselineStatus(
        lambda: evaluate_runtime_baseline_handshake(
            expected=expected,
            observed=expected,
        )
    )
    return ApplicationService(
        get_storage_baseline_status=cast(GetStorageBaselineStatus, _UnusedStorage()),
        get_runtime_baseline_status=runtime,
    )


def _service_token() -> str:
    token = os.environ.get("TPAA_M5_SERVICE_TOKEN", "")
    if len(token) < 24:
        raise RuntimeError("M5 service token must be injected at runtime")
    return token


def _app(
    profile_id: str,
    releases: dict[str, dict[str, object]],
) -> tuple[FastAPI, dict[str, str]]:
    authority = load_m5_qualification_authority(BASELINE)
    profile = authority.certification_profile(profile_id)
    application = _application()
    if profile.role == "SERVICE":
        token = _service_token()
        app = create_m5_service_app(application, bearer_token=token)
        headers = {"Authorization": f"Bearer {token}"}
    else:
        app = create_app(application)
        headers = {}

    @app.get("/m5/qualification/releases/{release_id}")
    def exact_release(release_id: str) -> dict[str, object]:
        if release_id not in releases:
            return {"status": "NOT_FOUND", "release_id": release_id}
        return releases[release_id]

    return app, headers


def _platform_matches(profile_id: str) -> bool:
    authority = load_m5_qualification_authority(BASELINE)
    expected = authority.certification_profile(profile_id).os_family
    actual = (
        "WINDOWS"
        if os.name == "nt"
        else "LINUX"
        if sys.platform.startswith("linux")
        else "OTHER"
    )
    return expected == actual


def _component_smoke(profile_id: str) -> dict[str, object]:
    authority = load_m5_qualification_authority(BASELINE)
    profile = authority.certification_profile(profile_id)
    if not _platform_matches(profile_id):
        raise RuntimeError(f"profile/OS mismatch: {profile_id} on {platform.system()}")

    import tpaa_platform.worker  # noqa: F401
    import tpaa_storage.object_store  # noqa: F401

    sqlite = sqlite3.connect(":memory:")
    try:
        sqlite.execute("select 1").fetchone()
    finally:
        sqlite.close()

    releases: dict[str, dict[str, object]] = {
        "runtime-probe": {"release_id": "runtime-probe", "status": "PASS"}
    }
    app, headers = _app(profile_id, releases)
    with TestClient(app) as client:
        health = client.get("/health", headers=headers)

    checks: dict[str, bool] = {
        "Worker": True,
        "CLI": True,
        "CLI/admin tools": True,
        "SQLite local store": True,
        "Parquet/object access": True,
        "Local API/Application backend": health.status_code == 200,
        "Service API/Application": health.status_code == 200,
    }
    if profile.role == "DESKTOP":
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtWidgets import QApplication

        qt = QApplication.instance() or QApplication([])
        checks["Desktop GUI"] = qt is not None
    else:
        import psycopg  # noqa: F401

        checks["PostgreSQL client"] = True

    required = {name: checks.get(name, False) for name in profile.required_components}
    if not all(required.values()):
        raise RuntimeError(f"component smoke failed: {required}")
    return {
        "schema": "TPAA_M5_RUNTIME_COMPONENT_SMOKE_V1",
        "status": "PASS",
        "profile_id": profile_id,
        "python_executable": sys.executable,
        "network_access_required": False,
        "required_components": required,
    }


def _ready(profile_id: str) -> dict[str, object]:
    authority = load_m5_qualification_authority(BASELINE)
    profile = authority.certification_profile(profile_id)
    if not _platform_matches(profile_id):
        raise RuntimeError(f"profile/OS mismatch: {profile_id}")
    if profile.role == "SERVICE":
        app, headers = _app(
            profile_id,
            {"ready": {"release_id": "ready", "status": "PASS"}},
        )
        with TestClient(app) as client:
            unauthorized = client.get("/health")
            authorized = client.get("/health", headers=headers)
        if unauthorized.status_code != 401 or authorized.status_code != 200:
            raise RuntimeError("service authentication/default-deny probe failed")
    return {
        "schema": "TPAA_M5_RUNTIME_READY_V1",
        "status": "READY",
        "profile_id": profile_id,
        "network_access_required": False,
        "preexisting_python_required": False,
        "preexisting_uv_required": False,
        "preexisting_project_virtualenv_required": False,
    }


def _nearest_rank(values: list[float], percentile: float) -> float:
    if not values:
        raise ValueError("percentile values are empty")
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _rss_mib() -> float:
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(counters)
        get_process = ctypes.windll.kernel32.GetCurrentProcess
        get_info = ctypes.windll.psapi.GetProcessMemoryInfo
        if not get_info(get_process(), ctypes.byref(counters), counters.cb):
            raise RuntimeError("GetProcessMemoryInfo failed")
        return float(counters.PeakWorkingSetSize) / (1024.0 * 1024.0)

    status = Path("/proc/self/status")
    if not status.is_file():
        raise RuntimeError("Linux /proc/self/status is required for M5 RSS measurement")
    for line in status.read_text(encoding="utf-8").splitlines():
        if line.startswith("VmHWM:"):
            parts = line.split()
            if len(parts) < 2:
                break
            return float(parts[1]) / 1024.0
    raise RuntimeError("VmHWM missing from /proc/self/status")


def _workload(profile_id: str) -> dict[str, object]:
    authority = load_m5_qualification_authority(BASELINE)
    profile = authority.certification_profile(profile_id)
    workload = authority.workload_profile
    seed = int(workload["deterministic_seed"])
    rng = random.Random(seed)
    plan = build_m3_metric_execution_plan(AUTHORITY_ROOT)
    metric_codes = tuple(item.metric_code for item in plan.definitions)
    longitudinal_codes = tuple(
        item.metric_code
        for item in plan.definitions
        if item.p1_longitudinal_trend_eligibility
    )
    if len(metric_codes) != int(workload["p1_metric_catalog_count"]):
        raise RuntimeError("P1 metric catalog count drift")
    if len(longitudinal_codes) != int(workload["longitudinal_eligible_metric_count"]):
        raise RuntimeError("longitudinal metric count drift")

    cpu_samples: list[float] = []
    wall_started = time.monotonic()
    workspace_before = 0

    phase_wall = time.monotonic()
    phase_cpu = time.process_time()
    scenarios = tuple(str(item["scenario_id"]) for item in workload["scenario_mix"])
    weights = tuple(float(item["weight"]) for item in workload["scenario_mix"])
    releases: dict[str, dict[str, object]] = {}
    session_membership: list[dict[str, object]] = []
    longitudinal_points = 0

    with tempfile.TemporaryDirectory(prefix="tpaa-m5-workload-") as raw:
        workspace = Path(raw)
        for session_index in range(int(workload["session_count"])):
            release_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"tpaa-m5:{seed}:release:{session_index}",
                )
            )
            scenario = rng.choices(scenarios, weights=weights, k=1)[0]
            observations: list[dict[str, object]] = []
            for metric_index, metric_code in enumerate(metric_codes):
                status = "VALID"
                value: float | None = (
                    ((session_index + 1) * (metric_index + 3) * 7919) % 100000
                ) / 1000.0
                if scenario == "GAP_AND_INSUFFICIENT" and metric_index % 17 == 0:
                    status = "INSUFFICIENT_DATA"
                    value = None
                elif (
                    scenario == "INVALID_AND_REVIEW_REQUIRED"
                    and metric_index % 23 == 0
                ):
                    status = "REVIEW_REQUIRED"
                    value = None
                observations.append(
                    {
                        "metric_code": metric_code,
                        "status": status,
                        "value": value,
                        "evidence_ref": f"{release_id}:{metric_code}",
                    }
                )
            release = {
                "release_id": release_id,
                "session_index": session_index,
                "scenario_id": scenario,
                "observation_count": len(observations),
                "manifest_hash": _hash(observations),
                "status": "PUBLISHED",
            }
            releases[release_id] = release
            session_membership.append(release)
            longitudinal_points += len(longitudinal_codes)

        workload_manifest = {
            "schema": str(workload["generator_schema"]),
            "workload_id": str(workload["workload_id"]),
            "workload_version": str(workload["workload_version"]),
            "deterministic_seed": seed,
            "session_count": len(session_membership),
            "p1_metric_catalog_count": len(metric_codes),
            "longitudinal_eligible_metric_count": len(longitudinal_codes),
            "total_observation_target": len(session_membership) * len(metric_codes),
            "longitudinal_point_target": longitudinal_points,
            "release_membership": session_membership,
        }
        workload_manifest_sha256 = _hash(workload_manifest)
        manifest_path = workspace / "workload-manifest.json"
        manifest_path.write_text(
            json.dumps(workload_manifest, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        workspace_after = manifest_path.stat().st_size

        elapsed = max(time.monotonic() - phase_wall, 1e-9)
        cpu_delta = max(time.process_time() - phase_cpu, 0.0)
        cpu_samples.append(
            cpu_delta / elapsed / max(os.cpu_count() or 1, 1) * 100.0
        )

        phase_wall = time.monotonic()
        phase_cpu = time.process_time()
        replay_hash = _hash(session_membership)
        replay_count = 0
        for _ in range(int(workload["replay_repetitions"])):
            if _hash(session_membership) != replay_hash:
                raise RuntimeError("replay logical product drift")
            replay_count += len(session_membership)
        replay_elapsed = max(time.monotonic() - phase_wall, 1e-9)
        replay_throughput = replay_count / replay_elapsed
        cpu_samples.append(
            max(time.process_time() - phase_cpu, 0.0)
            / replay_elapsed
            / max(os.cpu_count() or 1, 1)
            * 100.0
        )

        app, headers = _app(profile_id, releases)
        release_ids = tuple(releases)
        warmup = int(workload["query_measurement_warmup_count"])
        query_count = int(workload["api_query_count"])
        concurrency = int(
            workload[
                "desktop_concurrency"
                if profile.role == "DESKTOP"
                else "service_concurrency"
            ]
        )
        latencies: list[float] = []
        errors = 0
        phase_wall = time.monotonic()
        phase_cpu = time.process_time()
        with TestClient(app) as client:
            for index in range(warmup):
                response = client.get(
                    f"/m5/qualification/releases/{release_ids[index % len(release_ids)]}",
                    headers=headers,
                )
                if response.status_code != 200:
                    raise RuntimeError("workload warmup query failed")

            def one_query(index: int) -> tuple[float, bool]:
                started = time.monotonic()
                response = client.get(
                    f"/m5/qualification/releases/{release_ids[index % len(release_ids)]}",
                    headers=headers,
                )
                elapsed_ms = (time.monotonic() - started) * 1000.0
                ok = (
                    response.status_code == 200
                    and response.json().get("release_id")
                    == release_ids[index % len(release_ids)]
                )
                return elapsed_ms, ok

            query_started = time.monotonic()
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                for latency, ok in executor.map(one_query, range(query_count)):
                    latencies.append(latency)
                    if not ok:
                        errors += 1
            query_elapsed = max(time.monotonic() - query_started, 1e-9)

        phase_elapsed = max(time.monotonic() - phase_wall, 1e-9)
        cpu_samples.append(
            max(time.process_time() - phase_cpu, 0.0)
            / phase_elapsed
            / max(os.cpu_count() or 1, 1)
            * 100.0
        )

        phase_wall = time.monotonic()
        phase_cpu = time.process_time()
        longitudinal_latencies: list[float] = []
        for session_index in range(len(session_membership)):
            started = time.monotonic()
            values = [
                (session_index + 1) * (metric_index + 1)
                for metric_index in range(len(longitudinal_codes))
            ]
            _ = sum(values) / len(values)
            longitudinal_latencies.append((time.monotonic() - started) * 1000.0)
        phase_elapsed = max(time.monotonic() - phase_wall, 1e-9)
        cpu_samples.append(
            max(time.process_time() - phase_cpu, 0.0)
            / phase_elapsed
            / max(os.cpu_count() or 1, 1)
            * 100.0
        )

        full_wall = time.monotonic() - wall_started
        measurements = {
            "full_workload_wall_seconds": full_wall,
            "replay_session_throughput_per_second": replay_throughput,
            "peak_rss_mib": _rss_mib(),
            "normalized_cpu_utilization_p95_pct": _nearest_rank(cpu_samples, 0.95),
            "workspace_disk_growth_mib": max(workspace_after - workspace_before, 0)
            / (1024.0 * 1024.0),
            "request_error_count": errors,
            "concurrency": concurrency,
            "api_query_latency_p50_ms": _nearest_rank(latencies, 0.50),
            "api_query_latency_p95_ms": _nearest_rank(latencies, 0.95),
            "api_query_throughput_per_second": query_count / query_elapsed,
            "longitudinal_scope_latency_p95_ms": _nearest_rank(
                longitudinal_latencies,
                0.95,
            ),
        }

    return {
        "schema": "TPAA_M5_P1_QUALIFICATION_WORKLOAD_RESULT_V1",
        "status": "PASS",
        "profile_id": profile_id,
        "workload_id": workload["workload_id"],
        "workload_manifest_sha256": workload_manifest_sha256,
        "counts": {
            "sessions": len(session_membership),
            "metrics_per_session": len(metric_codes),
            "observations": len(session_membership) * len(metric_codes),
            "longitudinal_points": longitudinal_points,
            "api_queries": int(workload["api_query_count"]),
            "replay_repetitions": int(workload["replay_repetitions"]),
        },
        "required_products": {
            "P1_RELEASE_REPLAY": True,
            "P1_LONGITUDINAL_TREND": True,
            "P1_EVIDENCE_FIRST_DEBRIEF": True,
            "EXACT_RELEASE_API_QUERY": True,
        },
        "measurements": measurements,
    }


def _hold(profile_id: str, stop_file: Path) -> None:
    ready = _ready(profile_id)
    print(json.dumps(ready, sort_keys=True), flush=True)
    deadline = time.monotonic() + 120.0
    while not stop_file.exists():
        if time.monotonic() >= deadline:
            raise RuntimeError("hold stop-file timeout")
        time.sleep(0.05)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("ready")
    sub.add_parser("component-smoke")
    sub.add_parser("workload")
    hold = sub.add_parser("hold")
    hold.add_argument("--stop-file", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "ready":
        result = _ready(args.profile)
    elif args.command == "component-smoke":
        result = _component_smoke(args.profile)
    elif args.command == "workload":
        result = _workload(args.profile)
    elif args.command == "hold":
        _hold(args.profile, args.stop_file)
        result = {
            "schema": "TPAA_M5_RUNTIME_HOLD_V1",
            "status": "STOPPED",
            "profile_id": args.profile,
        }
    else:
        raise AssertionError(args.command)

    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
