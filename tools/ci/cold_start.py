#!/usr/bin/env python3
"""Rebuild current M0 from a clean local clone and rerun the governed gates."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _platform_name() -> str:
    system = platform.system().lower()
    if system in {"windows", "linux"}:
        return system
    raise RuntimeError(f"unsupported cold-start platform: {system}")


def _run(args: list[str], cwd: Path, *, env: dict[str, str] | None = None, timeout: int = 1200) -> None:
    completed = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        check=False,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"cold-start command failed rc={completed.returncode}: {args}")


def run(
    expected_platform: str | None,
    *,
    postgres_user: str | None = None,
    postgres_host: str | None = None,
    postgres_port: int | None = None,
    postgres_admin_database: str = "postgres",
    postgres_conninfo_template: str | None = None,
    postgres_psql: str = "psql",
) -> dict[str, object]:
    uv = shutil.which("uv")
    git = shutil.which("git")
    if uv is None or git is None:
        raise RuntimeError("git and uv are required for cold-start")
    actual = _platform_name()
    if expected_platform is not None and expected_platform != actual:
        raise RuntimeError(f"platform mismatch expected={expected_platform} actual={actual}")
    if postgres_conninfo_template is not None and (
        postgres_user is None or postgres_host is None or postgres_port is None
    ):
        raise RuntimeError(
            "postgres cold-start requires --postgres-user/--postgres-host/--postgres-port"
        )
    revision = subprocess.run(
        [git, "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    postgres_bootstrap = "NOT_REQUESTED"
    postgres_repository = "NOT_REQUESTED"
    with tempfile.TemporaryDirectory(prefix="tpaa-cold-start-") as raw:
        clone = Path(raw) / "repo"
        _run(
            [git, "clone", "--no-checkout", "--local", "--no-hardlinks", str(REPO_ROOT), str(clone)],
            REPO_ROOT,
        )
        _run([git, "checkout", "--detach", revision], clone)
        _run([uv, "sync", "--locked"], clone)
        env = os.environ.copy()
        env["TPAA_COLD_START_INNER"] = "1"
        dispatcher = [
            uv,
            "run",
            "--frozen",
            "python",
            "tools/dev/tpaa_dev.py",
        ]
        _run(
            [
                *dispatcher,
                "ci-check",
                "--expected-platform",
                actual,
            ],
            clone,
            env=env,
        )

        if postgres_conninfo_template is not None:
            assert postgres_user is not None
            assert postgres_host is not None
            assert postgres_port is not None
            common = [
                "--user",
                postgres_user,
                "--host",
                postgres_host,
                "--port",
                str(postgres_port),
                "--psql",
                postgres_psql,
            ]
            _run(
                [
                    *dispatcher,
                    "db-postgres-acceptance",
                    *common,
                    "--admin-database",
                    postgres_admin_database,
                    "--database",
                    "tpaa_m0_sto_001_cold_start_acceptance",
                ],
                clone,
                env=env,
            )
            postgres_bootstrap = "PASS"
            _run(
                [
                    *dispatcher,
                    "db-postgres-repository-acceptance",
                    *common,
                    "--admin-database",
                    postgres_admin_database,
                    "--database",
                    "tpaa_m0_sto_003_cold_start_acceptance",
                    "--conninfo-template",
                    postgres_conninfo_template,
                ],
                clone,
                env=env,
            )
            postgres_repository = "PASS"

        status = subprocess.run(
            [git, "status", "--porcelain"],
            cwd=clone,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if status:
            raise RuntimeError(f"cold-start clone became dirty: {status}")

    return {
        "schema": "TPAA_M0_COLD_START_V2",
        "task": "M0-DEV-006",
        "status": "PASS",
        "source_revision": revision,
        "platform": actual,
        "clean_clone": True,
        "uv_sync_locked": True,
        "m0_gates": "PASS",
        "postgres_bootstrap": postgres_bootstrap,
        "postgres_repository": postgres_repository,
        "worktree_clean": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-platform", choices=("windows", "linux"))
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--postgres-user")
    parser.add_argument("--postgres-host")
    parser.add_argument("--postgres-port", type=int)
    parser.add_argument("--postgres-admin-database", default="postgres")
    parser.add_argument("--postgres-conninfo-template")
    parser.add_argument("--postgres-psql", default="psql")
    args = parser.parse_args()
    try:
        result = run(
            args.expected_platform,
            postgres_user=args.postgres_user,
            postgres_host=args.postgres_host,
            postgres_port=args.postgres_port,
            postgres_admin_database=args.postgres_admin_database,
            postgres_conninfo_template=args.postgres_conninfo_template,
            postgres_psql=args.postgres_psql,
        )
        code = 0
    except Exception as exc:
        result = {
            "schema": "TPAA_M0_COLD_START_V2",
            "task": "M0-DEV-006",
            "status": "FAIL",
            "error": f"{type(exc).__name__}: {exc}",
        }
        code = 2
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
