"""PIQB B2 durable publication transaction and orphan-recovery substrate."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from .object_seal import LocalSealedObjectFlow, ObjectSealError
from .object_store import LocalObjectStore, ObjectStoreError, StoredObject


class ProductPublicationError(RuntimeError):
    """Fail-closed product publication failure with orphan identity when applicable."""

    def __init__(
        self,
        code: str,
        detail: str,
        *,
        sealed_object: StoredObject | None = None,
    ) -> None:
        self.code = code
        self.detail = detail
        self.sealed_object = sealed_object
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True, slots=True)
class ProductReleaseIdentity:
    release_id: str
    scope_type: str
    scope_key: str
    session_id: str | None
    longitudinal_scope_id: str | None
    catalog_version: str
    catalog_hash: str
    context_binding_hash: str
    manifest_hash: str


@dataclass(frozen=True, slots=True)
class ProductPublicationRequest:
    operation_id: str
    product_family: str
    product_id: str
    release: ProductReleaseIdentity
    sealed_uri: str
    payload: bytes
    media_type: str
    storage_backend: str
    idempotency_key: str
    expected_version_token: int


@dataclass(frozen=True, slots=True)
class ProductPublicationRegistration:
    product_family: str
    product_id: str
    release: ProductReleaseIdentity
    object_uri: str
    object_sha256: str
    object_byte_size: int
    media_type: str
    storage_backend: str
    idempotency_key: str
    expected_version_token: int


@dataclass(frozen=True, slots=True)
class ProductPublicationReceipt:
    product_family: str
    product_id: str
    release_id: str
    scope_type: str
    scope_key: str
    object_uri: str
    object_sha256: str
    version_token: int
    reused: bool


@dataclass(frozen=True, slots=True)
class ProductPublicationResult:
    sealed_object: StoredObject
    receipt: ProductPublicationReceipt


class ProductPublicationLedger(Protocol):
    """Engine-neutral durable registration/CAS port implemented by DB adapters."""

    def register(
        self,
        value: ProductPublicationRegistration,
    ) -> ProductPublicationReceipt:
        """Register the already-sealed object and advance its governed CAS pointer."""

    def exact_product(
        self,
        product_family: str,
        product_id: str,
    ) -> ProductPublicationReceipt:
        """Return an exact durable product/object registration."""

    def referenced_object_uris(
        self,
        logical_prefix: str | None = None,
    ) -> tuple[str, ...]:
        """Return DB-authoritative managed object URIs for recovery."""


class ProductPublicationUnitOfWork(Protocol):
    """Transaction boundary required by the publication coordinator."""

    @property
    def product_publication(self) -> ProductPublicationLedger:
        """Return the durable product publication ledger."""

    def __enter__(self) -> ProductPublicationUnitOfWork:
        """Enter one explicit write transaction."""

    def commit(self) -> None:
        """Commit only after durable registration and CAS succeed."""

    def rollback(self) -> None:
        """Roll back an active transaction."""

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        """Roll back any non-finalized transaction."""


ProductPublicationUnitOfWorkFactory = Callable[[], ProductPublicationUnitOfWork]


class ProductPublicationCoordinator:
    """Stage, verify, seal, then register through one explicit DB transaction."""

    def __init__(
        self,
        *,
        object_flow: LocalSealedObjectFlow,
        unit_of_work_factory: ProductPublicationUnitOfWorkFactory,
    ) -> None:
        self._object_flow = object_flow
        self._unit_of_work_factory = unit_of_work_factory

    def publish(self, request: ProductPublicationRequest) -> ProductPublicationResult:
        if not request.product_family.strip():
            raise ProductPublicationError(
                "PRODUCT_FAMILY_REQUIRED",
                "product_family",
            )
        if not request.product_id.strip():
            raise ProductPublicationError("PRODUCT_ID_REQUIRED", "product_id")
        if request.release.scope_type not in {"SESSION", "LONGITUDINAL"}:
            raise ProductPublicationError(
                "SCOPE_TYPE_INVALID",
                request.release.scope_type,
            )
        if not request.release.scope_key.strip():
            raise ProductPublicationError("SCOPE_KEY_REQUIRED", "scope_key")
        if not request.media_type.strip():
            raise ProductPublicationError("MEDIA_TYPE_REQUIRED", "media_type")
        if not request.storage_backend.strip():
            raise ProductPublicationError(
                "STORAGE_BACKEND_REQUIRED",
                "storage_backend",
            )
        if not request.idempotency_key.strip():
            raise ProductPublicationError(
                "IDEMPOTENCY_KEY_REQUIRED",
                "idempotency_key",
            )
        if request.expected_version_token < 0:
            raise ProductPublicationError(
                "EXPECTED_VERSION_TOKEN_INVALID",
                str(request.expected_version_token),
            )

        try:
            staged = self._object_flow.stage(
                sealed_uri=request.sealed_uri,
                data=request.payload,
                operation_id=request.operation_id,
            )
            sealed = self._object_flow.seal(staged)
        except (ObjectSealError, ObjectStoreError) as exc:
            raise ProductPublicationError(
                "OBJECT_SEAL_FAILED",
                str(exc),
            ) from exc

        registration = ProductPublicationRegistration(
            product_family=request.product_family,
            product_id=request.product_id,
            release=request.release,
            object_uri=sealed.logical_uri,
            object_sha256=sealed.artifact_sha256,
            object_byte_size=sealed.byte_size,
            media_type=request.media_type,
            storage_backend=request.storage_backend,
            idempotency_key=request.idempotency_key,
            expected_version_token=request.expected_version_token,
        )
        try:
            with self._unit_of_work_factory() as uow:
                receipt = uow.product_publication.register(registration)
                if (
                    receipt.product_family != registration.product_family
                    or receipt.product_id != registration.product_id
                    or receipt.release_id != registration.release.release_id
                    or receipt.scope_type != registration.release.scope_type
                    or receipt.scope_key != registration.release.scope_key
                    or receipt.object_uri != registration.object_uri
                    or receipt.object_sha256 != registration.object_sha256
                ):
                    raise ProductPublicationError(
                        "PUBLICATION_RECEIPT_IDENTITY_MISMATCH",
                        request.product_id,
                        sealed_object=sealed,
                    )
                uow.commit()
        except ProductPublicationError as exc:
            if exc.sealed_object is not None:
                raise
            raise ProductPublicationError(
                exc.code,
                exc.detail,
                sealed_object=sealed,
            ) from exc
        except Exception as exc:
            raise ProductPublicationError(
                "DATABASE_PUBLICATION_FAILED",
                type(exc).__name__,
                sealed_object=sealed,
            ) from exc

        return ProductPublicationResult(
            sealed_object=sealed,
            receipt=receipt,
        )


@dataclass(frozen=True, slots=True)
class OrphanRecoveryReport:
    logical_prefix: str
    scanned: int
    referenced: int
    orphaned: tuple[str, ...]
    removed: tuple[str, ...]
    dry_run: bool


@dataclass(frozen=True, slots=True)
class StagingRecoveryReport:
    logical_prefix: str
    scanned: int
    active_operations: tuple[str, ...]
    orphaned: tuple[str, ...]
    removed: tuple[str, ...]
    dry_run: bool


def recover_sealed_orphans(
    store: LocalObjectStore,
    *,
    logical_prefix: str,
    referenced_uris: Iterable[str],
    dry_run: bool = True,
) -> OrphanRecoveryReport:
    """Detect or remove sealed objects absent from the DB authority set."""

    referenced = frozenset(referenced_uris)
    objects = store.list_objects(logical_prefix)
    orphaned = tuple(
        item.logical_uri
        for item in objects
        if item.logical_uri not in referenced
    )
    removed: list[str] = []
    if not dry_run:
        by_uri = {item.logical_uri: item for item in objects}
        for logical_uri in orphaned:
            item = by_uri[logical_uri]
            if store.delete_object(
                logical_uri,
                expected_sha256=item.artifact_sha256,
            ):
                removed.append(logical_uri)
    return OrphanRecoveryReport(
        logical_prefix=logical_prefix,
        scanned=len(objects),
        referenced=sum(
            1 for item in objects if item.logical_uri in referenced
        ),
        orphaned=orphaned,
        removed=tuple(removed),
        dry_run=dry_run,
    )


def recover_registered_product_orphans(
    store: LocalObjectStore,
    ledger: ProductPublicationLedger,
    *,
    logical_prefix: str,
    dry_run: bool = True,
) -> OrphanRecoveryReport:
    """Recover sealed objects against the DB ledger as the only reference authority."""

    return recover_sealed_orphans(
        store,
        logical_prefix=logical_prefix,
        referenced_uris=ledger.referenced_object_uris(logical_prefix),
        dry_run=dry_run,
    )


def _staging_operation_id(logical_uri: str) -> str:
    parts = logical_uri.split("/")
    if len(parts) < 5 or parts[2] != "staging":
        raise ProductPublicationError(
            "STAGING_URI_INVALID",
            logical_uri,
        )
    operation_id = parts[3]
    if not operation_id:
        raise ProductPublicationError(
            "STAGING_URI_INVALID",
            logical_uri,
        )
    return operation_id


def recover_staging_orphans(
    store: LocalObjectStore,
    *,
    scheme: str,
    active_operation_ids: Iterable[str] = (),
    dry_run: bool = True,
) -> StagingRecoveryReport:
    """Reclaim staging bytes not owned by an explicitly active operation."""

    if scheme not in {"tpaa-object", "tpaa-parquet"}:
        raise ProductPublicationError("STAGING_SCHEME_INVALID", scheme)
    logical_prefix = f"{scheme}://staging"
    active = frozenset(active_operation_ids)
    objects = store.list_objects(logical_prefix)
    orphaned = tuple(
        item.logical_uri
        for item in objects
        if _staging_operation_id(item.logical_uri) not in active
    )
    removed: list[str] = []
    if not dry_run:
        by_uri = {item.logical_uri: item for item in objects}
        for logical_uri in orphaned:
            item = by_uri[logical_uri]
            if store.delete_object(
                logical_uri,
                expected_sha256=item.artifact_sha256,
            ):
                removed.append(logical_uri)
    return StagingRecoveryReport(
        logical_prefix=logical_prefix,
        scanned=len(objects),
        active_operations=tuple(sorted(active)),
        orphaned=orphaned,
        removed=tuple(removed),
        dry_run=dry_run,
    )
