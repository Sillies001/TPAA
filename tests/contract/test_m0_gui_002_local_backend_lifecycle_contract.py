from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GUI = ROOT / "src" / "tpaa_gui" / "local_backend.py"
CHILD = ROOT / "src" / "tpaa_api" / "local_backend_child.py"
DESKTOP_API = ROOT / "src" / "tpaa_api" / "desktop.py"
STATUS = ROOT / "docs" / "developer" / "M0_STATUS.md"
PLAN = ROOT / "docs" / "implementation" / "M0-GUI-002_LOCAL_BACKEND_LIFECYCLE_HANDSHAKE.md"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def test_gui_lifecycle_uses_stdlib_process_http_and_no_lower_layer_or_api_imports() -> None:
    imports = _imports(GUI)
    forbidden = {"tpaa_api", "tpaa_storage", "tpaa_canonical", "fastapi", "httpx", "psycopg", "sqlite3"}
    assert not any(name == prefix or name.startswith(prefix + ".") for name in imports for prefix in forbidden)
    assert "subprocess" in imports
    assert "secrets" in imports
    assert "urllib.request" in imports


def test_token_is_stdin_only_and_child_command_cannot_contain_secret() -> None:
    source = GUI.read_text(encoding="utf-8")
    assert "secrets.token_urlsafe(32)" in source
    assert '"bearer_token": self._token' in source
    assert 'child_env["__PYVENV_LAUNCHER__"] = resolved_executable' in source
    assert 'child_env["bearer_token"]' not in source
    assert 'child_env["token"]' not in source
    assert "Authorization" in source
    assert "query" not in source.lower()


def test_windows_venv_redirector_is_bypassed_without_weakening_pid_ownership() -> None:
    source = GUI.read_text(encoding="utf-8")
    assert "sys._base_executable" in source or 'getattr(sys, "_base_executable"' in source
    assert "__PYVENV_LAUNCHER__" in source
    assert "LISTENING_PID_MISMATCH" in source
    assert "pid != self._process.pid" in source

def test_child_binds_loopback_ephemeral_and_emits_non_secret_listening() -> None:
    source = CHILD.read_text(encoding="utf-8")
    assert 'sock.bind(("127.0.0.1", 0))' in source
    assert '"type": "LISTENING"' in source
    assert '"port": port' in source
    assert '"bearer_token"' not in source[source.index("_emit({"):]


def test_desktop_http_uses_constant_time_bearer_and_disables_browser_surface() -> None:
    source = DESKTOP_API.read_text(encoding="utf-8")
    assert "hmac.compare_digest" in source
    assert "HTTPBearer" in source
    assert "docs_url=None" in source
    assert "redoc_url=None" in source
    assert "openapi_url=None" in source
    assert "ORIGIN_FORBIDDEN" in source
    assert "CORSMiddleware" not in source


def test_shutdown_is_control_channel_first_then_bounded_terminate_kill() -> None:
    source = GUI.read_text(encoding="utf-8")
    assert '"type": "SHUTDOWN"' in source
    assert "GRACEFUL_SHUTDOWN_SECONDS = 5.0" in source
    assert "TERMINATE_WAIT_SECONDS = 2.0" in source
    assert "process.terminate()" in source
    assert "process.kill()" in source


def test_status_and_plan_keep_task_scope_explicit() -> None:
    assert "M0-GUI-002" in STATUS.read_text(encoding="utf-8")
    plan = PLAN.read_text(encoding="utf-8")
    assert "M0-GUI-002" in plan
    assert "M0-GUI-003" in plan
