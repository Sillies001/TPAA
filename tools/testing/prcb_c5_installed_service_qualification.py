#!/usr/bin/env python3
"""PRCB C5 true installed Service/PostgreSQL qualification for one OS profile."""

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
from tools.packaging.prcb_release_bundle import build_prcb_release_bundle  # noqa: E402
from tools.storage.postgres_db import (  # noqa: E402
    PsqlClient,
    _database_exists,
    _identifier,
    _literal,
    _recreate_scoped_database,
    bootstrap_postgres,
    verify_postgres,
)

SERVICE_PROFILES = {"LINUX_SERVICE_X64", "WINDOWS_SERVICE_X64"}
_DATABASE_PREFIX = "tpaa_prcb_c5_service_"
_INSTRUCTOR_TOKEN = "prcb-c5-service-instructor-qualification"
_ANALYST_TOKEN = "prcb-c5-service-analyst-qualification"


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


def _installed_command(stage: Path, profile: str, work_root: Path) -> list[str]:
    args = ["service-e2e", "--work-root", str(work_root)]
    if profile.startswith("WINDOWS_"):
        return ["cmd.exe", "/d", "/s", "/c", str(stage / "run.cmd"), *args]
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
    raise RuntimeError(
        "installed Service runtime did not emit one terminal JSON object"
    )


def _forbidden_runtime_material(stage: Path) -> tuple[str, ...]:
    forbidden: list[str] = []
    for path in sorted(item for item in stage.rglob("*") if item.is_file()):
        relative = path.relative_to(stage).as_posix()
        if relative.startswith("app/tests/") or "/fixtures/" in f"/{relative}/":
            forbidden.append(relative)
    return tuple(forbidden)


def _drop_database(client: PsqlClient, admin_database: str, database: str) -> None:
    if not _database_exists(client, admin_database, database):
        return
    client.run(
        admin_database,
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        f"WHERE datname = {_literal(database)} AND pid <> pg_backend_pid();\n"
        f"DROP DATABASE {_identifier(database)};\n",
    )


