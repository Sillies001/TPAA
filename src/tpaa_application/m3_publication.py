"""Idempotent publication and explicit historical replay for M3 Releases.

M3-OBS-003 carries the qualified M2 CAS/idempotency model forward to immutable
116-metric M3 Release snapshots. Historical reads and replay are always bound to
an explicit Release ID and never resolve current/latest Catalog, Context, World,
identity or provenance authority.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Protocol, cast, runtime_checkable

from tpaa_observation import M3ImmutableReleaseSnapshot, M3ReleaseSnapshotError


class M3PublicationError(RuntimeError):
    """Base deterministic M3 publication failure."""


class M3PublishCASConflict(M3PublicationError):
    def __init__(self, *, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"M3_PUBLISH_CAS_CONFLICT expected={expected} actual={actual}"
        )


class M3PublishIdempotencyConflict(M3PublicationError):
    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(f"M3_PUBLISH_IDEMPOTENCY_CONFLICT key={key}")


class M3PublishedReleaseConflict(M3PublicationError):
    def __init__(self, release_id: str) -> None:
        self.release_id = release_id
        super().__init__(f"M3_PUBLISHED_RELEASE_CONFLICT release_id={release_id}")


class M3ReleaseNotFound(M3PublicationError):
    def __init__(self, release_id: str) -> None:
        self.release_id = release_id
        super().__init__(f"M3_RELEASE_NOT_FOUND release_id={release_id}")


class M3MetricNotFound(M3PublicationError):
    def __init__(self, metric_code: str) -> None:
        self.metric_code = metric_code
        super().__init__(f"M3_METRIC_NOT_FOUND metric_code={metric_code}")


@dataclass(frozen=True)
class M3PublishedRelease:
    release: M3ImmutableReleaseSnapshot
    version_token: int
    status: str = "PUBLISHED"

    def __post_init__(self) -> None:
        if self.status != "PUBLISHED":
            raise M3PublicationError(
                f"M3_INVALID_PUBLISHED_STATUS status={self.status}"
            )
        if self.version_token < 1:
            raise M3PublicationError(
                "M3_INVALID_PUBLISHED_VERSION_TOKEN "
                f"token={self.version_token}"
            )


@dataclass(frozen=True)
class M3PublishResult:
    published: M3PublishedRelease
    reused: bool


@dataclass(frozen=True)
class M3ReplayComparison:
    release_id: str
    release_identity_equal: bool
    manifest_equal: bool
    catalog_equal: bool
    plan_equal: bool
    routing_equal: bool
    execution_equal: bool
    bindings_equal: bool
    provenance_equal: bool
    definitions_equal: bool
    execution_records_equal: bool
    evidence_bindings_equal: bool
    exact_logical_products_equal: bool


def compare_m3_release_replay(
    release: M3ImmutableReleaseSnapshot,
    candidate: M3ImmutableReleaseSnapshot,
) -> M3ReplayComparison:
    """Compare explicit immutable Release products without latest fallback."""

    release_identity_equal = (
        release.release_id == candidate.release_id
        and release.release_no == candidate.release_no
        and release.parent_release_id == candidate.parent_release_id
        and release.session_id == candidate.session_id
        and release.request_hash == candidate.request_hash
    )
    manifest_equal = release.manifest_hash == candidate.manifest_hash
    catalog_equal = (
        release.catalog_id == candidate.catalog_id
        and release.catalog_version == candidate.catalog_version
        and release.catalog_hash == candidate.catalog_hash
    )
    plan_equal = (
        release.metric_execution_plan_hash
        == candidate.metric_execution_plan_hash
    )
    routing_equal = (
        release.publication_routing_plan_hash
        == candidate.publication_routing_plan_hash
    )
    execution_equal = (
        release.execution_batch_hash == candidate.execution_batch_hash
        and release.plugin_manifest_hash == candidate.plugin_manifest_hash
    )
    bindings_equal = release.bindings == candidate.bindings
    provenance_equal = (
        release.bindings.provenance_hash == candidate.bindings.provenance_hash
        and release.bindings.provenance_json == candidate.bindings.provenance_json
    )
    definitions_equal = release.definitions == candidate.definitions
    execution_records_equal = (
        release.execution_records == candidate.execution_records
    )
    evidence_bindings_equal = (
        release.evidence_bindings == candidate.evidence_bindings
    )
    exact = all(
        (
            release_identity_equal,
            manifest_equal,
            catalog_equal,
            plan_equal,
            routing_equal,
            execution_equal,
            bindings_equal,
            provenance_equal,
            definitions_equal,
            execution_records_equal,
            evidence_bindings_equal,
        )
    )
    return M3ReplayComparison(
        release_id=release.release_id,
        release_identity_equal=release_identity_equal,
        manifest_equal=manifest_equal,
        catalog_equal=catalog_equal,
        plan_equal=plan_equal,
        routing_equal=routing_equal,
        execution_equal=execution_equal,
        bindings_equal=bindings_equal,
        provenance_equal=provenance_equal,
        definitions_equal=definitions_equal,
        execution_records_equal=execution_records_equal,
        evidence_bindings_equal=evidence_bindings_equal,
        exact_logical_products_equal=exact,
    )


@runtime_checkable
class M3ReleasePublicationRepository(Protocol):
    def idempotency_lookup(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
    ) -> M3PublishedRelease | None:
        """Resolve one exact prior request by key, or fail on key reuse."""

    def publish(
        self,
        release: M3ImmutableReleaseSnapshot,
        *,
        idempotency_key: str,
        expected_version_token: int,
    ) -> M3PublishResult:
        """CAS-publish one immutable release."""

    def get_release(self, release_id: str) -> M3PublishedRelease:
        """Read one explicit historical Release; never current/latest fallback."""

    def current(self, session_id: str) -> M3PublishedRelease | None:
        """Read the mutable current pointer for new publication only."""

    def version_token(self, session_id: str) -> int:
        """Read the current SESSION CAS token."""


class InMemoryM3ReleasePublicationRepository:
    """Thread-safe executable reference semantics for M3 publication."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._releases: dict[str, M3PublishedRelease] = {}
        self._current: dict[str, str] = {}
        self._tokens: dict[str, int] = {}
        self._idempotency: dict[str, tuple[str, str, str]] = {}

    @staticmethod
    def _require_key(idempotency_key: str) -> str:
        key = idempotency_key.strip()
        if not key:
            raise M3PublicationError("M3_IDEMPOTENCY_KEY_REQUIRED")
        return key

    def idempotency_lookup(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
    ) -> M3PublishedRelease | None:
        key = self._require_key(idempotency_key)
        with self._lock:
            prior = self._idempotency.get(key)
            if prior is None:
                return None
            prior_request_hash, _, release_id = prior
            if prior_request_hash != request_hash:
                raise M3PublishIdempotencyConflict(key)
            return self._releases[release_id]

    def publish(
        self,
        release: M3ImmutableReleaseSnapshot,
        *,
        idempotency_key: str,
        expected_version_token: int,
    ) -> M3PublishResult:
        key = self._require_key(idempotency_key)
        if expected_version_token < 0:
            raise M3PublicationError(
                "M3_EXPECTED_VERSION_TOKEN_INVALID "
                f"token={expected_version_token}"
            )

        with self._lock:
            prior = self._idempotency.get(key)
            if prior is not None:
                prior_request_hash, prior_manifest_hash, prior_release_id = prior
                if (
                    prior_request_hash != release.request_hash
                    or prior_manifest_hash != release.manifest_hash
                    or prior_release_id != release.release_id
                ):
                    raise M3PublishIdempotencyConflict(key)
                return M3PublishResult(
                    published=self._releases[prior_release_id],
                    reused=True,
                )

            session_id = release.session_id
            actual_token = self._tokens.get(session_id, 0)
            if actual_token != expected_version_token:
                raise M3PublishCASConflict(
                    expected=expected_version_token,
                    actual=actual_token,
                )

            expected_parent = self._current.get(session_id)
            expected_release_no = actual_token + 1
            if release.parent_release_id != expected_parent:
                raise M3PublicationError(
                    "M3_PUBLISH_PARENT_RELEASE_MISMATCH "
                    f"expected={expected_parent!r} "
                    f"actual={release.parent_release_id!r}"
                )
            if release.release_no != expected_release_no:
                raise M3PublicationError(
                    "M3_PUBLISH_RELEASE_NO_MISMATCH "
                    f"expected={expected_release_no} "
                    f"actual={release.release_no}"
                )

            existing = self._releases.get(release.release_id)
            if existing is not None:
                if existing.release.manifest_hash != release.manifest_hash:
                    raise M3PublishedReleaseConflict(release.release_id)
                self._idempotency[key] = (
                    release.request_hash,
                    release.manifest_hash,
                    release.release_id,
                )
                return M3PublishResult(published=existing, reused=True)

            next_token = actual_token + 1
            published = M3PublishedRelease(
                release=release,
                version_token=next_token,
            )
            self._releases[release.release_id] = published
            self._current[session_id] = release.release_id
            self._tokens[session_id] = next_token
            self._idempotency[key] = (
                release.request_hash,
                release.manifest_hash,
                release.release_id,
            )
            return M3PublishResult(published=published, reused=False)

    def get_release(self, release_id: str) -> M3PublishedRelease:
        with self._lock:
            published = self._releases.get(release_id)
        if published is None:
            raise M3ReleaseNotFound(release_id)
        return published

    def current(self, session_id: str) -> M3PublishedRelease | None:
        with self._lock:
            release_id = self._current.get(session_id)
            if release_id is None:
                return None
            return self._releases[release_id]

    def version_token(self, session_id: str) -> int:
        with self._lock:
            return self._tokens.get(session_id, 0)


