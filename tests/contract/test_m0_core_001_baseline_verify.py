from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFIER_PATH = REPO_ROOT / "tools" / "baseline" / "verify_baseline.py"
SPEC = importlib.util.spec_from_file_location("verify_baseline", VERIFIER_PATH)
assert SPEC is not None and SPEC.loader is not None
VERIFY_BASELINE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERIFY_BASELINE
SPEC.loader.exec_module(VERIFY_BASELINE)


class M0Core001BaselineVerifyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.source = REPO_ROOT / "baseline" / "CB-1.4.0"
        self.temp_dir = tempfile.TemporaryDirectory()
        self.baseline = Path(self.temp_dir.name) / "CB-1.4.0"
        shutil.copytree(self.source, self.baseline)
        # copytree preserves read-only modes from the frozen source; tests need controlled mutation.
        for path in self.baseline.rglob("*"):
            if path.is_file():
                path.chmod(0o644)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_approved_snapshot_passes_exactly(self) -> None:
        lock, results, errors = VERIFY_BASELINE.verify(self.baseline)
        self.assertEqual(lock["baseline"]["core"], "CB-1.4.0")
        self.assertEqual(len(results), 21)
        self.assertTrue(all(item.status == "PASS" for item in results))
        self.assertEqual(errors, [])

    def test_controlled_artifact_byte_drift_fails(self) -> None:
        target = self.baseline / "canonical" / "STAGE_REGISTRY.json"
        target.write_bytes(target.read_bytes() + b"\n")
        _, results, errors = VERIFY_BASELINE.verify(self.baseline)
        stage = next(item for item in results if item.file == "STAGE_REGISTRY.json")
        self.assertEqual(stage.status, "FAIL")
        self.assertEqual(stage.reason, "CONTROLLED_ARTIFACT_DRIFT")
        self.assertTrue(any("STAGE_REGISTRY.json" in item for item in errors))

    def test_missing_controlled_artifact_fails(self) -> None:
        (self.baseline / "canonical" / "CORE_RULES.json").unlink()
        _, results, errors = VERIFY_BASELINE.verify(self.baseline)
        core_rules = next(item for item in results if item.file == "CORE_RULES.json")
        self.assertEqual(core_rules.status, "FAIL")
        self.assertEqual(core_rules.reason, "MISSING_CONTROLLED_ARTIFACT")
        self.assertTrue(any("missing controlled artifacts" in item for item in errors))

    def test_unlisted_canonical_artifact_fails(self) -> None:
        (self.baseline / "canonical" / "SHADOW_AUTHORITY.json").write_text("{}\n", encoding="utf-8")
        _, _, errors = VERIFY_BASELINE.verify(self.baseline)
        self.assertTrue(any("unexpected/uncontrolled canonical artifacts" in item for item in errors))

    def test_baseline_lock_drift_fails_before_trusting_contents(self) -> None:
        lock_path = self.baseline / "BASELINE_LOCK.json"
        data = json.loads(lock_path.read_text(encoding="utf-8"))
        data["baseline"]["core"] = "CB-TAMPERED"
        lock_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(VERIFY_BASELINE.BaselineVerificationError) as context:
            VERIFY_BASELINE.verify(self.baseline)
        self.assertIn("BASELINE_LOCK hash mismatch", str(context.exception))


if __name__ == "__main__":
    unittest.main()
