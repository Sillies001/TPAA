"""M3-WORLD-004 mission-system product semantics and applicability inputs.

This module consumes the frozen Core mission-system identity shape and the
P1 Catalog family_applicability_contracts. It does not infer a product
capability from physical sensor type and it does not execute Metric logic.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from uuid import UUID

CORE_SCHEMA_VERSION = "1.8.0"
CORE_TABLE = "master.mission_system_instance"
CATALOG_DELIVERY_MILESTONE = "M3"
CATALOG_DELIVERY_BATCH = "P1_REMAINDER_84"
SUBJECT_TYPE = "MISSION_SYSTEM_INSTANCE"

FAMILY_CODES = (
    "P1-TRK-*",
    "P1-ID-*",
    "P1-PSV-*",
    "P1-ESM-*",
    "P1-DL-*",
    "P1-FUS-*",
)
EXPECTED_FAMILY_COUNTS = {
    "P1-TRK-*": 7,
    "P1-ID-*": 12,
    "P1-PSV-*": 7,
    "P1-ESM-*": 6,
    "P1-DL-*": 8,
    "P1-FUS-*": 8,
}
EXPECTED_PRODUCT_SEMANTICS = (
    "ASSOCIATION_IDENTIFICATION_PRODUCT",
    "LOCAL_TRACK_PRODUCT",
)
CORE_SYSTEM_TYPES = (
    "RADAR",
    "IRST",
    "EO",
    "RWR",
    "ESM",
    "DATALINK",
    "FUSION",
    "MISSION_COMPUTER",
    "OTHER",
)
CORE_STATUSES = ("ACTIVE", "INACTIVE", "RETIRED")
FIXTURE_SCHEMA = "TPAA_M3_WORLD_004_MISSION_SYSTEMS_V1"
FIXTURE_VERSION = "1.0.0"


class M3MissionProductApplicabilityError(RuntimeError):
    """Deterministic fail-closed M3-WORLD-004 error."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class M3MissionSystemSubject:
    mission_system_instance_id: str
    aircraft_id: str
    system_type: str
    system_code: str
    status: str
    configuration_hash: str
    product_semantics: tuple[str, ...]
    source_identity_ref: str


@dataclass(frozen=True)
class M3FamilyApplicabilityContract:
    family_code: str
    subject_type: str
    applicability_mode: str
    allowed_system_types: tuple[str, ...]
    required_product_semantics: str | None
    family_meaning: str
    metric_codes: tuple[str, ...]


@dataclass(frozen=True)
class M3MissionProductApplicability:
    family_code: str
    subject_type: str
    mission_system_instance_id: str
    system_type: str
    applicability_mode: str
    allowed_system_types: tuple[str, ...]
    required_product_semantics: str | None
    applicable: bool
    reason_code: str
    product_input_emitted: bool
    catalog_sha256: str
    core_schema_sha256: str
    logical_hash: str


@dataclass(frozen=True)
class M3MissionProductInputSet:
    fixture_id: str
    fixture_version: str
    fixture_sha256: str
    catalog_sha256: str
    core_schema_sha256: str
    subjects: tuple[M3MissionSystemSubject, ...]
    contracts: tuple[M3FamilyApplicabilityContract, ...]
    logical_hash: str
    metric_logic_executed: bool = False
    persistence_executed: bool = False
    publication_executed: bool = False


def _load(path: Path, code: str) -> dict[str, object]:
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise M3MissionProductApplicabilityError(
            code,
            f"{path.as_posix()}: {exc}",
        ) from exc
    if not isinstance(raw, dict) or not all(isinstance(key, str) for key in raw):
        raise M3MissionProductApplicabilityError(
            code,
            f"{path.as_posix()}: root must be string-keyed object",
        )
    return cast(dict[str, object], raw)


def _object(
    value: object,
    *,
    field: str,
    code: str = "M3_WORLD_004_AUTHORITY_INVALID",
) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise M3MissionProductApplicabilityError(
            code,
            f"{field} must be string-keyed object",
        )
    return cast(dict[str, object], value)


def _required_str(
    mapping: dict[str, object],
    key: str,
    *,
    code: str = "M3_WORLD_004_FIXTURE_INVALID",
) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise M3MissionProductApplicabilityError(
            code,
            f"{key} must be non-empty string",
        )
    return value


def _sha(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_AUTHORITY_MISSING",
            path.as_posix(),
        ) from exc


def _hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _uuid(value: str, *, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_UUID_INVALID",
            f"{field}={value!r}",
        ) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_UUID_INVALID",
            f"{field}={value!r}",
        )
    return value


def _sha256_hex(value: str, *, field: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_FIXTURE_INVALID",
            f"{field} must be lower-case SHA-256 hex",
        )
    return value


