#!/usr/bin/env python3
"""Generate/check the M0 OpenAPI DTO snapshot directly from Canonical authority."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader  # noqa: E402

ARTIFACT_ID = "CROSS_LAYER_DTO_CONTRACTS"
DEFAULT_OUTPUT = REPO_ROOT / "api" / "openapi-m0.json"


def _nullable(schema: dict[str, object]) -> dict[str, object]:
    return {"anyOf": [schema, {"type": "null"}]}


def _transport_schema(transport: str) -> dict[str, object]:
    nullable = transport.endswith("?")
    base = transport[:-1] if nullable else transport
    if base == "string":
        schema: dict[str, object] = {"type": "string"}
    elif base == "uuid-string":
        schema = {"type": "string", "format": "uuid"}
    elif base == "decimal-string":
        schema = {"type": "string", "pattern": r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$"}
    elif base == "integer":
        schema = {"type": "integer"}
    elif base == "number":
        schema = {"type": "number"}
    elif base == "boolean":
        schema = {"type": "boolean"}
    elif base == "array[string]":
        schema = {"type": "array", "items": {"type": "string"}}
    elif base == "object":
        schema = {"type": "object", "additionalProperties": True}
    elif base == "json-union":
        schema = {
            "oneOf": [
                {"type": "string"},
                {"type": "integer"},
                {"type": "number"},
                {"type": "boolean"},
                {"type": "object", "additionalProperties": True},
                {"type": "array", "items": {}},
                {"type": "null"},
            ]
        }
    else:
        raise ValueError(f"unsupported transport type: {transport}")
    schema["x-tpaa-transport-type"] = transport
    return _nullable(schema) if nullable else schema


def _projection_schema(declared: str, contracts: dict[str, object]) -> dict[str, object]:
    nullable = declared.endswith("?")
    base = declared[:-1] if nullable else declared
    if base == "object":
        schema: dict[str, object] = {"type": "object", "additionalProperties": True}
    elif base == "object[]":
        schema = {"type": "array", "items": {"type": "object", "additionalProperties": True}}
    elif base.endswith("[]") and base[:-2] in contracts:
        schema = {"type": "array", "items": {"$ref": f"#/components/schemas/{base[:-2]}"}}
    elif base in contracts:
        schema = {"$ref": f"#/components/schemas/{base}"}
    else:
        raise ValueError(f"unsupported projection type: {declared}")
    schema["x-tpaa-projection-type"] = declared
    return _nullable(schema) if nullable else schema


def build_snapshot() -> dict[str, object]:
    artifact = CanonicalArtifactLoader().load(
        ARTIFACT_ID,
        expectation=ArtifactExpectation(required_top_level_keys=("contracts", "transport_rules")),
    )
    raw_contracts = artifact.payload["contracts"]
    raw_rules = artifact.payload["transport_rules"]
    if not isinstance(raw_contracts, dict) or not isinstance(raw_rules, dict):
        raise ValueError("Canonical DTO authority shape invalid")

    schemas: dict[str, object] = {}
    for dto_name in sorted(raw_contracts):
        raw_contract = raw_contracts[dto_name]
        if not isinstance(dto_name, str) or not isinstance(raw_contract, dict):
            raise ValueError("DTO contract must be object")
        fields_key = "fields" if "fields" in raw_contract else "projection_fields"
        raw_fields = raw_contract.get(fields_key)
        if not isinstance(raw_fields, list):
            raise ValueError(f"{dto_name}.{fields_key} must be list")
        properties: dict[str, object] = {}
        required: list[str] = []
        for raw_field in raw_fields:
            if not isinstance(raw_field, dict):
                raise ValueError(f"{dto_name} field entry must be object")
            field = raw_field.get("field")
            required_flag = raw_field.get("required")
            if not isinstance(field, str) or not isinstance(required_flag, bool):
                raise ValueError(f"{dto_name} field declaration invalid")
            if fields_key == "fields":
                transport = raw_field.get("transport_type")
                if not isinstance(transport, str):
                    raise ValueError(f"{dto_name}.{field} transport type invalid")
                properties[field] = _transport_schema(transport)
            else:
                declared = raw_field.get("type")
                if not isinstance(declared, str):
                    raise ValueError(f"{dto_name}.{field} projection type invalid")
                properties[field] = _projection_schema(declared, raw_contracts)
            if required_flag:
                required.append(field)
        schema: dict[str, object] = {
            "type": "object",
            "additionalProperties": False,
            "properties": properties,
        }
        if required:
            schema["required"] = required
        schemas[dto_name] = schema

    return {
        "openapi": "3.1.0",
        "info": {"title": "TPAA M0 Canonical DTO Snapshot", "version": "0.0.0"},
        "paths": {},
        "components": {"schemas": schemas},
        "x-tpaa-authority": {
            "artifact_id": artifact.artifact_id,
            "artifact_version": artifact.version_label,
            "sha256": artifact.sha256,
            "core_baseline": artifact.core_baseline,
        },
        "x-tpaa-transport-rules": raw_rules,
    }


def serialized_snapshot() -> str:
    return json.dumps(build_snapshot(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = serialized_snapshot()
    if args.check:
        try:
            actual = args.output.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"OPENAPI_SNAPSHOT_FAIL missing={args.output}", file=sys.stderr)
            return 2
        if actual != expected:
            print(f"OPENAPI_SNAPSHOT_FAIL drift={args.output}", file=sys.stderr)
            return 2
        print(f"OPENAPI_SNAPSHOT_PASS path={args.output}")
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8", newline="\n")
    print(f"OPENAPI_SNAPSHOT_WRITE path={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
