from __future__ import annotations

from pathlib import PurePosixPath

from tpaa_canonical import CanonicalArtifactLoader

from ..models import GeneratedFile, GenerationResult, SourceArtifactRef
from ..rendering import render_python


class GeneratedPackageInitGenerator:
    generator_id = "generated-package-init"

    def generate(self, loader: CanonicalArtifactLoader) -> GenerationResult:
        core = str(loader.baseline_metadata["core"])
        source = SourceArtifactRef(
            artifact_id="BASELINE_LOCK",
            version=core,
            sha256=loader.trusted_lock_sha256,
        )
        lines = [
            '"""Deterministically generated TPAA projections. Do not edit by hand."""',
        ]
        return GenerationResult.create(
            generator_id=self.generator_id,
            sources=(source,),
            files=(
                GeneratedFile(
                    relative_path=PurePosixPath("src/tpaa_generated/__init__.py"),
                    content=render_python(lines),
                ),
            ),
            metadata={"projection": "GENERATED_PACKAGE"},
        )
