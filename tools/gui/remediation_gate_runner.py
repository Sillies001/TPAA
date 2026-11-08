#!/usr/bin/env python3
"""Execute and record the shared G6-G12 reclosure gates.

This tool never changes phase state.  It records real commands and exit codes;
the phase owner must separately review stage-specific functional, visual and
external gates before setting READY_FOR_RECLOSURE.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend" / "gui-v33"


def _command(stage: str) -> list[tuple[str, list[str], Path]]:
    number = int(stage[1:])
    python = sys.executable
    commands: list[tuple[str, list[str], Path]] = [
        ("ruff", [python, "-m", "ruff", "check", "src", "tests", "tools", "migrations"], ROOT),
        ("mypy", [python, "tools/dev/tpaa_dev.py", "typecheck"], ROOT),
        (
            "pytest",
            [
                python,
                "-m",
                "pytest",
                "tests/contract/gui_v33",
                "tests/unit/application",
                "tests/unit/api",
                "tests/unit/runtime",
                "tests/unit/storage",
                "tests/unit/gui",
                "-q",
                "-p",
                "no:cacheprovider",
            ],
            ROOT,
        ),
        (
            "successor",
            [python, f"tools/baseline/adopt_g{number}_successor.py", "--check"],
            ROOT,
        ),
    ]
    codegen = {
        6: "tools/codegen/g6_historical_generate.py",
        7: "tools/codegen/g7_batch_events_generate.py",
        8: "tools/codegen/g8_co_attack_generate.py",
        9: "tools/codegen/g9_replay_generate.py",
    }.get(number)
    if codegen:
        commands.append(("codegen", [python, codegen, "--check"], ROOT))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm.cmd"
    commands.extend(
        [
            ("frontend_typecheck", [npm, "run", "typecheck"], FRONTEND),
            ("frontend_build", [npm, "run", "build"], FRONTEND),
        ]
    )
    return commands


def run(stage: str) -> dict[str, object]:
    gates: list[dict[str, object]] = []
    for name, command, cwd in _command(stage):
        started = time.monotonic()
        completed = subprocess.run(  # noqa: S603 - fixed repository-owned command list
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        output = (completed.stdout + "\n" + completed.stderr).strip()
        gates.append(
            {
                "name": name,
                "command": command,
                "cwd": cwd.relative_to(ROOT).as_posix() or ".",
                "exit_code": completed.returncode,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
                "output_tail": output[-4000:],
            }
        )
        if completed.returncode != 0:
            break
    status = "PASS" if gates and all(gate["exit_code"] == 0 for gate in gates) else "FAIL"
    return {
        "schema": "TPAA_GUI_RECLOSURE_GATE_EVIDENCE_V1",
        "stage": stage,
        "status": status,
        "gates": gates,
        "release_claim": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=[f"G{i}" for i in range(6, 13)], required=True)
    args = parser.parse_args()
    result = run(args.stage)
    target = ROOT / "evidence" / f"gui-{args.stage.lower()}-v33-reclosure-gates.json"
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{args.stage}_RECLOSURE_GATES_{result['status']} evidence={target.relative_to(ROOT)}")
    return 0 if result["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
