from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

from ..errors import CodegenError, CodegenErrorContext, CodegenReason
from ..models import GeneratedFile, GenerationResult, SourceArtifactRef
from ..naming import project_unique_identifiers
from ..rendering import render_python

GENERATOR_ID = "metric-registry"
ARTIFACT_ID = "P1_METRIC_CATALOG"
_PROJECTED_FIELDS = (
    "metric_code",
    "name",
    "semantic_id",
    "semantic_version",
    "family",
    "subject_type",
    "unit",
    "value_kind",
    "algorithm_id",
    "algorithm_version",
    "delivery_milestone",
    "delivery_batch",
    "observation_lane",
    "publication_route",
    "structured_output_schema_id",
    "p1_longitudinal_trend_eligibility",
)


def _shape(identity: str | None, detail: str) -> CodegenError:
    return CodegenError(
        CodegenReason.UNSUPPORTED_ARTIFACT_SHAPE,
        CodegenErrorContext(
            generator_id=GENERATOR_ID,
            artifact_id=ARTIFACT_ID,
            identity=identity,
            detail=detail,
        ),
    )


class MetricRegistryGenerator:
    generator_id = GENERATOR_ID

    def generate(self, loader: CanonicalArtifactLoader) -> GenerationResult:
        artifact = loader.load(
            ARTIFACT_ID,
            expectation=ArtifactExpectation(
                version="1.14.0",
                schema_version="1.6.0",
                required_top_level_keys=("metrics",),
            ),
        )
        raw_metrics = artifact.payload.get("metrics")
        if not isinstance(raw_metrics, list):
            raise _shape(None, "metrics must be a list")
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in raw_metrics:
            if not isinstance(raw, dict):
                raise _shape(None, "metric entry must be an object")
            code = raw.get("metric_code")
            if not isinstance(code, str) or not code:
                raise _shape(None, "metric_code must be a non-empty string")
            if code in seen:
                raise CodegenError(
                    CodegenReason.DUPLICATE_VALUE,
                    CodegenErrorContext(
                        generator_id=GENERATOR_ID,
                        artifact_id=ARTIFACT_ID,
                        identity=code,
                        detail="duplicate metric_code",
                    ),
                )
            seen.add(code)
            missing = [field for field in _PROJECTED_FIELDS if field not in raw]
            if missing:
                raise _shape(code, f"missing projected fields: {', '.join(missing)}")
            for field in _PROJECTED_FIELDS:
                value = raw[field]
                if field == "semantic_version":
                    if not isinstance(value, int):
                        raise _shape(code, "semantic_version must be an integer")
                elif field == "p1_longitudinal_trend_eligibility":
                    if not isinstance(value, bool):
                        raise _shape(code, "p1_longitudinal_trend_eligibility must be boolean")
                elif field == "structured_output_schema_id":
                    if value is not None and not isinstance(value, str):
                        raise _shape(code, "structured_output_schema_id must be string or null")
                elif not isinstance(value, str):
                    raise _shape(code, f"{field} must be a string")
            records.append(dict(raw))
        records.sort(key=lambda item: str(item["metric_code"]))
        names = project_unique_identifiers(
            (str(item["metric_code"]) for item in records),
            generator_id=GENERATOR_ID,
            artifact_id=ARTIFACT_ID,
        )

        lines = [
            '"""Generated TPAA P1 Metric identity/metadata registry. Do not edit by hand."""',
            "",
            "from enum import StrEnum",
            "from types import MappingProxyType",
            "from typing import Mapping",
            "",
            "class P1MetricCode(StrEnum):",
        ]
        for record in records:
            code = str(record["metric_code"])
            lines.append(f"    {names[code]} = {code!r}")
        lines.extend(["", "P1_METRICS: tuple[Mapping[str, object], ...] = ("])
        for record in records:
            lines.append("    MappingProxyType({")
            for field in _PROJECTED_FIELDS:
                lines.append(f"        {field!r}: {record[field]!r},")
            lines.append("    }),")
        lines.append(")")

        return GenerationResult.create(
            generator_id=self.generator_id,
            sources=(
                SourceArtifactRef(artifact.artifact_id, artifact.version_label, artifact.sha256),
            ),
            files=(
                GeneratedFile(
                    PurePosixPath("src/tpaa_generated/metric_registry.py"),
                    render_python(lines),
                ),
            ),
            metadata={"metric_count": str(len(records)), "projected_field_count": str(len(_PROJECTED_FIELDS))},
        )