class M3PublicationService:
    """Application facade that keeps historical reads explicitly Release-bound."""

    def __init__(self, repository: M3ReleasePublicationRepository) -> None:
        self._repository = repository

    def publish(
        self,
        release: M3ImmutableReleaseSnapshot,
        *,
        idempotency_key: str,
        expected_version_token: int,
    ) -> M3PublishResult:
        return self._repository.publish(
            release,
            idempotency_key=idempotency_key,
            expected_version_token=expected_version_token,
        )

    def historical_release(self, release_id: str) -> M3PublishedRelease:
        return self._repository.get_release(release_id)

    def current(self, session_id: str) -> M3PublishedRelease | None:
        return self._repository.current(session_id)

    def replay(
        self,
        release_id: str,
        candidate: M3ImmutableReleaseSnapshot,
    ) -> M3ReplayComparison:
        historical = self._repository.get_release(release_id)
        return compare_m3_release_replay(historical.release, candidate)


    def release_summary(self, release_id: str) -> dict[str, object]:
        """Project one explicit historical Release without current/latest lookup."""

        published = self.historical_release(release_id)
        release = published.release
        return {
            "release_id": release.release_id,
            "release_no": release.release_no,
            "parent_release_id": release.parent_release_id,
            "session_id": release.session_id,
            "request_hash": release.request_hash,
            "catalog_id": release.catalog_id,
            "catalog_version": release.catalog_version,
            "catalog_hash": release.catalog_hash,
            "metric_execution_plan_hash": release.metric_execution_plan_hash,
            "publication_routing_plan_hash": release.publication_routing_plan_hash,
            "execution_batch_hash": release.execution_batch_hash,
            "plugin_manifest_hash": release.plugin_manifest_hash,
            "manifest_hash": release.manifest_hash,
            "status": published.status,
            "version_token": published.version_token,
            "metric_count": len(release.definitions),
            "binding_hashes": {
                "context_hash": release.bindings.context_hash,
                "world_hash": release.bindings.world_hash,
                "identity_hash": release.bindings.identity_hash,
                "provenance_hash": release.bindings.provenance_hash,
            },
        }

    def metric_list(self, release_id: str) -> list[dict[str, object]]:
        """Project all frozen Metric products from one explicit Release."""

        release = self.historical_release(release_id).release
        records = {item.metric_code: item for item in release.execution_records}
        evidence = {item.metric_code: item for item in release.evidence_bindings}
        return [
            {
                "release_id": release.release_id,
                "metric_code": definition.metric_code,
                "semantic_id": definition.semantic_id,
                "semantic_version": definition.semantic_version,
                "definition_hash": definition.definition_hash,
                "authority_lineage_hash": definition.authority_lineage_hash,
                "subject_type": definition.subject_type,
                "observation_lane": definition.observation_lane,
                "publication_route": definition.publication_route,
                "value_kind": definition.value_kind,
                "structured_output_schema_id": (
                    definition.structured_output_schema_id
                ),
                "execution_record_hash": (
                    records[definition.metric_code].record_logical_hash
                ),
                "evidence_hash": evidence[definition.metric_code].evidence_hash,
            }
            for definition in release.definitions
        ]

    def metric_detail(
        self,
        release_id: str,
        metric_code: str,
    ) -> dict[str, object]:
        """Project frozen Definition/execution/Evidence for one Metric."""

        release = self.historical_release(release_id).release
        try:
            definition = release.definition(metric_code)
            evidence = release.evidence(metric_code)
        except M3ReleaseSnapshotError as exc:
            raise M3MetricNotFound(metric_code) from exc
        record = next(
            (
                item
                for item in release.execution_records
                if item.metric_code == metric_code
            ),
            None,
        )
        if record is None:
            raise M3MetricNotFound(metric_code)
        evidence_payload = cast(
            dict[str, object],
            json.loads(evidence.evidence_json),
        )
        return {
            "release_id": release.release_id,
            "metric_code": metric_code,
            "definition": definition.projection(),
            "execution": record.projection(),
            "evidence": {
                "definition_hash": evidence.definition_hash,
                "execution_record_hash": evidence.execution_record_hash,
                "evidence_hash": evidence.evidence_hash,
                "payload": evidence_payload,
            },
            "release_provenance": {
                "manifest_hash": release.manifest_hash,
                "context_hash": release.bindings.context_hash,
                "world_hash": release.bindings.world_hash,
                "identity_hash": release.bindings.identity_hash,
                "provenance_hash": release.bindings.provenance_hash,
            },
        }

    def metric_evidence(
        self,
        release_id: str,
        metric_code: str,
    ) -> dict[str, object]:
        """Project one frozen Evidence binding from an explicit historical Release."""

        release = self.historical_release(release_id).release
        try:
            definition = release.definition(metric_code)
            evidence = release.evidence(metric_code)
        except M3ReleaseSnapshotError as exc:
            raise M3MetricNotFound(metric_code) from exc
        payload = cast(
            dict[str, object],
            json.loads(evidence.evidence_json),
        )
        return {
            "release_id": release.release_id,
            "metric_code": metric_code,
            "semantic_id": definition.semantic_id,
            "semantic_version": definition.semantic_version,
            "definition_hash": evidence.definition_hash,
            "execution_record_hash": evidence.execution_record_hash,
            "evidence_hash": evidence.evidence_hash,
            "payload": payload,
            "release_provenance": {
                "manifest_hash": release.manifest_hash,
                "provenance_hash": release.bindings.provenance_hash,
            },
        }
