#!/usr/bin/env python3
"""Real Windows/Linux M0-PLAT-001..003 smoke."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tpaa_platform import (  # noqa: E402
    InterProcessFileLock,
    LockUnavailable,
    PlatformFilesystem,
    WorkerPayload,
    atomic_replace_bytes,
    ensure_no_case_collisions,
    run_spawn_echo,
)


def main() -> int:
    checks: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix="tpaa-平台-") as raw:
        root = Path(raw)
        filesystem = PlatformFilesystem(root)
        target = filesystem.resolve("Unicode/测试/Result.txt")
        atomic_replace_bytes(target, b"first")
        atomic_replace_bytes(target, b"second")
        checks.append({"check": "unicode_path_atomic_replace", "status": target.read_bytes() == b"second"})

        collision_failed = False
        try:
            ensure_no_case_collisions(["Résumé.txt", "re\u0301sume\u0301.TXT"])
        except ValueError:
            collision_failed = True
        checks.append({"check": "case_unicode_collision", "status": collision_failed})

        lock_path = root / "locks" / "worker.lock"
        first = InterProcessFileLock(lock_path)
        second = InterProcessFileLock(lock_path)
        first.acquire()
        second_failed = False
        try:
            try:
                second.acquire(blocking=False)
            except LockUnavailable:
                second_failed = True
        finally:
            second.release()
            first.release()
        checks.append({"check": "nonblocking_lock_conflict", "status": second_failed})

        payload = WorkerPayload(
            job_id="M0-PLAT-SPAWN-SMOKE",
            request_hash="0" * 64,
            command="echo",
            arguments=("unicode-测试",),
        )
        checks.append({"check": "spawn_payload_roundtrip", "status": run_spawn_echo(payload) == payload})

    status = "PASS" if all(bool(item["status"]) for item in checks) else "FAIL"
    print(
        json.dumps(
            {
                "schema": "TPAA_M0_PLATFORM_SMOKE_V1",
                "status": status,
                "checks": checks,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
