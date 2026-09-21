from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEV_CLI = REPO_ROOT / "tools" / "dev" / "tpaa_dev.py"
GENERATORS = REPO_ROOT / "src" / "tpaa_codegen" / "generators"


def test_generators_do_not_directly_read_canonical_json_or_baseline_paths() -> None:
    for path in sorted(GENERATORS.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "baseline/CB-" not in text, path
        assert ".json\"" not in text and ".json'" not in text, path
        assert "json.load(" not in text and "json.loads(" not in text, path


def test_codegen_check_detects_generated_byte_drift_and_restore_passes() -> None:
    target = REPO_ROOT / "src" / "tpaa_generated" / "baseline.py"
    original = target.read_bytes()
    try:
        target.write_bytes(original + b"# drift\n")
        failed = subprocess.run(
            [sys.executable, str(DEV_CLI), "generate", "--check"],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        assert failed.returncode == 2
        assert "CODEGEN_CHECK_FAIL" in failed.stderr
    finally:
        target.write_bytes(original)
    passed = subprocess.run(
        [sys.executable, str(DEV_CLI), "generate", "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert passed.returncode == 0, passed.stderr
