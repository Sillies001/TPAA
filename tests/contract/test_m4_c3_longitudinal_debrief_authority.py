from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
VALIDATOR = ROOT / "tools" / "baseline" / "validate_m4_longitudinal_authority.py"

def test_m4_c3_authority_is_controlled_and_versioned() -> None:
    loader = CanonicalArtifactLoader(BASELINE)
    artifact = loader.load("M4_LONGITUDINAL_DEBRIEF_AUTHORITY", expectation=ArtifactExpectation(version="1.0.0", schema_version="1.6.0", required_top_level_keys=("sample_profile","comparison_key_contract","trend_profile","release_replay_contract","dto_contracts","golden_vectors")))
    payload = artifact.payload
    assert payload["change_class"] == "C3_SEMANTIC_CONTRACT"
    assert payload["status"] == "APPROVED_FOR_PROTECTED_MAIN_ADOPTION"
    assert payload["scope"]["admitted_capability_phase"] == ["P1"]
    assert payload["scope"]["admitted_subject_types"] == ["AIRCRAFT", "MISSION_SYSTEM_INSTANCE"]
    assert payload["scope"]["p4_p5_human_team_assessment_active"] is False
    assert payload["scope"]["db_schema_version"] == "1.6.0"
    assert payload["scope"]["shadow_schema_permitted"] is False

def test_m4_c3_independent_validator_passes() -> None:
    result = subprocess.run([sys.executable, str(VALIDATOR)], cwd=ROOT, check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert evidence["task_id"] == "M4-GOV-001"
    assert evidence["tracking_issue"] == 122
    assert evidence["failed_acceptance"] == []
    assert all(evidence["acceptance"].values())
