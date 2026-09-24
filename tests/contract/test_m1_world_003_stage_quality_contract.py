from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"
CORE_MODEL = ROOT / "baseline" / "CB-1.4.0" / "canonical" / "CORE_LOGICAL_MODEL.json"


def test_episode_stage_authority_requires_quality_product_fields() -> None:
    model = json.loads(CORE_MODEL.read_text(encoding="utf-8"))
    fields = {field["name"]: field for field in model["tables"]["episode.episode_stage"]["fields"]}

    assert fields["stage_status"]["sql"] == "stage_status text NOT NULL"
    assert "coverage BETWEEN 0 AND 1" in fields["coverage"]["sql"]
    assert "confidence BETWEEN 0 AND 1" in fields["confidence"]["sql"]
    assert fields["detector_version"]["sql"] == "detector_version text NOT NULL"


def test_m1_world_003_acceptance_command_emits_machine_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "stage-quality.json"
    result = subprocess.run(
        [sys.executable, str(DEV), "m1-stage-quality-check", "--evidence", str(evidence)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["schema"] == "TPAA_M1_WORLD_003_STAGE_QUALITY_EVIDENCE_V1"
    assert payload["task_id"] == "M1-WORLD-003"
    assert payload["status"] == "PASS"
    assert payload["projection_count"] == 8
    assert payload["stage_count"] == 32
    assert payload["unique_stage_id_set_count"] == 1
    assert payload["stage_status"] == "VALID"
    assert payload["coverage"] == 1.0
    assert payload["confidence"] == 1.0
    assert payload["detector_version"] == "M1_BASIC_FLIGHT_STAGE_PROJECTOR_V1"
    assert payload["replay_stable"] is True
    assert payload["world_002_projection_preserved"] is True
    assert payload["quality_fields_exact"] is True
    assert payload["numeric_bounds_valid"] is True
    assert payload["stage_quality_projection_executed"] is True
    assert payload["database_persistence_executed"] is False
    assert payload["revision_supersede_executed"] is False
    assert payload["logical_hash_executed"] is False
    assert payload["evidence_refs_projected"] is False
    assert payload["world_projection_executed"] is False
    assert payload["metric_logic_executed"] is False
