from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import pytest

from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
FIXTURE = ROOT / "tests" / "fixtures" / "m2" / "C3_QA_SNS_AUTHORITY_V1"


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    ).hexdigest()


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    return [
        [sum(a[i][k] * b[k][j] for k in range(len(b))) for j in range(len(b[0]))]
        for i in range(len(a))
    ]


def _transpose(a: list[list[float]]) -> list[list[float]]:
    return [list(row) for row in zip(*a, strict=True)]


def _quad(g: list[float], p: list[list[float]]) -> float:
    return sum(g[i] * p[i][j] * g[j] for i in range(len(g)) for j in range(len(g)))


def _quat_matrix(raw: list[float]) -> list[list[float]]:
    if len(raw) != 4 or not all(math.isfinite(value) for value in raw):
        raise ValueError("quaternion invalid")
    norm = math.sqrt(sum(value * value for value in raw))
    if norm == 0.0:
        raise ValueError("quaternion zero norm")
    w, x, y, z = (value / norm for value in raw)
    return [
        [1.0 - 2.0 * (y * y + z * z), 2.0 * (x * y - z * w), 2.0 * (x * z + y * w)],
        [2.0 * (x * y + z * w), 1.0 - 2.0 * (x * x + z * z), 2.0 * (y * z - x * w)],
        [2.0 * (x * z - y * w), 2.0 * (y * z + x * w), 1.0 - 2.0 * (x * x + y * y)],
    ]


def _mv(a: list[list[float]], v: list[float]) -> list[float]:
    return [sum(row[j] * v[j] for j in range(len(v))) for row in a]


def _authority() -> dict[str, Any]:
    loader = CanonicalArtifactLoader(BASELINE)
    artifact = loader.load(
        "M2_QA_SNS_AUTHORITY",
        expectation=ArtifactExpectation(
            version="1.0.0",
            schema_version="1.6.0",
            required_top_level_keys=(
                "qa_001_frame_convention",
                "qa_002_uncertainty_contract",
                "reference_match_quality_profile",
                "golden_vectors",
            ),
        ),
    )
    return dict(artifact.payload)


def test_c3_authority_is_controlled_approved_and_fixture_hash_locked() -> None:
    authority = _authority()
    assert authority["status"] == "APPROVED_BY_DELEGATED_OWNER_AUTHORITY"
    assert authority["change_class"] == "C3_SEMANTIC_CONTRACT"

    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    source_path = FIXTURE / manifest["files"]["source"]["path"]
    source_bytes = source_path.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    assert source_sha == manifest["files"]["source"]["sha256"]
    expected_input = hashlib.sha256(
        f"source/c3-authority-golden.json={source_sha}\n".encode("ascii")
    ).hexdigest()
    assert expected_input == manifest["input_sha256"]

    source = json.loads(source_bytes.decode("utf-8"))
    assert source["authority_sha256"] == manifest["authority_refs"]["c3_authority_sha256"]
    assert source["golden_vectors"] == authority["golden_vectors"]
    assert source["reference_match_quality_profile"] == authority["reference_match_quality_profile"]


def test_c3_qa001_nonidentity_frame_and_boresight_golden() -> None:
    authority = _authority()
    case = authority["golden_vectors"]["qa_001"]
    inp = case["input"]
    expected = case["expected"]

    r_ecef = [
        inp["target_position_ecef_m"][i] - inp["own_position_ecef_m"][i]
        for i in range(3)
    ]
    r_body = _mv(_transpose(_quat_matrix(inp["own_attitude_quat"])), r_ecef)
    r_sensor = _mv(_transpose(_quat_matrix(inp["sensor_boresight_quat"])), r_body)

    assert r_ecef == pytest.approx(expected["r_rel_ecef_m"], abs=1e-12)
    assert r_body == pytest.approx(expected["own_body_vector_m"], abs=1e-12)
    assert r_sensor == pytest.approx(expected["sensor_vector_m"], abs=1e-12)
    assert math.atan2(r_body[1], r_body[0]) == pytest.approx(
        expected["own_body_az_rad"], abs=1e-12
    )
    assert math.atan2(-r_body[2], math.hypot(r_body[0], r_body[1])) == pytest.approx(
        expected["own_body_el_rad"], abs=1e-12
    )
    assert math.atan2(r_sensor[1], r_sensor[0]) == pytest.approx(
        expected["sensor_az_rad"], abs=1e-12
    )
    assert math.atan2(-r_sensor[2], math.hypot(r_sensor[0], r_sensor[1])) == pytest.approx(
        expected["sensor_el_rad"], abs=1e-12
    )

    with pytest.raises(ValueError, match="zero norm"):
        _quat_matrix([0.0, 0.0, 0.0, 0.0])


