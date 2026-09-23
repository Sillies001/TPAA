from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tpaa_platform import (
    InterProcessFileLock,
    LockUnavailable,
    PlatformFilesystem,
    PlatformPathError,
    WorkerPayload,
    atomic_replace_bytes,
    ensure_no_case_collisions,
    run_spawn_echo,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SMOKE = REPO_ROOT / "tools" / "platform" / "smoke.py"


def test_logical_paths_are_separator_neutral_unicode_safe_and_root_bounded(tmp_path) -> None:
    fs = PlatformFilesystem(tmp_path / "根目录")
    target = fs.resolve("alpha/测试/result.txt")
    assert target.parts[-3:] == ("alpha", "测试", "result.txt")
    assert str(target).startswith(str(fs.root))

    with pytest.raises(PlatformPathError):
        fs.resolve("../escape")
    with pytest.raises(PlatformPathError):
        fs.resolve("C:/drive-specific")
    with pytest.raises(PlatformPathError):
        fs.resolve(r"windows\separator")


def test_case_and_unicode_collisions_are_rejected() -> None:
    with pytest.raises(PlatformPathError):
        ensure_no_case_collisions(["Résumé.txt", "re\u0301sume\u0301.TXT"])


def test_atomic_replace_closes_temp_and_lock_conflict_is_fail_closed(tmp_path) -> None:
    target = tmp_path / "nested" / "payload.bin"
    atomic_replace_bytes(target, b"one")
    atomic_replace_bytes(target, b"two")
    assert target.read_bytes() == b"two"
    assert not list(target.parent.glob("*.tmp"))

    first = InterProcessFileLock(tmp_path / "locks" / "x.lock")
    second = InterProcessFileLock(tmp_path / "locks" / "x.lock")
    first.acquire()
    try:
        with pytest.raises(LockUnavailable):
            second.acquire(blocking=False)
    finally:
        second.release()
        first.release()


def test_worker_payload_round_trips_through_real_spawn() -> None:
    payload = WorkerPayload(
        job_id="job-1",
        request_hash="a" * 64,
        command="echo",
        arguments=("测试", "value"),
    )
    assert run_spawn_echo(payload) == payload


def test_platform_smoke_script_passes() -> None:
    result = subprocess.run(
        [sys.executable, str(SMOKE)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["status"] == "PASS"
    assert all(item["status"] is True for item in evidence["checks"])
