from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from tpaa_qualification import load_m5_qualification_authority

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
TASK_BASELINE = ROOT / "docs" / "baseline" / "SDIB-1.4" / "M5_TASK_BASELINE.json"
WORKFLOW = ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
EXIT_PATH = ROOT / "tools" / "testing" / "m5_exit_review.py"

SPEC = importlib.util.spec_from_file_location("m5_exit_review", EXIT_PATH)
assert SPEC is not None and SPEC.loader is not None
EXIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXIT)


def test_m5_batch_4_exact_task_inventory_and_scope() -> None:
    payload = json.loads(TASK_BASELINE.read_text(encoding="utf-8"))
    ids = tuple(row["task_id"] for row in payload["tasks"])
    assert payload["task_count"] == 23
    assert ids[-3:] == ("M5-TST-005", "M5-TST-006", "M5-TST-007")
    authority = load_m5_qualification_authority(BASELINE)
    assert authority.db_schema_version == "1.6.0"
    assert authority.admitted_phases == ("P1",)
    assert authority.excluded_phases == ("P2", "P3", "P4", "P5", "P6")


def test_m5_batch_4_signoff_principals_are_role_exact_and_distinct() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    signoffs = EXIT.SIGNOFF_PRINCIPALS
    assert tuple(row["role"] for row in signoffs) == tuple(
        authority.formal_release_acceptance_profile["required_signoff_roles"]
    )
    assert len({row["actor_id"] for row in signoffs}) == 3
    assert all(row["actor_kind"] == "GOVERNED_EVIDENCE_PRINCIPAL" for row in signoffs)


def test_m5_batch_4_workflow_preserves_fourteen_job_topology() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    required = (
        "Execute M5 Batch 4 clean formal package reconstruction",
        "Review M5-TST-005 same-candidate four-profile parity",
        "Review M5-TST-006 cold reconstruction and complete RC manifest",
        "Review exact M5 task inventory and Exit gate",
        "tpaa-m5-batch-4-platform-",
        "tpaa-m5-batch-4-review-",
        "tpaa-m5-exit-review-",
    )
    for token in required:
        assert token in text
    assert "\n  m5-exit-review:" not in text
    assert text.count("\n  m0-cross-platform:") == 1
    assert text.count("\n  m0-logical-equivalence:") == 1
    assert text.count("\n  m4-exit-review:") == 1


def test_m5_batch_4_cold_reconstruction_follows_c3_archive_rule() -> None:
    authority = load_m5_qualification_authority(BASELINE)
    assert authority.package_lifecycle_profile["archive_rule"] == (
        "Archive bytes may differ by OS/profile; package manifest logical identities "
        "and governed source/dependency/baseline hashes must remain exact."
    )
    source = (
        ROOT / "tools" / "testing" / "m5_batch_4_cold_reconstruction.py"
    ).read_text(encoding="utf-8")
    assert '"deterministic_packages_exact"' not in source
    assert '"package_manifest_logical_identity_exact"' in source
    assert '"archive_byte_identity_used_as_release_gate": False' in source
