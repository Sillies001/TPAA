from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from tools.baseline.authority_diff import build_report
from tools.baseline.verify_authority_consistency import verify

REPO_ROOT = Path(__file__).resolve().parents[2]
PREDECESSOR_AUTHORITY = REPO_ROOT / "baseline" / "CB-1.4.0"
CURRENT_AUTHORITY = REPO_ROOT / "baseline" / "CB-1.5.0"
COMPLIANCE_MATRIX = REPO_ROOT / "docs" / "compliance" / "W0_COMPLIANCE_MATRIX.json"
AUTHORITY_DIFF_EVIDENCE = REPO_ROOT / "docs" / "reviews" / "W0_R3_3_AUTHORITY_DIFF.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _authority_root(
    root: Path,
    *,
    db_schema: str,
    extra: dict[str, dict[str, Any]] | None = None,
) -> Path:
    canonical = root / "canonical"
    core = {
        "core_baseline": "CB-TEST",
        "db_schema_version": db_schema,
        "tables": {"test.item": {"schema_version": db_schema, "fields": []}},
    }
    dto = {"core_baseline": "CB-TEST", "contracts": {}}
    artifacts: dict[str, dict[str, Any]] = {
        "CORE_LOGICAL_MODEL.json": core,
        "CROSS_LAYER_DTO_CONTRACTS.json": dto,
    }
    artifacts.update(extra or {})
    entries: list[dict[str, object]] = []
    for name, value in sorted(artifacts.items()):
        path = canonical / name
        _write_json(path, value)
        entries.append({"file": name, "sha256": _sha256(path), "bytes": path.stat().st_size})
    lock = {
        "baseline": {
            "core": "CB-TEST",
            "db_schema": db_schema,
            "rebaseline": "TEST",
            "lock_lineage_sha256": ["a" * 64],
        },
        "artifacts": entries,
    }
    _write_json(root / "BASELINE_LOCK.json", lock)
    return root


def test_authority_diff_is_deterministic_and_non_adopting(tmp_path: Path) -> None:
    reference = _authority_root(tmp_path / "reference", db_schema="1.0.0")
    candidate = _authority_root(
        tmp_path / "candidate",
        db_schema="2.0.0",
        extra={
            "NEW_AUTHORITY.json": {
                "core_baseline": "CB-TEST",
                "db_schema_version": "1.0.0",
            }
        },
    )

    first = build_report(
        reference_root=reference,
        candidate_root=candidate,
        reference_label="REFERENCE",
        candidate_label="CANDIDATE",
    )
    second = build_report(
        reference_root=reference,
        candidate_root=candidate,
        reference_label="REFERENCE",
        candidate_label="CANDIDATE",
    )

    assert first == second
    assert first["status"] == "DIFFERENT"
    assert first["adoption_state"] == "DIFF_ONLY_NOT_ADOPTED"
    assert first["summary"] == {
        "ADDED": 1,
        "REMOVED": 0,
        "MODIFIED": 1,
        "UNCHANGED": 1,
    }


def test_predecessor_authority_remains_review_required_and_unmodified() -> None:
    result = verify(PREDECESSOR_AUTHORITY)

    assert result["status"] == "REVIEW_REQUIRED"
    assert result["adoption_state"] == "NOT_ADOPTED_BY_THIS_CHECK"
    assert result["baseline"]["core"] == "CB-1.4.0"
    assert result["baseline"]["db_schema"] == "1.9.0"
    assert result["hard_failures"] == []
    finding = result["review_findings"][0]
    assert finding["code"] == ("HISTORICAL_DB_DECLARATIONS_REQUIRE_COMPATIBILITY_AUTHORITY")
    files = {item["file"] for item in finding["declarations"]}
    assert "P1_METRIC_CATALOG.json" in files
    assert "IMPORT_PROVENANCE.json" in files
    finding_codes = {item["code"] for item in result["review_findings"]}
    assert "INDEX_AUTHORITY_NOT_DECLARED" in finding_codes
    assert "API_ROUTE_AUTHORITY_NOT_DECLARED" in finding_codes


def test_w0_successor_authority_is_fully_closed() -> None:
    result = verify(CURRENT_AUTHORITY)

    assert result["status"] == "PASS"
    assert result["adoption_state"] == "APPROVED_BY_AUTHORITY_DECISION"
    assert result["baseline"]["core"] == "CB-1.5.0"
    assert result["baseline"]["db_schema"] == "1.9.0"
    assert result["baseline"]["controlled_artifact_count"] == 37
    assert result["hard_failures"] == []
    assert result["review_findings"] == []


