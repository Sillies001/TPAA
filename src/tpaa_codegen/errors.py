from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CodegenReason(StrEnum):
    UNKNOWN_ARTIFACT = "UNKNOWN_ARTIFACT"
    UNSUPPORTED_ARTIFACT_SHAPE = "UNSUPPORTED_ARTIFACT_SHAPE"
    INVALID_IDENTIFIER = "INVALID_IDENTIFIER"
    DUPLICATE_IDENTIFIER = "DUPLICATE_IDENTIFIER"
    DUPLICATE_VALUE = "DUPLICATE_VALUE"
    UNRESOLVED_REFERENCE = "UNRESOLVED_REFERENCE"
    CONFLICTING_DEFINITION = "CONFLICTING_DEFINITION"
    UNSUPPORTED_DTO_CONSTRUCT = "UNSUPPORTED_DTO_CONSTRUCT"
    OUTPUT_PATH_COLLISION = "OUTPUT_PATH_COLLISION"
    NON_DETERMINISTIC_OUTPUT = "NON_DETERMINISTIC_OUTPUT"
    GENERATED_FILE_MISSING = "GENERATED_FILE_MISSING"
    GENERATED_FILE_DRIFT = "GENERATED_FILE_DRIFT"
    UNEXPECTED_GENERATED_FILE = "UNEXPECTED_GENERATED_FILE"
    PROVENANCE_HEADER_MISMATCH = "PROVENANCE_HEADER_MISMATCH"
    GENERATED_TREE_DIRTY = "GENERATED_TREE_DIRTY"
    REGENERATE_DIFF_FAILED = "REGENERATE_DIFF_FAILED"
    GIT_UNAVAILABLE = "GIT_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class CodegenErrorContext:
    generator_id: str
    artifact_id: str | None = None
    identity: str | None = None
    detail: str | None = None


class CodegenError(RuntimeError):
    def __init__(self, reason: CodegenReason, context: CodegenErrorContext) -> None:
        self.reason = reason
        self.context = context
        parts = [f"reason={reason.value}", f"generator={context.generator_id}"]
        if context.artifact_id is not None:
            parts.append(f"artifact_id={context.artifact_id}")
        if context.identity is not None:
            parts.append(f"identity={context.identity}")
        if context.detail is not None:
            parts.append(f"detail={context.detail}")
        super().__init__("CODEGEN_FAIL " + " ".join(parts))
