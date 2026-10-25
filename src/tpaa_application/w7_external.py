"""W7 external-capability activation registry.

External integrations are unavailable unless an exact endpoint and immutable
acceptance-evidence digest are configured together.  This is a runtime gate,
not a presentation convention.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

W7_EXTERNAL_CAPABILITIES = (
    "JOINT_LVC_LIVE_GATEWAY",
    "EXTERNAL_PLUGIN_EXECUTION",
    "MEDIA_OBJECT_DELIVERY_EXPORT",
    "MODEL_ONLINE_MONITORING_ROLLBACK",
)

_STATES = frozenset(
    {
        "NOT_CONFIGURED",
        "DEPENDENCY_MISSING",
        "NOT_ACCEPTED",
        "UNAVAILABLE",
        "AVAILABLE",
    }
)


class W7ExternalCapabilityError(ValueError):
    """Invalid or unsafe external-capability activation record."""


@dataclass(frozen=True, slots=True)
class W7ExternalCapability:
    capability: str
    state: str
    reason_code: str
    endpoint_ref: str | None = None
    acceptance_evidence_sha256: str | None = None

    def __post_init__(self) -> None:
        if self.capability not in W7_EXTERNAL_CAPABILITIES:
            raise W7ExternalCapabilityError(f"W7_EXTERNAL_CAPABILITY_INVALID:{self.capability}")
        if self.state not in _STATES:
            raise W7ExternalCapabilityError(f"W7_EXTERNAL_STATE_INVALID:{self.capability}")
        if not self.reason_code:
            raise W7ExternalCapabilityError(f"W7_EXTERNAL_REASON_REQUIRED:{self.capability}")
        if self.state == "AVAILABLE":
            if not self.endpoint_ref or not self.endpoint_ref.strip():
                raise W7ExternalCapabilityError(f"W7_EXTERNAL_ENDPOINT_REQUIRED:{self.capability}")
            digest = self.acceptance_evidence_sha256
            if (
                digest is None
                or len(digest) != 64
                or digest != digest.lower()
                or any(char not in "0123456789abcdef" for char in digest)
            ):
                raise W7ExternalCapabilityError(
                    f"W7_EXTERNAL_ACCEPTANCE_EVIDENCE_REQUIRED:{self.capability}"
                )
        elif self.endpoint_ref is not None or self.acceptance_evidence_sha256 is not None:
            raise W7ExternalCapabilityError(
                f"W7_EXTERNAL_UNACCEPTED_REFERENCE_FORBIDDEN:{self.capability}"
            )

    def projection(self) -> dict[str, object]:
        return {
            "capability": self.capability,
            "state": self.state,
            "action_enabled": self.state == "AVAILABLE",
            "reason_code": self.reason_code,
            "endpoint_ref": self.endpoint_ref,
            "acceptance_evidence_sha256": self.acceptance_evidence_sha256,
        }


class W7ExternalCapabilityRegistry:
    """Exact four-capability activation view used by Desktop and Service."""

    def __init__(self, records: Sequence[W7ExternalCapability]) -> None:
        observed = tuple(record.capability for record in records)
        if observed != W7_EXTERNAL_CAPABILITIES:
            raise W7ExternalCapabilityError("W7_EXTERNAL_CAPABILITY_SET_OR_ORDER_INVALID")
        self._records = tuple(records)

    @classmethod
    def local_closed(cls) -> W7ExternalCapabilityRegistry:
        reasons = (
            "APPROVED_STAGING_ENDPOINT_REQUIRED",
            "TRUST_ROOT_AND_SANDBOX_REQUIRED",
            "OBJECT_STORE_AND_REDACTION_POLICY_REQUIRED",
            "MONITORING_ENDPOINT_AND_APPROVAL_REQUIRED",
        )
        return cls(
            tuple(
                W7ExternalCapability(
                    capability=capability,
                    state="NOT_CONFIGURED",
                    reason_code=reason,
                )
                for capability, reason in zip(W7_EXTERNAL_CAPABILITIES, reasons, strict=True)
            )
        )

    def execute(self) -> dict[str, object]:
        items = [record.projection() for record in self._records]
        return {
            "schema": "TPAA_W7_EXTERNAL_CAPABILITY_AVAILABILITY_V1",
            "items": items,
            "all_external_actions_gated": not any(bool(item["action_enabled"]) for item in items),
        }


def build_w7_external_registry(
    records: Sequence[Mapping[str, object]],
) -> W7ExternalCapabilityRegistry:
    """Strict mapping adapter for an approved deployment configuration loader."""

    return W7ExternalCapabilityRegistry(
        tuple(
            W7ExternalCapability(
                capability=str(record.get("capability", "")),
                state=str(record.get("state", "")),
                reason_code=str(record.get("reason_code", "")),
                endpoint_ref=(
                    None if record.get("endpoint_ref") is None else str(record["endpoint_ref"])
                ),
                acceptance_evidence_sha256=(
                    None
                    if record.get("acceptance_evidence_sha256") is None
                    else str(record["acceptance_evidence_sha256"])
                ),
            )
            for record in records
        )
    )


__all__ = [
    "W7_EXTERNAL_CAPABILITIES",
    "W7ExternalCapability",
    "W7ExternalCapabilityError",
    "W7ExternalCapabilityRegistry",
    "build_w7_external_registry",
]
