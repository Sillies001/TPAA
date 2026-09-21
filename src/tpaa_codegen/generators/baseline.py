from __future__ import annotations

from pathlib import PurePosixPath

from tpaa_canonical import CanonicalArtifactLoader

from ..models import GeneratedFile, GenerationResult
from ..rendering import render_python


class BaselineMetadataGenerator:
    generator_id = "baseline-metadata"

    def generate(self, loader: CanonicalArtifactLoader) -> GenerationResult:
        metadata = loader.baseline_metadata
        core = str(metadata["core"])
        db_schema = str(metadata["db_schema"])
        lines = [
            '"""Generated TPAA baseline metadata. Do not edit by hand."""',
            "",
            f'CORE_BASELINE = {core!r}',
            f'DB_SCHEMA_VERSION = {db_schema!r}',
            f'BASELINE_LOCK_SHA256 = {loader.trusted_lock_sha256!r}',
        ]
        return GenerationResult.create(
            generator_id=self.generator_id,
            sources=(),
            files=(
                GeneratedFile(
                    relative_path=PurePosixPath("src/tpaa_generated/baseline.py"),
                    content=render_python(lines),
                ),
            ),
            metadata={"projection": "BASELINE_LOCK"},
        )
