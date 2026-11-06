from __future__ import annotations

import json
from pathlib import Path

import tpaa_service.__main__ as service_cli


def test_service_check_config_returns_preflight_json(monkeypatch, capsys) -> None:
    app_root = Path("C:/packaged-tpaa")
    observed: dict[str, Path | None] = {}

    def preflight(*, app_root: Path | None = None) -> dict[str, str]:
        observed["app_root"] = app_root
        return {
            "schema": "TPAA_SERVICE_PREFLIGHT_V1",
            "status": "READY",
        }

    monkeypatch.setattr(
        service_cli,
        "service_preflight",
        preflight,
    )
    assert service_cli.main(["--check-config"], app_root=app_root) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "READY"
    assert observed == {"app_root": app_root}


def test_service_startup_error_does_not_echo_exception_detail(monkeypatch, capsys) -> None:
    def fail(*, app_root=None) -> dict[str, object]:
        raise RuntimeError("password=must-not-be-printed")

    monkeypatch.setattr(service_cli, "service_preflight", fail)
    assert service_cli.main(["--check-config"]) == 2
    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert payload["error_type"] == "RuntimeError"
    assert "must-not-be-printed" not in captured.err
