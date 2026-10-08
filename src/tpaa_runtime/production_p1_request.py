"""Strict ED-2.0 production P1 request boundary.

This module converts JSON-safe Job payloads into the exact Catalog input and
Mission-System identity contracts required by production P1.  It never reads
fixtures, never guesses a subject identity and never silently drops a Metric.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast
from uuid import UUID

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
class ProductionP1SourceSelection:
    flight_payload: dict[str, object]
    source_count: int


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


def select_production_p1_sources(
    payload: Mapping[str, object],
) -> ProductionP1SourceSelection:
    """Select exactly one FLIGHT source from the governed source set."""

    raw_documents = payload.get("source_documents")
    if raw_documents is None:
        flight_payload = dict(payload)
        import_meta = _mapping(
            flight_payload.get("source_import"),
            field="source_import",
        )
        if import_meta.get("source_family") != "FLIGHT":
            raise ProductionP1RequestError(
                "ED2_P1_PRIMARY_FLIGHT_SOURCE_MISSING",
                "source_import",
            )
        return ProductionP1SourceSelection(
            flight_payload=flight_payload,
            source_count=1,
        )

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
    flight = []
    for index, item in enumerate(documents):
        meta = _mapping(
            item.get("source_import"),
            field=f"source_documents[{index}].source_import",
        )
        if meta.get("source_family") == "FLIGHT":
            flight.append(item)
    if len(flight) != 1:
        raise ProductionP1RequestError(
            "ED2_P1_PRIMARY_FLIGHT_SOURCE_CARDINALITY",
            str(len(flight)),
        )
    return ProductionP1SourceSelection(
        flight_payload=flight[0],
        source_count=len(documents),
    )
