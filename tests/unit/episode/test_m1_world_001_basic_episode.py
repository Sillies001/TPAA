from pathlib import Path

from tpaa_episode import detect_basic_episode

ROOT = Path(__file__).resolve().parents[3]
NOMINAL = ROOT / "tests" / "fixtures" / "m1" / "BF_M1_NOMINAL_V1"
GAP = ROOT / "tests" / "fixtures" / "m1" / "BF_M1_GAP_V1"
AUTHORITY_ROOT = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def test_basic_episode_identity_and_interval_are_replay_stable() -> None:
    first = detect_basic_episode(NOMINAL, authority_root=AUTHORITY_ROOT)
    second = detect_basic_episode(NOMINAL, authority_root=AUTHORITY_ROOT)

    assert first == second
    assert first.episode_type == "BASIC_FLIGHT"
    assert first.subject_scope == "AIRCRAFT"
    assert first.start_session_time_us == 1_000_000
    assert first.end_session_time_us == 9_000_000
    assert first.revision_no == 1
    assert first.supersedes_episode_id is None
    assert first.detector_version == "M1_BASIC_FLIGHT_EPISODE_V1"
    assert first.database_persistence_executed is False
    assert first.stage_projection_executed is False
    assert first.world_projection_executed is False
    assert first.metric_logic_executed is False


def test_fixture_case_label_is_not_part_of_episode_business_identity() -> None:
    nominal = detect_basic_episode(NOMINAL, authority_root=AUTHORITY_ROOT)
    gap = detect_basic_episode(GAP, authority_root=AUTHORITY_ROOT)

    assert nominal.fixture_id != gap.fixture_id
    assert nominal.session_id == gap.session_id
    assert nominal.context_id == gap.context_id
    assert nominal.primary_aircraft_id == gap.primary_aircraft_id
    assert nominal.start_session_time_us == gap.start_session_time_us
    assert nominal.end_session_time_us == gap.end_session_time_us
    assert nominal.detector_version == gap.detector_version
    assert nominal.episode_id == gap.episode_id
    assert nominal.logical_hash == gap.logical_hash
