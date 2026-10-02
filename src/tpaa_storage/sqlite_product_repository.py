"""SQLite PIQB B2 product release/object registration over frozen DB 1.6.0."""

from __future__ import annotations

import sqlite3
from uuid import UUID, uuid5

from .product_publication import (
    ProductPublicationError,
    ProductPublicationReceipt,
    ProductPublicationRegistration,
)

_OBJECT_NAMESPACE = UUID("3f78c2bf-e754-55c0-8ff3-c758c679c71c")
_BINDING_NAMESPACE = UUID("8ef13a2d-58f6-5637-8d83-7ff7354758b4")
_JOB_NAMESPACE = UUID("5ef42f8c-806a-5f55-8bf4-015069783216")
_COMPONENT_VERSION = "PIQB-B2-PRODUCT-PUBLICATION-1.0.0"


def _uuid(value: str, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ProductPublicationError("UUID_INVALID", field) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise ProductPublicationError("UUID_INVALID", field)
    return value


class SQLiteProductPublicationLedger:
    """Register sealed product objects, releases and CAS pointers atomically."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def _execute(
        self,
        sql: str,
        params: tuple[object, ...] = (),
    ) -> sqlite3.Cursor:
        try:
            return self._connection.execute(sql, params)
        except sqlite3.DatabaseError as exc:
            raise ProductPublicationError(
                "SQLITE_PRODUCT_PUBLICATION_FAILED",
                str(exc),
            ) from exc

    def _idempotent(
        self,
        value: ProductPublicationRegistration,
    ) -> ProductPublicationReceipt | None:
        rows = self._execute(
            '''SELECT b.owner_type, b.owner_id, b.release_id,
                      r.scope_type, r.scope_key, r.release_no,
                      o.managed_uri, o.artifact_sha256
               FROM "registry.compute_job" AS j
               JOIN "registry.analysis_release" AS r
                 ON r.compute_job_id = j.job_id
               JOIN "registry.object_binding" AS b
                 ON b.release_id = r.release_id
               JOIN "registry.object_reference" AS o
                 ON o.object_ref_id = b.object_ref_id
               WHERE j.job_key = ?''',
            (value.idempotency_key,),
        ).fetchall()
        if not rows:
            return None
        if len(rows) != 1:
            raise ProductPublicationError(
                "IDEMPOTENCY_KEY_CARDINALITY",
                value.idempotency_key,
            )
        row = rows[0]
        expected = (
            value.product_family,
            value.product_id,
            value.release.release_id,
            value.release.scope_type,
            value.release.scope_key,
            value.object_uri,
            value.object_sha256,
        )
        actual = (
            str(row[0]),
            str(row[1]),
            str(row[2]),
            str(row[3]),
            str(row[4]),
            str(row[6]),
            str(row[7]),
        )
        if actual != expected:
            raise ProductPublicationError(
                "IDEMPOTENCY_KEY_CONFLICT",
                value.idempotency_key,
            )
        return ProductPublicationReceipt(
            product_family=value.product_family,
            product_id=value.product_id,
            release_id=value.release.release_id,
            scope_type=value.release.scope_type,
            scope_key=value.release.scope_key,
            object_uri=value.object_uri,
            object_sha256=value.object_sha256,
            version_token=int(row[5]),
            reused=True,
        )

    def register(
        self,
        value: ProductPublicationRegistration,
    ) -> ProductPublicationReceipt:
        _uuid(value.product_id, "product_id")
        release = value.release
        _uuid(release.release_id, "release_id")
        if release.session_id is not None:
            _uuid(release.session_id, "session_id")
        if release.longitudinal_scope_id is not None:
            _uuid(release.longitudinal_scope_id, "longitudinal_scope_id")
        if release.scope_type not in {"SESSION", "LONGITUDINAL"}:
            raise ProductPublicationError(
                "SCOPE_TYPE_INVALID",
                release.scope_type,
            )
        if value.expected_version_token < 0:
            raise ProductPublicationError(
                "EXPECTED_VERSION_TOKEN_INVALID",
                str(value.expected_version_token),
            )

        reused = self._idempotent(value)
        if reused is not None:
            return reused

        pointer = self._execute(
            '''SELECT current_release_id, version_token
               FROM "registry.release_scope_pointer"
               WHERE scope_type = ? AND scope_key = ?''',
            (release.scope_type, release.scope_key),
        ).fetchall()
        if len(pointer) > 1:
            raise ProductPublicationError(
                "RELEASE_POINTER_CARDINALITY",
                release.scope_key,
            )
        current_release_id = None if not pointer else pointer[0][0]
        actual_token = 0 if not pointer else int(pointer[0][1])
        if actual_token != value.expected_version_token:
            raise ProductPublicationError(
                "PUBLISH_CAS_CONFLICT",
                f"expected={value.expected_version_token} actual={actual_token}",
            )

        object_ref_id = str(
            uuid5(
                _OBJECT_NAMESPACE,
                f"{value.object_uri}|{value.object_sha256}",
            )
        )
        existing_object = self._execute(
            '''SELECT object_ref_id, artifact_sha256, size_bytes, sealed, gc_state
               FROM "registry.object_reference"
               WHERE managed_uri = ?''',
            (value.object_uri,),
        ).fetchall()
        if existing_object:
            if len(existing_object) != 1:
                raise ProductPublicationError(
                    "OBJECT_URI_CARDINALITY",
                    value.object_uri,
                )
            row = existing_object[0]
            if (
                str(row[1]) != value.object_sha256
                or int(row[2]) != value.object_byte_size
                or int(row[3]) != 1
                or str(row[4]) != "ACTIVE"
            ):
                raise ProductPublicationError(
                    "SEALED_OBJECT_REGISTRY_CONFLICT",
                    value.object_uri,
                )
            object_ref_id = str(row[0])
        else:
            self._execute(
                '''INSERT INTO "registry.object_reference" (
                       object_ref_id, managed_uri, media_type, size_bytes,
                       artifact_sha256, logical_content_hash, storage_backend,
                       sealed, gc_state, gc_state_version,
                       gc_marked_at, created_at, deleted_at
                   ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, 'ACTIVE', 0, NULL,
                             CURRENT_TIMESTAMP, NULL)''',
                (
                    object_ref_id,
                    value.object_uri,
                    value.media_type,
                    value.object_byte_size,
                    value.object_sha256,
                    release.manifest_hash,
                    value.storage_backend,
                ),
            )

        job_id = str(
            uuid5(
                _JOB_NAMESPACE,
                f"{value.idempotency_key}|{release.manifest_hash}",
            )
        )
        self._execute(
            '''INSERT INTO "registry.compute_job" (
                   job_id, job_type, session_id, episode_id, job_key, status,
                   component_version, input_hash, progress, reason_codes,
                   error_detail, created_at, started_at, finished_at
               ) VALUES (?, ?, ?, NULL, ?, 'SUCCEEDED', ?, ?, 1.0, '[]',
                         NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
                         CURRENT_TIMESTAMP)''',
            (
                job_id,
                f"PIQB_PRODUCT_PUBLICATION:{value.product_family}",
                release.session_id,
                value.idempotency_key,
                _COMPONENT_VERSION,
                release.manifest_hash,
            ),
        )

        next_token = actual_token + 1
        self._execute(
            '''INSERT INTO "registry.analysis_release" (
                   release_id, scope_type, scope_key, session_id,
                   longitudinal_scope_id, release_no, compute_job_id,
                   catalog_version, catalog_hash, context_binding_hash,
                   status, parent_release_id, manifest_hash, created_at,
                   published_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PUBLISHED', ?, ?,
                         CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
            (
                release.release_id,
                release.scope_type,
                release.scope_key,
                release.session_id,
                release.longitudinal_scope_id,
                next_token,
                job_id,
                release.catalog_version,
                release.catalog_hash,
                release.context_binding_hash,
                current_release_id,
                release.manifest_hash,
            ),
        )

        binding_id = str(
            uuid5(
                _BINDING_NAMESPACE,
                (
                    f"{value.product_family}|{value.product_id}|"
                    f"{release.release_id}|{object_ref_id}"
                ),
            )
        )
        self._execute(
            '''INSERT INTO "registry.object_binding" (
                   binding_id, object_ref_id, owner_type, owner_id,
                   release_id, role, created_at
               ) VALUES (?, ?, ?, ?, ?, 'PRIMARY_PRODUCT',
                         CURRENT_TIMESTAMP)''',
            (
                binding_id,
                object_ref_id,
                value.product_family,
                value.product_id,
                release.release_id,
            ),
        )

        if pointer:
            cursor = self._execute(
                '''UPDATE "registry.release_scope_pointer"
                   SET current_release_id = ?, version_token = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE scope_type = ? AND scope_key = ?
                     AND version_token = ?''',
                (
                    release.release_id,
                    next_token,
                    release.scope_type,
                    release.scope_key,
                    actual_token,
                ),
            )
            if cursor.rowcount != 1:
                raise ProductPublicationError(
                    "PUBLISH_CAS_UPDATE_LOST",
                    release.scope_key,
                )
        else:
            self._execute(
                '''INSERT INTO "registry.release_scope_pointer" (
                       scope_type, scope_key, current_release_id,
                       version_token, updated_at
                   ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)''',
                (
                    release.scope_type,
                    release.scope_key,
                    release.release_id,
                    next_token,
                ),
            )

        return ProductPublicationReceipt(
            product_family=value.product_family,
            product_id=value.product_id,
            release_id=release.release_id,
            scope_type=release.scope_type,
            scope_key=release.scope_key,
            object_uri=value.object_uri,
            object_sha256=value.object_sha256,
            version_token=next_token,
            reused=False,
        )

    def exact_product(
        self,
        product_family: str,
        product_id: str,
    ) -> ProductPublicationReceipt:
        _uuid(product_id, "product_id")
        rows = self._execute(
            '''SELECT b.owner_type, b.owner_id, b.release_id,
                      r.scope_type, r.scope_key, r.release_no,
                      o.managed_uri, o.artifact_sha256
               FROM "registry.object_binding" AS b
               JOIN "registry.analysis_release" AS r
                 ON r.release_id = b.release_id
               JOIN "registry.object_reference" AS o
                 ON o.object_ref_id = b.object_ref_id
               WHERE b.owner_type = ? AND b.owner_id = ?
                 AND b.role = 'PRIMARY_PRODUCT' ''',
            (product_family, product_id),
        ).fetchall()
        if len(rows) != 1:
            raise ProductPublicationError(
                "PRODUCT_REGISTRATION_CARDINALITY",
                f"{product_family}:{product_id}:rows={len(rows)}",
            )
        row = rows[0]
        return ProductPublicationReceipt(
            product_family=str(row[0]),
            product_id=str(row[1]),
            release_id=str(row[2]),
            scope_type=str(row[3]),
            scope_key=str(row[4]),
            version_token=int(row[5]),
            object_uri=str(row[6]),
            object_sha256=str(row[7]),
            reused=False,
        )

    def referenced_object_uris(
        self,
        logical_prefix: str | None = None,
    ) -> tuple[str, ...]:
        if logical_prefix is None:
            rows = self._execute(
                '''SELECT managed_uri
                   FROM "registry.object_reference"
                   WHERE sealed = 1 AND gc_state = 'ACTIVE'
                   ORDER BY managed_uri'''
            ).fetchall()
        else:
            rows = self._execute(
                '''SELECT managed_uri
                   FROM "registry.object_reference"
                   WHERE sealed = 1 AND gc_state = 'ACTIVE'
                     AND managed_uri LIKE ?
                   ORDER BY managed_uri''',
                (f"{logical_prefix}%",),
            ).fetchall()
        return tuple(str(row[0]) for row in rows)