def _logical_product(report: dict[str, Any]) -> tuple[dict[str, object], str]:
    product = {
        "schema": "TPAA_PRCB_C5_SERVICE_P1_P6_LOGICAL_PRODUCT_V1",
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
        "service_authentication_verified": report.get(
            "service_authentication_verified"
        ),
        "service_rbac_verified": report.get("service_rbac_verified"),
        "service_latest_alias_rejected": report.get("service_latest_alias_rejected"),
        "api_exact_read_restart_replay": report.get("api_exact_read_restart_replay"),
        "api_exact_read_backup_restore_replay": report.get(
            "api_exact_read_backup_restore_replay"
        ),
        "api_service_fingerprint": report.get("api_service_fingerprint"),
        "persistent_audit_verified": report.get("persistent_audit_verified"),
        "security_audit_verified": report.get("security_audit_verified"),
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
    profile: str,
    user: str,
    host: str,
    port: int,
    psql: str,
    admin_database: str,
    database: str,
    restore_database: str,
    conninfo_template: str,
    expected_revision: str,
    package_output: Path,
    evidence: Path,
) -> dict[str, object]:
    revision = git_revision()
    if revision != expected_revision:
        raise RuntimeError(
            f"exact-head mismatch expected={expected_revision} observed={revision}"
        )
    if profile not in SERVICE_PROFILES:
        raise RuntimeError(f"unsupported Service profile: {profile}")
    if database == restore_database:
        raise RuntimeError("primary and restore PostgreSQL databases must differ")
    for name in (database, restore_database):
        if not name.startswith(_DATABASE_PREFIX):
            raise RuntimeError(f"C5 Service database outside governed prefix: {name}")
        _identifier(name)

    package, summary_path = build_prcb_release_bundle(profile, package_output)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if (
        not isinstance(summary, dict)
        or summary.get("status") != "PASS"
        or summary.get("product_version") != "1.0.1"
        or summary.get("source_revision") != revision
        or summary.get("profile_id") != profile
    ):
        raise RuntimeError("PRCB C5 Service package summary identity mismatch")

    client = PsqlClient(
        user=user,
        host=host,
        port=port,
        psql_executable=psql,
    )
    _recreate_scoped_database(
        client,
        admin_database,
        database,
        required_prefix=_DATABASE_PREFIX,
    )
    _recreate_scoped_database(
        client,
        admin_database,
        restore_database,
        required_prefix=_DATABASE_PREFIX,
    )
    try:
        primary_bootstrap = bootstrap_postgres(client, database)
        primary_conninfo = conninfo_template.format(database=database)
        restore_conninfo = conninfo_template.format(database=restore_database)
        with tempfile.TemporaryDirectory(
            prefix="tpaa-prcb-c5-service-installed-"
        ) as raw:
            stage = Path(raw) / "installed"
            _extract(package, stage)
            forbidden = _forbidden_runtime_material(stage)
            if forbidden:
                raise RuntimeError(
                    "installed Service candidate contains forbidden test material: "
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
                raise RuntimeError("installed PRCB Service release manifest mismatch")

            environment = dict(os.environ)
            environment.update(
                {
                    "TPAA_SERVICE_CONNINFO": primary_conninfo,
                    "TPAA_SERVICE_RESTORE_CONNINFO": restore_conninfo,
                    "TPAA_C5_INSTRUCTOR_TOKEN": _INSTRUCTOR_TOKEN,
                    "TPAA_C5_ANALYST_TOKEN": _ANALYST_TOKEN,
                }
            )
            work_root = Path(raw) / "work"
            completed = subprocess.run(
                _installed_command(stage, profile, work_root),
                cwd=stage,
                check=False,
                capture_output=True,
                text=True,
                env=environment,
            )
            if completed.returncode != 0:
                raise RuntimeError(
                    "installed Service P1-P6 E2E failed "
                    f"rc={completed.returncode} stderr={completed.stderr[-4000:]}"
                )
            installed = _json_stdout(completed.stdout)
            if (
                installed.get("schema")
                != "TPAA_PRCB_C5_INSTALLED_SERVICE_P1_P6_E2E_V1"
                or installed.get("status") != "PASS"
                or installed.get("product_version") != "1.0.1"
                or installed.get("runtime_profile") != "SERVICE"
                or installed.get("db_schema_version") != "1.9.0"
                or installed.get("canonical_baseline") != "CB-1.4.0"
                or installed.get("metric_count") != 5
                or installed.get("job_status") != "SUCCEEDED"
                or installed.get("p2_job_status") != "SUCCEEDED"
                or installed.get("p2_estimate_status") not in {
                    "IDENTIFIABLE",
                    "NOT_IDENTIFIABLE",
                }
                or installed.get("p3_job_status") != "SUCCEEDED"
                or installed.get("p4_job_status") != "SUCCEEDED"
                or installed.get("p5_job_status") != "SUCCEEDED"
                or installed.get("p6_forecast_job_status") != "SUCCEEDED"
                or installed.get("p6_counterfactual_job_status") != "SUCCEEDED"
                or installed.get("restart_exact_replay") is not True
                or installed.get("backup_restore_exact_replay") is not True
                or installed.get("api_exact_read_verified") is not True
                or installed.get("service_authentication_verified") is not True
                or installed.get("service_rbac_verified") is not True
                or installed.get("service_latest_alias_rejected") is not True
                or installed.get("api_exact_read_restart_replay") is not True
                or installed.get("api_exact_read_backup_restore_replay") is not True
                or installed.get("persistent_audit_verified") is not True
                or installed.get("security_audit_verified") is not True
                or installed.get("model_reviewer_service_role_configured") is not False
                or installed.get("tests_fixture_dependency") is not False
                or installed.get("formal_release_claimed") is not False
                or not isinstance(installed.get("api_service_fingerprint"), str)
                or len(cast(str, installed.get("api_service_fingerprint"))) != 64
            ):
                raise RuntimeError(
                    f"installed Service P1-P6 E2E report invalid: {installed}"
                )

            primary_after = verify_postgres(client, database)
            restored_after = verify_postgres(client, restore_database)
            if primary_after != restored_after:
                raise RuntimeError("C5 Service restored PostgreSQL authority drift")
            if primary_bootstrap != primary_after:
                raise RuntimeError("C5 Service primary PostgreSQL authority mutated")

            logical_product, logical_hash = _logical_product(installed)
            report: dict[str, object] = {
                "schema": "TPAA_PRCB_C5_INSTALLED_SERVICE_QUALIFICATION_V1",
                "status": "PASS",
                "qualification": "TPAA_1_0_1_CANDIDATE_NOT_QUALIFIED",
                "formal_release_claimed": False,
                "profile_id": profile,
                "source_revision": revision,
                "product_version": "1.0.1",
                "package": package.name,
                "package_sha256": sha256_file(package),
                "package_summary_sha256": sha256_file(summary_path),
                "release_manifest_sha256": sha256_file(release_manifest_path),
                "tests_packaged": False,
                "fixtures_packaged": False,
                "real_postgresql_executed": True,
                "pg_dump_restore_executed": True,
                "installed_runtime": installed,
                "logical_product": logical_product,
                "logical_product_sha256": logical_hash,
            }
        _write_json(evidence, report)
        return report
    finally:
        _drop_database(client, admin_database, restore_database)
        _drop_database(client, admin_database, database)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True, choices=sorted(SERVICE_PROFILES))
    parser.add_argument("--user", default="tpaa")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5432)
    parser.add_argument("--psql", default="psql")
    parser.add_argument("--admin-database", default="postgres")
    parser.add_argument("--database", default="tpaa_prcb_c5_service_primary")
    parser.add_argument(
        "--restore-database",
        default="tpaa_prcb_c5_service_restore",
    )
    parser.add_argument("--conninfo-template", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--package-output", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    report = qualify(
        profile=args.profile,
        user=args.user,
        host=args.host,
        port=args.port,
        psql=args.psql,
        admin_database=args.admin_database,
        database=args.database,
        restore_database=args.restore_database,
        conninfo_template=args.conninfo_template,
        expected_revision=args.source_revision,
        package_output=args.package_output,
        evidence=args.evidence,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
