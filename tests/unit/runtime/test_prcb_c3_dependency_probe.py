from __future__ import annotations

from pathlib import Path

from tpaa_runtime.readiness import ProductionDependencyProbe


class _StatusValue:
    schema_version = "1.9.0"
    core_baseline = "CB-1.4.0"


class _StorageStatus:
    def execute(self) -> _StatusValue:
        return _StatusValue()


def test_prcb_c3_dependency_probe_rechecks_object_root_each_time(
    tmp_path: Path,
) -> None:
    root = tmp_path / "objects"
    root.mkdir()
    probe = ProductionDependencyProbe(
        storage_status=_StorageStatus(),
        object_root=root,
    )
    assert set(probe.phase_flags().values()) == {True}

    root.rmdir()
    assert set(probe.phase_flags().values()) == {False}