def _catalog_family_prefix(family_code: str) -> str:
    if not family_code.endswith("*"):
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_CATALOG_FAMILY_INVALID",
            family_code,
        )
    return family_code[:-1]


def _validate_authority(
    authority_root: Path,
) -> tuple[
    str,
    str,
    tuple[M3FamilyApplicabilityContract, ...],
]:
    catalog_path = authority_root / "P1_METRIC_CATALOG.json"
    core_path = authority_root / "CORE_LOGICAL_MODEL.json"
    catalog = _load(catalog_path, "M3_WORLD_004_CATALOG_INVALID")
    core = _load(core_path, "M3_WORLD_004_CORE_INVALID")

    if core.get("db_schema_version") != CORE_SCHEMA_VERSION:
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_CORE_SCHEMA_DRIFT",
            repr(core.get("db_schema_version")),
        )
    tables = _object(core.get("tables"), field="CORE_LOGICAL_MODEL.tables")
    table = _object(tables.get(CORE_TABLE), field=CORE_TABLE)
    raw_fields = table.get("fields")
    if not isinstance(raw_fields, list):
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_CORE_TABLE_INVALID",
            "fields must be list",
        )
    fields: dict[str, dict[str, object]] = {}
    for item in raw_fields:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str):
            fields[name] = cast(dict[str, object], item)
    required_fields = {
        "mission_system_instance_id",
        "aircraft_id",
        "system_type",
        "system_code",
        "status",
        "configuration_hash",
    }
    if not required_fields <= set(fields):
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_CORE_IDENTITY_DRIFT",
            repr(sorted(set(fields))),
        )
    system_sql = str(fields["system_type"].get("sql"))
    status_sql = str(fields["status"].get("sql"))
    if not all(f"'{value}'" in system_sql for value in CORE_SYSTEM_TYPES):
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_CORE_SYSTEM_ENUM_DRIFT",
            system_sql,
        )
    if not all(f"'{value}'" in status_sql for value in CORE_STATUSES):
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_CORE_STATUS_ENUM_DRIFT",
            status_sql,
        )

    raw_contracts = _object(
        catalog.get("family_applicability_contracts"),
        field="P1_METRIC_CATALOG.family_applicability_contracts",
    )
    raw_metrics = catalog.get("metrics")
    if not isinstance(raw_metrics, list):
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_CATALOG_INVALID",
            "metrics must be list",
        )
    metric_rows = [
        cast(dict[str, object], item)
        for item in raw_metrics
        if isinstance(item, dict)
    ]

    contracts: list[M3FamilyApplicabilityContract] = []
    product_semantics: set[str] = set()
    for family_code in FAMILY_CODES:
        raw = _object(raw_contracts.get(family_code), field=family_code)
        subject_type = _required_str(
            raw,
            "subject_type",
            code="M3_WORLD_004_CATALOG_INVALID",
        )
        if subject_type != SUBJECT_TYPE:
            raise M3MissionProductApplicabilityError(
                "M3_WORLD_004_SUBJECT_AUTHORITY_DRIFT",
                f"{family_code}={subject_type!r}",
            )
        mode = _required_str(
            raw,
            "applicability_mode",
            code="M3_WORLD_004_CATALOG_INVALID",
        )
        family_meaning = _required_str(
            raw,
            "family_meaning",
            code="M3_WORLD_004_CATALOG_INVALID",
        )
        allowed_raw = raw.get("allowed_system_types", [])
        if not isinstance(allowed_raw, list) or not all(
            isinstance(item, str) for item in allowed_raw
        ):
            raise M3MissionProductApplicabilityError(
                "M3_WORLD_004_CATALOG_INVALID",
                f"{family_code}.allowed_system_types",
            )
        allowed = tuple(cast(list[str], allowed_raw))
        required_product = raw.get("required_product_semantics")
        if required_product is not None and not isinstance(required_product, str):
            raise M3MissionProductApplicabilityError(
                "M3_WORLD_004_CATALOG_INVALID",
                f"{family_code}.required_product_semantics",
            )

        if mode == "PRODUCT_CAPABILITY":
            if not isinstance(required_product, str) or allowed:
                raise M3MissionProductApplicabilityError(
                    "M3_WORLD_004_PRODUCT_CONTRACT_INVALID",
                    family_code,
                )
            product_semantics.add(required_product)
        elif mode in {"SYSTEM_TYPE_EXACT", "SYSTEM_TYPE_SET"}:
            if required_product is not None or not allowed:
                raise M3MissionProductApplicabilityError(
                    "M3_WORLD_004_SYSTEM_CONTRACT_INVALID",
                    family_code,
                )
            if any(value not in CORE_SYSTEM_TYPES for value in allowed):
                raise M3MissionProductApplicabilityError(
                    "M3_WORLD_004_SYSTEM_TYPE_AUTHORITY_INVALID",
                    repr(allowed),
                )
        else:
            raise M3MissionProductApplicabilityError(
                "M3_WORLD_004_APPLICABILITY_MODE_UNSUPPORTED",
                f"{family_code}={mode}",
            )

        prefix = _catalog_family_prefix(family_code)
        family_metrics = tuple(
            sorted(
                cast(str, row["metric_code"])
                for row in metric_rows
                if isinstance(row.get("metric_code"), str)
                and cast(str, row["metric_code"]).startswith(prefix)
                and row.get("delivery_milestone") == CATALOG_DELIVERY_MILESTONE
                and row.get("delivery_batch") == CATALOG_DELIVERY_BATCH
                and row.get("subject_type") == SUBJECT_TYPE
            )
        )
        if len(family_metrics) != EXPECTED_FAMILY_COUNTS[family_code]:
            raise M3MissionProductApplicabilityError(
                "M3_WORLD_004_FAMILY_MEMBERSHIP_DRIFT",
                f"{family_code}={len(family_metrics)}",
            )
        contracts.append(
            M3FamilyApplicabilityContract(
                family_code=family_code,
                subject_type=subject_type,
                applicability_mode=mode,
                allowed_system_types=allowed,
                required_product_semantics=required_product,
                family_meaning=family_meaning,
                metric_codes=family_metrics,
            )
        )

    if tuple(sorted(product_semantics)) != EXPECTED_PRODUCT_SEMANTICS:
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_PRODUCT_SEMANTICS_DRIFT",
            repr(sorted(product_semantics)),
        )

    return _sha(catalog_path), _sha(core_path), tuple(contracts)


