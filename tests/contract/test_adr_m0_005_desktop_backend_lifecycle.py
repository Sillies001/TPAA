from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "tools" / "desktop" / "DESKTOP_BACKEND_LIFECYCLE_POLICY.json"
ADR_PATH = REPO_ROOT / "docs" / "adr" / "ADR-M0-005-desktop-backend-lifecycle-ipc.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _policy() -> dict[str, object]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def test_adr_m0_005_is_closed_and_machine_policy_is_frozen() -> None:
    assert "**Status:** CLOSED" in ADR_PATH.read_text(encoding="utf-8")
    policy = _policy()
    assert policy["schema"] == "TPAA_DESKTOP_BACKEND_LIFECYCLE_POLICY_V1"
    assert policy["status"] == "FROZEN"
    assert policy["decision_id"] == "ADR-M0-005"


def test_gui_owns_one_isolated_child_and_never_attaches_to_unowned_backend() -> None:
    ownership = _policy()["ownership"]
    assert isinstance(ownership, dict)
    assert ownership["gui_owns_backend_process"] is True
    assert ownership["process_model"] == "one_dedicated_child_process_per_gui_process"
    assert ownership["in_process_backend_forbidden"] is True
    assert ownership["attach_to_unowned_backend_forbidden"] is True
    assert ownership["service_profile_uses_this_policy"] is False


def test_desktop_listener_is_loopback_and_os_ephemeral_without_probe_rebind_race() -> None:
    listener = _policy()["listener"]
    assert isinstance(listener, dict)
    assert listener["host"] == "127.0.0.1"
    assert listener["port_selection"] == "child_bind_os_ephemeral_port_zero"
    assert listener["fixed_port_forbidden"] is True
    assert listener["localhost_hostname_forbidden"] is True
    assert listener["non_loopback_bind_forbidden"] is True
    assert listener["preflight_find_free_then_close_forbidden"] is True


def test_token_is_per_process_memory_only_and_never_launch_metadata() -> None:
    policy = _policy()
    token = policy["token"]
    control = policy["control_channel"]
    assert isinstance(token, dict)
    assert isinstance(control, dict)
    assert token["algorithm"] == "python_secrets_token_urlsafe"
    assert token["random_bytes"] == 32
    assert token["lifetime"] == "one_backend_process"
    assert token["persistence"] == "memory_only"
    assert token["http_transport"] == "Authorization: Bearer <token>"
    assert token["comparison"] == "constant_time"
    assert control["token_delivery"] == "first_start_control_record_over_stdin"
    assert control["token_in_argv_forbidden"] is True
    assert control["token_in_environment_forbidden"] is True
    assert control["token_in_file_forbidden"] is True
    assert control["token_in_stdout_forbidden"] is True
    assert control["token_in_logs_forbidden"] is True


def test_ready_requires_listener_then_authenticated_core_backed_http_handshake() -> None:
    startup = _policy()["startup_handshake"]
    assert isinstance(startup, dict)
    assert startup["protocol"] == "TPAA_LOCAL_BACKEND_CONTROL_V1"
    assert startup["listener_record"] == "LISTENING"
    assert startup["listener_record_must_follow_successful_bind"] is True
    assert startup["listener_record_secret_fields_forbidden"] is True
    assert startup["http_confirmation"] == ["GET /readiness", "GET /version"]
    assert startup["http_requires_bearer"] is True
    assert startup["ready_requires_http_200_readiness"] is True
    assert startup["mismatch_or_backend_exit_is_not_ready"] is True
    assert startup["startup_timeout_seconds"] == 10


def test_desktop_http_surface_is_minimized_and_bearer_protected() -> None:
    surface = _policy()["desktop_http_surface"]
    assert isinstance(surface, dict)
    assert surface["bearer_required_for_all_routes"] is True
    assert surface["interactive_docs_enabled"] is False
    assert surface["openapi_route_enabled"] is False
    assert surface["cors_enabled"] is False
    assert surface["origin_header_policy"] == "reject_unless_explicitly_allowlisted"


def test_shutdown_is_cooperative_first_with_bounded_force_fallback() -> None:
    shutdown = _policy()["shutdown"]
    assert isinstance(shutdown, dict)
    assert shutdown["normal_mechanism"] == "SHUTDOWN control record over stdin"
    assert shutdown["graceful_wait_seconds"] == 5
    assert shutdown["fallback_terminate"] is True
    assert shutdown["terminate_wait_seconds"] == 2
    assert shutdown["final_fallback_kill"] is True
    assert shutdown["backend_exit_makes_gui_not_ready_immediately"] is True
    assert shutdown["shutdown_http_endpoint_forbidden"] is True


def test_pyside6_activation_remains_owned_by_m0_gui_001() -> None:
    pyproject = PYPROJECT_PATH.read_text(encoding="utf-8").lower()
    policy = _policy()
    owners = policy["implementation_owners"]
    assert isinstance(owners, dict)
    assert owners["pyside_shell"] == "M0-GUI-001"
    assert '"pyside6==6.11.2"' in pyproject
    assert "[[tool.uv.index]]" not in pyproject


def test_developer_cli_exposes_desktop_lifecycle_policy_gate() -> None:
    cli = (REPO_ROOT / "tools" / "dev" / "tpaa_dev.py").read_text(encoding="utf-8")
    assert 'CommandSpec("verify-desktop-lifecycle-policy", "ADR-M0-005", "IMPLEMENTED"' in cli
    assert 'sub.add_parser("verify-desktop-lifecycle-policy"' in cli
