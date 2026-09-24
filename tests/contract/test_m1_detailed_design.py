from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
VERIFY_MODULE = "tools.governance.verify_m1_detailed_design"
DESIGN = REPO_ROOT / "docs" / "design" / "M1" / "M1_A_C_DETAILED_DESIGN.json"
M1_C_DESIGN = (
    REPO_ROOT
    / "docs"
    / "design"
    / "M1"
    / "M1_C_EPISODE_STAGE_WORLD_IMPLEMENTATION_DESIGN.json"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_m1_detailed_design_verifier_passes_without_admitting_m1() -> None:
    result = _run("-m", VERIFY_MODULE)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["schema"] == "TPAA_M1_DETAILED_DESIGN_VERIFICATION_V1"
    assert evidence["status"] == "PASS"
    assert evidence["admission"] == "NOT_DECIDED_BY_DESIGN_VERIFIER"
    assert all(item["status"] == "PASS" for item in evidence["checks"])


def test_m1_detailed_design_keeps_sensor_families_out_of_vertical_slice() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    guardrails = design["guardrails"]
    assert set(guardrails["m1_vertical_slice_sensor_families_excluded"]) == {
        "RADAR",
        "IRST",
        "ESM",
        "DL",
        "FUS",
    }
    assert guardrails["pre_admission_feature_code_authorized"] is False
    assert guardrails["canonical_semantics_may_be_redefined"] is False


def test_m1_detailed_design_has_exact_fixture_and_stage_contracts() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    assert set(design["wave_a_fixture_contract"]["bundle_ids"]) == {
        "BF_M1_NOMINAL_V1",
        "BF_M1_GAP_V1",
        "BF_M1_ANGLE_WRAP_V1",
        "BF_M1_STRUCTURED_PARTIAL_V1",
        "BF_M1_STAGE_BOUNDARY_V1",
        "BF_M1_REPLAY_V1",
        "BF_M1_CROSS_PLATFORM_V1",
        "BF_M1_FAILURE_V1",
    }
    assert design["wave_c_episode_stage_world_design_ahead"]["stage"]["ordered_stages"] == [
        "SETUP_ENTRY",
        "EXECUTION",
        "STABILIZATION_RECOVERY",
        "COMPLETION",
    ]


def test_m1_data_spine_uses_exact_representative_canonical_fields() -> None:
    design = json.loads(DESIGN.read_text(encoding="utf-8"))
    fields = set(
        design["wave_b_data_spine"]["canonical_aircraft_state"]["required_fields"]
    )
    assert fields == {
        "body_p_rad_s",
        "nz_g",
        "heading_true_rad",
        "tas_mps",
        "mach",
        "session_time_us",
        "quality_mask",
    }
    stage_selection = design["wave_b_data_spine"]["evaluation_context"][
        "stage_profile_selection"
    ]
    assert stage_selection["profile_id"] == "BASIC_FLIGHT_V1"
    assert stage_selection["new_context_binding_role_invented"] is False


def test_m1_detailed_design_verifier_is_available_through_unified_cli() -> None:
    result = _run(str(DEV), "verify-m1-detailed-design")
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"


def test_m1_c_design_ahead_is_explicit_and_keeps_implementation_blocked() -> None:
    design = json.loads(M1_C_DESIGN.read_text(encoding="utf-8"))

    assert design["schema"] == "TPAA_M1_C_EPISODE_STAGE_WORLD_IMPLEMENTATION_DESIGN_V1"
    assert design["wave"] == "M1-C"
    assert design["design_ahead_from_wave"] == "M1-B"
    assert design["implementation_state"] == "DESIGN_ONLY"
    assert set(design["implementation_prerequisites"]) == {
        "M1-DATA-001",
        "M1-DATA-002",
        "M1-DATA-003",
        "M1-DATA-004",
        "M1-DATA-005",
        "M1-DATA-006",
        "M1-DATA-007",
    }
    stage = design["stage_contract"]
    assert stage["fixture_marker_contract"]["terminator_marker"] == "END"
    assert stage["fixture_marker_contract"]["terminator_is_stage"] is False
    assert design["world_contract"]["truth_may_substitute_for_missing_perception"] is False
    assert design["world_contract"]["missing_adjudication_may_be_inferred"] is False
