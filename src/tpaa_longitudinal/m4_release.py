"""M4 Batch 2 immutable longitudinal Release publication and replay."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass
from uuid import UUID, uuid5

from .m4_sample import M4LongitudinalError, M4LongitudinalScope
from .m4_trend import M4PerformanceTrendSeries

M4_LONGITUDINAL_RELEASE_NAMESPACE = UUID(
    "35c9519e-7ee7-5d6a-88d2-ec82eb767718"
)


@dataclass(frozen=True)
class M4LongitudinalReleaseInput:
    input_session_release_id: str
    input_sample_id: str

    def projection(self) -> dict[str, object]:
        return {
            "longitudinal_release_scope_type": "LONGITUDINAL",
            "input_session_release_id": self.input_session_release_id,
            "input_release_scope_type": "SESSION",
            "input_sample_id": self.input_sample_id,
        }


@dataclass(frozen=True)
class M4LongitudinalReleaseSnapshot:
    release_id: str
    request_hash: str
    scope_type: str
    scope_key: str
    longitudinal_scope_id: str
    release_no: int
    compute_job_id: str
    catalog_version: str
    catalog_hash: str
    context_binding_hash: str
    status: str
    parent_release_id: str | None
    manifest_hash: str
    created_at_utc: str
    inputs: tuple[M4LongitudinalReleaseInput, ...]
    trend_series: M4PerformanceTrendSeries

    def logical_membership(self) -> dict[str, object]:
        return {
            "release_id": self.release_id,
            "request_hash": self.request_hash,
            "scope_type": self.scope_type,
            "scope_key": self.scope_key,
            "longitudinal_scope_id": self.longitudinal_scope_id,
            "release_no": self.release_no,
            "compute_job_id": self.compute_job_id,
            "catalog_version": self.catalog_version,
            "catalog_hash": self.catalog_hash,
            "context_binding_hash": self.context_binding_hash,
            "status": self.status,
            "parent_release_id": self.parent_release_id,
            "manifest_hash": self.manifest_hash,
            "created_at": self.created_at_utc,
            "inputs": [item.projection() for item in self.inputs],
            "trend": self.trend_series.logical_product(),
        }


@dataclass(frozen=True)
class M4PublishedLongitudinalRelease:
    release: M4LongitudinalReleaseSnapshot
    version_token: int
    published_at_utc: str

    @property
    def status(self) -> str:
        return "PUBLISHED"


@dataclass(frozen=True)
class M4PublishResult:
    published: M4PublishedLongitudinalRelease
    reused: bool


@dataclass(frozen=True)
class M4ReplayComparison:
    release_id: str
    manifest_equal: bool
    input_membership_equal: bool
    trend_logical_product_equal: bool
    exact_logical_products_equal: bool


@dataclass(frozen=True)
class M4ReplayView:
    view_mode: str
    base_release_id: str
    retrospective_release_id: str | None
    release_ids: tuple[str, ...]


def _canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (TypeError, ValueError) as exc:
        raise M4LongitudinalError(
            "M4_RELEASE_CANONICAL_JSON_INVALID",
            type(exc).__name__,
        ) from exc


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()


def _hash64(value: str, *, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise M4LongitudinalError(
            "M4_RELEASE_HASH_INVALID",
            f"{field}={value!r}",
        )
    return value


def _uuid(
    value: str,
    *,
    field: str,
    missing_code: str = "FAIL_CLOSED_EXACT_RELEASE_REQUIRED",
) -> str:
    if not value:
        raise M4LongitudinalError(missing_code, field)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M4LongitudinalError(
            "M4_RELEASE_UUID_INVALID",
            f"{field}={value!r}",
        ) from exc
    if str(parsed) != value or parsed.int == 0:
        raise M4LongitudinalError(
            "M4_RELEASE_UUID_INVALID",
            f"{field}={value!r}",
        )
    return value


def _utc(value: str, *, field: str) -> str:
    if not value.endswith("Z") or "T" not in value:
        raise M4LongitudinalError(
            "M4_RELEASE_UTC_INVALID",
            f"{field}={value!r}",
        )
    return value


def allocate_m4_longitudinal_release_id(
    *,
    longitudinal_scope_key: str,
    request_hash: str,
) -> str:
    _hash64(longitudinal_scope_key, field="longitudinal_scope_key")
    _hash64(request_hash, field="request_hash")
    return str(
        uuid5(
            M4_LONGITUDINAL_RELEASE_NAMESPACE,
            f"{longitudinal_scope_key}|{request_hash}",
        )
    )


def build_m4_longitudinal_release(
    *,
    release_id: str,
    request_hash: str,
    release_no: int,
    parent_release_id: str | None,
    compute_job_id: str,
    catalog_version: str,
    catalog_hash: str,
    context_binding_hash: str,
    longitudinal_scope_id: str,
    scope: M4LongitudinalScope,
    trend_series: M4PerformanceTrendSeries,
    created_at_utc: str,
) -> M4LongitudinalReleaseSnapshot:
    _uuid(release_id, field="release_id")
    _hash64(request_hash, field="request_hash")
    _uuid(compute_job_id, field="compute_job_id")
    _uuid(longitudinal_scope_id, field="longitudinal_scope_id")
    _hash64(catalog_hash, field="catalog_hash")
    _hash64(context_binding_hash, field="context_binding_hash")
    _hash64(scope.longitudinal_scope_key, field="scope_key")
    _utc(created_at_utc, field="created_at_utc")
    if not catalog_version.strip():
        raise M4LongitudinalError(
            "M4_RELEASE_CATALOG_VERSION_REQUIRED",
            "catalog_version",
        )
    if release_no < 1:
        raise M4LongitudinalError(
            "M4_RELEASE_NO_INVALID",
            str(release_no),
        )
    if parent_release_id is not None:
        _uuid(parent_release_id, field="parent_release_id")
    if (release_no == 1) != (parent_release_id is None):
        raise M4LongitudinalError(
            "M4_RELEASE_PARENT_CHAIN_INVALID",
            f"release_no={release_no} parent={parent_release_id}",
        )
    expected_release_id = allocate_m4_longitudinal_release_id(
        longitudinal_scope_key=scope.longitudinal_scope_key,
        request_hash=request_hash,
    )
    if release_id != expected_release_id:
        raise M4LongitudinalError(
            "M4_RELEASE_IDENTITY_MISMATCH",
            release_id,
        )
    if (
        trend_series.release_id != release_id
        or trend_series.longitudinal_scope_id != longitudinal_scope_id
        or trend_series.longitudinal_scope_key
        != scope.longitudinal_scope_key
        or trend_series.comparison_key_hash
        != scope.comparison_key_hash
        or trend_series.subject_type != scope.subject_type
        or trend_series.subject_id != scope.subject_id
        or trend_series.metric_semantic_id
        != scope.metric_semantic_id
        or trend_series.metric_semantic_version
        != scope.metric_semantic_version
    ):
        raise M4LongitudinalError(
            "M4_RELEASE_TREND_SCOPE_MISMATCH",
            trend_series.trend_id,
        )
    if not trend_series.input_membership:
        raise M4LongitudinalError(
            "M4_RELEASE_INPUT_MEMBERSHIP_EMPTY",
            release_id,
        )
    seen_samples: set[str] = set()
    inputs: list[M4LongitudinalReleaseInput] = []
    for session_release_id, sample_id in trend_series.input_membership:
        _uuid(session_release_id, field="input_session_release_id")
        _uuid(sample_id, field="input_sample_id")
        if sample_id in seen_samples:
            raise M4LongitudinalError(
                "M4_RELEASE_INPUT_SAMPLE_DUPLICATE",
                sample_id,
            )
        seen_samples.add(sample_id)
        inputs.append(
            M4LongitudinalReleaseInput(
                input_session_release_id=session_release_id,
                input_sample_id=sample_id,
            )
        )
    input_tuple = tuple(inputs)
    manifest_material = {
        "release_id": release_id,
        "request_hash": request_hash,
        "scope_type": "LONGITUDINAL",
        "scope_key": scope.longitudinal_scope_key,
        "longitudinal_scope_id": longitudinal_scope_id,
        "release_no": release_no,
        "compute_job_id": compute_job_id,
        "catalog_version": catalog_version,
        "catalog_hash": catalog_hash,
        "context_binding_hash": context_binding_hash,
        "parent_release_id": parent_release_id,
        "created_at": created_at_utc,
        "inputs": [item.projection() for item in input_tuple],
        "trend": trend_series.logical_product(),
    }
    manifest_hash = _canonical_hash(manifest_material)
    return M4LongitudinalReleaseSnapshot(
        release_id=release_id,
        request_hash=request_hash,
        scope_type="LONGITUDINAL",
        scope_key=scope.longitudinal_scope_key,
        longitudinal_scope_id=longitudinal_scope_id,
        release_no=release_no,
        compute_job_id=compute_job_id,
        catalog_version=catalog_version,
        catalog_hash=catalog_hash,
        context_binding_hash=context_binding_hash,
        status="VALIDATED",
        parent_release_id=parent_release_id,
        manifest_hash=manifest_hash,
        created_at_utc=created_at_utc,
        inputs=input_tuple,
        trend_series=trend_series,
    )


def compare_m4_longitudinal_replay(
    historical: M4LongitudinalReleaseSnapshot,
    candidate: M4LongitudinalReleaseSnapshot,
) -> M4ReplayComparison:
    input_equal = historical.inputs == candidate.inputs
    trend_equal = (
        historical.trend_series.logical_hash
        == candidate.trend_series.logical_hash
    )
    manifest_equal = historical.manifest_hash == candidate.manifest_hash
    return M4ReplayComparison(
        release_id=historical.release_id,
        manifest_equal=manifest_equal,
        input_membership_equal=input_equal,
        trend_logical_product_equal=trend_equal,
        exact_logical_products_equal=(
            historical.release_id == candidate.release_id
            and manifest_equal
            and input_equal
            and trend_equal
        ),
    )


class InMemoryM4LongitudinalReleaseRepository:
    """Executable immutable/CAS reference semantics for M4 Batch 2."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._releases: dict[str, M4PublishedLongitudinalRelease] = {}
        self._current: dict[str, str] = {}
        self._tokens: dict[str, int] = {}
        self._idempotency: dict[str, tuple[str, str, str]] = {}

    @staticmethod
    def _key(idempotency_key: str) -> str:
        key = idempotency_key.strip()
        if not key:
            raise M4LongitudinalError(
                "M4_RELEASE_IDEMPOTENCY_KEY_REQUIRED",
                "idempotency_key",
            )
        return key

    def publish(
        self,
        release: M4LongitudinalReleaseSnapshot,
        *,
        idempotency_key: str,
        expected_version_token: int,
        published_at_utc: str,
    ) -> M4PublishResult:
        key = self._key(idempotency_key)
        _utc(published_at_utc, field="published_at_utc")
        if expected_version_token < 0:
            raise M4LongitudinalError(
                "M4_RELEASE_EXPECTED_VERSION_TOKEN_INVALID",
                str(expected_version_token),
            )
        with self._lock:
            prior = self._idempotency.get(key)
            if prior is not None:
                prior_request, prior_manifest, prior_release_id = prior
                if (
                    prior_request != release.request_hash
                    or prior_manifest != release.manifest_hash
                    or prior_release_id != release.release_id
                ):
                    raise M4LongitudinalError(
                        "M4_RELEASE_IDEMPOTENCY_CONFLICT",
                        key,
                    )
                return M4PublishResult(
                    published=self._releases[prior_release_id],
                    reused=True,
                )

            actual_token = self._tokens.get(release.scope_key, 0)
            if actual_token != expected_version_token:
                raise M4LongitudinalError(
                    "M4_RELEASE_CAS_CONFLICT",
                    (
                        f"expected={expected_version_token} "
                        f"actual={actual_token}"
                    ),
                )
            expected_parent = self._current.get(release.scope_key)
            if release.parent_release_id != expected_parent:
                raise M4LongitudinalError(
                    "M4_RELEASE_PARENT_RELEASE_MISMATCH",
                    (
                        f"expected={expected_parent!r} "
                        f"actual={release.parent_release_id!r}"
                    ),
                )
            if release.release_no != actual_token + 1:
                raise M4LongitudinalError(
                    "M4_RELEASE_NO_MISMATCH",
                    (
                        f"expected={actual_token + 1} "
                        f"actual={release.release_no}"
                    ),
                )
            existing = self._releases.get(release.release_id)
            if existing is not None:
                if existing.release.manifest_hash != release.manifest_hash:
                    raise M4LongitudinalError(
                        "M4_RELEASE_EXISTING_CONFLICT",
                        release.release_id,
                    )
                self._idempotency[key] = (
                    release.request_hash,
                    release.manifest_hash,
                    release.release_id,
                )
                return M4PublishResult(
                    published=existing,
                    reused=True,
                )

            next_token = actual_token + 1
            published = M4PublishedLongitudinalRelease(
                release=release,
                version_token=next_token,
                published_at_utc=published_at_utc,
            )
            self._releases[release.release_id] = published
            self._current[release.scope_key] = release.release_id
            self._tokens[release.scope_key] = next_token
            self._idempotency[key] = (
                release.request_hash,
                release.manifest_hash,
                release.release_id,
            )
            return M4PublishResult(published=published, reused=False)

    def get_release(self, release_id: str) -> M4PublishedLongitudinalRelease:
        canonical = _uuid(release_id, field="release_id")
        with self._lock:
            result = self._releases.get(canonical)
        if result is None:
            raise M4LongitudinalError(
                "M4_RELEASE_NOT_FOUND",
                canonical,
            )
        return result

    def current(
        self,
        longitudinal_scope_key: str,
    ) -> M4PublishedLongitudinalRelease | None:
        _hash64(longitudinal_scope_key, field="longitudinal_scope_key")
        with self._lock:
            release_id = self._current.get(longitudinal_scope_key)
            if release_id is None:
                return None
            return self._releases[release_id]

    def version_token(self, longitudinal_scope_key: str) -> int:
        _hash64(longitudinal_scope_key, field="longitudinal_scope_key")
        with self._lock:
            return self._tokens.get(longitudinal_scope_key, 0)


