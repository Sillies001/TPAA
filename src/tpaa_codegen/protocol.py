from __future__ import annotations

from typing import Protocol

from tpaa_canonical import CanonicalArtifactLoader

from .models import GenerationResult


class Generator(Protocol):
    generator_id: str

    def generate(self, loader: CanonicalArtifactLoader) -> GenerationResult: ...
