"""G11 CB-1.16.0 hardening successor and security/a11y contract."""

from __future__ import annotations

import json
from pathlib import Path

from tools.baseline.adopt_g11_successor import check_successor

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.16.0"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_g11_successor_locks_parent_and_keeps_route_count() -> None:
    check_successor()
    baseline = _load(BASELINE / "BASELINE_LOCK.json")["baseline"]
    assert isinstance(baseline, dict)
    assert baseline["core"] == "CB-1.16.0"
    assert baseline["db_schema"] == "1.10.0"
    security = _load(BASELINE / "canonical" / "API_ROUTE_SECURITY_AUTHORITY.json")
    routes = security["active_routes"]
    assert isinstance(routes, list) and len(routes) == 103


def test_g11_hardening_authority_rules() -> None:
    authority = _load(BASELINE / "canonical" / "GUI_HARDENING_AUTHORITY.json")
    rules = authority["rules"]
    assert rules["csp_self_only"] is True
    assert rules["exact_origin_loopback"] is True
    assert rules["desktop_nonce_enforced"] is True
    assert rules["off_the_record_profile"] is True
    assert rules["no_orphan_backend_process"] is True
    assert rules["renderer_crash_fail_closed"] is True
    assert rules["wcag_keyboard_focus"] is True


def test_g11_static_security_headers_enforced() -> None:
    source = (ROOT / "src" / "tpaa_api" / "desktop.py").read_text(encoding="utf-8")
    assert "frame-ancestors 'self'" in source
    assert 'response.headers["Cache-Control"] = "private, no-store"' in source
    assert "X-Content-Type-Options" in source
