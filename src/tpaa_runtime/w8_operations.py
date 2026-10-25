"""W8 operations productization and fail-closed target-environment gates."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Protocol, cast

from tpaa_qualification import M5QualificationAuthority


class W8OperationsError(RuntimeError):
    """Stable W8 operations/control-plane failure."""


W8_TARGET_PROFILES = (
    "WINDOWS_DESKTOP_X64",
    "LINUX_DESKTOP_X64",
    "WINDOWS_SERVICE_X64",
    "LINUX_SERVICE_X64",
)

W8_EVIDENCE_CATEGORIES = (
    "HARDWARE_WORKLOAD_PERFORMANCE",
    "POSTGRES_SECURITY_LIFECYCLE",
    "OBJECT_STORE_SECURITY_LIFECYCLE",
    "RECOVERY_RPO_RTO_FAILURE_INJECTION",
    "OBSERVABILITY_EXPORTER_SLO_ALERT",
    "PACKAGE_INSTALL_UPGRADE_ROLLBACK",
)

_PROFILE_STATES = frozenset(
    {"NOT_CONFIGURED", "LOCAL_VERIFIED_TARGET_PENDING", "ACCEPTED"}
)
_CONTROL_STAGES = (
    "WRITE_DRAIN",
    "SNAPSHOT",
    "RESTORE_STAGING",
    "ACTIVATE",
    "HEALTH_CHECK",
)


def _sha256(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise W8OperationsError(f"W8_SHA256_INVALID:{field}")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise W8OperationsError(f"W8_TEXT_INVALID:{field}")
    return value


def _canonical_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class W8TargetProfileEvidence:
    profile_id: str
    state: str
    endpoint_ref: str | None
    evidence_sha256: str | None
    categories: Mapping[str, str]

    def __post_init__(self) -> None:
        if self.profile_id not in W8_TARGET_PROFILES:
            raise W8OperationsError(
                f"W8_PROFILE_INVALID:{self.profile_id}"
            )
        if self.state not in _PROFILE_STATES:
            raise W8OperationsError(
                f"W8_PROFILE_STATE_INVALID:{self.profile_id}"
            )
        if tuple(self.categories) != W8_EVIDENCE_CATEGORIES:
            raise W8OperationsError(
                f"W8_EVIDENCE_CATEGORY_SET_INVALID:{self.profile_id}"
            )
        if any(
            value not in {"PENDING", "PASS"}
            for value in self.categories.values()
        ):
            raise W8OperationsError(
                f"W8_EVIDENCE_CATEGORY_STATE_INVALID:{self.profile_id}"
            )
        if self.state == "ACCEPTED":
            _text(self.endpoint_ref, "endpoint_ref")
            _sha256(self.evidence_sha256, "evidence_sha256")
            if any(value != "PASS" for value in self.categories.values()):
                raise W8OperationsError(
                    f"W8_ACCEPTED_EVIDENCE_INCOMPLETE:{self.profile_id}"
                )
        elif self.endpoint_ref is not None or self.evidence_sha256 is not None:
            raise W8OperationsError(
                f"W8_UNACCEPTED_TARGET_REFERENCE_FORBIDDEN:{self.profile_id}"
            )
        object.__setattr__(
            self,
            "categories",
            MappingProxyType(dict(self.categories)),
        )

    def projection(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "state": self.state,
            "endpoint_ref": self.endpoint_ref,
            "evidence_sha256": self.evidence_sha256,
            "categories": dict(self.categories),
            "target_acceptance_claimed": self.state == "ACCEPTED",
        }


class W8OperationsStatus:
    """One machine-readable W8 status bound to frozen M5 authority."""

    def __init__(
        self,
        authority: M5QualificationAuthority,
        evidence: Sequence[W8TargetProfileEvidence],
    ) -> None:
        observed = tuple(item.profile_id for item in evidence)
        if observed != W8_TARGET_PROFILES:
            raise W8OperationsError("W8_TARGET_PROFILE_SET_OR_ORDER_INVALID")
        if tuple(authority.mandatory_profile_ids) != W8_TARGET_PROFILES:
            raise W8OperationsError("W8_AUTHORITY_PROFILE_SET_MISMATCH")
        self._authority = authority
        self._evidence = tuple(evidence)

    @classmethod
    def local_closed(
        cls, authority: M5QualificationAuthority
    ) -> W8OperationsStatus:
        return cls(
            authority,
            tuple(
                W8TargetProfileEvidence(
                    profile_id=profile,
                    state="LOCAL_VERIFIED_TARGET_PENDING",
                    endpoint_ref=None,
                    evidence_sha256=None,
                    categories={
                        category: "PENDING"
                        for category in W8_EVIDENCE_CATEGORIES
                    },
                )
                for profile in W8_TARGET_PROFILES
            ),
        )

    def execute(self) -> dict[str, object]:
        workload = self._authority.workload_profile
        performance = self._authority.performance_resource_profile
        recovery = self._authority.upgrade_backup_restore_profile
        accepted = all(item.state == "ACCEPTED" for item in self._evidence)
        projection = {
            "schema": "TPAA_W8_OPERATIONS_STATUS_V1",
            "authority": {
                "authority_sha256": self._authority.authority_sha256,
                "baseline_lock_sha256": self._authority.baseline_lock_sha256,
                "workload_profile_sha256": self._authority.profile_hashes[
                    "workload_profile_sha256"
                ],
                "performance_profile_sha256": self._authority.profile_hashes[
                    "performance_profile_sha256"
                ],
                "recovery_profile_sha256": self._authority.profile_hashes[
                    "recovery_profile_sha256"
                ],
            },
            "workload_envelope": {
                "state": "FROZEN",
                "workload_id": workload["workload_id"],
                "workload_version": workload["workload_version"],
                "session_count": workload["session_count"],
                "total_observation_target": workload[
                    "total_observation_target"
                ],
                "api_query_count": workload["api_query_count"],
                "desktop_concurrency": workload["desktop_concurrency"],
                "service_concurrency": workload["service_concurrency"],
            },
            "performance_resource": {
                "common_thresholds": dict(
                    cast(Mapping[str, object], performance["common_thresholds"])
                ),
                "desktop_thresholds": dict(
                    cast(
                        Mapping[str, object],
                        performance["desktop_thresholds"],
                    )
                ),
                "service_thresholds": dict(
                    cast(
                        Mapping[str, object],
                        performance["service_thresholds"],
                    )
                ),
            },
            "recovery_objectives": {
                "committed_published_release_rpo_seconds": recovery[
                    "backup_restore"
                ]["committed_published_release_rpo_seconds"],
                "restore_rto_seconds_max": recovery["backup_restore"][
                    "restore_rto_seconds_max"
                ],
                "partial_cross_store_restore_permitted": recovery[
                    "backup_restore"
                ]["partial_cross_store_restore_permitted"],
            },
            "target_profiles": [item.projection() for item in self._evidence],
            "production_activation_allowed": accepted,
            "target_environment_acceptance_claimed": accepted,
            "formal_release_claimed": False,
        }
        return {
            **projection,
            "logical_status_sha256": _canonical_hash(projection),
        }


def build_w8_operations_status(
    authority: M5QualificationAuthority,
    records: Sequence[Mapping[str, object]],
) -> W8OperationsStatus:
    """Build a strict status from one approved deployment evidence document."""

    evidence: list[W8TargetProfileEvidence] = []
    for record in records:
        raw_categories = record.get("categories")
        if not isinstance(raw_categories, Mapping):
            raise W8OperationsError("W8_EVIDENCE_CATEGORIES_INVALID")
        evidence.append(
            W8TargetProfileEvidence(
                profile_id=str(record.get("profile_id", "")),
                state=str(record.get("state", "")),
                endpoint_ref=(
                    None
                    if record.get("endpoint_ref") is None
                    else str(record["endpoint_ref"])
                ),
                evidence_sha256=(
                    None
                    if record.get("evidence_sha256") is None
                    else str(record["evidence_sha256"])
                ),
                categories={str(key): str(value) for key, value in raw_categories.items()},
            )
        )
    return W8OperationsStatus(authority, evidence)


@dataclass(frozen=True, slots=True)
class W8ControlReceipt:
    stage: str
    state: str
    snapshot_sha256: str
    operation_ref: str

    def __post_init__(self) -> None:
        if self.stage not in (*_CONTROL_STAGES, "ROLLBACK"):
            raise W8OperationsError(f"W8_CONTROL_STAGE_INVALID:{self.stage}")
        _text(self.state, "state")
        _sha256(self.snapshot_sha256, "snapshot_sha256")
        _text(self.operation_ref, "operation_ref")

    def projection(self) -> dict[str, str]:
        return {
            "stage": self.stage,
            "state": self.state,
            "snapshot_sha256": self.snapshot_sha256,
            "operation_ref": self.operation_ref,
        }


class W8ServiceControlPort(Protocol):
    def write_drain(self) -> W8ControlReceipt: ...

    def snapshot(self, drain: W8ControlReceipt) -> W8ControlReceipt: ...

    def restore_staging(self, snapshot: W8ControlReceipt) -> W8ControlReceipt: ...

    def activate(self, restored: W8ControlReceipt) -> W8ControlReceipt: ...

    def health_check(self, activated: W8ControlReceipt) -> W8ControlReceipt: ...

    def rollback(self, activated: W8ControlReceipt) -> W8ControlReceipt: ...


class W8ServiceRecoveryOrchestrator:
    """Sequence Service recovery and automatically roll back failed activation."""

    def __init__(
        self,
        port: W8ServiceControlPort,
        *,
        audit: Callable[[Mapping[str, object]], None] | None = None,
    ) -> None:
        self._port = port
        self._audit = audit or (lambda _record: None)

    @staticmethod
    def _accept(
        receipt: W8ControlReceipt,
        *,
        stage: str,
        expected_state: str,
        snapshot_sha256: str | None,
    ) -> None:
        if receipt.stage != stage or receipt.state != expected_state:
            raise W8OperationsError(
                f"W8_CONTROL_RECEIPT_INVALID:{stage}:{receipt.state}"
            )
        if (
            snapshot_sha256 is not None
            and receipt.snapshot_sha256 != snapshot_sha256
        ):
            raise W8OperationsError(f"W8_CONTROL_SNAPSHOT_DRIFT:{stage}")

    def _record(self, receipt: W8ControlReceipt) -> None:
        self._audit(
            {
                "schema": "TPAA_W8_SERVICE_CONTROL_AUDIT_V1",
                **receipt.projection(),
            }
        )

    def execute(self) -> dict[str, object]:
        receipts: list[W8ControlReceipt] = []
        drain = self._port.write_drain()
        self._accept(
            drain,
            stage="WRITE_DRAIN",
            expected_state="MANAGED_WRITES_BLOCKED",
            snapshot_sha256=None,
        )
        receipts.append(drain)
        self._record(drain)

        snapshot = self._port.snapshot(drain)
        self._accept(
            snapshot,
            stage="SNAPSHOT",
            expected_state="VERIFIED",
            snapshot_sha256=None,
        )
        receipts.append(snapshot)
        self._record(snapshot)

        restored = self._port.restore_staging(snapshot)
        self._accept(
            restored,
            stage="RESTORE_STAGING",
            expected_state="VERIFIED_NOT_ACTIVATED",
            snapshot_sha256=snapshot.snapshot_sha256,
        )
        receipts.append(restored)
        self._record(restored)

        activated = self._port.activate(restored)
        self._accept(
            activated,
            stage="ACTIVATE",
            expected_state="ACTIVATED_PENDING_HEALTH",
            snapshot_sha256=snapshot.snapshot_sha256,
        )
        receipts.append(activated)
        self._record(activated)

        try:
            health = self._port.health_check(activated)
            self._accept(
                health,
                stage="HEALTH_CHECK",
                expected_state="READY",
                snapshot_sha256=snapshot.snapshot_sha256,
            )
        except Exception as exc:
            rollback = self._port.rollback(activated)
            self._accept(
                rollback,
                stage="ROLLBACK",
                expected_state="PRIOR_TARGET_RESTORED",
                snapshot_sha256=snapshot.snapshot_sha256,
            )
            receipts.append(rollback)
            self._record(rollback)
            raise W8OperationsError(
                f"W8_ACTIVATION_HEALTH_FAILED_ROLLED_BACK:{type(exc).__name__}"
            ) from exc
        receipts.append(health)
        self._record(health)
        projection = [receipt.projection() for receipt in receipts]
        return {
            "schema": "TPAA_W8_SERVICE_CONTROL_RESULT_V1",
            "state": "ACTIVATED_READY",
            "snapshot_sha256": snapshot.snapshot_sha256,
            "receipts": projection,
            "receipt_chain_sha256": _canonical_hash(projection),
        }


__all__ = [
    "W8_EVIDENCE_CATEGORIES",
    "W8_TARGET_PROFILES",
    "W8ControlReceipt",
    "W8OperationsError",
    "W8OperationsStatus",
    "W8ServiceControlPort",
    "W8ServiceRecoveryOrchestrator",
    "W8TargetProfileEvidence",
    "build_w8_operations_status",
]
