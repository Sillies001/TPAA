from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path

import pytest

from tools.testing.piqb_b2_p3_fixture import build_fixture, seed_upstream
from tpaa_application import (
    CanonicalP3WorkspaceLayerResolver,
    DurableM7P3WorkspaceRepository,
    P2PersistenceRepository,
    P3PersistenceError,
    P3PersistenceRepository,
)
from tpaa_capability import P3ModelExecutionProfile
from tpaa_storage import (
    LocalObjectStore,
    SQLiteDesktopUnitOfWork,
    bootstrap_sqlite,
)


def _register(
    database: Path,
    object_root: Path,
) -> None:
    fixture = build_fixture()
    object_store = LocalObjectStore(object_root)
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        seed_upstream(uow.canonical_rows)
        repo = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        repo.register_component(
            segment=fixture.segment,
            validation=fixture.validation,
            training=fixture.training,
            model_build=fixture.model_build,
            surface_build=fixture.surface_build,
            model_object=fixture.model_object,
            surface_object=fixture.surface_object,
        )
        repo.register_twin(
            fixture.twin,
            components=(fixture.component,),
        )
        repo.register_estimate(fixture.estimate)
        uow.commit()


def _projection(
    database: Path,
    object_root: Path,
) -> dict[str, object]:
    fixture = build_fixture()
    object_store = LocalObjectStore(object_root)
    with SQLiteDesktopUnitOfWork(database) as uow:
        p3 = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        p2 = P2PersistenceRepository(uow.canonical_rows)
        resolver = CanonicalP3WorkspaceLayerResolver(
            uow.canonical_rows,
            p3,
            p2,
        )
        durable = DurableM7P3WorkspaceRepository(p3, resolver)
        component = p3.exact_component(
            fixture.model_build.model.capability_model_id
        )
        twin = p3.exact_twin_revision(
            fixture.twin.twin_revision_id
        )
        estimate = p3.exact_capability_estimate(
            fixture.estimate.estimate_id
        )
        workspace = durable.exact_estimate(
            fixture.estimate.estimate_id
        )
        result = {
            "segment": asdict(
                p3.exact_segment(
                    fixture.segment.segment_snapshot_id
                )
            ),
            "validation": asdict(
                p3.exact_validation(
                    fixture.validation.validation_snapshot_id
                )
            ),
            "training": asdict(
                p3.exact_training(
                    fixture.training.dataset_snapshot_id
                )
            ),
            "model": asdict(component.model_build.model),
            "surface": asdict(
                component.surface_build.surface
            ),
            "model_artifact_sha256": (
                component.model_build.model.model_artifact_hash
            ),
            "surface_dataset_sha256": (
                component.surface_build.surface.dataset_hash
            ),
            "component_model_ref": (
                component.model_build.model.capability_model_id
            ),
            "model_object_ref_id": (
                component.model_object_ref_id
            ),
            "surface_object_ref_id": (
                component.surface_object_ref_id
            ),
            "twin": asdict(twin),
            "estimate": asdict(estimate),
            "workspace_observed": {
                "release_id": workspace.observed.release_id,
                "logical_hash": workspace.observed.logical_hash,
                "projection": dict(
                    workspace.observed.projection
                ),
            },
            "workspace_adjusted": {
                "release_id": workspace.adjusted.release_id,
                "logical_hash": workspace.adjusted.logical_hash,
                "projection": dict(
                    workspace.adjusted.projection
                ),
            },
            "workspace_component_refs": [
                item.model_build.model.capability_model_id
                for item in workspace.components
            ],
        }
        uow.commit()
        return result


def test_p3_durable_exact_reconstruction_survives_sqlite_restart(
    tmp_path: Path,
) -> None:
    database = tmp_path / "p3.db"
    object_root = tmp_path / "objects"
    bootstrap_sqlite(database)
    fixture = build_fixture()
    _register(database, object_root)
    result = _projection(database, object_root)

    assert result["model"] == asdict(fixture.model_build.model)
    assert result["surface"] == asdict(
        fixture.surface_build.surface
    )
    assert result["twin"] == asdict(fixture.twin)
    assert result["estimate"] == asdict(fixture.estimate)
    assert result["workspace_component_refs"] == [
        fixture.model_build.model.capability_model_id
    ]
    observed = result["workspace_observed"]
    adjusted = result["workspace_adjusted"]
    assert isinstance(observed, dict)
    assert isinstance(adjusted, dict)
    assert observed["release_id"] != adjusted["release_id"]
    assert adjusted["projection"]["estimate_id"] == (
        fixture.selected_p2_estimate_id
    )
    assert observed["projection"]["observation_id"] == (
        fixture.selected_source_observation_id
    )
    assert (
        result["estimate"]["claim_level"]
        == P3ModelExecutionProfile.from_canonical().estimate_claim_level
    )


def test_p3_durable_replay_is_idempotent_and_immutable(
    tmp_path: Path,
) -> None:
    database = tmp_path / "p3-replay.db"
    object_root = tmp_path / "objects-replay"
    bootstrap_sqlite(database)
    fixture = build_fixture()
    _register(database, object_root)
    first = _projection(database, object_root)

    object_store = LocalObjectStore(object_root)
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repo = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        repo.register_component(
            segment=fixture.segment,
            validation=fixture.validation,
            training=fixture.training,
            model_build=fixture.model_build,
            surface_build=fixture.surface_build,
            model_object=fixture.model_object,
            surface_object=fixture.surface_object,
        )
        repo.register_twin(
            fixture.twin,
            components=(fixture.component,),
        )
        repo.register_estimate(fixture.estimate)
        with pytest.raises(P3PersistenceError) as conflict:
            repo.register_estimate(
                replace(fixture.estimate, unit="m")
            )
        assert conflict.value.code == "P3_IMMUTABLE_CONFLICT"
        uow.commit()

    replay = _projection(database, object_root)
    assert replay == first


def test_p3_durable_twin_read_is_exact_not_latest(
    tmp_path: Path,
) -> None:
    database = tmp_path / "p3-twin.db"
    object_root = tmp_path / "objects-twin"
    bootstrap_sqlite(database)
    fixture = build_fixture()
    _register(database, object_root)

    with SQLiteDesktopUnitOfWork(database) as uow:
        p3 = P3PersistenceRepository(
            uow.canonical_rows,
            object_store=LocalObjectStore(object_root),
        )
        resolver = CanonicalP3WorkspaceLayerResolver(
            uow.canonical_rows,
            p3,
            P2PersistenceRepository(uow.canonical_rows),
        )
        durable = DurableM7P3WorkspaceRepository(p3, resolver)
        snapshot = durable.exact_twin(
            fixture.twin.twin_revision_id
        )
        assert snapshot.twin.twin_revision_id == (
            fixture.twin.twin_revision_id
        )
        assert snapshot.estimate.estimate_id == (
            fixture.estimate.estimate_id
        )
        uow.commit()
