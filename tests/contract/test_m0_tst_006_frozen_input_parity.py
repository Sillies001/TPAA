from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_governed_text_checkout_forces_lf_on_all_platforms() -> None:
    attributes = (REPO_ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "uv.lock text eol=lf" in attributes
    assert "*.json text eol=lf" in attributes
    assert "*.py text eol=lf" in attributes
