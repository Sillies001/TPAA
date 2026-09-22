#!/usr/bin/env python3
"""Verify the frozen ADR-M0-005 Desktop backend lifecycle/IPC decision."""

from __future__ import annotations

import argparse
import hmac
import json
import secrets
import socket
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "tools" / "desktop" / "DESKTOP_BACKEND_LIFECYCLE_POLICY.json"
ADR_PATH = REPO_ROOT / "docs" / "adr" / "ADR-M0-005-desktop-backend-lifecycle-ipc.md"
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"


def _ephemeral_loopback_spike() -> tuple[bool, str]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind(("127.0.0.1", 0))
        host, port = sock.getsockname()
        return host == "127.0.0.1" and isinstance(port, int) and port > 0, f"bound {host}:{port}"
    finally:
        sock.close()


def verify() -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    def record(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "detail": detail})

    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    adr = ADR_PATH.read_text(encoding="utf-8")
    pyproject = PYPROJECT_PATH.read_text(encoding="utf-8")

    record(
        "policy_frozen",
        policy.get("schema") == "TPAA_DESKTOP_BACKEND_LIFECYCLE_POLICY_V1"
        and policy.get("status") == "FROZEN"
        and policy.get("decision_id") == "ADR-M0-005",
        f"schema={policy.get('schema')} status={policy.get('status')} decision_id={policy.get('decision_id')}",
    )
    record("adr_closed", "**Status:** CLOSED" in adr, ADR_PATH.relative_to(REPO_ROOT).as_posix())

    ownership = policy.get("ownership", {})
    listener = policy.get("listener", {})
    control = policy.get("control_channel", {})
    token = policy.get("token", {})
    startup = policy.get("startup_handshake", {})
    http_surface = policy.get("desktop_http_surface", {})
    shutdown = policy.get("shutdown", {})

    record(
        "process_ownership",
        ownership.get("gui_owns_backend_process") is True
        and ownership.get("process_model") == "one_dedicated_child_process_per_gui_process"
        and ownership.get("in_process_backend_forbidden") is True
        and ownership.get("attach_to_unowned_backend_forbidden") is True
        and ownership.get("service_profile_uses_this_policy") is False,
        "GUI-owned isolated child; no in-process or unowned attach; Desktop-only",
    )
    record(
        "listener_scope",
        listener.get("host") == "127.0.0.1"
        and listener.get("port_selection") == "child_bind_os_ephemeral_port_zero"
        and listener.get("fixed_port_forbidden") is True
        and listener.get("localhost_hostname_forbidden") is True
        and listener.get("non_loopback_bind_forbidden") is True
        and listener.get("preflight_find_free_then_close_forbidden") is True,
        "127.0.0.1 only; child binds port 0; no fixed/probe-rebind port",
    )
    record(
        "private_control_channel",
        control.get("transport") == "parent_child_stdio_ndjson"
        and control.get("parent_to_child") == "stdin"
        and control.get("child_to_parent") == "stdout"
        and control.get("stdout_reserved_for_control_records") is True,
        "stdin/stdout NDJSON control channel",
    )
    record(
        "secret_transport",
        control.get("token_delivery") == "first_start_control_record_over_stdin"
        and all(
            control.get(key) is True
            for key in (
                "token_in_argv_forbidden",
                "token_in_environment_forbidden",
                "token_in_file_forbidden",
                "token_in_stdout_forbidden",
                "token_in_logs_forbidden",
            )
        ),
        "token only through private startup stdin record",
    )
    record(
        "token_policy",
        token.get("algorithm") == "python_secrets_token_urlsafe"
        and token.get("random_bytes") == 32
        and token.get("lifetime") == "one_backend_process"
        and token.get("persistence") == "memory_only"
        and token.get("http_transport") == "Authorization: Bearer <token>"
        and token.get("comparison") == "constant_time"
        and token.get("query_string_forbidden") is True
        and token.get("cookie_forbidden") is True
        and token.get("reuse_across_backend_processes_forbidden") is True,
        "32 random bytes; per-process memory-only bearer; constant-time compare",
    )
    record(
        "startup_fail_closed",
        startup.get("protocol") == "TPAA_LOCAL_BACKEND_CONTROL_V1"
        and startup.get("listener_record") == "LISTENING"
        and startup.get("listener_record_must_follow_successful_bind") is True
        and startup.get("listener_record_secret_fields_forbidden") is True
        and startup.get("http_confirmation") == ["GET /readiness", "GET /version"]
        and startup.get("http_requires_bearer") is True
        and startup.get("ready_requires_http_200_readiness") is True
        and startup.get("mismatch_or_backend_exit_is_not_ready") is True
        and startup.get("startup_timeout_seconds") == 10,
        "LISTENING then authenticated readiness/version; 10s timeout; mismatch/exit NOT_READY",
    )
    record(
        "desktop_http_restrictions",
        http_surface.get("bearer_required_for_all_routes") is True
        and http_surface.get("interactive_docs_enabled") is False
        and http_surface.get("openapi_route_enabled") is False
        and http_surface.get("cors_enabled") is False
        and http_surface.get("origin_header_policy") == "reject_unless_explicitly_allowlisted",
        "all routes bearer-protected; docs/OpenAPI/CORS disabled",
    )
    record(
        "graceful_shutdown_first",
        shutdown.get("normal_mechanism") == "SHUTDOWN control record over stdin"
        and shutdown.get("graceful_wait_seconds") == 5
        and shutdown.get("fallback_terminate") is True
        and shutdown.get("terminate_wait_seconds") == 2
        and shutdown.get("final_fallback_kill") is True
        and shutdown.get("backend_exit_makes_gui_not_ready_immediately") is True
        and shutdown.get("shutdown_http_endpoint_forbidden") is True,
        "control-channel shutdown; 5s graceful, 2s terminate, kill fallback",
    )

    spike_ok, spike_detail = _ephemeral_loopback_spike()
    record("ephemeral_loopback_spike", spike_ok, spike_detail)

    token_a = secrets.token_urlsafe(32)
    token_b = secrets.token_urlsafe(32)
    record(
        "token_primitive_spike",
        token_a != token_b and hmac.compare_digest(token_a, token_a) and not hmac.compare_digest(token_a, token_b),
        "stdlib secrets token generation and constant-time compare primitives PASS",
    )

    pyproject_lower = pyproject.lower()
    pyside_owner = policy.get("implementation_owners", {}).get("pyside_shell")
    record(
        "pyside_dependency_owned_by_m0_gui_001",
        '"pyside6==6.11.2"' in pyproject_lower
        and "[[tool.uv.index]]" not in pyproject_lower
        and pyside_owner == "M0-GUI-001",
        "M0-GUI-001 owns exact PySide6 6.11.2 activation; no project-level package-index override",
    )

    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {
        "evidence_schema": "TPAA_ADR_M0_005_EVIDENCE_V1",
        "status": status,
        "decision": "ADR-M0-005",
        "checks": checks,
        "execution_limitations": [
            "This verifier proves policy coherence and stdlib primitives on the current host; it is not the M0-GUI-002 cross-platform lifecycle acceptance.",
            "Windows/Linux child-process startup/crash/shutdown execution remains owned by M0-GUI-001/002 and later platform CI.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    payload = verify()
    print(json.dumps(payload, indent=2, sort_keys=True))
    if args.evidence:
        target = args.evidence if args.evidence.is_absolute() else REPO_ROOT / args.evidence
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if payload["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
