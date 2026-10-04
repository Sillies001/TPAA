from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "cross-platform-ci.yml"
ADOPTION = ROOT / "docs/baseline/PIQB-1.0/ACP_219_DB_1_8_0_ADOPTION.json"
REVIEW = ROOT / "docs/reviews/ACP_219_DB_1_8_0_AUTHORITY_ADOPTION_REVIEW.md"
TOOL = ROOT / "tools/testing/acp_219_authority_adoption.py"


def test_acp_219_adoption_is_retained_as_historical_evidence() -> None:
    adoption = json.loads(ADOPTION.read_text(encoding="utf-8"))
    assert adoption["proposal_id"] == "ACP-219"
    assert adoption["target_db_schema_version"] == "1.8.0"
    assert adoption["target_core_sha256"] == (
        "cbb15c1e0029be45213e4d7ab57a78fac47d7cc09c4627a9c388fafdadd2d44e"
    )
    assert REVIEW.is_file()
    assert TOOL.is_file()


def test_acp_219_gate_retires_when_successor_authority_candidate_is_active() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    jobs = re.findall(r"(?m)^  ([a-z0-9-]+):\n", workflow)
    assert len(jobs) == 14
    assert len(set(jobs)) == 14
    assert "Review ACP-219 DB 1.8.0 authority adoption gate" not in workflow
    assert "Execute ACP-219 PostgreSQL 1.7.0 to 1.8.0 migration qualification" not in workflow
    assert "Review ACP-221 DB 1.9.0 authority adoption gate" in workflow
    assert "Execute ACP-221 PostgreSQL 1.8.0 to 1.9.0 migration qualification" in workflow
