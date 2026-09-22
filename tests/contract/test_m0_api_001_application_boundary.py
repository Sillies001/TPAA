from __future__ import annotations

import ast
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
POLICY = REPO_ROOT / "tools" / "architecture" / "ARCHITECTURE_POLICY.json"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_application_layer_uses_storage_port_not_concrete_adapters() -> None:
    imports = set()
    for path in (SRC / "tpaa_application").glob("*.py"):
        imports.update(_imports(path))
    assert "tpaa_storage.ports" in imports
    forbidden = {
        "tpaa_storage.sqlite_repository",
        "tpaa_storage.postgres_repository",
        "sqlite3",
        "psycopg",
        "sqlalchemy",
        "asyncpg",
        "fastapi",
        "starlette",
        "PySide6",
    }
    assert imports.isdisjoint(forbidden)


def test_transport_packages_are_policy_limited_to_application_and_generated() -> None:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    governed = set(policy["lower_layer_packages"]) | set(policy["transport_packages"])
    for transport in ("tpaa_api", "tpaa_gui"):
        forbidden = set(policy["forbidden_first_party_edges"][transport])
        allowed = governed - forbidden - {transport}
        assert allowed == {"tpaa_application", "tpaa_generated"}


def test_application_service_does_not_claim_runtime_ready_handshake() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((SRC / "tpaa_application").glob("*.py"))
    ).lower()
    assert "ready =" not in source
    assert "readiness" not in source
    assert "mismatch" not in source
