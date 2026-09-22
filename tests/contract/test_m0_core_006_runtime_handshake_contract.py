from __future__ import annotations

import ast
from pathlib import Path

from tpaa_canonical import RuntimeBaselineMismatch

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE = REPO_ROOT / "src" / "tpaa_canonical" / "runtime_handshake.py"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_handshake_model_is_transport_and_storage_neutral() -> None:
    imports = _imports(MODULE)
    forbidden = {
        "fastapi",
        "starlette",
        "PySide6",
        "sqlite3",
        "psycopg",
        "sqlalchemy",
        "tpaa_api",
        "tpaa_gui",
        "tpaa_storage",
    }
    assert imports.isdisjoint(forbidden)


def test_acceptance_dimensions_have_distinct_fail_closed_codes() -> None:
    values = {item.value for item in RuntimeBaselineMismatch}
    assert "PRODUCT_BUILD_VERSION_MISMATCH" in values
    assert "CORE_BASELINE_MISMATCH" in values
    assert "DB_SCHEMA_VERSION_MISMATCH" in values
    assert "P1_METRIC_CATALOG_VERSION_MISMATCH" in values
    assert "P1_METRIC_CATALOG_SHA256_MISMATCH" in values


def test_handshake_does_not_claim_future_build_manifest_ownership() -> None:
    source = MODULE.read_text(encoding="utf-8").lower()
    assert "git rev-parse" not in source
    assert "subprocess" not in source
    assert "build-manifest.json" not in source
