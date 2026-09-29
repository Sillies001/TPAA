"""M5 transactional rollback and consistent file-set recovery primitives."""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast


class M5RecoveryError(RuntimeError):
    """Fail-closed local recovery primitive error."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return _sha256_bytes(path.read_bytes())


def _canonical_hash(value: object) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    )


def directory_state_hash(root: Path) -> str:
    """Hash one directory by relative path, content hash and byte count."""

    if not root.exists():
        return _sha256_bytes(b"TPAA_M5_ABSENT_DIRECTORY_V1")
    if not root.is_dir():
        raise M5RecoveryError(f"directory state target is not a directory: {root}")
    entries: list[dict[str, object]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
        )
    return _canonical_hash(entries)


def exercise_failed_install_rollback(
    *,
    candidate: Path,
    target: Path,
) -> tuple[str, str]:
    """Inject failure before commit and prove the pre-install state is unchanged."""

    if not candidate.is_dir():
        raise M5RecoveryError(f"candidate directory missing: {candidate}")
    before = directory_state_hash(target)
    staging = target.with_name(f".{target.name}.m5-install-staging")
    if staging.exists():
        shutil.rmtree(staging)
    try:
        shutil.copytree(candidate, staging)
        raise M5RecoveryError("INJECTED_M5_INSTALL_FAILURE_BEFORE_COMMIT")
    except M5RecoveryError as exc:
        if str(exc) != "INJECTED_M5_INSTALL_FAILURE_BEFORE_COMMIT":
            raise
        shutil.rmtree(staging, ignore_errors=True)
    after = directory_state_hash(target)
    if before != after:
        raise M5RecoveryError("failed-install rollback changed pre-install state")
    if staging.exists():
        raise M5RecoveryError("failed-install staging directory remained")
    return before, after


def create_consistent_file_backup(
    *,
    members: Mapping[str, Path],
    destination: Path,
) -> tuple[Path, str, dict[str, str]]:
    """Create a SHA-256 bound consistent backup of an explicit closed file set."""

    if not members:
        raise M5RecoveryError("backup member set is empty")
    if destination.exists():
        raise M5RecoveryError("backup destination must not already exist")
    destination.mkdir(parents=True)
    payload = destination / "payload"
    payload.mkdir()

    entries: list[dict[str, object]] = []
    member_hashes: dict[str, str] = {}
    for index, (category, source) in enumerate(members.items()):
        if not category or not source.is_file():
            raise M5RecoveryError(f"backup source unavailable: {category}={source}")
        data = source.read_bytes()
        digest = _sha256_bytes(data)
        backup_name = f"{index:04d}.bin"
        (payload / backup_name).write_bytes(data)
        entries.append(
            {
                "category": category,
                "payload_file": f"payload/{backup_name}",
                "sha256": digest,
                "bytes": len(data),
            }
        )
        member_hashes[category] = digest

    manifest = {
        "schema": "TPAA_M5_CONSISTENT_FILE_BACKUP_V1",
        "integrity_hash": "SHA-256",
        "members": entries,
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return manifest_path, sha256_file(manifest_path), member_hashes


def _load_verified_backup(
    backup: Path,
    *,
    expected_manifest_sha256: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    manifest_path = backup / "manifest.json"
    if not manifest_path.is_file():
        raise M5RecoveryError("backup manifest missing")
    if sha256_file(manifest_path) != expected_manifest_sha256:
        raise M5RecoveryError("backup manifest SHA-256 mismatch")
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise M5RecoveryError(f"backup manifest unavailable/corrupt: {exc}") from exc
    if (
        not isinstance(raw, dict)
        or raw.get("schema") != "TPAA_M5_CONSISTENT_FILE_BACKUP_V1"
        or raw.get("integrity_hash") != "SHA-256"
    ):
        raise M5RecoveryError("backup manifest schema/integrity invalid")
    members = raw.get("members")
    if not isinstance(members, list) or not members:
        raise M5RecoveryError("backup members missing")

    hashes: dict[str, str] = {}
    for item in members:
        if not isinstance(item, dict):
            raise M5RecoveryError("backup member row invalid")
        category = item.get("category")
        payload_file = item.get("payload_file")
        digest = item.get("sha256")
        byte_count = item.get("bytes")
        if (
            not isinstance(category, str)
            or not category
            or not isinstance(payload_file, str)
            or not isinstance(digest, str)
            or not isinstance(byte_count, int)
        ):
            raise M5RecoveryError("backup member metadata invalid")
        path = backup / payload_file
        if not path.is_file():
            raise M5RecoveryError(f"backup payload missing: {category}")
        data = path.read_bytes()
        if len(data) != byte_count or _sha256_bytes(data) != digest:
            raise M5RecoveryError(f"backup payload integrity mismatch: {category}")
        if category in hashes:
            raise M5RecoveryError(f"duplicate backup category: {category}")
        hashes[category] = digest
    return cast(dict[str, Any], raw), hashes


def restore_consistent_file_backup(
    *,
    backup: Path,
    expected_manifest_sha256: str,
    target: Path,
) -> dict[str, str]:
    """Verify the complete set first, then restore atomically into a clean target."""

    manifest, source_hashes = _load_verified_backup(
        backup,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    if target.exists():
        raise M5RecoveryError("restore target must be clean/nonexistent")

    staging = target.with_name(f".{target.name}.m5-restore-staging")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    try:
        rows = manifest["members"]
        assert isinstance(rows, list)
        restored: dict[str, str] = {}
        for index, item in enumerate(rows):
            assert isinstance(item, dict)
            category = str(item["category"])
            source = backup / str(item["payload_file"])
            destination = staging / f"{index:04d}.bin"
            shutil.copy2(source, destination)
            restored[category] = sha256_file(destination)
        if restored != source_hashes:
            raise M5RecoveryError("restored member hashes differ from backup")
        staging.replace(target)
        return restored
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
