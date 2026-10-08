"""Strict ED-2.0 production P1 request boundary.

This module converts JSON-safe Job payloads into the exact Catalog input and
Mission-System identity contracts required by production P1.  It never reads
fixtures, never guesses a subject identity and never silently drops a Metric.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from tpaa_ingest import (
    ProductionFlightJsonAdapter,
    ProductionInterchangeJsonAdapter,
    ProductionSourceAdapterError,
    SourceAdapter,
    SourceFamily,
    validate_production_flight_document,
    validate_production_interchange_document,
)

from .production_p1_catalog import ProductionP1CatalogContract
from .production_p1_materialization import ProductionP1SystemBinding


class ProductionP1RequestError(RuntimeError):
    """Fail-closed P1 request validation error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class ProductionP1SystemAuthority:
    mission_system_instance_id: str
    aircraft_id: str
    system_type: str
    system_code: str
    hardware_version: str | None
    software_version: str | None
    installation_id: str | None
    alignment_profile_version: str | None
    status: str
    configuration_hash: str
    reference_truth_profile_version: str | None
    reference_quality_status: str
    reference_uncertainty_summary: dict[str, object]
    alignment_uncertainty_summary: dict[str, object]
    context_tags: dict[str, object]

    def publication_binding(self) -> ProductionP1SystemBinding:
        return ProductionP1SystemBinding(
            mission_system_instance_id=self.mission_system_instance_id,
            aircraft_id=self.aircraft_id,
            reference_truth_profile_version=self.reference_truth_profile_version,
            reference_quality_status=self.reference_quality_status,
            reference_uncertainty_summary=self.reference_uncertainty_summary,
            alignment_uncertainty_summary=self.alignment_uncertainty_summary,
            context_tags=self.context_tags,
        )


@dataclass(frozen=True, slots=True)
class ProductionP1Request:
    inputs: dict[str, dict[str, object]]
    system_authorities: tuple[ProductionP1SystemAuthority, ...]
    system_bindings: dict[str, ProductionP1SystemBinding]


@dataclass(frozen=True, slots=True)
class ProductionP1SourceRef:
    source_family: SourceFamily
    source_id: str
    artifact_id: str
    artifact_sha256: str
    adapter_id: str
    adapter_version: str
    source_ref: str
    metric_input_hashes: dict[str, str]


@dataclass(frozen=True, slots=True)
class ProductionP1SourceSelection:
    flight_payload: dict[str, object]
    source_count: int
    session_id: str
    refs_by_family: dict[SourceFamily, tuple[ProductionP1SourceRef, ...]]


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or not all(
        isinstance(key, str) for key in value
    ):
        raise ProductionP1RequestError(
            "ED2_P1_REQUEST_MAPPING_INVALID",
            field,
        )
    return dict(cast(Mapping[str, object], value))


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ProductionP1RequestError(
            "ED2_P1_REQUEST_TEXT_INVALID",
            field,
        )
    return value


def _optional_text(value: object, *, field: str) -> str | None:
    if value is None:
        return None
    return _text(value, field=field)