def load_m3_mission_product_inputs(
    fixture_path: Path,
    *,
    authority_root: Path,
) -> M3MissionProductInputSet:
    """Load synthetic M3 mission-system inputs under frozen Catalog/Core authority."""

    catalog_sha256, core_sha256, contracts = _validate_authority(authority_root)
    fixture = _load(fixture_path, "M3_WORLD_004_FIXTURE_INVALID")
    if fixture.get("schema") != FIXTURE_SCHEMA:
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_FIXTURE_SCHEMA_MISMATCH",
            repr(fixture.get("schema")),
        )
    if fixture.get("fixture_version") != FIXTURE_VERSION:
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_FIXTURE_VERSION_MISMATCH",
            repr(fixture.get("fixture_version")),
        )
    if fixture.get("data_classification") != "SYNTHETIC":
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_CLASSIFICATION_FORBIDDEN",
            repr(fixture.get("data_classification")),
        )

    raw_subjects = fixture.get("mission_system_instances")
    if not isinstance(raw_subjects, list) or not raw_subjects:
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_FIXTURE_INVALID",
            "mission_system_instances must be non-empty list",
        )
    subjects: list[M3MissionSystemSubject] = []
    for index, raw in enumerate(raw_subjects):
        row = _object(
            raw,
            field=f"mission_system_instances[{index}]",
            code="M3_WORLD_004_FIXTURE_INVALID",
        )
        system_type = _required_str(row, "system_type")
        if system_type not in CORE_SYSTEM_TYPES:
            raise M3MissionProductApplicabilityError(
                "M3_WORLD_004_CORE_SYSTEM_TYPE_INVALID",
                system_type,
            )
        status = _required_str(row, "status")
        if status not in CORE_STATUSES:
            raise M3MissionProductApplicabilityError(
                "M3_WORLD_004_CORE_STATUS_INVALID",
                status,
            )
        raw_products = row.get("product_semantics")
        if not isinstance(raw_products, list) or not all(
            isinstance(item, str) for item in raw_products
        ):
            raise M3MissionProductApplicabilityError(
                "M3_WORLD_004_FIXTURE_INVALID",
                f"mission_system_instances[{index}].product_semantics",
            )
        products = tuple(sorted(cast(list[str], raw_products)))
        if len(products) != len(set(products)):
            raise M3MissionProductApplicabilityError(
                "M3_WORLD_004_PRODUCT_SEMANTICS_DUPLICATE",
                repr(products),
            )
        unknown = sorted(set(products) - set(EXPECTED_PRODUCT_SEMANTICS))
        if unknown:
            raise M3MissionProductApplicabilityError(
                "M3_WORLD_004_PRODUCT_SEMANTICS_UNGOVERNED",
                repr(unknown),
            )
        subjects.append(
            M3MissionSystemSubject(
                mission_system_instance_id=_uuid(
                    _required_str(row, "mission_system_instance_id"),
                    field="mission_system_instance_id",
                ),
                aircraft_id=_uuid(
                    _required_str(row, "aircraft_id"),
                    field="aircraft_id",
                ),
                system_type=system_type,
                system_code=_required_str(row, "system_code"),
                status=status,
                configuration_hash=_sha256_hex(
                    _required_str(row, "configuration_hash"),
                    field="configuration_hash",
                ),
                product_semantics=products,
                source_identity_ref=_required_str(row, "source_identity_ref"),
            )
        )

    identities = [subject.mission_system_instance_id for subject in subjects]
    if len(identities) != len(set(identities)):
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_IDENTITY_DUPLICATE",
            repr(identities),
        )

    fixture_hash = _sha(fixture_path)
    logical = {
        "fixture_id": _required_str(fixture, "fixture_id"),
        "fixture_version": FIXTURE_VERSION,
        "fixture_sha256": fixture_hash,
        "catalog_sha256": catalog_sha256,
        "core_schema_sha256": core_sha256,
        "subjects": [
            {
                "mission_system_instance_id": subject.mission_system_instance_id,
                "aircraft_id": subject.aircraft_id,
                "system_type": subject.system_type,
                "system_code": subject.system_code,
                "status": subject.status,
                "configuration_hash": subject.configuration_hash,
                "product_semantics": subject.product_semantics,
                "source_identity_ref": subject.source_identity_ref,
            }
            for subject in subjects
        ],
        "contracts": [
            {
                "family_code": contract.family_code,
                "subject_type": contract.subject_type,
                "applicability_mode": contract.applicability_mode,
                "allowed_system_types": contract.allowed_system_types,
                "required_product_semantics": contract.required_product_semantics,
                "metric_codes": contract.metric_codes,
            }
            for contract in contracts
        ],
    }
    return M3MissionProductInputSet(
        fixture_id=_required_str(fixture, "fixture_id"),
        fixture_version=FIXTURE_VERSION,
        fixture_sha256=fixture_hash,
        catalog_sha256=catalog_sha256,
        core_schema_sha256=core_sha256,
        subjects=tuple(subjects),
        contracts=contracts,
        logical_hash=_hash(logical),
    )


