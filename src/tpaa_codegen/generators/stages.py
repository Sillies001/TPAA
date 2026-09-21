from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

from ..errors import CodegenError, CodegenErrorContext, CodegenReason
from ..models import GeneratedFile, GenerationResult, SourceArtifactRef
from ..naming import project_unique_identifiers
from ..rendering import render_python

GENERATOR_ID = "stage-registry"
ARTIFACT_ID = "STAGE_REGISTRY"


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


class StageRegistryGenerator:
    generator_id = GENERATOR_ID

    def generate(self, loader: CanonicalArtifactLoader) -> GenerationResult:
        artifact = loader.load(
            ARTIFACT_ID,
            expectation=ArtifactExpectation(
                version="1.1.0", required_top_level_keys=("profiles",)
            ),
        )
        raw_profiles = artifact.payload.get("profiles")
        if not isinstance(raw_profiles, dict):
            raise _shape(None, "profiles must be an object")

        profiles: list[tuple[str, str, tuple[str, ...], dict[str, str]]] = []
        all_stages: set[str] = set()
        for profile_id in sorted(raw_profiles):
            raw = raw_profiles[profile_id]
            if not isinstance(profile_id, str) or not isinstance(raw, dict):
                raise _shape(str(profile_id), "profile must be an object with string identity")
            episode_type = raw.get("episode_type")
            ordered_stages = raw.get("ordered_stages")
            semantics = raw.get("semantics")
            if not isinstance(episode_type, str):
                raise _shape(profile_id, "episode_type must be a string")
            if not isinstance(ordered_stages, list) or not all(
                isinstance(item, str) and item for item in ordered_stages
            ):
                raise _shape(profile_id, "ordered_stages must be a list of non-empty strings")
            if len(ordered_stages) != len(set(ordered_stages)):
                raise CodegenError(
                    CodegenReason.DUPLICATE_VALUE,
                    CodegenErrorContext(
                        generator_id=GENERATOR_ID,
                        artifact_id=ARTIFACT_ID,
                        identity=profile_id,
                        detail="ordered_stages contains duplicate Stage identity",
                    ),
                )
            if not isinstance(semantics, dict) or set(semantics) != set(ordered_stages):
                raise _shape(profile_id, "semantics keys must exactly match ordered_stages")
            if not all(isinstance(k, str) and isinstance(v, str) for k, v in semantics.items()):
                raise _shape(profile_id, "semantics must map Stage string to semantic string")
            stages = tuple(ordered_stages)
            all_stages.update(stages)
            profiles.append((profile_id, episode_type, stages, dict(semantics)))

        enum_names = project_unique_identifiers(
            all_stages, generator_id=GENERATOR_ID, artifact_id=ARTIFACT_ID
        )
        profile_names = project_unique_identifiers(
            (profile[0] for profile in profiles),
            generator_id=GENERATOR_ID,
            artifact_id=ARTIFACT_ID,
        )

        lines = [
            '"""Generated TPAA Stage registry. Do not edit by hand."""',
            "",
            "from enum import StrEnum",
            "from types import MappingProxyType",
            "from typing import Mapping",
            "",
            "class StageCode(StrEnum):",
        ]
        for stage in sorted(all_stages):
            lines.append(f"    {enum_names[stage]} = {stage!r}")
        lines.extend(["", "class StageProfileId(StrEnum):"])
        for profile_id, _, _, _ in profiles:
            lines.append(f"    {profile_names[profile_id]} = {profile_id!r}")
        lines.extend(["", "STAGE_PROFILES: tuple[Mapping[str, object], ...] = ("])
        for profile_id, episode_type, stages, semantics in profiles:
            lines.append("    MappingProxyType({")
            lines.append(f"        'profile_id': {profile_id!r},")
            lines.append(f"        'episode_type': {episode_type!r},")
            lines.append(f"        'ordered_stages': {stages!r},")
            lines.append("        'semantics': MappingProxyType({")
            for stage in stages:
                lines.append(f"            {stage!r}: {semantics[stage]!r},")
            lines.append("        }),")
            lines.append("    }),")
        lines.append(")")

        return GenerationResult.create(
            generator_id=self.generator_id,
            sources=(
                SourceArtifactRef(artifact.artifact_id, artifact.version_label, artifact.sha256),
            ),
            files=(
                GeneratedFile(
                    PurePosixPath("src/tpaa_generated/stage_registry.py"),
                    render_python(lines),
                ),
            ),
            metadata={
                "profile_count": str(len(profiles)),
                "stage_identity_count": str(len(all_stages)),
            },
        )
