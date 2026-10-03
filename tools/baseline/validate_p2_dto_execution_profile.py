#!/usr/bin/env python3
"""Validate the M6 P2 cross-layer DTO and execution-profile C3 closure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import cast
from uuid import NAMESPACE_URL, UUID, uuid5

REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE = REPO_ROOT / "baseline" / "CB-1.4.0"
CANONICAL = BASELINE / "canonical"
DTO = CANONICAL / "CROSS_LAYER_DTO_CONTRACTS.json"
PROFILE = CANONICAL / "P2_LINEAR_REFERENCE_ADJUSTMENT_PROFILE.json"
AUTHORITY = CANONICAL / "P2_ATTRIBUTION_NORMALIZATION_AUTHORITY.json"
CORE = CANONICAL / "CORE_LOGICAL_MODEL.json"
LOCK = BASELINE / "BASELINE_LOCK.json"

EXPECTED_DTO_SHA256 = "9d94f75031afcbfe2391bed1245c3f8d95f124a6549a8f116aa1efb879ae45b4"
EXPECTED_P2_DTO_SUBSET_SHA256 = "d79d97eb41354ad61654372310bb1a92b37914a858213f5dfc4a1287e14c6706"
EXPECTED_M6_LOCK_SHA256 = "f95167aca59dc993ced607e55f21f01080c4e24cc0759bf97482d49654ea182b"
EXPECTED_PROFILE_SHA256 = (
    "202e255bd09349407e0e7cc4d77d8b848df99d84dc00e50e46871eb4f82f0d68"
)
EXPECTED_PARENT_LOCK_SHA256 = (
    "7eafadbb1d47297688595a8a0c48d4836dad13e040f76340ce2c0fa38a5547fa"
)
EXPECTED_CONTRACT_HASHES = {
    "runtime_binding_sha256": (
        "5e30333a9967f235a8b3bc8ce482d9b77074a1f5eb1d49f37ee8f2259979641c"
    ),
    "eligibility_sha256": (
        "c6e121fcf6f63169affbe7fff3528a25b161c294a774278ddf68fabf107e510c"
    ),
    "ordering_sha256": (
        "0ebaee36be8a673281274fc0c371d97c06dd0105ed9dce149d9e7b97a69656fa"
    ),
    "subject_balancing_sha256": (
        "16b51aba4a6f815cb46a5002090f28205773a76222257e7dd32f47787e84213f"
    ),
    "arithmetic_sha256": (
        "b8c03436b97c2b665dbea8155085769e53681b337c832861a04ffa830aaf8d22"
    ),
    "scaling_sha256": (
        "a20c1ad3493621aa38c0d64e03879817e822b18fb96719ace1687b2240f93324"
    ),
    "solver_sha256": (
        "66076eda5914787090912be310ca126dfb40dae207af313346b28e055b53e4ba"
    ),
    "support_sha256": (
        "125259622b1b5f98d6103ee46f551996329058b9f9b206bd439cd57a6622fb53"
    ),
    "adjustment_sha256": (
        "87b461894d807386eaee4baad0cb9c50c3299e1720a4f1069c066752ff66dd06"
    ),
    "uncertainty_sha256": (
        "f7cd453c2563683ab0e0196cd47c661847d5971265ff61b5d9d0131e22064568"
    ),
    "identifiability_sha256": (
        "b69367874828b5363b1690cef6347512f7d9ed8d867d730f36f4a7ff462e8538"
    ),
    "artifact_replay_sha256": (
        "0c3542f5ba5207003ccdca0e5c51bccda939cac828add58d13a2f0467fcb0633"
    ),
    "identity_sha256": (
        "3dc5959593560734db46371d52422a06adb5ba3fa667f5c75e063852967a27a7"
    ),
}
P2_DTO_NAMES = (
    "P2EligibleObservationDTO",
    "FactorFeatureSetDTO",
    "AttributionRunDTO",
    "AdjustedCapabilityEstimateDTO",
    "P2AdmissionStateDTO",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_object(path: Path) -> dict[str, object]:
    value: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{path.name} root must be object")
    return cast(dict[str, object], value)


def _obj(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{context} must be object")
    return cast(dict[str, object], value)


def _list(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be list")
    return cast(list[object], value)


def _text(value: object, context: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context} must be non-empty string")
    return value


def _canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


def _p2_dto_subset_hash(dto_contracts: dict[str, object]) -> str:
    subset = {
        name: _obj(dto_contracts.get(name), f"dto.{name}")
        for name in P2_DTO_NAMES
    }
    return _canonical_hash(subset)


def _lineage_preserves_m6(
    *,
    current_lock_sha256: str,
    lineage: list[object],
) -> bool:
    values = [_text(value, "lock.lineage") for value in lineage]
    if current_lock_sha256 == EXPECTED_M6_LOCK_SHA256:
        return bool(values) and values[0] == EXPECTED_PARENT_LOCK_SHA256
    try:
        index = values.index(EXPECTED_M6_LOCK_SHA256)
    except ValueError:
        return False
    return (
        index + 1 < len(values)
        and values[index + 1] == EXPECTED_PARENT_LOCK_SHA256
    )


def _lock_entry(lock: dict[str, object], filename: str) -> dict[str, object]:
    for raw in _list(lock.get("artifacts"), "lock.artifacts"):
        entry = _obj(raw, "lock artifact")
        if entry.get("file") == filename:
            return entry
    raise ValueError(f"{filename} missing from BASELINE_LOCK")


def _dto_field_names(contract: object, name: str) -> list[str]:
    obj = _obj(contract, name)
    result: list[str] = []
    for raw in _list(obj.get("fields"), f"{name}.fields"):
        field = _obj(raw, f"{name}.field")
        result.append(_text(field.get("field"), f"{name}.field.name"))
    return result


def _dto_field(contract: object, name: str, field_name: str) -> dict[str, object]:
    obj = _obj(contract, name)
    for raw in _list(obj.get("fields"), f"{name}.fields"):
        field = _obj(raw, f"{name}.field")
        if field.get("field") == field_name:
            return field
    raise ValueError(f"{name}.{field_name} missing")


def _core_field(
    tables: dict[str, object],
    table_name: str,
    field_name: str,
) -> dict[str, object]:
    table = _obj(tables.get(table_name), table_name)
    for raw in _list(table.get("fields"), f"{table_name}.fields"):
        field = _obj(raw, f"{table_name}.field")
        if field.get("name") == field_name:
            return field
    raise ValueError(f"{table_name}.{field_name} missing")


def verify() -> dict[str, object]:
    dto = _json_object(DTO)
    profile = _json_object(PROFILE)
    authority = _json_object(AUTHORITY)
    core = _json_object(CORE)
    lock = _json_object(LOCK)

    dto_entry = _lock_entry(lock, "CROSS_LAYER_DTO_CONTRACTS.json")
    profile_entry = _lock_entry(
        lock,
        "P2_LINEAR_REFERENCE_ADJUSTMENT_PROFILE.json",
    )
    baseline = _obj(lock.get("baseline"), "lock.baseline")
    lineage = _list(
        baseline.get("lock_lineage_sha256"),
        "lock.baseline.lock_lineage_sha256",
    )

    dto_contracts = _obj(dto.get("contracts"), "dto.contracts")
    authority_dtos = _obj(authority.get("dto_contracts"), "authority.dto_contracts")
    core_tables = _obj(core.get("tables"), "core.tables")

    current_dto_sha256 = _sha256(DTO)
    current_lock_sha256 = _sha256(LOCK)
    checks: dict[str, bool] = {
        "dto_hash": (
            _p2_dto_subset_hash(dto_contracts) == EXPECTED_P2_DTO_SUBSET_SHA256
        ),
        "profile_hash": _sha256(PROFILE) == EXPECTED_PROFILE_SHA256,
        "dto_lock_binding": (
            dto_entry.get("sha256") == current_dto_sha256
            and dto_entry.get("bytes") == len(DTO.read_bytes())
        ),
        "profile_lock_binding": (
            profile_entry.get("sha256") == EXPECTED_PROFILE_SHA256
            and profile_entry.get("bytes") == len(PROFILE.read_bytes())
        ),
        "controlled_count": len(_list(lock.get("artifacts"), "lock.artifacts")) >= 26,
        "schema_unchanged": baseline.get("db_schema") in {"1.6.0", "1.7.0"},
        "lineage_parent": _lineage_preserves_m6(
            current_lock_sha256=current_lock_sha256,
            lineage=lineage,
        ),
        "profile_identity": (
            profile.get("profile_id") == "P2_LINEAR_REFERENCE_ADJUSTMENT"
            and profile.get("version") == "1.0.0"
            and profile.get("db_schema_version") == "1.6.0"
            and profile.get("tracking_issue") == 161
        ),
    }

    for name in P2_DTO_NAMES:
        central_names = _dto_field_names(dto_contracts.get(name), name)
        authority_contract = _obj(authority_dtos.get(name), f"authority.{name}")
        authority_names = [
            _text(value, f"authority.{name}.field")
            for value in _list(authority_contract.get("fields"), f"authority.{name}.fields")
        ]
        checks[f"dto_fields:{name}"] = central_names == authority_names

    eligible = dto_contracts.get("P2EligibleObservationDTO")
    semantic = _dto_field(
        eligible,
        "P2EligibleObservationDTO",
        "metric_semantic_version",
    )
    observed = _dto_field(
        eligible,
        "P2EligibleObservationDTO",
        "observed_value",
    )
    knowledge = _dto_field(
        eligible,
        "P2EligibleObservationDTO",
        "knowledge_time_utc",
    )
    checks.update(
        {
            "semantic_version_transport_integer": (
                semantic.get("transport_type") == "integer"
            ),
            "numeric_observed_value": observed.get("transport_type") == "number",
            "knowledge_time_release_published": (
                knowledge.get("source")
                == (
                    "metric.capability_observation.release_id -> "
                    "registry.analysis_release.published_at"
                )
            ),
            "core_semantic_version_integer": (
                _core_field(
                    core_tables,
                    "metric.metric_definition",
                    "metric_semantic_version",
                ).get("type")
                == "integer"
            ),
            "core_adjusted_value_nullable": (
                _core_field(
                    core_tables,
                    "capability.adjusted_capability_estimate",
                    "adjusted_value",
                ).get("nullable")
                is True
            ),
        }
    )

    runtime = _obj(profile.get("runtime_binding"), "profile.runtime_binding")
    arithmetic = _obj(profile.get("arithmetic_contract"), "profile.arithmetic")
    solver = _obj(profile.get("solver_contract"), "profile.solver")
    uncertainty = _obj(profile.get("uncertainty_contract"), "profile.uncertainty")
    identity = _obj(profile.get("identity_contract"), "profile.identity")
    activation = _obj(profile.get("activation_rule"), "profile.activation")
    source = _obj(profile.get("source_bindings"), "profile.source_bindings")

    artifact_kind_field = _core_field(
        core_tables,
        "registry.context_artifact",
        "artifact_kind",
    )
    artifact_kind_sql = _text(
        artifact_kind_field.get("sql"),
        "registry.context_artifact.artifact_kind.sql",
    )
    checks.update(
        {
            "profile_dto_binding": (
                source.get("cross_layer_dto_sha256") == EXPECTED_DTO_SHA256
            ),
            "runtime_kind_supported": (
                runtime.get("artifact_kind") == "ASSESSMENT_PROFILE"
                and "'ASSESSMENT_PROFILE'" in artifact_kind_sql
            ),
            "runtime_exact_spec": (
                runtime.get("attribution_spec_id")
                == "P2_ATTRIBUTION_SPEC:P2_LINEAR_REFERENCE_ADJUSTMENT"
                and runtime.get("model_plugin") == "LINEAR_REFERENCE_ADJUSTMENT"
                and runtime.get("model_plugin_version") == "1.0.0"
                and runtime.get("exact_identity_only") is True
            ),
            "decimal_contract": (
                arithmetic.get("backend") == "PYTHON_DECIMAL"
                and arithmetic.get("decimal_precision") == 50
                and arithmetic.get("rounding_mode") == "ROUND_HALF_EVEN"
                and arithmetic.get("output_quantum") == "1E-12"
            ),
            "solver_contract": (
                solver.get("algorithm") == "DECIMAL_MODIFIED_GRAM_SCHMIDT_QR2"
                and solver.get("rank_ratio_minimum") == "1E-10"
                and solver.get("regularization_forbidden") is True
            ),
            "jackknife_contract": (
                uncertainty.get("method")
                == "JACKKNIFE_LEAVE_ONE_INDEPENDENT_SUBJECT_OUT"
                and uncertainty.get("level") == "0.95"
                and uncertainty.get("z_value") == "1.959963984540054"
            ),
            "profile_does_not_admit_p2": (
                activation.get("profile_adoption_does_not_admit_p2") is True
                and activation.get("p3_p6_active") is False
            ),
        }
    )

    namespace_url = _text(identity.get("namespace_url"), "identity.namespace_url")
    checks["namespace_url"] = namespace_url == str(NAMESPACE_URL)
    for name in ("factor_feature_set", "attribution_run", "adjusted_estimate"):
        section = _obj(identity.get(name), f"identity.{name}")
        urn = _text(section.get("urn"), f"identity.{name}.urn")
        namespace = _text(
            section.get("namespace_uuid"),
            f"identity.{name}.namespace_uuid",
        )
        checks[f"namespace:{name}"] = (
            str(uuid5(NAMESPACE_URL, urn)) == namespace
            and UUID(namespace).int != 0
        )

    section_map = {
        "runtime_binding_sha256": "runtime_binding",
        "eligibility_sha256": "eligibility_contract",
        "ordering_sha256": "ordering_contract",
        "subject_balancing_sha256": "subject_balancing_contract",
        "arithmetic_sha256": "arithmetic_contract",
        "scaling_sha256": "scaling_contract",
        "solver_sha256": "solver_contract",
        "support_sha256": "support_contract",
        "adjustment_sha256": "adjustment_contract",
        "uncertainty_sha256": "uncertainty_contract",
        "identifiability_sha256": "identifiability_contract",
        "artifact_replay_sha256": "artifact_replay_contract",
        "identity_sha256": "identity_contract",
    }
    hashes = _obj(profile.get("contract_hashes"), "profile.contract_hashes")
    for hash_name, section_name in section_map.items():
        expected = EXPECTED_CONTRACT_HASHES[hash_name]
        actual = _canonical_hash(profile.get(section_name))
        checks[f"hash:{hash_name}"] = (
            hashes.get(hash_name) == expected and actual == expected
        )

    failed = sorted(name for name, ok in checks.items() if not ok)
    return {
        "schema": "TPAA_M6_C3_P2_DTO_EXECUTION_PROFILE_EVIDENCE_V1",
        "tracking_issue": 161,
        "status": "PASS" if not failed else "FAIL",
        "dto_sha256": EXPECTED_DTO_SHA256,
        "current_dto_sha256": current_dto_sha256,
        "p2_dto_subset_sha256": EXPECTED_P2_DTO_SUBSET_SHA256,
        "profile_sha256": EXPECTED_PROFILE_SHA256,
        "checks": checks,
        "failed_checks": failed,
        "task_complete": False,
        "completion_gate": "EXACT_HEAD_AND_PROTECTED_MAIN_HOSTED_CI_REQUIRED",
    }


def main() -> int:
    try:
        result = verify()
    except Exception as exc:
        result = {
            "schema": "TPAA_M6_C3_P2_DTO_EXECUTION_PROFILE_EVIDENCE_V1",
            "tracking_issue": 161,
            "status": "FAIL",
            "task_complete": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
