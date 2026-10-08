from __future__ import annotations

import json
from pathlib import Path

import pytest

from tpaa_qualification.ed2_p1_request_contract import (
    ED2_P1_REQUEST_CONTRACT_SCHEMA,
    load_ed2_p1_request_contract,
)


def _write(path: Path, payload: object) -> Path:
    path.write_text(
        json.dumps(payload, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    return path


def test_ed2_p1_request_contract_loads_exact_schema(tmp_path: Path) -> None:
    path = _write(
        tmp_path / "p1-contract.json",
        {
            "schema": ED2_P1_REQUEST_CONTRACT_SCHEMA,
            "source_documents": [{}, {}, {}, {}, {}, {}],
            "metric_input_source_families": {
                "P1-AIR-001": ["FLIGHT"],
            },
            "p1_catalog_inputs": {"P1-AIR-001": {}},
            "mission_system_instances": {},
            "metric_system_bindings": {},
        },
    )

    loaded = load_ed2_p1_request_contract(path)

    assert loaded["schema"] == ED2_P1_REQUEST_CONTRACT_SCHEMA
    assert loaded["p1_catalog_inputs"] == {"P1-AIR-001": {}}


def test_ed2_p1_request_contract_missing_file_fails_closed(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        RuntimeError,
        match="production P1 qualification contract unavailable",
    ):
        load_ed2_p1_request_contract(tmp_path / "missing.json")


def test_ed2_p1_request_contract_schema_drift_fails_closed(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path / "p1-contract.json",
        {
            "schema": "DRIFTED",
            "source_documents": [{}, {}, {}, {}, {}, {}],
            "metric_input_source_families": {},
            "p1_catalog_inputs": {},
            "mission_system_instances": {},
            "metric_system_bindings": {},
        },
    )

    with pytest.raises(
        RuntimeError,
        match="production P1 qualification contract schema drift",
    ):
        load_ed2_p1_request_contract(path)


@pytest.mark.parametrize(
    "field",
    (
        "metric_input_source_families",
        "p1_catalog_inputs",
        "mission_system_instances",
        "metric_system_bindings",
    ),
)
def test_ed2_p1_request_contract_required_mapping_fails_closed(
    tmp_path: Path,
    field: str,
) -> None:
    payload: dict[str, object] = {
        "schema": ED2_P1_REQUEST_CONTRACT_SCHEMA,
        "source_documents": [{}, {}, {}, {}, {}, {}],
        "metric_input_source_families": {},
        "p1_catalog_inputs": {},
        "mission_system_instances": {},
        "metric_system_bindings": {},
    }
    payload[field] = []
    path = _write(tmp_path / f"{field}.json", payload)

    with pytest.raises(
        RuntimeError,
        match=f"production P1 qualification contract field invalid: {field}",
    ):
        load_ed2_p1_request_contract(path)



def test_ed2_p1_request_contract_requires_six_source_documents(
    tmp_path: Path,
) -> None:
    path = _write(
        tmp_path / "sources.json",
        {
            "schema": ED2_P1_REQUEST_CONTRACT_SCHEMA,
            "source_documents": [{}],
            "metric_input_source_families": {},
            "p1_catalog_inputs": {},
            "mission_system_instances": {},
            "metric_system_bindings": {},
        },
    )

    with pytest.raises(
        RuntimeError,
        match="production P1 qualification contract field invalid: source_documents",
    ):
        load_ed2_p1_request_contract(path)
