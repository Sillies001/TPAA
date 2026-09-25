from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tpaa_ingest import load_m2_reference_truth, load_m2_time_alignment
from tpaa_world import (
    M2ReferenceTimeWorldError,
    build_m2_reference_time_world,
    project_m2_reference_time_world,
)

ROOT = Path(__file__).resolve().parents[3]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
FIXTURES = ROOT / "tests" / "fixtures" / "m2"
REFERENCE = FIXTURES / "RT_M2_NOMINAL_V1"
TIME = FIXTURES / "TA_M2_NOMINAL_V1"
RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1"


def _project(release_id: str = RELEASE_ID):
    return project_m2_reference_time_world(
        REFERENCE,
        TIME,
        authority_root=AUTHORITY,
        release_id=release_id,
    )


def test_reference_time_world_is_replay_stable_and_core_compatible() -> None:
    first = _project()
    second = _project()

    assert first == second
    assert first.reference_manifest.world_kind == "TRUTH"
    assert first.time_manifest.world_kind == "MACHINE"
    assert first.reference_manifest.status == "READY"
    assert first.time_manifest.status == "READY"
    assert first.reference_manifest.session_id == first.time_manifest.session_id
    assert first.reference_manifest.session_id == first.reference_truth.session_id
    assert first.time_manifest.session_id == first.time_alignment.session_id
    assert first.reference_manifest.logical_content_hash == (
        first.reference_manifest.artifact_sha256
    )
    assert first.time_manifest.logical_content_hash == first.time_manifest.artifact_sha256
    assert len(first.reference_manifest.logical_content_hash) == 64
    assert len(first.time_manifest.logical_content_hash) == 64
    assert len(first.logical_hash) == 64
    assert len(first.core_schema_sha256) == 64
    assert len(first.world_policy_sha256) == 64
    assert first.shadow_schema_created is False
    assert first.metric_logic_executed is False
    assert first.stage_projection_executed is False
    assert first.persistence_executed is False
    assert first.observation_projection_executed is False
    assert first.release_publication_executed is False


def test_world_keeps_frozen_upstream_projections_without_recalculation() -> None:
    world = _project()

    assert world.reference_truth == load_m2_reference_truth(REFERENCE)
    assert world.time_alignment == load_m2_time_alignment(TIME)
    assert world.reference_manifest.start_session_time_us == min(
        row.session_time_us for row in world.reference_truth.rows
    )
    assert world.reference_manifest.end_session_time_us == max(
        row.session_time_us for row in world.reference_truth.rows
    )
    assert world.time_manifest.start_session_time_us < world.time_manifest.end_session_time_us


def test_release_changes_identity_not_logical_content() -> None:
    first = _project()
    second = _project("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2")

    assert first.logical_hash == second.logical_hash
    assert (
        first.reference_manifest.logical_content_hash
        == second.reference_manifest.logical_content_hash
    )
    assert first.time_manifest.logical_content_hash == second.time_manifest.logical_content_hash
    assert first.reference_manifest.world_product_id != second.reference_manifest.world_product_id
    assert first.time_manifest.world_product_id != second.time_manifest.world_product_id
    assert first.reference_manifest.request_hash != second.reference_manifest.request_hash
    assert first.time_manifest.request_hash != second.time_manifest.request_hash


def test_world_fails_closed_on_session_drift() -> None:
    reference = load_m2_reference_truth(REFERENCE)
    time = replace(
        load_m2_time_alignment(TIME),
        session_id="99999999-9999-4999-8999-999999999999",
    )

    with pytest.raises(M2ReferenceTimeWorldError) as caught:
        build_m2_reference_time_world(
            reference,
            time,
            authority_root=AUTHORITY,
            release_id=RELEASE_ID,
        )

    assert caught.value.code == "M2_WORLD_SESSION_DRIFT"


def test_world_rejects_noncanonical_release_identity() -> None:
    with pytest.raises(M2ReferenceTimeWorldError) as caught:
        project_m2_reference_time_world(
            REFERENCE,
            TIME,
            authority_root=AUTHORITY,
            release_id="not-a-uuid",
        )

    assert caught.value.code == "M2_WORLD_UUID_INVALID"
