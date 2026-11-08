"""G8 UI must reject stale event facts during rapid V08 selection changes."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MAIN = ROOT / "frontend" / "gui-v33" / "src" / "main.ts"


def test_weapon_fact_loader_discards_stale_responses_and_checks_exact_event() -> None:
    source = MAIN.read_text(encoding="utf-8")
    assert "requestSerial: 0" in source
    assert "const requestSerial = ++state.weaponWorkbench.requestSerial" in source
    assert source.count("requestSerial !== state.weaponWorkbench.requestSerial") >= 3
    assert 'state.domainSelection.weaponEventId = weaponEventId' in source
    assert 'V24_EVENT_CONTEXT_STALE' in source
    assert 'detail?.weapon_event_id ?? ""' in source
