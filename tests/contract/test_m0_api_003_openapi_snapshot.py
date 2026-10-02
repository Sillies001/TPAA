from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = REPO_ROOT / "api" / "openapi-m0.json"
TOOL = REPO_ROOT / "tools" / "api" / "openapi_snapshot.py"


def test_openapi_snapshot_is_exact_projection_of_canonical_authority() -> None:
    result = subprocess.run(
        [sys.executable, str(TOOL), "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    schemas = payload["components"]["schemas"]
    context = schemas["EvaluationContextDTO"]
    assert "valid_from_session_time_us" not in context["required"]
    assert context["properties"]["valid_from_session_time_us"]["anyOf"][0][
        "x-tpaa-transport-type"
    ] == "decimal-string?"
    for p3_dto in (
        "P3EligibleAdjustedEstimateDTO",
        "P3LifecycleSegmentDTO",
        "P3ModelValidationSnapshotDTO",
        "CapabilityModelDTO",
        "CapabilitySurfaceDTO",
        "AircraftTwinRevisionDTO",
        "IntrinsicCapabilityEstimateDTO",
        "P3AdmissionStateDTO",
    ):
        assert p3_dto in schemas
    for m8_dto in (
        "P4SubjectContextDTO",
        "HumanMachineEvidenceDTO",
        "InstructorAnnotationDTO",
        "ApprovalStateDTO",
        "P4AssessmentRevisionDTO",
        "P5CompositionSnapshotDTO",
        "TeamMissionEvidenceDTO",
        "P5AssessmentRevisionDTO",
        "P4P5AdmissionStateDTO",
    ):
        assert m8_dto in schemas
    observation = schemas["CapabilityObservationDTO"]
    assert "observation_start_session_time_us" in observation["required"]
    assert observation["properties"]["value"]["x-tpaa-transport-type"] == "json-union"
    assert payload["x-tpaa-transport-rules"]["session_time_us"] == (
        "decimal-string for JS-visible API"
    )
    assert payload["x-tpaa-transport-rules"]["structured_metric"] == (
        "object, never JSON string"
    )


def test_snapshot_carries_frozen_authority_hash() -> None:
    payload = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    authority = payload["x-tpaa-authority"]
    assert authority["artifact_id"] == "CROSS_LAYER_DTO_CONTRACTS"
    assert authority["core_baseline"] == "CB-1.4.0"
    assert authority["sha256"] == (
        "28f7209e40709fb4eb53ceffdfee3542e867f060c4e63605cc1ad149a8e3819a"
    )
