from __future__ import annotations

import keyword
import re
from collections.abc import Iterable

from .errors import CodegenError, CodegenErrorContext, CodegenReason

_NON_IDENTIFIER = re.compile(r"[^0-9A-Za-z_]+")


def python_identifier(canonical_id: str, *, generator_id: str, artifact_id: str) -> str:
    value = _NON_IDENTIFIER.sub("_", canonical_id).strip("_")
    if not value:
        raise CodegenError(
            CodegenReason.INVALID_IDENTIFIER,
            CodegenErrorContext(
                generator_id=generator_id,
                artifact_id=artifact_id,
                identity=canonical_id,
                detail="Canonical identity cannot be projected to a Python identifier",
            ),
        )
    if value[0].isdigit():
        value = f"_{value}"
    if keyword.iskeyword(value):
        value = f"{value}_"
    return value


def project_unique_identifiers(
    canonical_ids: Iterable[str], *, generator_id: str, artifact_id: str
) -> dict[str, str]:
    projected: dict[str, str] = {}
    reverse: dict[str, str] = {}
    for canonical_id in sorted(canonical_ids):
        python_name = python_identifier(
            canonical_id, generator_id=generator_id, artifact_id=artifact_id
        )
        previous = reverse.get(python_name)
        if previous is not None and previous != canonical_id:
            raise CodegenError(
                CodegenReason.DUPLICATE_IDENTIFIER,
                CodegenErrorContext(
                    generator_id=generator_id,
                    artifact_id=artifact_id,
                    identity=canonical_id,
                    detail=f"Python identifier {python_name!r} collides with {previous!r}",
                ),
            )
        projected[canonical_id] = python_name
        reverse[python_name] = canonical_id
    return projected
