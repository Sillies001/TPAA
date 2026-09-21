#!/usr/bin/env python3
"""Machine-readable acceptance verifier for M0-CORE-004 generated-source governance."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_canonical import CanonicalArtifactLoader  # noqa: E402
from tpaa_codegen import GENERATOR_VERSION, GenerationCoordinator, default_generators  # noqa: E402
from tpaa_codegen.governance import verify_generated_tree  # noqa: E402
from tpaa_codegen.provenance import GENERATED_MARKER  # noqa: E402

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
ADR_PATH = REPO_ROOT / "docs" / "adr" / "ADR-M0-007-generated-source-policy.md"
DEV_CLI = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"


def _head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "UNAVAILABLE"


def _command_states() -> dict[str, str]:
    completed = subprocess.run(
        [sys.executable, str(DEV_CLI), "list", "--json"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return {}
    return {row["name"]: row["state"] for row in json.loads(completed.stdout)}


def verify() -> dict[str, object]:
    loader = CanonicalArtifactLoader()
    coordinator = GenerationCoordinator(loader, default_generators())
    first = coordinator.build()
    second = coordinator.build()
    checks: list[dict[str, object]] = []

    def add(check_id: str, passed: bool, detail: str) -> None:
        checks.append(
            {"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": detail}
        )

    first_map = {item.relative_path.as_posix(): item.content for item in first.files}
    second_map = {item.relative_path.as_posix(): item.content for item in second.files}
    add("DETERMINISTIC-REBUILD", first_map == second_map, f"files={len(first_map)}")

    try:
        report = verify_generated_tree(REPO_ROOT, first.files)
    except Exception as exc:
        add("GENERATED-TREE", False, str(exc))
        expected_count = len(first.files)
        python_count = 0
    else:
        add(
            "GENERATED-TREE",
            True,
            f"exact files={len(report.expected_files)} python_files={len(report.python_files)}",
        )
        expected_count = len(report.expected_files)
        python_count = len(report.python_files)

    provenance_ok = True
    provenance_detail: list[str] = []
    for result in first.results:
        if not result.sources:
            provenance_ok = False
            provenance_detail.append(f"{result.generator_id}:no-source")
        for source in result.sources:
            if not source.artifact_id or not source.version or not _SHA256.fullmatch(source.sha256):
                provenance_ok = False
                provenance_detail.append(f"{result.generator_id}:{source.artifact_id}:invalid-source")
        for generated in result.files:
            if generated.relative_path.suffix != ".py":
                continue
            text = generated.content.decode("utf-8")
            if not text.startswith(GENERATED_MARKER + "\n"):
                provenance_ok = False
                provenance_detail.append(f"{generated.relative_path}:marker")
            if f"# generator_id={result.generator_id}\n" not in text:
                provenance_ok = False
                provenance_detail.append(f"{generated.relative_path}:generator-id")
            if f"# generator_version={GENERATOR_VERSION}\n" not in text:
                provenance_ok = False
                provenance_detail.append(f"{generated.relative_path}:generator-version")
            for source in result.sources:
                line = (
                    f"# source artifact_id={source.artifact_id} version={source.version} "
                    f"sha256={source.sha256}\n"
                )
                if line not in text:
                    provenance_ok = False
                    provenance_detail.append(f"{generated.relative_path}:{source.artifact_id}")
    add(
        "PROVENANCE-HEADERS",
        provenance_ok,
        "all Python outputs carry exact source/version/hash and generator version"
        if provenance_ok
        else ",".join(provenance_detail),
    )

    adr_text = ADR_PATH.read_text(encoding="utf-8") if ADR_PATH.is_file() else ""
    adr_ok = (
        "**Status:** CLOSED" in adr_text
        and "checked-in generated source" in adr_text.lower()
        and "regenerate-diff" in adr_text
    )
    add("ADR-M0-007-CLOSED", adr_ok, ADR_PATH.relative_to(REPO_ROOT).as_posix())

    command_states = _command_states()
    commands_ok = all(
        command_states.get(name) == "IMPLEMENTED"
        for name in ("generate", "verify-generated", "regenerate-diff")
    )
    add(
        "GOVERNED-COMMANDS",
        commands_ok,
        "generate/verify-generated/regenerate-diff IMPLEMENTED"
        if commands_ok
        else json.dumps(command_states, sort_keys=True),
    )

    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    return {
        "evidence_schema": "TPAA_M0_GATE_EVIDENCE_V1",
        "task_id": "M0-CORE-004",
        "gate_id": "M0-CORE-004.GENERATED_SOURCE_GOVERNANCE",
        "workstream": "WS-CORE",
        "status": status,
        "source_revision": _head(),
        "core_baseline": loader.expected_core_baseline,
        "baseline_lock_sha256": loader.trusted_lock_sha256,
        "generator_version": GENERATOR_VERSION,
        "expected_generated_file_count": expected_count,
        "generated_python_file_count": python_count,
        "checks": checks,
        "execution_limitations": [
            "This evidence proves the vendor-neutral CI gate contract on the current Linux host; it does not claim execution by an external CI service.",
            "Windows execution is not claimed; later platform/CI qualification evidence remains required.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    evidence = verify()
    text = json.dumps(evidence, indent=2, sort_keys=True) + "\n"
    if args.evidence is not None:
        target = args.evidence if args.evidence.is_absolute() else REPO_ROOT / args.evidence
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    print(text, end="")
    return 0 if evidence["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
