from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / "tools" / "dev" / "tpaa_dev.py"


def test_m1_world_001_acceptance_command_emits_machine_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "basic-episode.json"
    result = subprocess.run(
        [sys.executable, str(DEV), "m1-basic-episode-check", "--evidence", str(evidence)],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(evidence.read_text(encoding="utf-8"))
    assert payload["schema"] == "TPAA_M1_WORLD_001_BASIC_EPISODE_EVIDENCE_V1"
    assert payload["task_id"] == "M1-WORLD-001"
    assert payload["status"] == "PASS"
    assert payload["projection_count"] == 8
    assert payload["unique_episode_id_count"] == 1
    assert payload["unique_logical_hash_count"] == 1
    assert payload["same_governed_identity_across_fixtures"] is True
    assert payload["replay_stable"] is True
    assert payload["expected_intervals_exact"] is True
    assert payload["database_persistence_executed"] is False
    assert payload["stage_projection_executed"] is False
    assert payload["world_projection_executed"] is False
    assert payload["metric_logic_executed"] is False
