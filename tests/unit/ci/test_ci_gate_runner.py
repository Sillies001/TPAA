from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
RUNNER_PATH = REPO_ROOT / "tools" / "ci" / "run_gate.py"


def _load_runner() -> Any:
    spec = importlib.util.spec_from_file_location("tpaa_ci_run_gate", RUNNER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_platform_name_is_governed_os_family() -> None:
    runner = _load_runner()
    assert runner._platform_name() in {"windows", "linux"}


def test_dispatcher_command_uses_current_interpreter() -> None:
    runner = _load_runner()
    command = runner._dispatcher("verify-baseline")
    assert Path(command[0]).resolve() == Path(runner.sys.executable).resolve()
    assert command[-1] == "verify-baseline"


def test_ci_scope_does_not_claim_later_release_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = _load_runner()
    monkeypatch.setattr(runner, "_platform_name", lambda: "linux")
    monkeypatch.setattr(
        runner,
        "_run_gate",
        lambda name, args: {
            "name": name,
            "command": list(args),
            "status": "PASS",
            "return_code": 0,
            "duration_seconds": 0.0,
        },
    )
    monkeypatch.setattr(
        runner,
        "_sqlite_bootstrap_gate",
        lambda: {
            "name": "sqlite-bootstrap-verify",
            "command": [],
            "status": "PASS",
            "return_code": 0,
            "duration_seconds": 0.0,
        },
    )
    monkeypatch.setattr(
        runner, "_capture", lambda args: "0" * 40 if "rev-parse" in args else "uv 0.12.17"
    )
    evidence = tmp_path / "ci.json"

    assert runner.run(expected_platform="linux", evidence=evidence) == 0
    text = evidence.read_text(encoding="utf-8")
    assert '"build manifest"' in text
    assert '"SBOM"' in text
    assert '"cold-start"' in text
    assert '"M0 Exit Gate"' in text
