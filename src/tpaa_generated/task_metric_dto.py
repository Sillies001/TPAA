"""Generated task-level Assessment Metric DTO contracts; do not edit."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

TaskMetricStatus = Literal[
    "READY", "PENDING", "N_A", "INSUFFICIENT", "INVALID", "ERROR", "INCOMPARABLE"
]
TaskMetricAdmissionStatus = Literal[
    "CANDIDATE_TEST_ONLY", "CANDIDATE_AWAITING_BUSINESS_APPROVAL", "ADMITTED", "RETIRED"
]


@dataclass(frozen=True, slots=True)
class TaskMetricDefinitionDTO:
    semantic_id: str
    definition_version: str
    definition_sha256: str
    name_zh: str
    name_en: str
    value_kind: str
    unit: str
    direction: str
    applicable_training_types: tuple[str, ...]
    admission_status: TaskMetricAdmissionStatus
    display_decimal_places: int


@dataclass(frozen=True, slots=True)
class TaskMetricResultDTO:
    result_id: str
    semantic_id: str
    definition_version: str
    definition_sha256: str
    batch_id: str
    session_id: str
    release_id: str
    context_id: str
    evaluated_side: str
    numerator: str | None
    denominator: str | None
    value: str | None
    status: TaskMetricStatus
    reason_codes: tuple[str, ...]
    coverage: float
    j_state: str
    source_refs: tuple[Mapping[str, object], ...]
    evidence_refs: tuple[Mapping[str, object], ...]
    computed_at: str
    algorithm_contract_sha256: str


@dataclass(frozen=True, slots=True)
class TaskMetricCompareRequestDTO:
    semantic_id: str
    definition_version: str
    batch_scopes: tuple[Mapping[str, str], ...]
    evaluated_side: str
    phase_scope: str
    start_session_time_us: str
    end_session_time_us: str


@dataclass(frozen=True, slots=True)
class TaskMetricEvidenceDTO:
    semantic_id: str
    definition_sha256: str
    source_refs: tuple[Mapping[str, object], ...]
    evidence_refs: tuple[Mapping[str, object], ...]
    scope_hash: str
    result_sha256: str
