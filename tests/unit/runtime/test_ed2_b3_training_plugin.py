from __future__ import annotations

import pytest

from tpaa_application import ED2_TRAINING_PLUGIN_CONTRACTS
from tpaa_runtime import (
    GovernedTrainingPluginRuntime,
    TrainingPluginBinding,
    TrainingPluginCompositionError,
)


def _bindings() -> tuple[TrainingPluginBinding, ...]:
    return tuple(
        TrainingPluginBinding(
            contract=contract,
            implementation_id=f"TPAA:{contract}",
            implementation_version="1.0.0",
            authority_hash="a" * 64,
        )
        for contract in ED2_TRAINING_PLUGIN_CONTRACTS
    )


def test_ed2_b3_training_plugin_composes_exact_frozen_contract_set() -> None:
    composition = GovernedTrainingPluginRuntime().compose(
        profile_id="ED2_TRAINING_PLUGIN_PROFILE",
        profile_version="1.0.0",
        bindings=_bindings(),
    )
    payload = composition.payload()
    assert payload["untrusted_dynamic_loading"] is False
    components = payload["components"]
    assert isinstance(components, list)
    assert tuple(item["contract"] for item in components) == (
        ED2_TRAINING_PLUGIN_CONTRACTS
    )
    assert all("module_path" not in item for item in components)


def test_ed2_b3_training_plugin_rejects_missing_or_reordered_contract() -> None:
    bindings = _bindings()
    with pytest.raises(
        TrainingPluginCompositionError,
        match="CONTRACT_SET_INVALID",
    ):
        GovernedTrainingPluginRuntime().compose(
            profile_id="ED2_TRAINING_PLUGIN_PROFILE",
            profile_version="1.0.0",
            bindings=tuple(reversed(bindings)),
        )
