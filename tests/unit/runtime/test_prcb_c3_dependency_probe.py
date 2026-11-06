from __future__ import annotations

from pathlib import Path

from tpaa_runtime.readiness import ProductionDependencyProbe


class _StatusValue:
    schema_version = "1.9.0"
    core_baseline = "CB-1.5.0"
    authority_artifact_id = "CORE_LOGICAL_MODEL"
    authority_sha256 = "a" * 64
    baseline_lock_sha256 = "b" * 64


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


def test_w1_readiness_reports_all_dependency_components(tmp_path: Path) -> None:
    root = tmp_path / "objects"
    root.mkdir()
    probe = ProductionDependencyProbe(
        storage_status=_StorageStatus(),
        object_root=root,
        identity_ready=False,
        migration_ready=lambda: True,
    )
    components = probe.component_status().payload()
    assert components == {
        "migration_head": True,
        "authority_closure": True,
        "object_store": True,
        "identity": False,
        "worker": True,
    }
    assert set(probe.phase_flags().values()) == {False}
