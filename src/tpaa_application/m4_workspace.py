"""M4 exact-release longitudinal and evidence-first Debrief application projections."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from typing import Protocol, runtime_checkable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from uuid import UUID, uuid5

from tpaa_longitudinal import (
    M4LongitudinalError,
    M4LongitudinalPublicationService,
    M4PublishedLongitudinalRelease,
)

M4_ANNOTATION_NAMESPACE = UUID("12d0cf49-6757-5f69-892b-c5075c76469e")
M4_ANNOTATION_TYPES = frozenset(
    {
        "BOOKMARK",
        "COMMENT",
        "EVIDENCE_NOTE",
        "DEBRIEF_POINT",
        "CORRECTION_NOTE",
    }
)
M4_ANNOTATION_OPERATIONS = frozenset({"CREATE", "SUPERSEDE", "DELETE"})
M4_DEBRIEF_VIEW_MODES = frozenset({"ORIGINAL_AS_KNOWN", "RETROSPECTIVE"})
M4_ANNOTATION_VIEWS = frozenset({"NONE", "AS_OF_UTC", "EXACT_REVISION_SET"})


class M4ApplicationError(RuntimeError):
    """Fail-closed M4 application/query error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class M4TrendQuery:
    release_id: str
    trend_id: str | None = None
    subject_type: str | None = None
    subject_id: str | None = None
    metric_code: str | None = None
    comparison_key_hash: str | None = None

    def projection(self) -> dict[str, object]:
        return {
            "release_id": self.release_id,
            "trend_id": self.trend_id,
            "subject_type": self.subject_type,
            "subject_id": self.subject_id,
            "metric_code": self.metric_code,
            "comparison_key_hash": self.comparison_key_hash,
        }


@dataclass(frozen=True)
class M4DebriefQuery:
    base_release_id: str
    view_mode: str
    retrospective_release_id: str | None
    annotation_view: str
    annotation_as_of_utc: str | None
    annotation_ids: tuple[str, ...]

    def projection(self) -> dict[str, object]:
        return {
            "base_release_id": self.base_release_id,
            "view_mode": self.view_mode,
            "retrospective_release_id": self.retrospective_release_id,
            "annotation_view": self.annotation_view,
            "annotation_as_of_utc": self.annotation_as_of_utc,
            "annotation_ids": list(self.annotation_ids),
        }


@dataclass(frozen=True)
class M4DebriefTimelineItem:
    item_id: str
    item_type: str
    session_id: str
    episode_id: str | None
    stage_id: str | None
    start_session_time_us: int | None
    end_session_time_us: int | None
    evidence_set_id: str | None
    source_release_id: str

    def projection(
        self,
        *,
        base_release_id: str,
        knowledge_time_mode: str,
    ) -> dict[str, object]:
        return {
            "base_release_id": base_release_id,
            "item_id": self.item_id,
            "item_type": self.item_type,
            "session_id": self.session_id,
            "episode_id": self.episode_id,
            "stage_id": self.stage_id,
            "start_session_time_us": (
                None
                if self.start_session_time_us is None
                else str(self.start_session_time_us)
            ),
            "end_session_time_us": (
                None
                if self.end_session_time_us is None
                else str(self.end_session_time_us)
            ),
            "evidence_set_id": self.evidence_set_id,
            "source_release_id": self.source_release_id,
            "knowledge_time_mode": knowledge_time_mode,
        }


@dataclass(frozen=True)
class M4AnnotationCommand:
    request_id: str
    operation: str
    base_release_id: str
    target_annotation_id: str | None
    session_id: str
    episode_id: str | None
    stage_id: str | None
    author_id: str
    annotation_type: str
    start_session_time_us: int | None
    end_session_time_us: int | None
    body_text: str
    visibility: str
    reason: str
    evidence_set_id: str | None


