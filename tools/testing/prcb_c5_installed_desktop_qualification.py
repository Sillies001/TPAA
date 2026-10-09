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
    args = ["desktop-e2e", "--work-root", str(work_root)]
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


def _ed2_b2_command(
    stage: Path,
    platform_name: str,
    work_root: Path,
) -> list[str]:
    args = ["ed2-b2-e2e", "--work-root", str(work_root)]
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
        "schema": "TPAA_PRCB_C5_DESKTOP_P1_P6_LOGICAL_PRODUCT_V1",
        "product_version": report.get("product_version"),
        "db_schema_version": report.get("db_schema_version"),
        "canonical_baseline": report.get("canonical_baseline"),
        "release_id": report.get("release_id"),
        "metric_count": report.get("metric_count"),
        "catalog_definition_count": report.get("catalog_definition_count"),
        "metric_code_count": report.get("metric_code_count"),
        "capability_observation_count": report.get(
            "capability_observation_count"
        ),
        "system_observation_count": report.get("system_observation_count"),
        "evidence_only_metric_instance_count": report.get(
            "evidence_only_metric_instance_count"
        ),
        "world_product_count": report.get("world_product_count"),
        "stage_count": report.get("stage_count"),
        "world_relation_count": report.get("world_relation_count"),
        "job_status": report.get("job_status"),
        "p2_job_status": report.get("p2_job_status"),
        "p2_release_id": report.get("p2_release_id"),
        "p2_estimate_id": report.get("p2_estimate_id"),
        "p2_estimate_status": report.get("p2_estimate_status"),
        "p2_source_observation_id": report.get("p2_source_observation_id"),
        "p2_source_knowledge_time_utc": report.get(
            "p2_source_knowledge_time_utc"
        ),
        "p2_reason_codes": report.get("p2_reason_codes"),
        "p2_claim_level": report.get("p2_claim_level"),
        "p2_adjusted_value": report.get("p2_adjusted_value"),
        "p2_unit": report.get("p2_unit"),
        "p3_job_status": report.get("p3_job_status"),
        "p3_estimate_id": report.get("p3_estimate_id"),
        "p4_job_status": report.get("p4_job_status"),
        "p4_revision_id": report.get("p4_revision_id"),
        "p5_job_status": report.get("p5_job_status"),
        "p5_revision_id": report.get("p5_revision_id"),
        "p6_forecast_job_status": report.get("p6_forecast_job_status"),
        "p6_forecast_result_id": report.get("p6_forecast_result_id"),
        "p6_counterfactual_job_status": report.get("p6_counterfactual_job_status"),
        "p6_counterfactual_run_id": report.get("p6_counterfactual_run_id"),
        "restart_exact_replay": report.get("restart_exact_replay"),
        "backup_restore_exact_replay": report.get("backup_restore_exact_replay"),
        "api_exact_read_verified": report.get("api_exact_read_verified"),
        "desktop_discovery_verified": report.get("desktop_discovery_verified"),
        "desktop_authentication_verified": report.get(
            "desktop_authentication_verified"
        ),
        "desktop_latest_alias_rejected": report.get(
            "desktop_latest_alias_rejected"
        ),
        "api_exact_read_restart_replay": report.get(
            "api_exact_read_restart_replay"
        ),
        "desktop_discovery_restart_replay": report.get(
            "desktop_discovery_restart_replay"
        ),
        "api_exact_read_backup_restore_replay": report.get(
            "api_exact_read_backup_restore_replay"
        ),
        "desktop_discovery_backup_restore_replay": report.get(
            "desktop_discovery_backup_restore_replay"
        ),
        "api_discovery_fingerprint": report.get("api_discovery_fingerprint"),
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
                "installed Desktop P1-P6 E2E failed "
                f"rc={completed.returncode} stderr={completed.stderr[-2000:]}"
            )
        installed = _json_stdout(completed.stdout)
        if (
            installed.get("schema")
            != "TPAA_PRCB_C5_INSTALLED_DESKTOP_P1_P6_E2E_V1"
            or installed.get("status") != "PASS"
            or installed.get("product_version") != "1.0.1"
            or installed.get("db_schema_version") != "1.9.0"
            or installed.get("catalog_definition_count") != 116
            or installed.get("metric_code_count") != 116
            or not isinstance(installed.get("metric_count"), int)
            or int(installed["metric_count"]) < 116
            or not isinstance(
                installed.get("capability_observation_count"),
                int,
            )
            or int(installed["capability_observation_count"]) <= 0
            or not isinstance(
                installed.get("system_observation_count"),
                int,
            )
            or int(installed["system_observation_count"]) <= 0
            or not isinstance(
                installed.get("evidence_only_metric_instance_count"),
                int,
            )
            or int(installed["evidence_only_metric_instance_count"]) <= 0
            or installed.get("world_product_count") != 4
            or installed.get("stage_count") != 4
            or installed.get("world_relation_count") != 3
            or installed.get("p2_job_status") != "SUCCEEDED"
            or installed.get("p2_estimate_status") not in {
                "IDENTIFIABLE",
                "NOT_IDENTIFIABLE",
            }
            or not isinstance(installed.get("p2_source_observation_id"), str)
            or not isinstance(installed.get("p2_source_knowledge_time_utc"), str)
            or not isinstance(installed.get("p2_reason_codes"), list)
            or not isinstance(installed.get("p2_claim_level"), str)
            or not isinstance(installed.get("p2_unit"), str)
            or installed.get("p3_job_status") != "SUCCEEDED"
            or installed.get("p4_job_status") != "SUCCEEDED"
            or installed.get("p5_job_status") != "SUCCEEDED"
            or installed.get("p6_forecast_job_status") != "SUCCEEDED"
            or installed.get("p6_counterfactual_job_status") != "SUCCEEDED"
            or installed.get("p2_restart_exact_replay") is not True
            or installed.get("p2_backup_restore_exact_replay") is not True
            or installed.get("p3_p6_restart_exact_replay") is not True
            or installed.get("p3_p6_backup_restore_exact_replay") is not True
            or installed.get("restart_exact_replay") is not True
            or installed.get("backup_restore_exact_replay") is not True
            or installed.get("api_exact_read_verified") is not True
            or installed.get("desktop_discovery_verified") is not True
            or installed.get("desktop_authentication_verified") is not True
            or installed.get("desktop_latest_alias_rejected") is not True
            or installed.get("api_exact_read_restart_replay") is not True
            or installed.get("desktop_discovery_restart_replay") is not True
            or installed.get("api_exact_read_backup_restore_replay") is not True
            or installed.get("desktop_discovery_backup_restore_replay") is not True
            or not isinstance(installed.get("api_discovery_fingerprint"), str)
            or len(cast(str, installed.get("api_discovery_fingerprint"))) != 64
            or installed.get("persistent_audit_verified") is not True
            or installed.get("tests_fixture_dependency") is not False
            or installed.get("formal_release_claimed") is not False
        ):
            raise RuntimeError(f"installed Desktop P1-P6 E2E report invalid: {installed}")

        ed2_b2_completed = subprocess.run(
            _ed2_b2_command(
                stage,
                platform_name,
                Path(raw) / "ed2-b2-work",
            ),
            cwd=stage,
            check=False,
            capture_output=True,
            text=True,
            env=dict(os.environ),
        )
        if ed2_b2_completed.returncode != 0:
            raise RuntimeError(
                "installed Desktop ED2 B2 continuous E2E failed "
                f"rc={ed2_b2_completed.returncode} "
                f"stderr={ed2_b2_completed.stderr[-4000:]}"
            )
        ed2_b2 = _json_stdout(ed2_b2_completed.stdout)
        if (
            ed2_b2.get("schema")
            != "TPAA_ED2_B2_CONTINUOUS_QUALIFICATION_RESULT_V1"
            or ed2_b2.get("status") != "PASS"
            or ed2_b2.get("product_version") != "1.0.1"
            or ed2_b2.get("runtime_profile") != "DESKTOP"
            or ed2_b2.get("db_schema_version") != "1.9.0"
            or ed2_b2.get("canonical_baseline") != "CB-1.4.0"
            or len(cast(list[object], ed2_b2.get("session_ids", []))) != 5
            or len(cast(list[object], ed2_b2.get("p1_release_ids", []))) != 5
            or len(cast(list[object], ed2_b2.get("p2_estimate_ids", []))) != 4
            or len(cast(list[object], ed2_b2.get("p3_estimate_ids", []))) != 4
            or len(
                cast(
                    list[object],
                    ed2_b2.get("p4_approved_revision_ids", []),
                )
            )
            != 4
            or not isinstance(ed2_b2.get("p6_forecast_result_id"), str)
            or not isinstance(ed2_b2.get("p6_counterfactual_run_id"), str)
            or ed2_b2.get("restart_exact_replay") is not True
            or ed2_b2.get("tests_fixture_dependency") is not False
            or ed2_b2.get("production_seed_dependency") is not False
            or ed2_b2.get("formal_release_claimed") is not False
        ):
            raise RuntimeError(
                f"installed Desktop ED2 B2 report invalid: {ed2_b2}"
            )

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
            "ed2_b2_continuous_runtime": ed2_b2,
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
