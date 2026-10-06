from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_prcb_c2_p4_p5_compute_input_authority_uses_db_1_9_snapshot() -> None:
    source = (
        ROOT / "src" / "tpaa_application" / "p4_p5_compute_input.py"
    ).read_text(encoding="utf-8")
    assert '"registry.dataset_snapshot"' in source
    assert '"input_refs": input_refs' in source
    assert '"input_refs": "uuid_array"' in source
    assert "build_p4_interaction_scope_snapshot(" in source
    assert "exact_p5_composition(" in source
    assert "exact_p4_revision(" in source
    assert "tests/fixtures" not in source
    assert "InMemory" not in source
