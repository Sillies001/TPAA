from __future__ import annotations

import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
BUILDER_PATH = REPO_ROOT / "tools" / "baseline" / "adopt_w0_successor.py"


def _load_builder():
    spec = importlib.util.spec_from_file_location("tpaa_w0_successor_builder", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_w0_route_authority_is_reconstructed_from_hashed_frozen_input() -> None:
    builder = _load_builder()
    frozen_path = builder.FROZEN_API_ROUTE_AUTHORITY
    expected = json.loads(frozen_path.read_text(encoding="utf-8"))

    assert builder._sha256(frozen_path) == builder.FROZEN_API_ROUTE_AUTHORITY_SHA256
    assert builder._api_route_authority() == expected
    assert expected["core_baseline"] == "CB-1.5.0"
    assert expected["decision_id"] == "W0-AUTHORITY-CONVERGENCE-2026-10-19"


def test_w0_route_reconstruction_does_not_scan_current_api_source() -> None:
    source = BUILDER_PATH.read_text(encoding="utf-8")

    assert '(REPO_ROOT / "src" / "tpaa_api").glob' not in source
    assert "ast.parse" not in source
