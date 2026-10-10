"""Immutable production Job output receipts over the DB 1.9 snapshot carrier."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import cast
from uuid import UUID, uuid5

from tpaa_storage.canonical_rows import CanonicalRowRepository

_NAMESPACE = UUID("e2b20000-8cb5-54c4-9174-1324fe77f4db")
_SNAPSHOT_TYPE = "ED2_PRODUCTION_JOB_OUTPUT"
_SCHEMA_VERSION = "TPAA_ED2_PRODUCTION_JOB_OUTPUT_V1"


class ProductionJobOutputError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


@dataclass(frozen=True, slots=True)
class ProductionJobOutput:
    snapshot_id: str
    job_id: str
    command: str
    product_refs: tuple[tuple[str, str], ...]
    logical_content_hash: str

    def mapping(self) -> dict[str, str]:
        return dict(self.product_refs)


def production_job_output_snapshot_id(job_id: str, command: str) -> str:
    try:
        parsed = UUID(job_id)
    except ValueError as exc:
        raise ProductionJobOutputError(
            "ED2_JOB_OUTPUT_JOB_ID_INVALID",
            job_id,
        ) from exc
    if parsed.int == 0 or str(parsed) != job_id or not command:
        raise ProductionJobOutputError(
            "ED2_JOB_OUTPUT_IDENTITY_INVALID",
            f"{job_id}:{command}",
        )
    return str(uuid5(_NAMESPACE, f"{job_id}:{command}"))


def _manifest(
    *,
    job_id: str,
    command: str,
    product_refs: tuple[tuple[str, str], ...],
) -> dict[str, object]:
    return {
        "schema": _SCHEMA_VERSION,
        "job_id": job_id,
        "command": command,
        "product_refs": [
            {"role": role, "ref": ref}
            for role, ref in product_refs
        ],
    }


def _hash(value: object) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(raw).hexdigest()


class ProductionJobOutputRepository:
    def __init__(self, rows: CanonicalRowRepository) -> None:
        self._rows = rows

    def register(
        self,
        *,
        job_id: str,
        command: str,
        product_refs: tuple[tuple[str, str], ...],
    ) -> ProductionJobOutput:
        if (
            not product_refs
            or len({role for role, _ in product_refs}) != len(product_refs)
            or any(not role or not ref for role, ref in product_refs)
        ):
            raise ProductionJobOutputError(
                "ED2_JOB_OUTPUT_REFS_INVALID",
                command,
            )
        ordered = tuple(sorted(product_refs))
        snapshot_id = production_job_output_snapshot_id(job_id, command)
        manifest = _manifest(
            job_id=job_id,
            command=command,
            product_refs=ordered,
        )
        digest = _hash(manifest)
        current = self._rows.one(
            "registry.dataset_snapshot",
            where={"dataset_snapshot_id": snapshot_id},
            columns=(
                "snapshot_type",
                "query_or_manifest",
                "input_refs",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        expected_refs: tuple[str, ...] = ()
        if current is None:
            self._rows.insert(
                "registry.dataset_snapshot",
                {
                    "dataset_snapshot_id": snapshot_id,
                    "snapshot_type": _SNAPSHOT_TYPE,
                    "query_or_manifest": manifest,
                    "input_refs": expected_refs,
                    "data_hash": digest,
                    "schema_version": _SCHEMA_VERSION,
                    "frozen": True,
                },
                field_kinds={
                    "query_or_manifest": "json",
                    "input_refs": "uuid_array",
                },
            )
        else:
            raw = current["query_or_manifest"]
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            refs_raw = current["input_refs"]
            if isinstance(refs_raw, str):
                refs_value: object = json.loads(refs_raw)
            else:
                refs_value = refs_raw
            refs = tuple(
                str(item)
                for item in cast(
                    list[object] | tuple[object, ...],
                    refs_value,
                )
            )
            frozen = current["frozen"]
            if isinstance(frozen, int) and not isinstance(frozen, bool):
                frozen = bool(frozen)
            if (
                parsed != manifest
                or refs != expected_refs
                or str(current["snapshot_type"]) != _SNAPSHOT_TYPE
                or str(current["data_hash"]) != digest
                or str(current["schema_version"]) != _SCHEMA_VERSION
                or frozen is not True
            ):
                raise ProductionJobOutputError(
                    "ED2_JOB_OUTPUT_IMMUTABLE_CONFLICT",
                    snapshot_id,
                )
        return ProductionJobOutput(
            snapshot_id=snapshot_id,
            job_id=job_id,
            command=command,
            product_refs=ordered,
            logical_content_hash=digest,
        )

    def exact(self, *, job_id: str, command: str) -> ProductionJobOutput:
        snapshot_id = production_job_output_snapshot_id(job_id, command)
        row = self._rows.one(
            "registry.dataset_snapshot",
            where={"dataset_snapshot_id": snapshot_id},
            columns=(
                "snapshot_type",
                "query_or_manifest",
                "data_hash",
                "schema_version",
                "frozen",
            ),
        )
        if row is None:
            raise ProductionJobOutputError(
                "ED2_JOB_OUTPUT_NOT_FOUND",
                snapshot_id,
            )
        raw = row["query_or_manifest"]
        manifest = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(manifest, dict):
            raise ProductionJobOutputError(
                "ED2_JOB_OUTPUT_INTEGRITY_FAILED",
                snapshot_id,
            )
        raw_refs = manifest.get("product_refs")
        if not isinstance(raw_refs, list):
            raise ProductionJobOutputError(
                "ED2_JOB_OUTPUT_INTEGRITY_FAILED",
                snapshot_id,
            )
        refs: list[tuple[str, str]] = []
        for item in raw_refs:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("role"), str)
                or not isinstance(item.get("ref"), str)
            ):
                raise ProductionJobOutputError(
                    "ED2_JOB_OUTPUT_INTEGRITY_FAILED",
                    snapshot_id,
                )
            refs.append((str(item["role"]), str(item["ref"])))
        ordered = tuple(sorted(refs))
        rebuilt_manifest = _manifest(
            job_id=job_id,
            command=command,
            product_refs=ordered,
        )
        digest = _hash(rebuilt_manifest)
        if (
            manifest != rebuilt_manifest
            or str(row["snapshot_type"]) != _SNAPSHOT_TYPE
            or str(row["data_hash"]) != digest
            or str(row["schema_version"]) != _SCHEMA_VERSION
            or row["frozen"] not in (True, 1)
        ):
            raise ProductionJobOutputError(
                "ED2_JOB_OUTPUT_INTEGRITY_FAILED",
                snapshot_id,
            )
        return ProductionJobOutput(
            snapshot_id=snapshot_id,
            job_id=job_id,
            command=command,
            product_refs=ordered,
            logical_content_hash=digest,
        )
