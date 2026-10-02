"""PostgreSQL PIQB B2 product release/object registration over DB 1.6.0."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from .product_identity import (
    PRODUCT_PUBLICATION_COMPONENT_VERSION,
    product_binding_id,
    product_job_id,
    product_object_ref_id,
)
from .product_publication import (
    ProductPublicationError,
    ProductPublicationReceipt,
    ProductPublicationRegistration,
)


def _uuid(value: str, field: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise ProductPublicationError("UUID_INVALID", field) from exc
    if parsed.int == 0 or str(parsed) != value:
        raise ProductPublicationError("UUID_INVALID", field)
    return value


class PostgreSQLProductPublicationLedger:
    """Psycopg-backed durable product registration with transaction locks."""

    def __init__(self, connection: Any) -> None:
        self._connection = connection

    def _execute(
        self,
        sql: str,
        params: tuple[object, ...] = (),
    ) -> Any:
        try:
            cursor = self._connection.cursor()
            cursor.execute(sql, params)
            return cursor
        except Exception as exc:
            raise ProductPublicationError(
                "POSTGRES_PRODUCT_PUBLICATION_FAILED",
                str(exc),
            ) from exc

    def _fetchall(
        self,
        sql: str,
        params: tuple[object, ...] = (),
    ) -> list[tuple[object, ...]]:
        cursor = self._execute(sql, params)
        try:
            return list(cursor.fetchall())
        finally:
            cursor.close()

    def _lock(self, key: str) -> None:
        cursor = self._execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (key,),
        )
        cursor.close()

    def _idempotent(
        self,
        value: ProductPublicationRegistration,
    ) -> ProductPublicationReceipt | None:
        rows = self._fetchall(
            '''SELECT b.owner_type, b.owner_id, b.release_id,
                      r.scope_type, r.scope_key, r.release_no,
                      o.managed_uri, o.artifact_sha256
               FROM "registry"."compute_job" AS j
               JOIN "registry"."analysis_release" AS r
                 ON r.compute_job_id = j.job_id
               JOIN "registry"."object_binding" AS b
                 ON b.release_id = r.release_id
               JOIN "registry"."object_reference" AS o
                 ON o.object_ref_id = b.object_ref_id
               WHERE j.job_key = %s''',
            (value.idempotency_key,),
        )
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

        self._lock(f"PIQB_PRODUCT_IDEMPOTENCY|{value.idempotency_key}")
        self._lock(
            f"PIQB_PRODUCT_SCOPE|{release.scope_type}|{release.scope_key}"
        )

        reused = self._idempotent(value)
        if reused is not None:
            return reused

        pointer = self._fetchall(
            '''SELECT current_release_id, version_token
               FROM "registry"."release_scope_pointer"
               WHERE scope_type = %s AND scope_key = %s
               FOR UPDATE''',
            (release.scope_type, release.scope_key),
        )
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

        object_ref_id = product_object_ref_id(
            value.object_uri,
            value.object_sha256,
        )
        existing_object = self._fetchall(
            '''SELECT object_ref_id, artifact_sha256, size_bytes, sealed, gc_state
               FROM "registry"."object_reference"
               WHERE managed_uri = %s''',
            (value.object_uri,),
        )
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
                or bool(row[3]) is not True
                or str(row[4]) != "ACTIVE"
            ):
                raise ProductPublicationError(
                    "SEALED_OBJECT_REGISTRY_CONFLICT",
                    value.object_uri,
                )
            object_ref_id = str(row[0])
        else:
            cursor = self._execute(
                '''INSERT INTO "registry"."object_reference" (
                       object_ref_id, managed_uri, media_type, size_bytes,
                       artifact_sha256, logical_content_hash, storage_backend,
                       sealed, gc_state, gc_state_version,
                       gc_marked_at, created_at, deleted_at
                   ) VALUES (%s, %s, %s, %s, %s, %s, %s, true,
                             'ACTIVE', 0, NULL, CURRENT_TIMESTAMP, NULL)''',
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
            cursor.close()

        job_id = product_job_id(
            value.idempotency_key,
            release.manifest_hash,
        )
        cursor = self._execute(
            '''INSERT INTO "registry"."compute_job" (
                   job_id, job_type, session_id, episode_id, job_key, status,
                   component_version, input_hash, progress, reason_codes,
                   error_detail, created_at, started_at, finished_at
               ) VALUES (%s, %s, %s, NULL, %s, 'SUCCEEDED', %s, %s,
                         1.0, %s, NULL, CURRENT_TIMESTAMP,
                         CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)''',
            (
                job_id,
                f"PIQB_PRODUCT_PUBLICATION:{value.product_family}",
                release.session_id,
                value.idempotency_key,
                PRODUCT_PUBLICATION_COMPONENT_VERSION,
                release.manifest_hash,
                [],
            ),
        )
        cursor.close()

        next_token = actual_token + 1
        cursor = self._execute(
            '''INSERT INTO "registry"."analysis_release" (
                   release_id, scope_type, scope_key, session_id,
                   longitudinal_scope_id, release_no, compute_job_id,
                   catalog_version, catalog_hash, context_binding_hash,
                   status, parent_release_id, manifest_hash, created_at,
                   published_at
               ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                         'PUBLISHED', %s, %s, CURRENT_TIMESTAMP,
                         CURRENT_TIMESTAMP)''',
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
        cursor.close()

        binding_id = product_binding_id(
            value.product_family,
            value.product_id,
            release.release_id,
            object_ref_id,
        )
        cursor = self._execute(
            '''INSERT INTO "registry"."object_binding" (
                   binding_id, object_ref_id, owner_type, owner_id,
                   release_id, role, created_at
               ) VALUES (%s, %s, %s, %s, %s, 'PRIMARY_PRODUCT',
                         CURRENT_TIMESTAMP)''',
            (
                binding_id,
                object_ref_id,
                value.product_family,
                value.product_id,
                release.release_id,
            ),
        )
        cursor.close()

        if pointer:
            cursor = self._execute(
                '''UPDATE "registry"."release_scope_pointer"
                   SET current_release_id = %s, version_token = %s,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE scope_type = %s AND scope_key = %s
                     AND version_token = %s''',
                (
                    release.release_id,
                    next_token,
                    release.scope_type,
                    release.scope_key,
                    actual_token,
                ),
            )
            try:
                if cursor.rowcount != 1:
                    raise ProductPublicationError(
                        "PUBLISH_CAS_UPDATE_LOST",
                        release.scope_key,
                    )
            finally:
                cursor.close()
        else:
            cursor = self._execute(
                '''INSERT INTO "registry"."release_scope_pointer" (
                       scope_type, scope_key, current_release_id,
                       version_token, updated_at
                   ) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)''',
                (
                    release.scope_type,
                    release.scope_key,
                    release.release_id,
                    next_token,
                ),
            )
            cursor.close()

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
        rows = self._fetchall(
            '''SELECT b.owner_type, b.owner_id, b.release_id,
                      r.scope_type, r.scope_key, r.release_no,
                      o.managed_uri, o.artifact_sha256
               FROM "registry"."object_binding" AS b
               JOIN "registry"."analysis_release" AS r
                 ON r.release_id = b.release_id
               JOIN "registry"."object_reference" AS o
                 ON o.object_ref_id = b.object_ref_id
               WHERE b.owner_type = %s AND b.owner_id = %s
                 AND b.role = 'PRIMARY_PRODUCT' ''',
            (product_family, product_id),
        )
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
            rows = self._fetchall(
                '''SELECT managed_uri
                   FROM "registry"."object_reference"
                   WHERE sealed = true AND gc_state = 'ACTIVE'
                   ORDER BY managed_uri'''
            )
        else:
            rows = self._fetchall(
                '''SELECT managed_uri
                   FROM "registry"."object_reference"
                   WHERE sealed = true AND gc_state = 'ACTIVE'
                     AND managed_uri LIKE %s
                   ORDER BY managed_uri''',
                (f"{logical_prefix}%",),
            )
        return tuple(str(row[0]) for row in rows)
