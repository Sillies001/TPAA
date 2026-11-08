from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_canonical import CanonicalArtifactError, CanonicalArtifactLoader
from tpaa_runtime.gui_capabilities import (
    GuiCapabilityError,
    _validate_contiguous_phase_lineage,
    resolve_gui_capabilities,
)

ROOT = Path(__file__).resolve().parents[3]


def test_trusted_g4_g5_and_g6_capability_sets_are_lineage_aware() -> None:
    g4 = resolve_gui_capabilities(ROOT / "baseline" / "CB-1.9.0" / "canonical")
    g5 = resolve_gui_capabilities(ROOT / "baseline" / "CB-1.10.0" / "canonical")
    g6 = resolve_gui_capabilities(ROOT / "baseline" / "CB-1.11.0" / "canonical")
    assert g4.core_baseline == "CB-1.9.0"
    assert g4.active == frozenset({"G2", "G3", "G4"})
    assert g5.core_baseline == "CB-1.10.0"
    assert g5.active == frozenset({"G2", "G3", "G4", "G5"})
    assert g6.core_baseline == "CB-1.11.0"
    assert g6.active == frozenset({"G2", "G3", "G4", "G5", "G6"})


def test_directory_name_alone_cannot_activate_without_exact_lock_pin() -> None:
    with pytest.raises(CanonicalArtifactError, match="BASELINE_LOCK_HASH_MISMATCH"):
        CanonicalArtifactLoader(
            ROOT / "baseline" / "CB-1.10.0",
            expected_core_baseline="CB-1.10.0",
            trusted_lock_sha256="0" * 64,
            expected_controlled_artifact_count=51,
        )


def test_phase_approval_lineage_must_be_contiguous() -> None:
    with pytest.raises(GuiCapabilityError, match="GUI_PHASE_LINEAGE_GAP:G6"):
        _validate_contiguous_phase_lineage({"G2", "G3", "G4", "G6"})
