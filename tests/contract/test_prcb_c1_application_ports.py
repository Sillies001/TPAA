from __future__ import annotations

from pathlib import Path

from tpaa_application import ApplicationService
from tpaa_application.m3_publication import (
    InMemoryM3ReleasePublicationRepository,
    M3PublicationService,
)


class _Storage:
    def execute(self):
        raise RuntimeError("not used")


def test_prcb_application_service_uses_structural_m1_m3_m4_ports() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (
        root / "src" / "tpaa_application" / "service.py"
    ).read_text(encoding="utf-8")
    assert "m1_publication: P1PublicationUseCase" in source
    assert "m3_publication: M3PublicationUseCase" in source
    assert "m4_workspace: M4WorkspaceUseCase" in source
    assert "m1_publication: M1PublicationService" not in source
    assert "m3_publication: M3PublicationService" not in source
    assert "m4_workspace: M4WorkspaceService" not in source


def test_legacy_m3_service_still_satisfies_workspace_surface() -> None:
    service = M3PublicationService(InMemoryM3ReleasePublicationRepository())
    application = ApplicationService(
        get_storage_baseline_status=_Storage(),
        m3_publication=service,
    )
    assert callable(application.m3_workspace)
