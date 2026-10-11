"""Governed ED-2 Training Plugin composition runtime."""

from __future__ import annotations

from dataclasses import dataclass

from tpaa_application.ed2_upper_products import ED2_TRAINING_PLUGIN_CONTRACTS


class TrainingPluginCompositionError(RuntimeError):
    """Fail-closed Training Plugin composition error."""


@dataclass(frozen=True, slots=True)
class TrainingPluginBinding:
    contract: str
    implementation_id: str
    implementation_version: str
    authority_hash: str
    enabled: bool = True


@dataclass(frozen=True, slots=True)
class TrainingPluginComposition:
    profile_id: str
    profile_version: str
    bindings: tuple[TrainingPluginBinding, ...]

    def payload(self) -> dict[str, object]:
        return {
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "components": [
                {
                    "contract": item.contract,
                    "implementation_id": item.implementation_id,
                    "implementation_version": item.implementation_version,
                    "authority_hash": item.authority_hash,
                    "enabled": item.enabled,
                }
                for item in self.bindings
            ],
            "untrusted_dynamic_loading": False,
        }


class GovernedTrainingPluginRuntime:
    """Compose only the frozen semantic contracts; it never imports arbitrary code."""

    def compose(
        self,
        *,
        profile_id: str,
        profile_version: str,
        bindings: tuple[TrainingPluginBinding, ...],
    ) -> TrainingPluginComposition:
        if not profile_id.strip() or not profile_version.strip():
            raise TrainingPluginCompositionError(
                "ED2_PLUGIN_PROFILE_IDENTITY_REQUIRED"
            )
        contracts = tuple(item.contract for item in bindings)
        if contracts != ED2_TRAINING_PLUGIN_CONTRACTS:
            raise TrainingPluginCompositionError(
                "ED2_PLUGIN_CONTRACT_SET_INVALID"
            )
        for item in bindings:
            if (
                not item.implementation_id.strip()
                or not item.implementation_version.strip()
                or not item.enabled
                or len(item.authority_hash) != 64
                or any(
                    ch not in "0123456789abcdef"
                    for ch in item.authority_hash
                )
            ):
                raise TrainingPluginCompositionError(
                    f"ED2_PLUGIN_BINDING_INVALID:{item.contract}"
                )
        return TrainingPluginComposition(
            profile_id=profile_id,
            profile_version=profile_version,
            bindings=bindings,
        )