def test_c3_qa002_nondegenerate_covariance_golden() -> None:
    authority = _authority()
    case = authority["golden_vectors"]["qa_002"]
    inp = case["input"]
    expected = case["expected"]

    sigma_t_s = (inp["time_alignment_two_sided_hard_bound_us"] / 1_000_000.0) / math.sqrt(3.0)
    p_inputs = [[0.0] * 6 for _ in range(6)]
    for i in range(3):
        for j in range(3):
            p_inputs[i][j] = inp["target_position_covariance_ecef_m2"][i][j]
            p_inputs[i + 3][j + 3] = inp["own_position_covariance_ecef_m2"][i][j]
    g_time = inp["target_velocity_ecef_mps"] + inp["own_velocity_ecef_mps"]
    for i in range(6):
        for j in range(6):
            p_inputs[i][j] += g_time[i] * g_time[j] * sigma_t_s * sigma_t_s

    j = inp["relative_state_jacobian"]
    p_rel = _matmul(_matmul(j, p_inputs), _transpose(j))
    r_ecef_to_body = _transpose(_quat_matrix(inp["own_attitude_quat"]))
    p_body = _matmul(_matmul(r_ecef_to_body, p_rel), _transpose(r_ecef_to_body))
    r_body = _mv(r_ecef_to_body, inp["r_rel_ecef_m"])
    x, y, z = r_body
    horizontal = math.hypot(x, y)
    distance = math.sqrt(x * x + y * y + z * z)

    g_range = [x / distance, y / distance, z / distance]
    g_az = [-y / (horizontal * horizontal), x / (horizontal * horizontal), 0.0]
    g_el = [
        z * x / (distance * distance * horizontal),
        z * y / (distance * distance * horizontal),
        -horizontal / (distance * distance),
    ]
    sigma_att = inp["own_attitude_sigma_rad"]
    elevation = math.atan2(-z, horizontal)

    assert sigma_t_s == pytest.approx(expected["time_alignment_sigma_s"], abs=1e-15)
    for actual_row, expected_row in zip(p_inputs, expected["p_inputs_m2"], strict=True):
        assert actual_row == pytest.approx(expected_row, abs=1e-12)
    for actual_row, expected_row in zip(p_rel, expected["p_rel_ecef_m2"], strict=True):
        assert actual_row == pytest.approx(expected_row, abs=1e-12)
    for actual_row, expected_row in zip(p_body, expected["p_rel_own_body_m2"], strict=True):
        assert actual_row == pytest.approx(expected_row, abs=1e-12)

    sigma_range = math.sqrt(_quad(g_range, p_body))
    sigma_az = math.sqrt(
        _quad(g_az, p_body) + sigma_att * sigma_att / (math.cos(elevation) ** 2)
    )
    sigma_el = math.sqrt(_quad(g_el, p_body) + sigma_att * sigma_att)
    sigma_position = math.sqrt(sum(p_rel[i][i] for i in range(3)))

    assert sigma_range == pytest.approx(expected["sigma_range_m"], abs=1e-12)
    assert sigma_az == pytest.approx(expected["sigma_az_rad"], abs=1e-12)
    assert sigma_el == pytest.approx(expected["sigma_el_rad"], abs=1e-12)
    assert sigma_position == pytest.approx(expected["sigma_position_3d_m"], abs=1e-12)


def test_c3_reference_match_quality_profile_hash_and_semantics() -> None:
    authority = _authority()
    profile = dict(authority["reference_match_quality_profile"])
    profile_hash = profile.pop("profile_hash")
    profile.pop("profile_hash_algorithm")
    profile.pop("relationship_to_existing_profile_fields")
    assert _canonical_hash(profile) == profile_hash
    assert profile["max_interpolation_age_us"] == profile["max_gap_us"] == 50000
    assert profile["accepted_reference_quality_statuses"] == ["ACCEPTED"]
    assert profile["required_uncertainty_components"] == [
        "reference_truth_uncertainty",
        "alignment_uncertainty",
        "sensor_measurement_uncertainty",
    ]
    assert all(value is None for value in profile["max_sigma_by_error_domain"].values())