class M4LongitudinalPublicationService:
    """Exact-release service; current() is discovery, never replay fallback."""

    def __init__(
        self,
        repository: InMemoryM4LongitudinalReleaseRepository,
    ) -> None:
        self._repository = repository

    def publish(
        self,
        release: M4LongitudinalReleaseSnapshot,
        *,
        idempotency_key: str,
        expected_version_token: int,
        published_at_utc: str,
    ) -> M4PublishResult:
        return self._repository.publish(
            release,
            idempotency_key=idempotency_key,
            expected_version_token=expected_version_token,
            published_at_utc=published_at_utc,
        )

    def historical_release(
        self,
        release_id: str,
    ) -> M4PublishedLongitudinalRelease:
        return self._repository.get_release(release_id)

    def current(
        self,
        longitudinal_scope_key: str,
    ) -> M4PublishedLongitudinalRelease | None:
        return self._repository.current(longitudinal_scope_key)

    def replay(
        self,
        release_id: str,
        candidate: M4LongitudinalReleaseSnapshot,
    ) -> M4ReplayComparison:
        historical = self.historical_release(release_id)
        return compare_m4_longitudinal_replay(
            historical.release,
            candidate,
        )

    def original_as_known(self, release_id: str) -> M4ReplayView:
        historical = self.historical_release(release_id)
        exact = historical.release.release_id
        return M4ReplayView(
            view_mode="ORIGINAL_AS_KNOWN",
            base_release_id=exact,
            retrospective_release_id=None,
            release_ids=(exact,),
        )

    def retrospective(
        self,
        base_release_id: str,
        retrospective_release_id: str,
    ) -> M4ReplayView:
        base = self.historical_release(base_release_id).release
        if not retrospective_release_id:
            raise M4LongitudinalError(
                "FAIL_CLOSED_RETROSPECTIVE_RELEASE_REQUIRED",
                "retrospective_release_id",
            )
        retrospective = self.historical_release(
            retrospective_release_id
        ).release
        if retrospective.release_id == base.release_id:
            raise M4LongitudinalError(
                "M4_RETROSPECTIVE_RELEASE_MUST_DIFFER",
                base.release_id,
            )
        if retrospective.scope_key != base.scope_key:
            raise M4LongitudinalError(
                "M4_RETROSPECTIVE_SCOPE_MISMATCH",
                retrospective.release_id,
            )
        return M4ReplayView(
            view_mode="RETROSPECTIVE",
            base_release_id=base.release_id,
            retrospective_release_id=retrospective.release_id,
            release_ids=(
                base.release_id,
                retrospective.release_id,
            ),
        )
