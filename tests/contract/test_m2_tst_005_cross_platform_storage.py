from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tools.testing.m2_cross_platform_storage_qualification import (
    REQUIRED_LOGICAL_EVIDENCE,
)

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"
REVISION = "a" * 40


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(DEV), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=180,
    )


def test_m2_tst_005_aggregates_cross_platform_and_storage_parity(
    tmp_path: Path,
) -> None:
    logical_root = tmp_path / "logical"
    logical_root.mkdir()
    for name in REQUIRED_LOGICAL_EVIDENCE:
        revision_field = (
            {"expected_revision": REVISION}
            if name == "m2-data-005-logical-equivalence.json"
            else {"source_revision": REVISION}
        )
        (logical_root / name).write_text(
            json.dumps(
                {
                    "schema": f"TEST::{name}",
                    "status": "PASS",
                    "task_complete": True,
                    **revision_field,
                    "failed_acceptance": [],
                }
            ),
            encoding="utf-8",
        )

    storage = tmp_path / "storage-parity.json"
    storage.write_text(
        json.dumps(
            {
                "schema": "TPAA_M1_BATCH_2_STORAGE_PARITY_V1",
                "source_revision": REVISION,
                "status": "PASS",
                "fixture_id": "FROZEN_CORE_STORAGE_FIXTURE",
                "release_id": "11111111-1111-4111-8111-111111111111",
                "manifest_hash": "b" * 64,
                "sqlite_membership_hash": "c" * 64,
                "postgres_membership_hash": "c" * 64,
                "acceptance": {
                    "core_schema_is_frozen_1_6_0": True,
                    "sqlite_publish_pass": True,
                    "postgres_publish_pass": True,
                    "receipt_identity_equal": True,
                    "logical_release_membership_equal": True,
                    "logical_membership_hash_equal": True,
                },
                "failed_acceptance": [],
            }
        ),
        encoding="utf-8",
    )

    output = tmp_path / "qualification.json"
    result = _run(
        "m2-cross-platform-storage-qualification",
        "--logical-root",
        str(logical_root),
        "--storage-parity",
        str(storage),
        "--expected-revision",
        REVISION,
        "--output",
        str(output),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema"] == (
        "TPAA_M2_TST_005_CROSS_PLATFORM_STORAGE_QUALIFICATION_V1"
    )
    assert payload["task_id"] == "M2-TST-005"
    assert payload["status"] == "PASS"
    assert payload["task_complete"] is True
    assert payload["implementation_complete"] is True
    assert payload["failed_acceptance"] == []
    assert all(payload["acceptance"].values())
    assert payload["logical_product"]["required_logical_product_count"] == 22


def test_m2_tst_005_fails_when_storage_hashes_differ(tmp_path: Path) -> None:
    logical_root = tmp_path / "logical"
    logical_root.mkdir()
    for name in REQUIRED_LOGICAL_EVIDENCE:
        (logical_root / name).write_text(
            json.dumps(
                {
                    "status": "PASS",
                    "source_revision": REVISION,
                    "failed_acceptance": [],
                }
            ),
            encoding="utf-8",
        )
    storage = tmp_path / "storage-parity.json"
    storage.write_text(
        json.dumps(
            {
                "schema": "TPAA_M1_BATCH_2_STORAGE_PARITY_V1",
                "source_revision": REVISION,
                "status": "PASS",
                "sqlite_membership_hash": "c" * 64,
                "postgres_membership_hash": "d" * 64,
                "acceptance": {
                    "core_schema_is_frozen_1_6_0": True,
                    "sqlite_publish_pass": True,
                    "postgres_publish_pass": True,
                    "receipt_identity_equal": True,
                    "logical_release_membership_equal": True,
                    "logical_membership_hash_equal": True,
                },
                "failed_acceptance": [],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "qualification.json"
    result = _run(
        "m2-cross-platform-storage-qualification",
        "--logical-root",
        str(logical_root),
        "--storage-parity",
        str(storage),
        "--expected-revision",
        REVISION,
        "--output",
        str(output),
    )
    assert result.returncode == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["status"] == "FAIL"
    assert (
        "sqlite_postgres_logical_membership_hash_equal"
        in payload["failed_acceptance"]
    )