@dataclass(frozen=True)
class M4DebriefAnnotation:
    annotation_id: str
    base_release_id: str
    session_id: str
    episode_id: str | None
    stage_id: str | None
    author_id: str
    annotation_type: str
    start_session_time_us: int | None
    end_session_time_us: int | None
    body_text: str
    visibility: str
    status: str
    revision_no: int
    supersedes_annotation_id: str | None
    evidence_set_id: str | None
    reason: str
    audit_id: int
    request_id: str
    created_at: str

    def projection(self) -> dict[str, object]:
        return {
            "annotation_id": self.annotation_id,
            "base_release_id": self.base_release_id,
            "session_id": self.session_id,
            "episode_id": self.episode_id,
            "stage_id": self.stage_id,
            "author_id": self.author_id,
            "annotation_type": self.annotation_type,
            "start_session_time_us": (
                None
                if self.start_session_time_us is None
                else str(self.start_session_time_us)
            ),
            "end_session_time_us": (
                None
                if self.end_session_time_us is None
                else str(self.end_session_time_us)
            ),
            "body_text": self.body_text,
            "visibility": self.visibility,
            "status": self.status,
            "revision_no": self.revision_no,
            "supersedes_annotation_id": self.supersedes_annotation_id,
            "evidence_set_id": self.evidence_set_id,
            "reason": self.reason,
            "audit_id": str(self.audit_id),
            "request_id": self.request_id,
            "created_at": self.created_at,
        }


def _uuid(value: str, *, field: str) -> str:
    if not value:
        raise M4ApplicationError("FAIL_CLOSED_EXACT_RELEASE_REQUIRED", field)
    try:
        parsed = UUID(value)
    except ValueError as exc:
        raise M4ApplicationError(
            "M4_DTO_UUID_INVALID",
            f"{field}={value!r}",
        ) from exc
    if str(parsed) != value or parsed.int == 0:
        raise M4ApplicationError(
            "M4_DTO_UUID_INVALID",
            f"{field}={value!r}",
        )
    return value


