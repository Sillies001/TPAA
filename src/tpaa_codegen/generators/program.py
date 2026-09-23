from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath
from typing import Any

from tpaa_canonical import ArtifactExpectation, CanonicalArtifact, CanonicalArtifactLoader

from ..errors import CodegenError, CodegenErrorContext, CodegenReason
from ..models import GeneratedFile, GenerationResult, SourceArtifactRef
from ..naming import project_unique_identifiers
from ..rendering import render_python

GENERATOR_ID = "program-registry"


def _fail(artifact_id: str, identity: str | None, detail: str) -> CodegenError:
    return CodegenError(
        CodegenReason.UNSUPPORTED_ARTIFACT_SHAPE,
        CodegenErrorContext(
            generator_id=GENERATOR_ID,
            artifact_id=artifact_id,
            identity=identity,
            detail=detail,
        ),
    )


def _require_records(
    artifact: CanonicalArtifact, key: str, identity_key: str
) -> tuple[dict[str, Any], ...]:
    raw = artifact.payload.get(key)
    if not isinstance(raw, list):
        raise _fail(artifact.artifact_id, None, f"{key} must be a list")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            raise _fail(artifact.artifact_id, None, f"{key} entries must be objects")
        identity = item.get(identity_key)
        if not isinstance(identity, str) or not identity:
            raise _fail(artifact.artifact_id, None, f"{identity_key} must be a non-empty string")
        if identity in seen:
            raise CodegenError(
                CodegenReason.DUPLICATE_VALUE,
                CodegenErrorContext(
                    generator_id=GENERATOR_ID,
                    artifact_id=artifact.artifact_id,
                    identity=identity,
                    detail=f"duplicate Canonical identity in {key}",
                ),
            )
        seen.add(identity)
        records.append(dict(item))
    return tuple(sorted(records, key=lambda item: str(item[identity_key])))


def _require_string(record: Mapping[str, Any], key: str, *, artifact_id: str, identity: str) -> str:
    value = record.get(key)
    if not isinstance(value, str):
        raise _fail(artifact_id, identity, f"{key} must be a string")
    return value


def _source(artifact: CanonicalArtifact) -> SourceArtifactRef:
    return SourceArtifactRef(
        artifact_id=artifact.artifact_id,
        version=artifact.version_label,
        sha256=artifact.sha256,
    )


def _render_enum(class_name: str, records: tuple[dict[str, Any], ...], identity_key: str, *, artifact_id: str) -> list[str]:
    identities = [_require_string(r, identity_key, artifact_id=artifact_id, identity="<record>") for r in records]
    names = project_unique_identifiers(identities, generator_id=GENERATOR_ID, artifact_id=artifact_id)
    lines = [f"class {class_name}(StrEnum):"]
    if not identities:
        lines.append("    pass")
    else:
        for identity in identities:
            lines.append(f"    {names[identity]} = {identity!r}")
    return lines


def _render_records(constant: str, records: tuple[dict[str, Any], ...], fields: tuple[str, ...], identity_key: str, *, artifact_id: str) -> list[str]:
    lines = [f"{constant}: tuple[Mapping[str, object], ...] = ("]
    for record in records:
        identity = _require_string(record, identity_key, artifact_id=artifact_id, identity="<record>")
        lines.append("    MappingProxyType({")
        for field in fields:
            value = record.get(field)
            if field in {"p_capability_impact", "required_workstreams"}:
                if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                    raise _fail(artifact_id, identity, f"{field} must be a list of strings")
                value = tuple(value)
            elif not isinstance(value, str):
                raise _fail(artifact_id, identity, f"{field} must be a string")
            lines.append(f"        {field!r}: {value!r},")
        lines.append("    }),")
    lines.append(")")
    return lines


class ProgramRegistryGenerator:
    generator_id = GENERATOR_ID

    def generate(self, loader: CanonicalArtifactLoader) -> GenerationResult:
        p = loader.load(
            "CAPABILITY_PHASE_REGISTRY",
            expectation=ArtifactExpectation(
                version="1.0.0",
                required_top_level_keys=("capability_phases",),
            ),
        )
        m = loader.load(
            "DEVELOPMENT_MILESTONE_REGISTRY",
            expectation=ArtifactExpectation(version="1.0.0", required_top_level_keys=("milestones",)),
        )
        ws = loader.load(
            "ENGINEERING_WORKSTREAM_REGISTRY",
            expectation=ArtifactExpectation(version="1.0.0", required_top_level_keys=("workstreams",)),
        )

        phases = _require_records(p, "capability_phases", "p_code")
        milestones = _require_records(m, "milestones", "code")
        workstreams = _require_records(ws, "workstreams", "code")

        lines: list[str] = [
            '"""Generated TPAA P/M/WS program registries. Do not edit by hand."""',
            "",
            "from collections.abc import Mapping",
            "from enum import StrEnum",
            "from types import MappingProxyType",
            "",
            "",
        ]
        lines.extend(_render_enum("CapabilityPhase", phases, "p_code", artifact_id=p.artifact_id))
        lines.append("")
        lines.extend(_render_enum("DevelopmentMilestone", milestones, "code", artifact_id=m.artifact_id))
        lines.append("")
        lines.extend(_render_enum("EngineeringWorkstream", workstreams, "code", artifact_id=ws.artifact_id))
        lines.append("")
        lines.extend(
            _render_records(
                "CAPABILITY_PHASES",
                phases,
                ("p_code", "name", "purpose", "baseline_status", "frozen_extension_scope"),
                "p_code",
                artifact_id=p.artifact_id,
            )
        )
        lines.append("")
        lines.extend(
            _render_records(
                "DEVELOPMENT_MILESTONES",
                milestones,
                ("code", "name", "name_cn", "objective", "p_capability_impact", "required_workstreams"),
                "code",
                artifact_id=m.artifact_id,
            )
        )
        lines.append("")
        lines.extend(
            _render_records(
                "ENGINEERING_WORKSTREAMS",
                workstreams,
                ("code", "name", "scope"),
                "code",
                artifact_id=ws.artifact_id,
            )
        )

        return GenerationResult.create(
            generator_id=self.generator_id,
            sources=(_source(p), _source(m), _source(ws)),
            files=(
                GeneratedFile(
                    relative_path=PurePosixPath("src/tpaa_generated/program_registry.py"),
                    content=render_python(lines),
                ),
            ),
            metadata={
                "capability_phase_count": str(len(phases)),
                "milestone_count": str(len(milestones)),
                "workstream_count": str(len(workstreams)),
            },
        )
