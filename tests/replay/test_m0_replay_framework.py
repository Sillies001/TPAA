from __future__ import annotations

import json

from tools.testing.fixture_harness import DEFAULT_BUNDLE, golden_check, load_spec, replay_check


def test_m0_replay_framework_uses_frozen_refs_not_current_refs() -> None:
    spec = load_spec(DEFAULT_BUNDLE)
    current = json.loads(spec.current_refs_path.read_text(encoding="utf-8"))

    assert current["context_ref"] != spec.replay_context_ref
    assert current["stage_ref"] != spec.replay_stage_ref
    assert current["profile_ref"] != spec.replay_profile_ref
    assert replay_check(DEFAULT_BUNDLE) == golden_check(DEFAULT_BUNDLE)
