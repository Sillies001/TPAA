from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable

from tpaa_canonical import CanonicalArtifactLoader

from .errors import CodegenError, CodegenErrorContext, CodegenReason
from .manifest import build_manifest
from .models import GeneratedFile, GenerationResult
from .provenance import decorate_python_source
from .protocol import Generator
from .rendering import render_json

GENERATOR_VERSION = "0.2.0"
MANIFEST_PATH = PurePosixPath("src/tpaa_generated/_generation_manifest.json")


@dataclass(frozen=True, slots=True)
class GenerationSummary:
    results: tuple[GenerationResult, ...]
    manifest_file: GeneratedFile

    @property
    def files(self) -> tuple[GeneratedFile, ...]:
        generated = tuple(file for result in self.results for file in result.files)
        return generated + (self.manifest_file,)


class GenerationCoordinator:
    def __init__(self, loader: CanonicalArtifactLoader, generators: Iterable[Generator]) -> None:
        self._loader = loader
        self._generators = tuple(sorted(generators, key=lambda item: item.generator_id))

    def build(self) -> GenerationSummary:
        raw_results = tuple(generator.generate(self._loader) for generator in self._generators)
        results: tuple[GenerationResult, ...] = tuple(
            GenerationResult.create(
                generator_id=result.generator_id,
                sources=result.sources,
                files=tuple(
                    GeneratedFile(
                        relative_path=file.relative_path,
                        content=(
                            decorate_python_source(
                                file.content,
                                generator_id=result.generator_id,
                                generator_version=GENERATOR_VERSION,
                                sources=result.sources,
                            )
                            if file.relative_path.suffix == ".py"
                            else file.content
                        ),
                    )
                    for file in result.files
                ),
                metadata=result.metadata,
            )
            for result in raw_results
        )
        seen: dict[PurePosixPath, str] = {}
        for result in results:
            for file in result.files:
                previous = seen.get(file.relative_path)
                if previous is not None:
                    raise CodegenError(
                        CodegenReason.OUTPUT_PATH_COLLISION,
                        CodegenErrorContext(
                            generator_id=result.generator_id,
                            identity=file.relative_path.as_posix(),
                            detail=f"output already produced by generator {previous}",
                        ),
                    )
                seen[file.relative_path] = result.generator_id
        if MANIFEST_PATH in seen:
            raise CodegenError(
                CodegenReason.OUTPUT_PATH_COLLISION,
                CodegenErrorContext(
                    generator_id="coordinator",
                    identity=MANIFEST_PATH.as_posix(),
                    detail="manifest output path is reserved",
                ),
            )
        manifest = build_manifest(
            generator_version=GENERATOR_VERSION,
            core_baseline=self._loader.expected_core_baseline,
            baseline_lock_sha256=self._loader.trusted_lock_sha256,
            results=results,
        )
        manifest_file = GeneratedFile(relative_path=MANIFEST_PATH, content=render_json(manifest))
        return GenerationSummary(results=results, manifest_file=manifest_file)

    def write(self, repo_root: Path) -> GenerationSummary:
        summary = self.build()
        root = repo_root.resolve()
        for file in summary.files:
            target = root.joinpath(*file.relative_path.parts).resolve()
            if root not in target.parents:
                raise CodegenError(
                    CodegenReason.OUTPUT_PATH_COLLISION,
                    CodegenErrorContext(
                        generator_id="coordinator",
                        identity=file.relative_path.as_posix(),
                        detail="generated output escapes repository root",
                    ),
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(file.content)
        return summary
