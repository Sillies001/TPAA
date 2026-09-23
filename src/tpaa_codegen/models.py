from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class SourceArtifactRef:
    artifact_id: str
    version: str
    sha256: str


@dataclass(frozen=True, slots=True)
class GeneratedFile:
    relative_path: PurePosixPath
    content: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")


@dataclass(frozen=True, slots=True)
class GenerationResult:
    generator_id: str
    sources: tuple[SourceArtifactRef, ...]
    files: tuple[GeneratedFile, ...]
    metadata: Mapping[str, str]

    @classmethod
    def create(
        cls,
        *,
        generator_id: str,
        sources: tuple[SourceArtifactRef, ...],
        files: tuple[GeneratedFile, ...],
        metadata: Mapping[str, str] | None = None,
    ) -> GenerationResult:
        return cls(
            generator_id=generator_id,
            sources=sources,
            files=files,
            metadata=MappingProxyType(dict(metadata or {})),
        )
