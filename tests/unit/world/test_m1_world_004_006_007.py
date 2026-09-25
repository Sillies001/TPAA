from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_world import WorldProjectionError, project_minimal_p1_world

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY_ROOT = ROOT / "baseline" / "CB-1.4.0" / "canonical"
RELEASE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _project(fixture_id: str = "BF_M1_NOMINAL_V1"):
    return project_minimal_p1_world(
        FIXTURES / fixture_id,
        authority_root=AUTHORITY_ROOT,
        release_id=RELEASE_ID,
    )


def test_minimal_world_is_replay_stable_and_contains_no_fabricated_p_or_j() -> None:
    first = _project()
    second = _project()

    assert first == second
    assert first.world_kind == "TRUTH"
    assert first.capability_code == "BASIC_CORE"
    assert first.present_capability_letters == ("C", "W", "A", "M")
    assert first.absent_capability_letters == ("P", "J")
    assert len(first.canonical_rows) == 8
    assert len(first.stages) == 4
    assert len(first.logical_content_hash) == 64
    assert len(first.request_hash) == 64
    assert first.world_evidence_ref.ref_id == first.world_product_id
    assert first.world_evidence_ref.logical_hash == first.logical_content_hash
    assert first.database_persistence_executed is False
    assert first.observation_projection_executed is False
    assert first.release_publication_executed is False
    assert first.metric_logic_executed is False


def test_world_binds_exact_context_canonical_episode_and_stage_evidence() -> None:
    world = _project()
    classes = [ref.ref_class for ref in world.evidence_refs]

    assert classes.count("EVALUATION_CONTEXT") == 1
    assert classes.count("CANONICAL") == 1
    assert classes.count("EPISODE") == 1
    assert classes.count("STAGE") == 4
    assert all(len(ref.logical_hash) == 64 for ref in world.evidence_refs)
    assert {ref.ref_id for ref in world.evidence_refs if ref.ref_class == "STAGE"} == {
        stage.stage_id for stage in world.stages
    }


def test_logical_content_hash_is_release_independent_but_identity_is_not() -> None:
    first = _project()
    second = project_minimal_p1_world(
        FIXTURES / "BF_M1_NOMINAL_V1",
        authority_root=AUTHORITY_ROOT,
        release_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    )

    assert first.logical_content_hash == second.logical_content_hash
    assert first.world_product_id != second.world_product_id
    assert first.request_hash != second.request_hash


@pytest.mark.parametrize("bundle", sorted(path for path in FIXTURES.iterdir() if path.is_dir()))
def test_every_governed_fixture_has_cross_platform_stable_world_hash(bundle: Path) -> None:
    first = project_minimal_p1_world(
        bundle,
        authority_root=AUTHORITY_ROOT,
        release_id=RELEASE_ID,
    )
    second = project_minimal_p1_world(
        bundle,
        authority_root=AUTHORITY_ROOT,
        release_id=RELEASE_ID,
    )

    assert first.logical_content_hash == second.logical_content_hash
    assert first.world_product_id == second.world_product_id


def test_world_rejects_noncanonical_release_identity() -> None:
    with pytest.raises(WorldProjectionError) as caught:
        project_minimal_p1_world(
            FIXTURES / "BF_M1_NOMINAL_V1",
            authority_root=AUTHORITY_ROOT,
            release_id="not-a-uuid",
        )

    assert caught.value.code == "M1_WORLD_UUID_INVALID"
