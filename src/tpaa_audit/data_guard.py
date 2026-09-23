"""Development-data guard: synthetic/public by default; controlled data fail closed."""

from __future__ import annotations

from enum import StrEnum


class DataClassification(StrEnum):
    SYNTHETIC = "SYNTHETIC"
    PUBLIC = "PUBLIC"
    OPERATIONAL = "OPERATIONAL"
    SENSITIVE = "SENSITIVE"


class DataPolicyError(PermissionError):
    def __init__(self, classification: DataClassification) -> None:
        self.classification = classification
        super().__init__(f"DEVELOPMENT_DATA_NOT_APPROVED classification={classification.value}")


class DevelopmentDataGuard:
    """M0 policy gate; approval references must be explicit for controlled data."""

    def authorize(
        self,
        classification: DataClassification,
        *,
        approval_reference: str | None = None,
    ) -> None:
        if classification in {DataClassification.SYNTHETIC, DataClassification.PUBLIC}:
            return
        if approval_reference is None or not approval_reference.strip():
            raise DataPolicyError(classification)
