from __future__ import annotations

from pathlib import Path

from tpaa_application.m4_workspace import (
    InMemoryM4DebriefRepository,
    M4DebriefRepository,
)
from tpaa_longitudinal import (
    InMemoryM4LongitudinalReleaseRepository,
    M4LongitudinalReleaseRepository,
)


def test_legacy_m4_repositories_satisfy_engine_neutral_ports() -> None:
    assert isinstance(
        InMemoryM4LongitudinalReleaseRepository(),
        M4LongitudinalReleaseRepository,
    )
    assert isinstance(InMemoryM4DebriefRepository(), M4DebriefRepository)


def test_prcb_m4_service_constructors_do_not_require_inmemory_types() -> None:
    root = Path(__file__).resolve().parents[2]
    release_source = (
        root / "src" / "tpaa_longitudinal" / "m4_release.py"
    ).read_text(encoding="utf-8")
    workspace_source = (
        root / "src" / "tpaa_application" / "m4_workspace.py"
    ).read_text(encoding="utf-8")
    assert "repository: M4LongitudinalReleaseRepository" in release_source
    assert "debrief: M4DebriefRepository" in workspace_source