def test_successor_explicitly_inherits_unchanged_predecessor_authorities() -> None:
    compatibility_path = (
        CURRENT_AUTHORITY / "canonical" / "SCHEMA_COMPATIBILITY_AUTHORITY.json"
    )
    compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))
    inherited = {item["file"] for item in compatibility["core_inheritance"]}

    assert len(inherited) == 27
    assert "P3_CAPABILITY_TWIN_AUTHORITY.json" in inherited
    for name in inherited:
        assert (CURRENT_AUTHORITY / "canonical" / name).read_bytes() == (
            PREDECESSOR_AUTHORITY / "canonical" / name
        ).read_bytes()


def test_frozen_authority_diff_has_required_semantic_coverage() -> None:
    report = json.loads(AUTHORITY_DIFF_EVIDENCE.read_text(encoding="utf-8"))

    assert report["semantic_coverage"] == {
        "tables": "EXPLICIT",
        "fields": "EXPLICIT",
        "enum_and_check_constraints": "EXPLICIT_FROM_FIELD_SQL",
        "indexes": "EXPLICIT_OR_REPORTED_NOT_DECLARED",
        "dto_contracts": "EXPLICIT",
        "api_transport_rules": "EXPLICIT",
        "api_routes": "EXPLICIT_OR_REPORTED_NOT_DECLARED",
    }
    assert report["candidate_governance_extensions"] == {
        "schema_compatibility": "GOVERNED_BY_SCHEMA_COMPATIBILITY_AUTHORITY",
        "indexes": "GOVERNED_BY_PHYSICAL_INDEX_AUTHORITY",
        "api_routes": "GOVERNED_BY_API_ROUTE_AUTHORITY",
        "baseline_decision": "GOVERNED_BY_W0_BASELINE_AUTHORITY_DECISION",
    }
    artifacts = {item["file"]: item for item in report["artifacts"]}
    database = artifacts["CORE_LOGICAL_MODEL.json"]["semantic_diff"]["database"]
    assert database["tables"]["summary"] == {
        "added": 18,
        "removed": 0,
        "modified": 77,
        "unchanged": 0,
    }
    assert len(database["added_table_definitions"]) == 18
    assert database["indexes"]["status"] == "NOT_DECLARED_IN_COMPARED_CORE_AUTHORITY"
    dto_api = artifacts["CROSS_LAYER_DTO_CONTRACTS.json"]["semantic_diff"]["dto_and_api"]
    assert dto_api["dto_contracts"]["summary"] == {
        "added": 31,
        "removed": 0,
        "modified": 0,
        "unchanged": 7,
    }
    assert len(dto_api["added_contract_definitions"]) == 31
    assert dto_api["api_transport_rules"]["summary"]["added"] == 3
    assert dto_api["api_routes"]["status"] == "NOT_DECLARED_IN_COMPARED_DTO_AUTHORITY"


def test_current_physical_schema_mismatch_is_a_hard_failure(tmp_path: Path) -> None:
    authority = _authority_root(tmp_path / "authority", db_schema="2.0.0")
    core_path = authority / "canonical" / "CORE_LOGICAL_MODEL.json"
    core = json.loads(core_path.read_text(encoding="utf-8"))
    core["db_schema_version"] = "1.0.0"
    _write_json(core_path, core)
    lock_path = authority / "BASELINE_LOCK.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    for entry in lock["artifacts"]:
        if entry["file"] == "CORE_LOGICAL_MODEL.json":
            entry["sha256"] = _sha256(core_path)
            entry["bytes"] = core_path.stat().st_size
    _write_json(lock_path, lock)

    result = verify(authority)

    assert result["status"] == "FAIL"
    assert any(
        finding["code"] == "CURRENT_DB_SCHEMA_MISMATCH" for finding in result["hard_failures"]
    )


def test_w0_compliance_matrix_records_local_approval_without_release_claim() -> None:
    matrix = json.loads(COMPLIANCE_MATRIX.read_text(encoding="utf-8"))

    assert matrix["schema"] == "TPAA_COMPLIANCE_MATRIX_V1"
    assert matrix["adoption_state"] == "APPROVED_LOCAL_NOT_PUSHED"
    requirements = {item["id"]: item for item in matrix["requirements"]}
    assert set(requirements) == {"W0-A", "W0-B", "W0-C", "W0-D", "W0-E", "W0-F"}
    assert requirements["W0-A"]["status"] == "CLOSED"
    assert requirements["W0-B"]["status"] == "CLOSED_PASS"
    assert requirements["W0-C"]["status"] == "CLOSED_CROSS_PLATFORM_VERIFIED"
    assert requirements["W0-D"]["status"] == "APPROVED_CLOSED"
    assert requirements["W0-E"]["status"] == "APPROVED_CLOSED"
    assert requirements["W0-F"]["status"] == "W0_SCOPE_CLOSED"