def project_m3_family_applicability(
    inputs: M3MissionProductInputSet,
    *,
    family_code: str,
    mission_system_instance_id: str,
) -> M3MissionProductApplicability:
    """Project one family applicability decision without creating fake observations."""

    contracts = {
        contract.family_code: contract
        for contract in inputs.contracts
    }
    contract = contracts.get(family_code)
    if contract is None:
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_FAMILY_NOT_GOVERNED",
            family_code,
        )
    subjects = {
        subject.mission_system_instance_id: subject
        for subject in inputs.subjects
    }
    subject = subjects.get(mission_system_instance_id)
    if subject is None:
        raise M3MissionProductApplicabilityError(
            "M3_WORLD_004_SUBJECT_NOT_FOUND",
            mission_system_instance_id,
        )

    if contract.applicability_mode == "PRODUCT_CAPABILITY":
        required = contract.required_product_semantics
        if required is None:
            raise M3MissionProductApplicabilityError(
                "M3_WORLD_004_PRODUCT_CONTRACT_INVALID",
                family_code,
            )
        applicable = required in subject.product_semantics
        reason_code = (
            "APPLICABLE_PRODUCT_CAPABILITY"
            if applicable
            else "NOT_APPLICABLE_PRODUCT_CAPABILITY_MISSING"
        )
    else:
        applicable = subject.system_type in contract.allowed_system_types
        reason_code = (
            "APPLICABLE_SYSTEM_TYPE"
            if applicable
            else "NOT_APPLICABLE_SYSTEM_TYPE"
        )

    logical = {
        "family_code": contract.family_code,
        "subject_type": contract.subject_type,
        "mission_system_instance_id": subject.mission_system_instance_id,
        "system_type": subject.system_type,
        "applicability_mode": contract.applicability_mode,
        "allowed_system_types": contract.allowed_system_types,
        "required_product_semantics": contract.required_product_semantics,
        "applicable": applicable,
        "reason_code": reason_code,
        "product_input_emitted": applicable,
        "catalog_sha256": inputs.catalog_sha256,
        "core_schema_sha256": inputs.core_schema_sha256,
    }
    return M3MissionProductApplicability(
        family_code=contract.family_code,
        subject_type=contract.subject_type,
        mission_system_instance_id=subject.mission_system_instance_id,
        system_type=subject.system_type,
        applicability_mode=contract.applicability_mode,
        allowed_system_types=contract.allowed_system_types,
        required_product_semantics=contract.required_product_semantics,
        applicable=applicable,
        reason_code=reason_code,
        product_input_emitted=applicable,
        catalog_sha256=inputs.catalog_sha256,
        core_schema_sha256=inputs.core_schema_sha256,
        logical_hash=_hash(logical),
    )