def _hash64(value: str, *, field: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise M4ApplicationError(
            "M4_DTO_HASH_INVALID",
            f"{field}={value!r}",
        )
    return value


def _utc(value: str, *, field: str) -> str:
    if not value.endswith("Z") or "T" not in value:
        raise M4ApplicationError(
            "M4_DTO_UTC_INVALID",
            f"{field}={value!r}",
        )
    return value


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _release_dto(
    published: M4PublishedLongitudinalRelease,
) -> dict[str, object]:
    release = published.release
    return {
        "release_id": release.release_id,
        "longitudinal_scope_id": release.longitudinal_scope_id,
        "scope_key": release.scope_key,
        "release_no": release.release_no,
        "catalog_version": release.catalog_version,
        "catalog_hash": release.catalog_hash,
        "context_binding_hash": release.context_binding_hash,
        "status": published.status,
        "parent_release_id": release.parent_release_id,
        "manifest_hash": release.manifest_hash,
        "input_session_release_ids": [
            item.input_session_release_id for item in release.inputs
        ],
        "input_sample_ids": [
            item.input_sample_id for item in release.inputs
        ],
        "created_at": release.created_at_utc,
        "published_at": published.published_at_utc,
    }


def _scope_dto(
    published: M4PublishedLongitudinalRelease,
) -> dict[str, object]:
    series = published.release.trend_series
    return {
        "longitudinal_scope_id": series.longitudinal_scope_id,
        "longitudinal_scope_key": series.longitudinal_scope_key,
        "subject_type": series.subject_type,
        "subject_id": series.subject_id,
        "metric_semantic_id": series.metric_semantic_id,
        "metric_semantic_version": series.metric_semantic_version,
        "comparison_key_hash": series.comparison_key_hash,
        "session_order_scope_id": series.session_order_scope_id,
        "trend_profile_version": series.trend_profile_version,
        "descriptor_hash": series.longitudinal_scope_key,
    }


def _series_dto(
    published: M4PublishedLongitudinalRelease,
) -> dict[str, object]:
    return published.release.trend_series.projection()


def _points_dto(
    published: M4PublishedLongitudinalRelease,
) -> list[dict[str, object]]:
    return [
        point.projection()
        for point in published.release.trend_series.points
    ]


@runtime_checkable
class M4DebriefRepository(Protocol):
    """Engine-neutral exact-release Debrief repository port."""

    def register_timeline(
        self,
        release_id: str,
        items: Sequence[M4DebriefTimelineItem],
    ) -> None: ...

    def timeline(self, release_id: str) -> tuple[M4DebriefTimelineItem, ...]: ...

    def apply_annotation(
        self,
        command: M4AnnotationCommand,
    ) -> M4DebriefAnnotation: ...

    def annotations_for(
        self,
        query: M4DebriefQuery,
    ) -> tuple[M4DebriefAnnotation, ...]: ...


class InMemoryM4DebriefRepository:
    """Append/revision annotation and exact-release timeline reference store."""

    def __init__(self, *, clock: Callable[[], str] = _utc_now) -> None:
        self._clock = clock
        self._timelines: dict[str, tuple[M4DebriefTimelineItem, ...]] = {}
        self._annotations: dict[str, M4DebriefAnnotation] = {}
        self._annotation_order: list[str] = []
        self._request_index: dict[str, tuple[str, str]] = {}
        self._next_audit_id = 1

    def register_timeline(
        self,
        release_id: str,
        items: Sequence[M4DebriefTimelineItem],
    ) -> None:
        _uuid(release_id, field="release_id")
        if release_id in self._timelines:
            raise M4ApplicationError(
                "M4_DEBRIEF_TIMELINE_IMMUTABLE",
                release_id,
            )
        for item in items:
            _uuid(item.session_id, field="session_id")
            _uuid(item.source_release_id, field="source_release_id")
            if item.episode_id is not None:
                _uuid(item.episode_id, field="episode_id")
            if item.stage_id is not None:
                _uuid(item.stage_id, field="stage_id")
            if item.evidence_set_id is not None:
                _uuid(item.evidence_set_id, field="evidence_set_id")
            if item.item_type not in {
                "STAGE",
                "EVENT",
                "METRIC",
                "EVIDENCE",
                "ANNOTATION",
            }:
                raise M4ApplicationError(
                    "M4_DEBRIEF_ITEM_TYPE_INVALID",
                    item.item_type,
                )
        self._timelines[release_id] = tuple(items)

    def timeline(self, release_id: str) -> tuple[M4DebriefTimelineItem, ...]:
        _uuid(release_id, field="release_id")
        return self._timelines.get(release_id, ())

    def apply_annotation(
        self,
        command: M4AnnotationCommand,
    ) -> M4DebriefAnnotation:
        _validate_annotation_command(command)
        fingerprint = hashlib.sha256(
            json.dumps(
                {
                    "request_id": command.request_id,
                    "operation": command.operation,
                    "base_release_id": command.base_release_id,
                    "target_annotation_id": command.target_annotation_id,
                    "session_id": command.session_id,
                    "episode_id": command.episode_id,
                    "stage_id": command.stage_id,
                    "author_id": command.author_id,
                    "annotation_type": command.annotation_type,
                    "start_session_time_us": command.start_session_time_us,
                    "end_session_time_us": command.end_session_time_us,
                    "body_text": command.body_text,
                    "visibility": command.visibility,
                    "reason": command.reason,
                    "evidence_set_id": command.evidence_set_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        prior = self._request_index.get(command.request_id)
        if prior is not None:
            prior_fingerprint, annotation_id = prior
            if prior_fingerprint != fingerprint:
                raise M4ApplicationError(
                    "M4_ANNOTATION_REQUEST_CONFLICT",
                    command.request_id,
                )
            return self._annotations[annotation_id]

        target: M4DebriefAnnotation | None = None
        if command.target_annotation_id is not None:
            target = self._annotations.get(command.target_annotation_id)
            if target is None:
                raise M4ApplicationError(
                    "M4_ANNOTATION_TARGET_NOT_FOUND",
                    command.target_annotation_id,
                )
            if target.base_release_id != command.base_release_id:
                raise M4ApplicationError(
                    "M4_ANNOTATION_BASE_RELEASE_MISMATCH",
                    command.target_annotation_id,
                )
            if target.status != "ACTIVE":
                raise M4ApplicationError(
                    "M4_ANNOTATION_TARGET_NOT_ACTIVE",
                    command.target_annotation_id,
                )
            self._annotations[target.annotation_id] = replace(
                target,
                status="SUPERSEDED",
            )

        revision_no = 1 if target is None else target.revision_no + 1
        annotation_id = str(
            uuid5(
                M4_ANNOTATION_NAMESPACE,
                f"{command.request_id}|{fingerprint}",
            )
        )
        created_at = _utc(self._clock(), field="created_at")
        annotation = M4DebriefAnnotation(
            annotation_id=annotation_id,
            base_release_id=command.base_release_id,
            session_id=command.session_id,
            episode_id=command.episode_id,
            stage_id=command.stage_id,
            author_id=command.author_id,
            annotation_type=command.annotation_type,
            start_session_time_us=command.start_session_time_us,
            end_session_time_us=command.end_session_time_us,
            body_text=command.body_text,
            visibility=command.visibility,
            status="DELETED" if command.operation == "DELETE" else "ACTIVE",
            revision_no=revision_no,
            supersedes_annotation_id=(
                None if target is None else target.annotation_id
            ),
            evidence_set_id=command.evidence_set_id,
            reason=command.reason,
            audit_id=self._next_audit_id,
            request_id=command.request_id,
            created_at=created_at,
        )
        self._next_audit_id += 1
        self._annotations[annotation.annotation_id] = annotation
        self._annotation_order.append(annotation.annotation_id)
        self._request_index[command.request_id] = (
            fingerprint,
            annotation.annotation_id,
        )
        return annotation

    def annotations_for(
        self,
        query: M4DebriefQuery,
    ) -> tuple[M4DebriefAnnotation, ...]:
        candidates = tuple(
            self._annotations[annotation_id]
            for annotation_id in self._annotation_order
            if self._annotations[annotation_id].base_release_id
            == query.base_release_id
        )
        if query.annotation_view == "NONE":
            return ()
        if query.annotation_view == "AS_OF_UTC":
            assert query.annotation_as_of_utc is not None
            return tuple(
                item
                for item in candidates
                if item.created_at <= query.annotation_as_of_utc
            )
        selected = set(query.annotation_ids)
        result = tuple(
            item
            for item in candidates
            if item.annotation_id in selected
        )
        if {item.annotation_id for item in result} != selected:
            raise M4ApplicationError(
                "M4_ANNOTATION_REVISION_SET_INCOMPLETE",
                repr(query.annotation_ids),
            )
        return result


def _validate_annotation_command(command: M4AnnotationCommand) -> None:
    if not command.request_id.strip():
        raise M4ApplicationError(
            "M4_ANNOTATION_REQUEST_ID_REQUIRED",
            "request_id",
        )
    if command.operation not in M4_ANNOTATION_OPERATIONS:
        raise M4ApplicationError(
            "M4_ANNOTATION_OPERATION_INVALID",
            command.operation,
        )
    _uuid(command.base_release_id, field="base_release_id")
    _uuid(command.session_id, field="session_id")
    _uuid(command.author_id, field="author_id")
    if command.episode_id is not None:
        _uuid(command.episode_id, field="episode_id")
    if command.stage_id is not None:
        _uuid(command.stage_id, field="stage_id")
    if command.evidence_set_id is not None:
        _uuid(command.evidence_set_id, field="evidence_set_id")
    if command.annotation_type not in M4_ANNOTATION_TYPES:
        raise M4ApplicationError(
            "FAIL_CLOSED_ASSESSMENT_NOT_ADMITTED",
            command.annotation_type,
        )
    if not command.body_text:
        raise M4ApplicationError(
            "M4_ANNOTATION_BODY_REQUIRED",
            "body_text",
        )
    if not command.visibility:
        raise M4ApplicationError(
            "M4_ANNOTATION_VISIBILITY_REQUIRED",
            "visibility",
        )
    if not command.reason:
        raise M4ApplicationError(
            "FAIL_CLOSED_AUDIT_REASON_REQUIRED",
            "reason",
        )
    if command.operation == "CREATE":
        if command.target_annotation_id is not None:
            raise M4ApplicationError(
                "M4_ANNOTATION_CREATE_TARGET_FORBIDDEN",
                command.target_annotation_id,
            )
    else:
        if command.target_annotation_id is None:
            raise M4ApplicationError(
                "M4_ANNOTATION_TARGET_REQUIRED",
                command.operation,
            )
        _uuid(
            command.target_annotation_id,
            field="target_annotation_id",
        )


def _validate_debrief_query(query: M4DebriefQuery) -> None:
    _uuid(query.base_release_id, field="base_release_id")
    if query.view_mode not in M4_DEBRIEF_VIEW_MODES:
        raise M4ApplicationError(
            "M4_DEBRIEF_VIEW_MODE_INVALID",
            query.view_mode,
        )
    if query.view_mode == "ORIGINAL_AS_KNOWN":
        if query.retrospective_release_id is not None:
            raise M4ApplicationError(
                "M4_DEBRIEF_RETROSPECTIVE_FORBIDDEN",
                query.retrospective_release_id,
            )
    else:
        if query.retrospective_release_id is None:
            raise M4ApplicationError(
                "FAIL_CLOSED_RETROSPECTIVE_RELEASE_REQUIRED",
                "retrospective_release_id",
            )
        _uuid(
            query.retrospective_release_id,
            field="retrospective_release_id",
        )

    if query.annotation_view not in M4_ANNOTATION_VIEWS:
        raise M4ApplicationError(
            "M4_ANNOTATION_VIEW_INVALID",
            query.annotation_view,
        )
    if query.annotation_view == "NONE":
        if query.annotation_as_of_utc is not None or query.annotation_ids:
            raise M4ApplicationError(
                "M4_ANNOTATION_VIEW_ARGUMENT_FORBIDDEN",
                query.annotation_view,
            )
    elif query.annotation_view == "AS_OF_UTC":
        if query.annotation_as_of_utc is None:
            raise M4ApplicationError(
                "M4_ANNOTATION_AS_OF_REQUIRED",
                "annotation_as_of_utc",
            )
        _utc(
            query.annotation_as_of_utc,
            field="annotation_as_of_utc",
        )
        if query.annotation_ids:
            raise M4ApplicationError(
                "M4_ANNOTATION_VIEW_ARGUMENT_FORBIDDEN",
                "annotation_ids",
            )
    elif not query.annotation_ids:
        raise M4ApplicationError(
            "M4_ANNOTATION_REVISION_SET_REQUIRED",
            "annotation_ids",
        )
    for annotation_id in query.annotation_ids:
        _uuid(annotation_id, field="annotation_ids")


class M4WorkspaceService:
    """Application-only M4 projections; transport and GUI consume these DTOs."""

    def __init__(
        self,
        *,
        longitudinal: M4LongitudinalPublicationService,
        debrief: M4DebriefRepository,
    ) -> None:
        self._longitudinal = longitudinal
        self._debrief = debrief

    def _release(
        self,
        release_id: str,
    ) -> M4PublishedLongitudinalRelease:
        try:
            return self._longitudinal.historical_release(release_id)
        except M4LongitudinalError as exc:
            raise M4ApplicationError(exc.code, exc.detail) from exc

    def trend(self, query: M4TrendQuery) -> dict[str, object]:
        _uuid(query.release_id, field="release_id")
        published = self._release(query.release_id)
        series = published.release.trend_series
        filters = (
            ("trend_id", query.trend_id, series.trend_id),
            ("subject_type", query.subject_type, series.subject_type),
            ("subject_id", query.subject_id, series.subject_id),
            ("metric_code", query.metric_code, series.metric_code),
            (
                "comparison_key_hash",
                query.comparison_key_hash,
                series.comparison_key_hash,
            ),
        )
        for field, requested, actual in filters:
            if requested is not None and requested != actual:
                raise M4ApplicationError(
                    "M4_TREND_QUERY_NO_MATCH",
                    f"{field}={requested!r}",
                )
        return {
            "query": query.projection(),
            "release": _release_dto(published),
            "scope": _scope_dto(published),
            "series": _series_dto(published),
            "points": _points_dto(published),
        }

    def annotation(
        self,
        command: M4AnnotationCommand,
    ) -> dict[str, object]:
        self._release(command.base_release_id)
        return self._debrief.apply_annotation(command).projection()

    def debrief(self, query: M4DebriefQuery) -> dict[str, object]:
        _validate_debrief_query(query)
        base = self._release(query.base_release_id)
        releases = [query.base_release_id]
        if query.view_mode == "RETROSPECTIVE":
            assert query.retrospective_release_id is not None
            retrospective = self._release(query.retrospective_release_id)
            if retrospective.release.scope_key != base.release.scope_key:
                raise M4ApplicationError(
                    "M4_DEBRIEF_RETROSPECTIVE_SCOPE_MISMATCH",
                    query.retrospective_release_id,
                )
            releases.append(query.retrospective_release_id)

        timeline: list[dict[str, object]] = []
        for release_id in releases:
            timeline.extend(
                item.projection(
                    base_release_id=query.base_release_id,
                    knowledge_time_mode=query.view_mode,
                )
                for item in self._debrief.timeline(release_id)
            )
        annotations = [
            item.projection()
            for item in self._debrief.annotations_for(query)
        ]
        return {
            "query": query.projection(),
            "base_release": _release_dto(base),
            "timeline": timeline,
            "annotations": annotations,
        }
