#!/usr/bin/env python3
"""F0 scaffold for Demo-v33 task-metric code generation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "generated" / "task-metrics" / "scaffold.json"
METRICS = ("KILL_RATIO", "EXCHANGE_RATIO", "MISSION_COMPLETION_RATE")


def _payload() -> dict[str, object]:
    return {
        "schema": "TPAA_TASK_METRIC_CODEGEN_SCAFFOLD_V1",
        "stage": "F0_SCAFFOLD_ONLY",
        "metric_semantic_ids": list(METRICS),
        "definitions_materialized": False,
        "generated_dto": False,
        "generated_typescript": False,
        "generated_markdown": False,
        "admission_status": "NOT_ADMITTED",
        "next_stage": "F1",
    }


def _render() -> bytes:
    return (json.dumps(_payload(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def check() -> None:
    if not OUTPUT.is_file():
        raise RuntimeError("missing F0 task-metric codegen scaffold")
    if OUTPUT.read_bytes() != _render():
        raise RuntimeError("F0 task-metric codegen scaffold drifted")


def write() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_bytes(_render())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check()
    else:
        write()
    print("TASK_METRIC_CODEGEN_SCAFFOLD_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
