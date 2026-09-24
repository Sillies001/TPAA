from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"


def test_m1_world_002_acceptance_command_emits_machine_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "basic-stage.json"
    result = subprocess.run(
        [sys.executable, str(DEV), "m1-basic-stage-check", "--evidence", str(evidence)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["schema"] == "TPAA_M1_WORLD_002_BASIC_STAGE_EVIDENCE_V1"
    assert payload["task_id"] == "M1-WORLD-002"
    assert payload["status"] == "PASS"
    assert payload["projection_count"] == 8
    assert payload["stage_count"] == 32
    assert payload["unique_stage_id_set_count"] == 1
    assert payload["ordered_stages"] == [
        "SETUP_ENTRY",
        "EXECUTION",
        "STABILIZATION_RECOVERY",
        "COMPLETION",
    ]
    assert payload["interval_semantics"] == "half-open"
    assert payload["terminator_marker"] == "END"
    assert payload["terminator_published_as_stage"] is False
    assert payload["replay_stable"] is True
    assert payload["expected_intervals_exact"] is True
    assert payload["order_exact"] is True
    assert payload["half_open_exact"] is True
    assert payload["stage_quality_projection_executed"] is False
    assert payload["revision_supersede_executed"] is False
    assert payload["logical_hash_executed"] is False
    assert payload["evidence_refs_projected"] is False
    assert payload["world_projection_executed"] is False
    assert payload["metric_logic_executed"] is False