def _uuid(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    try:
        parsed = UUID(text)
    except ValueError as exc:
        raise ProductionP1RequestError(
            "ED2_P1_REQUEST_UUID_INVALID",
            field,
        ) from exc
    if parsed.int == 0 or str(parsed) != text:
        raise ProductionP1RequestError(
            "ED2_P1_REQUEST_UUID_INVALID",
            field,
        )
    return text


def _canonical_input_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


def _metric_input_hashes(
    value: object,
    *,
    field: str,
) -> dict[str, str]:
    raw = _mapping(value, field=field)
    return {
        metric_code: _hash64(
            digest,
            field=f"{field}.{metric_code}",
        )
        for metric_code, digest in raw.items()
    }


def _hash64(value: object, *, field: str) -> str:
    text = _text(value, field=field)
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ProductionP1RequestError(
            "ED2_P1_REQUEST_HASH_INVALID",
            field,
        )
    return text


def _system_authority(
    system_id: str,
    raw: object,
    *,
    aircraft_id: str,
    allowed_system_types: tuple[str, ...],
) -> ProductionP1SystemAuthority:
    item = _mapping(raw, field=f"mission_system_instances.{system_id}")
    identity = _uuid(
        item.get("mission_system_instance_id"),
        field=f"{system_id}.mission_system_instance_id",
    )
    if identity != system_id:
        raise ProductionP1RequestError(
            "ED2_P1_SYSTEM_AUTHORITY_ID_DRIFT",
            system_id,
        )
    bound_aircraft = _uuid(
        item.get("aircraft_id"),
        field=f"{system_id}.aircraft_id",
    )
    if bound_aircraft != aircraft_id:
        raise ProductionP1RequestError(
            "ED2_P1_SYSTEM_AIRCRAFT_SCOPE_DRIFT",
            system_id,
        )
    system_type = _text(
        item.get("system_type"),
        field=f"{system_id}.system_type",
    )
    if system_type not in allowed_system_types:
        raise ProductionP1RequestError(
            "ED2_P1_SYSTEM_TYPE_INVALID",
            f"{system_id}:{system_type}",
        )
    status = _text(item.get("status"), field=f"{system_id}.status")
    if status not in {"ACTIVE", "INACTIVE", "RETIRED"}:
        raise ProductionP1RequestError(
            "ED2_P1_SYSTEM_STATUS_INVALID",
            f"{system_id}:{status}",
        )
    return ProductionP1SystemAuthority(
        mission_system_instance_id=system_id,
        aircraft_id=bound_aircraft,
        system_type=system_type,
        system_code=_text(
            item.get("system_code"),
            field=f"{system_id}.system_code",
        ),
        hardware_version=_optional_text(
            item.get("hardware_version"),
            field=f"{system_id}.hardware_version",
        ),
        software_version=_optional_text(
            item.get("software_version"),
            field=f"{system_id}.software_version",
        ),
        installation_id=_optional_text(
            item.get("installation_id"),
            field=f"{system_id}.installation_id",
        ),
        alignment_profile_version=_optional_text(
            item.get("alignment_profile_version"),
            field=f"{system_id}.alignment_profile_version",
        ),
        status=status,
        configuration_hash=_hash64(
            item.get("configuration_hash"),
            field=f"{system_id}.configuration_hash",
        ),
        reference_truth_profile_version=_optional_text(
            item.get("reference_truth_profile_version"),
            field=f"{system_id}.reference_truth_profile_version",
        ),
        reference_quality_status=_text(
            item.get("reference_quality_status"),
            field=f"{system_id}.reference_quality_status",
        ),
        reference_uncertainty_summary=_mapping(
            item.get("reference_uncertainty_summary"),
            field=f"{system_id}.reference_uncertainty_summary",
        ),
        alignment_uncertainty_summary=_mapping(
            item.get("alignment_uncertainty_summary"),
            field=f"{system_id}.alignment_uncertainty_summary",
        ),
        context_tags=_mapping(
            item.get("context_tags"),
            field=f"{system_id}.context_tags",
        ),
    )


def parse_production_p1_request(
    payload: Mapping[str, object],
    *,
    contract: ProductionP1CatalogContract,
    aircraft_id: str,
    source_selection: ProductionP1SourceSelection,
) -> ProductionP1Request:
    """Validate and normalize exact-116 Catalog inputs plus system authority."""

    input_root = _mapping(
        payload.get("p1_catalog_inputs"),
        field="p1_catalog_inputs",
    )
    expected_codes = set(contract.metric_codes)
    observed_codes = set(input_root)
    if observed_codes != expected_codes:
        raise ProductionP1RequestError(
            "ED2_P1_INPUT_MEMBERSHIP_INCOMPLETE",
            (
                f"missing={sorted(expected_codes - observed_codes)!r};"
                f"extra={sorted(observed_codes - expected_codes)!r}"
            ),
        )
    inputs = {
        code: _mapping(input_root[code], field=f"p1_catalog_inputs.{code}")
        for code in contract.metric_codes
    }

    lineage_root = _mapping(
        payload.get("metric_input_source_families"),
        field="metric_input_source_families",
    )
    if set(lineage_root) != expected_codes:
        raise ProductionP1RequestError(
            "ED2_P1_SOURCE_LINEAGE_MEMBERSHIP_INVALID",
            (
                f"missing={sorted(expected_codes - set(lineage_root))!r};"
                f"extra={sorted(set(lineage_root) - expected_codes)!r}"
            ),
        )
    required_by_family: dict[str, frozenset[SourceFamily]] = {
        "REFERENCE_TRUTH": frozenset(
            {
                SourceFamily.FLIGHT,
                SourceFamily.RANGE_ACMI,
                SourceFamily.SCENARIO,
            }
        ),
        "TIME_ALIGNMENT": frozenset(
            {
                SourceFamily.FLIGHT,
                SourceFamily.RANGE_ACMI,
                SourceFamily.SCENARIO,
            }
        ),
        "AIRCRAFT_FLIGHT": frozenset(
            {SourceFamily.FLIGHT, SourceFamily.SCENARIO}
        ),
        "AIRCRAFT_ENERGY": frozenset(
            {SourceFamily.FLIGHT, SourceFamily.SCENARIO}
        ),
        "AIRCRAFT_CONTROL_RESPONSE": frozenset(
            {SourceFamily.FLIGHT, SourceFamily.SCENARIO}
        ),
        "AIRCRAFT_HANDLING": frozenset(
            {SourceFamily.FLIGHT, SourceFamily.SCENARIO}
        ),
        "AIRCRAFT_PERSISTENCE": frozenset(
            {SourceFamily.FLIGHT, SourceFamily.SCENARIO}
        ),
        "SENSOR_DETECTION": frozenset(
            {
                SourceFamily.MISSION_AVIONICS,
                SourceFamily.RANGE_ACMI,
                SourceFamily.SCENARIO,
            }
        ),
        "SENSOR_ACCURACY": frozenset(
            {
                SourceFamily.MISSION_AVIONICS,
                SourceFamily.RANGE_ACMI,
                SourceFamily.SCENARIO,
            }
        ),
        "TRACK_PERFORMANCE": frozenset(
            {
                SourceFamily.MISSION_AVIONICS,
                SourceFamily.RANGE_ACMI,
                SourceFamily.SCENARIO,
            }
        ),
        "ASSOCIATION_IDENTIFICATION": frozenset(
            {
                SourceFamily.MISSION_AVIONICS,
                SourceFamily.RANGE_ACMI,
                SourceFamily.SCENARIO,
            }
        ),
        "PASSIVE_SENSOR": frozenset(
            {
                SourceFamily.MISSION_AVIONICS,
                SourceFamily.RANGE_ACMI,
                SourceFamily.SCENARIO,
            }
        ),
        "RWR_ESM": frozenset(
            {
                SourceFamily.MISSION_AVIONICS,
                SourceFamily.RANGE_ACMI,
                SourceFamily.SCENARIO,
            }
        ),
        "DATALINK": frozenset(
            {
                SourceFamily.TDL,
                SourceFamily.RANGE_ACMI,
                SourceFamily.SCENARIO,
            }
        ),
        "SENSOR_FUSION": frozenset(
            {
                SourceFamily.MISSION_AVIONICS,
                SourceFamily.RANGE_ACMI,
                SourceFamily.SCENARIO,
            }
        ),
    }
    definition_by_code = {
        definition.metric_code: definition
        for definition in contract.plan.definitions
    }
    for code in contract.metric_codes:
        raw_families = lineage_root[code]
        if (
            not isinstance(raw_families, Sequence)
            or isinstance(raw_families, (str, bytes))
            or not raw_families
            or not all(isinstance(item, str) for item in raw_families)
        ):
            raise ProductionP1RequestError(
                "ED2_P1_SOURCE_LINEAGE_INVALID",
                code,
            )
        families: list[SourceFamily] = []
        for raw_family in cast(Sequence[str], raw_families):
            try:
                family = SourceFamily(raw_family)
            except ValueError as exc:
                raise ProductionP1RequestError(
                    "ED2_P1_SOURCE_LINEAGE_FAMILY_UNSUPPORTED",
                    f"{code}:{raw_family}",
                ) from exc
            if family in families:
                raise ProductionP1RequestError(
                    "ED2_P1_SOURCE_LINEAGE_DUPLICATE",
                    f"{code}:{family.value}",
                )
            if not source_selection.refs_by_family.get(family):
                raise ProductionP1RequestError(
                    "ED2_P1_SOURCE_LINEAGE_UNREGISTERED",
                    f"{code}:{family.value}",
                )
            families.append(family)

        definition = definition_by_code[code]
        required = required_by_family.get(definition.family)
        if required is None:
            raise ProductionP1RequestError(
                "ED2_P1_SOURCE_LINEAGE_POLICY_MISSING",
                definition.family,
            )
        if not required.issubset(set(families)):
            raise ProductionP1RequestError(
                "ED2_P1_SOURCE_LINEAGE_INSUFFICIENT",
                (
                    f"{code}:required="
                    f"{sorted(item.value for item in required)!r}:"
                    f"actual={sorted(item.value for item in families)!r}"
                ),
            )
        if "_source_lineage" in inputs[code]:
            raise ProductionP1RequestError(
                "ED2_P1_SOURCE_LINEAGE_OVERRIDE_FORBIDDEN",
                code,
            )
        base_input_hash = _canonical_input_hash(inputs[code])
        for family in families:
            if family is SourceFamily.FLIGHT:
                continue
            claims = [
                ref.metric_input_hashes[code]
                for ref in source_selection.refs_by_family[family]
                if code in ref.metric_input_hashes
            ]
            if not claims:
                raise ProductionP1RequestError(
                    "ED2_P1_SOURCE_INPUT_BINDING_MISSING",
                    f"{code}:{family.value}",
                )
            if any(claim != base_input_hash for claim in claims):
                raise ProductionP1RequestError(
                    "ED2_P1_SOURCE_INPUT_HASH_DRIFT",
                    f"{code}:{family.value}",
                )
        refs = [
            ref
            for family in sorted(families, key=lambda item: item.value)
            for ref in source_selection.refs_by_family[family]
        ]
        inputs[code]["_source_lineage"] = [
            {
                "source_family": ref.source_family.value,
                "source_id": ref.source_id,
                "artifact_id": ref.artifact_id,
                "artifact_sha256": ref.artifact_sha256,
                "adapter_id": ref.adapter_id,
                "adapter_version": ref.adapter_version,
                "source_ref": ref.source_ref,
            }
            for ref in refs
        ]

    system_codes = {
        definition.metric_code
        for definition in contract.plan.definitions
        if definition.subject_type == "MISSION_SYSTEM_INSTANCE"
    }
    binding_root = _mapping(
        payload.get("metric_system_bindings"),
        field="metric_system_bindings",
    )
    if set(binding_root) != system_codes:
        raise ProductionP1RequestError(
            "ED2_P1_SYSTEM_BINDING_MEMBERSHIP_INVALID",
            (
                f"missing={sorted(system_codes - set(binding_root))!r};"
                f"extra={sorted(set(binding_root) - system_codes)!r}"
            ),
        )
    system_root = _mapping(
        payload.get("mission_system_instances"),
        field="mission_system_instances",
    )
    system_ids = {
        _uuid(value, field=f"metric_system_bindings.{code}")
        for code, value in binding_root.items()
    }
    if set(system_root) != system_ids:
        raise ProductionP1RequestError(
            "ED2_P1_SYSTEM_AUTHORITY_MEMBERSHIP_INVALID",
            (
                f"missing={sorted(system_ids - set(system_root))!r};"
                f"extra={sorted(set(system_root) - system_ids)!r}"
            ),
        )

    authorities = {
        system_id: _system_authority(
            system_id,
            system_root[system_id],
            aircraft_id=aircraft_id,
            allowed_system_types=contract.plan.allowed_mission_system_types,
        )
        for system_id in sorted(system_ids)
    }
    bindings: dict[str, ProductionP1SystemBinding] = {}
    for definition in contract.plan.definitions:
        if definition.subject_type != "MISSION_SYSTEM_INSTANCE":
            continue
        raw_id = binding_root[definition.metric_code]
        system_id = _uuid(
            raw_id,
            field=f"metric_system_bindings.{definition.metric_code}",
        )
        authority = authorities[system_id]
        if (
            definition.allowed_mission_system_types
            and authority.system_type
            not in definition.allowed_mission_system_types
        ):
            raise ProductionP1RequestError(
                "ED2_P1_SYSTEM_DEFINITION_TYPE_INVALID",
                f"{definition.metric_code}:{authority.system_type}",
            )
        metric_input = inputs[definition.metric_code]
        input_system_id = metric_input.get("mission_system_instance_id")
        if input_system_id is not None and input_system_id != system_id:
            raise ProductionP1RequestError(
                "ED2_P1_SYSTEM_BINDING_DRIFT",
                definition.metric_code,
            )
        metric_input["mission_system_instance_id"] = system_id

        input_system_type = metric_input.get("system_type")
        if (
            input_system_type is not None
            and input_system_type != authority.system_type
        ):
            raise ProductionP1RequestError(
                "ED2_P1_SYSTEM_TYPE_DRIFT",
                definition.metric_code,
            )
        metric_input["system_type"] = authority.system_type
        bindings[definition.metric_code] = authority.publication_binding()

    return ProductionP1Request(
        inputs=inputs,
        system_authorities=tuple(
            authorities[system_id] for system_id in sorted(authorities)
        ),
        system_bindings=bindings,
    )


def _inspect_source_document(
    document: Mapping[str, object],
    *,
    index: int,
) -> tuple[dict[str, object], str, ProductionP1SourceRef]:
    item = dict(document)
    source_json = _text(
        item.get("source_json"),
        field=f"source_documents[{index}].source_json",
    )
    source_bytes = source_json.encode("utf-8")
    metadata = _mapping(
        item.get("source_import"),
        field=f"source_documents[{index}].source_import",
    )
    family_text = _text(
        metadata.get("source_family"),
        field=f"source_documents[{index}].source_family",
    )
    try:
        family = SourceFamily(family_text)
    except ValueError as exc:
        raise ProductionP1RequestError(
            "ED2_P1_SOURCE_FAMILY_UNSUPPORTED",
            family_text,
        ) from exc

    try:
        adapter: SourceAdapter
        if family is SourceFamily.FLIGHT:
            flight = validate_production_flight_document(source_bytes)
            session_id = _uuid(
                flight.get("session_id"),
                field=f"source_documents[{index}].session_id",
            )
            metric_input_hashes: dict[str, str] = {}
            adapter = ProductionFlightJsonAdapter()
        else:
            interchange = validate_production_interchange_document(
                source_bytes,
                expected_family=family,
            )
            session_id = interchange.session_id
            metric_input_hashes = _metric_input_hashes(
                interchange.payload.get("metric_input_hashes"),
                field=f"source_documents[{index}].metric_input_hashes",
            )
            adapter = ProductionInterchangeJsonAdapter(family)

        envelope = adapter.inspect(
            source_ref=_text(
                metadata.get("source_ref"),
                field=f"source_documents[{index}].source_ref",
            ),
            data=source_bytes,
            media_type=_text(
                metadata.get("media_type"),
                field=f"source_documents[{index}].media_type",
            ),
            classification_label=(
                None
                if metadata.get("classification_label") is None
                else _text(
                    metadata.get("classification_label"),
                    field=f"source_documents[{index}].classification_label",
                )
            ),
        )
    except ProductionSourceAdapterError as exc:
        raise ProductionP1RequestError(exc.code, exc.detail) from exc

    imported_session_id = _uuid(
        metadata.get("session_id"),
        field=f"source_documents[{index}].source_import.session_id",
    )
    if imported_session_id != session_id:
        raise ProductionP1RequestError(
            "ED2_P1_SOURCE_IMPORT_SESSION_DRIFT",
            f"index={index}:document={session_id}:import={imported_session_id}",
        )
    source_id = _uuid(
        metadata.get("source_id"),
        field=f"source_documents[{index}].source_id",
    )
    artifact_id = _uuid(
        metadata.get("artifact_id"),
        field=f"source_documents[{index}].artifact_id",
    )
    return (
        item,
        session_id,
        ProductionP1SourceRef(
            source_family=family,
            source_id=source_id,
            artifact_id=artifact_id,
            artifact_sha256=envelope.artifact_sha256,
            adapter_id=envelope.adapter_id,
            adapter_version=envelope.adapter_version,
            source_ref=envelope.source_ref,
            metric_input_hashes=metric_input_hashes,
        ),
    )


def select_production_p1_sources(
    payload: Mapping[str, object],
) -> ProductionP1SourceSelection:
    """Inspect the governed source set and select exactly one primary FLIGHT."""

    raw_documents = payload.get("source_documents")
    if raw_documents is None:
        documents = [dict(payload)]
    else:
        if (
            not isinstance(raw_documents, Sequence)
            or isinstance(raw_documents, (str, bytes))
            or not raw_documents
        ):
            raise ProductionP1RequestError(
                "ED2_P1_SOURCE_SET_INVALID",
                "source_documents",
            )
        documents = [
            _mapping(item, field=f"source_documents[{index}]")
            for index, item in enumerate(raw_documents)
        ]

    flight: list[dict[str, object]] = []
    session_id: str | None = None
    source_ids: set[str] = set()
    artifact_ids: set[str] = set()
    refs: dict[SourceFamily, list[ProductionP1SourceRef]] = {}
    for index, document in enumerate(documents):
        item, current_session, source_ref = _inspect_source_document(
            document,
            index=index,
        )
        if session_id is None:
            session_id = current_session
        elif current_session != session_id:
            raise ProductionP1RequestError(
                "ED2_P1_SOURCE_SET_SESSION_DRIFT",
                current_session,
            )
        if source_ref.source_id in source_ids:
            raise ProductionP1RequestError(
                "ED2_P1_SOURCE_SET_IDENTITY_DUPLICATE",
                source_ref.source_id,
            )
        if source_ref.artifact_id in artifact_ids:
            raise ProductionP1RequestError(
                "ED2_P1_SOURCE_SET_IDENTITY_DUPLICATE",
                source_ref.artifact_id,
            )
        source_ids.add(source_ref.source_id)
        artifact_ids.add(source_ref.artifact_id)
        refs.setdefault(source_ref.source_family, []).append(source_ref)
        if source_ref.source_family is SourceFamily.FLIGHT:
            flight.append(item)

    if len(flight) != 1 or session_id is None:
        raise ProductionP1RequestError(
            "ED2_P1_PRIMARY_FLIGHT_SOURCE_CARDINALITY",
            str(len(flight)),
        )
    return ProductionP1SourceSelection(
        flight_payload=flight[0],
        source_count=len(documents),
        session_id=session_id,
        refs_by_family={
            family: tuple(
                sorted(
                    family_refs,
                    key=lambda ref: (ref.source_id, ref.artifact_id),
                )
            )
            for family, family_refs in refs.items()
        },
    )

