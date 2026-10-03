from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
ADOPTION = ROOT / "docs/baseline/PIQB-1.0/ACP_216_DB_1_7_0_ADOPTION.json"
REVIEW = ROOT / "docs/reviews/ACP_216_DB_1_7_0_AUTHORITY_ADOPTION_REVIEW.md"
TOOL = ROOT / "tools/testing/acp_216_authority_adoption.py"


def test_acp_216_adoption_is_retained_as_historical_evidence() -> None:
    adoption = json.loads(ADOPTION.read_text(encoding="utf-8"))
    assert adoption["proposal_id"] == "ACP-216"
    assert adoption["target_db_schema_version"] == "1.7.0"
    assert adoption["target_core_sha256"] == (
        "dd8461ff572338006455f7b6eac5325900c60640f5d163c3b61c3f5bd5767f74"
    )
    assert REVIEW.is_file()
    assert TOOL.is_file()


def test_acp_216_gate_retires_when_successor_authority_candidate_is_active() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    jobs = re.findall(r"(?m)^  ([a-z0-9-]+):\n", workflow)
    assert len(jobs) == 14
    assert len(set(jobs)) == 14
    assert "Review ACP-216 DB 1.7.0 authority adoption gate" not in workflow
    assert "Execute ACP-216 PostgreSQL 1.6.0 to 1.7.0 migration qualification" not in workflow
    assert "Review ACP-219 DB 1.8.0 authority adoption gate" in workflow
    assert "Execute ACP-219 PostgreSQL 1.7.0 to 1.8.0 migration qualification" in workflow
