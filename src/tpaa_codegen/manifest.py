from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .models import GenerationResult


def build_manifest(
    *,
    generator_version: str,
    core_baseline: str,
    baseline_lock_sha256: str,
    results: Iterable[GenerationResult],
) -> dict[str, Any]:
    ordered = sorted(results, key=lambda item: item.generator_id)
    return {
        "manifest_type": "TPAA_CODEGEN_MANIFEST",
        "manifest_version": 1,
        "generator_version": generator_version,
        "core_baseline": core_baseline,
        "baseline_lock_sha256": baseline_lock_sha256,
        "generators": [
            {
                "generator_id": result.generator_id,
                "metadata": dict(sorted(result.metadata.items())),
                "sources": [
                    {
                        "artifact_id": source.artifact_id,
                        "version": source.version,
                        "sha256": source.sha256,
                    }
                    for source in sorted(result.sources, key=lambda item: item.artifact_id)
                ],
                "outputs": [
                    {
                        "path": file.relative_path.as_posix(),
                        "sha256": file.sha256,
                        "bytes": len(file.content),
                    }
                    for file in sorted(result.files, key=lambda item: item.relative_path.as_posix())
                ],
            }
            for result in ordered
        ],
    }
