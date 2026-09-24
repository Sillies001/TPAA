from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from tpaa_episode import BasicStageError, project_basic_flight_stages

ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
NOMINAL = FIXTURES / "BF_M1_NOMINAL_V1"
AUTHORITY_ROOT = ROOT / "baseline" / "CB-1.4.0" / "canonical"


def _write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _mutated_bundle(tmp_path: Path, markers: list[dict[str, str]]) -> Path:
    target = tmp_path / "BF_M1_NOMINAL_V1"
    shutil.copytree(NOMINAL, target)
    source_path = target / "source" / "flight.json"
    source = json.loads(source_path.read_text(encoding="utf-8"))
    source["official_stage_markers"] = markers
    _write_json(source_path, source)

    manifest_path = target / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    source_sha = hashlib.sha256(source_path.read_bytes()).hexdigest()
    context_sha = manifest["files"]["context"]["sha256"]
    manifest["files"]["source"]["sha256"] = source_sha
    basis = (
        f"source/flight.json={source_sha}\ncontext/evaluation-context.json={context_sha}\n"
    ).encode("ascii")
    manifest["input_sha256"] = hashlib.sha256(basis).hexdigest()
    _write_json(manifest_path, manifest)
    return target


def _nominal_markers() -> list[dict[str, str]]:
    source = json.loads((NOMINAL / "source" / "flight.json").read_text(encoding="utf-8"))
    return list(source["official_stage_markers"])


def test_basic_stage_order_boundaries_and_ids_are_exact_and_replay_stable() -> None:
    first = project_basic_flight_stages(NOMINAL, authority_root=AUTHORITY_ROOT)
    second = project_basic_flight_stages(NOMINAL, authority_root=AUTHORITY_ROOT)

    assert first == second
    assert [stage.stage_type for stage in first.stages] == [
        "SETUP_ENTRY",
        "EXECUTION",
        "STABILIZATION_RECOVERY",
        "COMPLETION",
    ]
    assert [stage.stage_order for stage in first.stages] == [0, 1, 2, 3]
    assert [(stage.start_session_time_us, stage.end_session_time_us) for stage in first.stages] == [
        (1_000_000, 3_000_000),
        (3_000_000, 5_000_000),
        (5_000_000, 7_000_000),
        (7_000_000, 9_000_000),
    ]
    assert len({stage.stage_id for stage in first.stages}) == 4
    assert all(stage.precedence_source == "CONTEXT_OFFICIAL_MARKER" for stage in first.stages)
    assert all(stage.detection_method == "CONTEXT" for stage in first.stages)
    assert first.terminator_marker == "END"
    assert all(stage.stage_type != "END" for stage in first.stages)


def test_stage_membership_is_half_open_at_exact_boundary() -> None:
    projection = project_basic_flight_stages(NOMINAL, authority_root=AUTHORITY_ROOT)
    setup, execution, _, _ = projection.stages

    assert setup.contains(2_999_999) is True
    assert setup.contains(3_000_000) is False
    assert execution.contains(3_000_000) is True


def test_missing_end_terminator_fails_closed(tmp_path: Path) -> None:
    bundle = _mutated_bundle(tmp_path, _nominal_markers()[:-1])

    with pytest.raises(BasicStageError) as caught:
        project_basic_flight_stages(bundle, authority_root=AUTHORITY_ROOT)

    assert caught.value.code == "M1_STAGE_TERMINATOR_MISSING"


def test_unknown_stage_code_fails_closed(tmp_path: Path) -> None:
    markers = _nominal_markers()
    markers[1] = {**markers[1], "stage": "INVENTED_STAGE"}
    bundle = _mutated_bundle(tmp_path, markers)

    with pytest.raises(BasicStageError) as caught:
        project_basic_flight_stages(bundle, authority_root=AUTHORITY_ROOT)

    assert caught.value.code == "M1_STAGE_CODE_UNKNOWN"


def test_duplicate_marker_boundary_fails_closed(tmp_path: Path) -> None:
    markers = _nominal_markers()
    markers[2] = {**markers[2], "source_time_us": markers[1]["source_time_us"]}
    bundle = _mutated_bundle(tmp_path, markers)

    with pytest.raises(BasicStageError) as caught:
        project_basic_flight_stages(bundle, authority_root=AUTHORITY_ROOT)

    assert caught.value.code == "M1_STAGE_INTERVAL_INVALID"


def test_out_of_order_marker_fails_closed(tmp_path: Path) -> None:
    markers = _nominal_markers()
    markers[2] = {**markers[2], "source_time_us": "1000000"}
    bundle = _mutated_bundle(tmp_path, markers)

    with pytest.raises(BasicStageError) as caught:
        project_basic_flight_stages(bundle, authority_root=AUTHORITY_ROOT)

    assert caught.value.code == "M1_STAGE_MARKER_ORDER_INVALID"
