from __future__ import annotations

from tools.storage.migration_harness import run


def test_migration_harness_replays_1_6_to_1_7_to_1_8_to_1_9_chain() -> None:
    evidence = run()
    assert evidence["status"] == "PASS"
    assert evidence["schema"] == "TPAA_M0_MIGRATION_HARNESS_V4"
    assert evidence["schema_target"] == "1.9.0"
    assert evidence["schema_transition"] == "1.6.0->1.7.0->1.8.0->1.9.0"
    assert evidence["proposal_chain"] == ["ACP-216", "ACP-219", "ACP-221"]
    checks = evidence["checks"]
    assert isinstance(checks, dict)
    assert checks
    assert all(checks.values())
