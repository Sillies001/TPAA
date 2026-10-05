"""Exact protected-main capability admission projection for PIQB B1."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from tpaa_context import M8AdmissionEvidence, P6AdmissionEvidence
from tpaa_longitudinal import P3AdmissionEvidence

_REQUIRED_JOB_COUNT = 14
_PHASES = ("P1", "P2", "P3", "P4", "P5", "P6")


class FeatureAvailabilityState(StrEnum):
    """Product-facing availability states frozen by PIQB B0."""

    AVAILABLE = "AVAILABLE"
    NOT_ADMITTED = "NOT_ADMITTED"
    UNAVAILABLE = "UNAVAILABLE"
    UNSUPPORTED_PROFILE = "UNSUPPORTED_PROFILE"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    NOT_CONFIGURED = "NOT_CONFIGURED"


@dataclass(frozen=True, slots=True)
class AdmissionRecord:
    """One immutable protected-main capability qualification record."""

    phase: str
    qualification: str
    source_revision: str
    run_number: int
    actions_run_id: int
    event_name: str = "push"
    git_ref: str = "refs/heads/main"
    protected_main: bool = True
    decision: str = "GO"
    run_conclusion: str = "success"
    required_jobs_success: int = _REQUIRED_JOB_COUNT
    required_jobs_total: int = _REQUIRED_JOB_COUNT
    admitted: bool = True

    @property
    def exact(self) -> bool:
        return (
            self.phase in _PHASES
            and len(self.source_revision) == 40
            and all(ch in "0123456789abcdef" for ch in self.source_revision)
            and self.run_number > 0
            and self.actions_run_id > 0
            and self.event_name == "push"
            and self.git_ref == "refs/heads/main"
            and self.protected_main
            and self.decision == "GO"
            and self.run_conclusion == "success"
            and self.required_jobs_success == _REQUIRED_JOB_COUNT
            and self.required_jobs_total == _REQUIRED_JOB_COUNT
            and self.admitted
        )


_QUALIFIED_ROADMAP = {
    "P1": AdmissionRecord(
        phase="P1",
        qualification="P1_M5_QUALIFIED",
        source_revision="68767397c028f7aa6ad3a22a49302710481951c6",
        run_number=470,
        actions_run_id=36549239360,
    ),
    "P2": AdmissionRecord(
        phase="P2",
        qualification="P2_M6_QUALIFIED",
        source_revision="892e4a64a321be9c7252b66207a7d1d90a6ce98d",
        run_number=494,
        actions_run_id=36697493917,
    ),
    "P3": AdmissionRecord(
        phase="P3",
        qualification="P3_M7_QUALIFIED",
        source_revision="c78604ade0aeffdbf7395fccfc0951751beae751",
        run_number=510,
        actions_run_id=36807335564,
    ),
    "P4": AdmissionRecord(
        phase="P4",
        qualification="P4_P5_M8_QUALIFIED",
        source_revision="06b9f0c55dda803765fc265b8d5ca0353620476f",
        run_number=527,
        actions_run_id=36869057230,
    ),
    "P5": AdmissionRecord(
        phase="P5",
        qualification="P4_P5_M8_QUALIFIED",
        source_revision="06b9f0c55dda803765fc265b8d5ca0353620476f",
        run_number=527,
        actions_run_id=36869057230,
    ),
    "P6": AdmissionRecord(
        phase="P6",
        qualification="P6_M9_QUALIFIED",
        source_revision="06945127c86069918ffdfd415201d321d53aae4d",
        run_number=549,
        actions_run_id=37000963653,
    ),
}


class ProductAdmissionResolver:
    """Resolve product capability admission from exact qualification evidence."""

    def __init__(
        self,
        records: Mapping[str, AdmissionRecord] | None = None,
    ) -> None:
        source = dict(_QUALIFIED_ROADMAP if records is None else records)
        if tuple(source) != _PHASES:
            raise ValueError("admission records must contain ordered P1-P6")
        if any(record.phase != phase for phase, record in source.items()):
            raise ValueError("admission record phase mismatch")
        self._records = source

    def record(self, phase: str) -> AdmissionRecord:
        try:
            return self._records[phase]
        except KeyError as exc:
            raise ValueError(f"unsupported capability phase: {phase}") from exc

    def admitted(self, phase: str) -> bool:
        return self.record(phase).exact

    def p3_evidence(self) -> P3AdmissionEvidence | None:
        record = self.record("P3")
        if not record.exact:
            return None
        return P3AdmissionEvidence(
            source_revision=record.source_revision,
            event_name=record.event_name,
            git_ref=record.git_ref,
            protected_main=record.protected_main,
            m7_exit_decision=record.decision,
            run_conclusion=record.run_conclusion,
            required_jobs_success=record.required_jobs_success,
            required_jobs_total=record.required_jobs_total,
            p4_p6_inactive=True,
        )

    def m8_evidence(self) -> M8AdmissionEvidence | None:
        p4 = self.record("P4")
        p5 = self.record("P5")
        if not p4.exact or not p5.exact or p4.source_revision != p5.source_revision:
            return None
        return M8AdmissionEvidence(
            source_revision=p4.source_revision,
            event_name=p4.event_name,
            git_ref=p4.git_ref,
            protected_main=p4.protected_main,
            m8_exit_decision=p4.decision,
            run_conclusion=p4.run_conclusion,
            required_jobs_success=p4.required_jobs_success,
            required_jobs_total=p4.required_jobs_total,
            p4_admitted=True,
            p5_admitted=True,
            p6_inactive=True,
        )

    def p6_evidence(self) -> P6AdmissionEvidence | None:
        record = self.record("P6")
        if not record.exact:
            return None
        return P6AdmissionEvidence(
            source_revision=record.source_revision,
            event_name=record.event_name,
            git_ref=record.git_ref,
            protected_main=record.protected_main,
            m9_exit_decision=record.decision,
            run_conclusion=record.run_conclusion,
            required_jobs_success=record.required_jobs_success,
            required_jobs_total=record.required_jobs_total,
            p6_admitted=True,
        )

    def feature_state(
        self,
        phase: str,
        *,
        configured: bool,
        dependency_ready: bool = True,
        supported_profile: bool = True,
        available: bool = True,
    ) -> FeatureAvailabilityState:
        if not supported_profile:
            return FeatureAvailabilityState.UNSUPPORTED_PROFILE
        if not self.admitted(phase):
            return FeatureAvailabilityState.NOT_ADMITTED
        if not configured:
            return FeatureAvailabilityState.NOT_CONFIGURED
        if not dependency_ready:
            return FeatureAvailabilityState.DEPENDENCY_MISSING
        if not available:
            return FeatureAvailabilityState.UNAVAILABLE
        return FeatureAvailabilityState.AVAILABLE


class ProductFeatureAvailability:
    """Application use case exposing one deterministic P1-P6 availability view."""

    def __init__(
        self,
        resolver: ProductAdmissionResolver,
        *,
        configured: Mapping[str, bool],
        dependency_ready: Mapping[str, bool] | None = None,
        supported_profile: Mapping[str, bool] | None = None,
        available: Mapping[str, bool] | None = None,
    ) -> None:
        if tuple(configured) != _PHASES:
            raise ValueError("configured feature map must contain ordered P1-P6")
        self._resolver = resolver
        self._configured = dict(configured)
        self._dependency_ready = self._phase_flags(
            dependency_ready,
            default=True,
            field="dependency_ready",
        )
        self._supported_profile = self._phase_flags(
            supported_profile,
            default=True,
            field="supported_profile",
        )
        self._available = self._phase_flags(
            available,
            default=True,
            field="available",
        )

    @staticmethod
    def _phase_flags(
        values: Mapping[str, bool] | None,
        *,
        default: bool,
        field: str,
    ) -> dict[str, bool]:
        if values is None:
            return {phase: default for phase in _PHASES}
        if tuple(values) != _PHASES:
            raise ValueError(f"{field} map must contain ordered P1-P6")
        return dict(values)

    def execute(self) -> dict[str, object]:
        items: list[dict[str, object]] = []
        for phase in _PHASES:
            record = self._resolver.record(phase)
            state = self._resolver.feature_state(
                phase,
                configured=self._configured[phase],
                dependency_ready=self._dependency_ready[phase],
                supported_profile=self._supported_profile[phase],
                available=self._available[phase],
            )
            items.append(
                {
                    "phase": phase,
                    "state": state.value,
                    "admitted": record.exact,
                    "qualification": record.qualification,
                    "source_revision": record.source_revision,
                    "run_number": record.run_number,
                    "actions_run_id": record.actions_run_id,
                }
            )
        return {
            "schema": "TPAA_PRODUCT_FEATURE_AVAILABILITY_V1",
            "items": items,
        }
