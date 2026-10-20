"""Fail-closed blue/green activation after a verified Service staging restore."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from tpaa_platform.filesync import atomic_replace_bytes

_GENERATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class ServiceActivationError(RuntimeError):
    """A staging generation could not be activated without risking write loss."""


class ServiceTrafficSwitch(Protocol):
    """Deployment control-plane operations required for safe blue/green activation."""

    def current_generation(self) -> str: ...

    def set_write_enabled(self, generation_id: str, *, enabled: bool) -> None: ...

    def route_to(self, generation_id: str) -> None: ...

    def health_check(self, generation_id: str) -> bool: ...


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _digest(value: object, *, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or value != value.lower()
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ServiceActivationError(f"{field} must be lowercase SHA-256")
    return value


def _generation(value: object, *, field: str) -> str:
    if not isinstance(value, str) or _GENERATION_ID.fullmatch(value) is None:
        raise ServiceActivationError(f"{field} is invalid")
    return value


@dataclass(frozen=True, slots=True)
class ServiceStagingGeneration:
    """One immutable application/database/object-store deployment generation."""

    generation_id: str
    application_build_sha256: str
    snapshot_sha256: str
    database_identity_sha256: str
    object_store_identity_sha256: str

    def __post_init__(self) -> None:
        _generation(self.generation_id, field="generation_id")
        _digest(self.application_build_sha256, field="application_build_sha256")
        _digest(self.snapshot_sha256, field="snapshot_sha256")
        _digest(self.database_identity_sha256, field="database_identity_sha256")
        _digest(self.object_store_identity_sha256, field="object_store_identity_sha256")


@dataclass(frozen=True, slots=True)
class ServiceActivationReceipt:
    schema: str
    state: str
    activated_at_utc: str
    previous_generation_id: str
    active_generation_id: str
    snapshot_sha256: str
    health_verified: bool
    writes_enabled: bool

    def record(self) -> dict[str, object]:
        return asdict(self)


def _verified_snapshot(receipt: Mapping[str, object]) -> str:
    if (
        receipt.get("schema") != "TPAA_SERVICE_STAGING_RESTORE_V1"
        or receipt.get("profile") != "SERVICE"
        or receipt.get("database_state") != "VERIFIED_STAGING"
        or receipt.get("object_state") != "VERIFIED_STAGING"
        or receipt.get("activation_state") != "NOT_ACTIVATED"
        or receipt.get("activation_required") is not True
    ):
        raise ServiceActivationError("Service staging restore receipt is not activatable")
    return _digest(receipt.get("snapshot_sha256"), field="snapshot_sha256")


def activate_verified_service_staging(
    *,
    restore_receipt: Mapping[str, object],
    target: ServiceStagingGeneration,
    traffic_switch: ServiceTrafficSwitch,
) -> ServiceActivationReceipt:
    """Route to a read-disabled staging generation and open writes only after health."""

    snapshot_sha256 = _verified_snapshot(restore_receipt)
    if snapshot_sha256 != target.snapshot_sha256:
        raise ServiceActivationError("staging generation snapshot does not match restore receipt")
    previous = _generation(
        traffic_switch.current_generation(),
        field="previous_generation_id",
    )
    if previous == target.generation_id:
        raise ServiceActivationError("staging generation is already active")

    routed = False
    writes_enabled = False
    try:
        traffic_switch.set_write_enabled(target.generation_id, enabled=False)
        traffic_switch.route_to(target.generation_id)
        routed = True
        if not traffic_switch.health_check(target.generation_id):
            raise ServiceActivationError("staging generation health check failed")
        traffic_switch.set_write_enabled(target.generation_id, enabled=True)
        writes_enabled = True
    except Exception as exc:
        if routed and not writes_enabled:
            try:
                traffic_switch.route_to(previous)
            except Exception as rollback_exc:
                raise ServiceActivationError(
                    "staging activation failed and traffic rollback also failed"
                ) from rollback_exc
        if isinstance(exc, ServiceActivationError):
            raise
        raise ServiceActivationError("staging activation control-plane operation failed") from exc

    return ServiceActivationReceipt(
        schema="TPAA_SERVICE_ACTIVATION_V1",
        state="ACTIVE",
        activated_at_utc=_utc_now(),
        previous_generation_id=previous,
        active_generation_id=target.generation_id,
        snapshot_sha256=snapshot_sha256,
        health_verified=True,
        writes_enabled=True,
    )


class AtomicFileServiceTrafficSwitch:
    """Local reference adapter using one atomically replaced generation pointer."""

    def __init__(
        self,
        state_file: Path,
        *,
        health_probe: Callable[[str], bool],
        write_control: Callable[[str, bool], None],
    ) -> None:
        if not state_file.is_absolute():
            raise ValueError("Service traffic-switch state path must be absolute")
        self._state_file = state_file
        self._health_probe = health_probe
        self._write_control = write_control

    def current_generation(self) -> str:
        try:
            raw = json.loads(self._state_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ServiceActivationError("active generation pointer is unavailable") from exc
        if not isinstance(raw, Mapping) or raw.get("schema") != "TPAA_ACTIVE_GENERATION_V1":
            raise ServiceActivationError("active generation pointer schema mismatch")
        return _generation(raw.get("generation_id"), field="active_generation_id")

    def set_write_enabled(self, generation_id: str, *, enabled: bool) -> None:
        self._write_control(_generation(generation_id, field="generation_id"), enabled)

    def route_to(self, generation_id: str) -> None:
        selected = _generation(generation_id, field="generation_id")
        payload = {
            "schema": "TPAA_ACTIVE_GENERATION_V1",
            "generation_id": selected,
            "updated_at_utc": _utc_now(),
        }
        atomic_replace_bytes(
            self._state_file,
            (json.dumps(payload, sort_keys=True) + "\n").encode("utf-8"),
        )

    def health_check(self, generation_id: str) -> bool:
        return self._health_probe(_generation(generation_id, field="generation_id"))


__all__ = [
    "AtomicFileServiceTrafficSwitch",
    "ServiceActivationError",
    "ServiceActivationReceipt",
    "ServiceStagingGeneration",
    "ServiceTrafficSwitch",
    "activate_verified_service_staging",
]
