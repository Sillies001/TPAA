from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_acp_216_pre_adoption_readiness_is_historical_only() -> None:
    workflow = (ROOT / ".github/workflows/cross-platform-ci.yml").read_text(encoding="utf-8")
    assert "Review ACP-216 adoption readiness without authority mutation" not in workflow
    assert "Review ACP-216 DB 1.7.0 authority adoption gate" in workflow
    assert (ROOT / "tools/testing/acp_216_adoption_readiness.py").is_file()
    assert (ROOT / "docs/reviews/ACP_216_ADOPTION_READINESS_REVIEW.md").is_file()
    assert (ROOT / "docs/baseline/PIQB-1.0/ACP_216_DB_1_7_0_ADOPTION.json").is_file()
