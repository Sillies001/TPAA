from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

from ..errors import CodegenError, CodegenErrorContext, CodegenReason
from ..models import GeneratedFile, GenerationResult, SourceArtifactRef
from ..naming import project_unique_identifiers, python_identifier
from ..rendering import render_python

GENERATOR_ID = "dto-types"
ARTIFACT_ID = "CROSS_LAYER_DTO_CONTRACTS"
_TRANSPORT_TYPES = {
    "string": "str",
    "string?": "str | None",
    "uuid-string": "str",
    "uuid-string?": "str | None",
    "integer": "int",
    "number": "int | float",
    "boolean": "bool",
    "decimal-string": "str",
    "decimal-string?": "str | None",
    "array[string]": "list[str]",
    "object": "dict[str, JSONValue]",
    "json-union": "JSONValue",
}


def _error(reason: CodegenReason, identity: str | None, detail: str) -> CodegenError:
    return CodegenError(
        reason,
        CodegenErrorContext(
            generator_id=GENERATOR_ID,
            artifact_id=ARTIFACT_ID,
            identity=identity,
            detail=detail,
        ),
    )


def _field_name(value: Any, dto: str) -> str:
    if not isinstance(value, str) or not value:
        raise _error(CodegenReason.UNSUPPORTED_ARTIFACT_SHAPE, dto, "field must be non-empty string")
    projected = python_identifier(value, generator_id=GENERATOR_ID, artifact_id=ARTIFACT_ID)
    if projected != value:
        raise _error(
            CodegenReason.INVALID_IDENTIFIER,
            f"{dto}.{value}",
            "DTO transport field names must already be valid Python identifiers",
        )
    return value


class DtoTypesGenerator:
    generator_id = GENERATOR_ID

    def generate(self, loader: CanonicalArtifactLoader) -> GenerationResult:
        artifact = loader.load(
            ARTIFACT_ID,
            expectation=ArtifactExpectation(required_top_level_keys=("contracts",)),
        )
        raw_contracts = artifact.payload.get("contracts")
        if not isinstance(raw_contracts, dict):
            raise _error(CodegenReason.UNSUPPORTED_ARTIFACT_SHAPE, None, "contracts must be object")
        project_unique_identifiers(
            raw_contracts.keys(), generator_id=GENERATOR_ID, artifact_id=ARTIFACT_ID
        )

        lines = [
            '"""Generated TPAA cross-layer DTO transport types. Do not edit by hand."""',
            "",
            "from __future__ import annotations",
            "",
            "from typing import NotRequired, Required, TypedDict",
            "",
            "type JSONScalar = str | int | float | bool | None",
            "type JSONValue = JSONScalar | list[JSONValue] | dict[str, JSONValue]",
            "",
        ]
        dto_count = 0
        field_count = 0
        for dto_name in sorted(raw_contracts):
            contract = raw_contracts[dto_name]
            if not isinstance(dto_name, str) or not isinstance(contract, dict):
                raise _error(CodegenReason.UNSUPPORTED_ARTIFACT_SHAPE, str(dto_name), "contract must be object")
            fields_key = "fields" if "fields" in contract else "projection_fields"
            raw_fields = contract.get(fields_key)
            if not isinstance(raw_fields, list):
                raise _error(CodegenReason.UNSUPPORTED_ARTIFACT_SHAPE, dto_name, f"{fields_key} must be list")
            seen_fields: set[str] = set()
            lines.append(f"class {dto_name}(TypedDict, total=False):")
            if not raw_fields:
                lines.append("    pass")
            for raw_field in raw_fields:
                if not isinstance(raw_field, dict):
                    raise _error(CodegenReason.UNSUPPORTED_ARTIFACT_SHAPE, dto_name, "field entry must be object")
                field = _field_name(raw_field.get("field"), dto_name)
                if field in seen_fields:
                    raise _error(CodegenReason.DUPLICATE_VALUE, f"{dto_name}.{field}", "duplicate DTO field")
                seen_fields.add(field)
                required = raw_field.get("required")
                if not isinstance(required, bool):
                    raise _error(CodegenReason.UNSUPPORTED_ARTIFACT_SHAPE, f"{dto_name}.{field}", "required must be boolean")
                if fields_key == "fields":
                    transport = raw_field.get("transport_type")
                    if not isinstance(transport, str) or transport not in _TRANSPORT_TYPES:
                        raise _error(CodegenReason.UNSUPPORTED_DTO_CONSTRUCT, f"{dto_name}.{field}", f"unsupported transport_type={transport!r}")
                    python_type = _TRANSPORT_TYPES[transport]
                else:
                    declared = raw_field.get("type")
                    if not isinstance(declared, str):
                        raise _error(CodegenReason.UNSUPPORTED_DTO_CONSTRUCT, f"{dto_name}.{field}", "projection type must be string")
                    if declared == "object[]":
                        python_type = "list[dict[str, JSONValue]]"
                    elif declared == "object?":
                        python_type = "dict[str, JSONValue] | None"
                    elif declared.endswith("[]") and declared[:-2] in raw_contracts:
                        python_type = f"list[{declared[:-2]}]"
                    elif declared in raw_contracts:
                        python_type = declared
                    else:
                        raise _error(CodegenReason.UNSUPPORTED_DTO_CONSTRUCT, f"{dto_name}.{field}", f"unsupported projection type={declared!r}")
                wrapper = "Required" if required else "NotRequired"
                lines.append(f"    {field}: {wrapper}[{python_type}]")
                field_count += 1
            lines.append("")
            dto_count += 1

        return GenerationResult.create(
            generator_id=self.generator_id,
            sources=(SourceArtifactRef(artifact.artifact_id, artifact.version_label, artifact.sha256),),
            files=(GeneratedFile(PurePosixPath("src/tpaa_generated/dto.py"), render_python(lines)),),
            metadata={"dto_count": str(dto_count), "field_count": str(field_count)},
        )
