"""PRCB durable M4 longitudinal/debrief adapters over canonical DB 1.9."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid5

from tpaa_application.m4_workspace import (
    M4_ANNOTATION_NAMESPACE,
    M4AnnotationCommand,
    M4ApplicationError,
    M4DebriefAnnotation,
    M4DebriefQuery,
    M4DebriefTimelineItem,
    validate_m4_annotation_command,
)
from tpaa_longitudinal import (
    M4LongitudinalError,
    M4LongitudinalReleaseRepository,
    M4LongitudinalReleaseSnapshot,
    M4LongitudinalScope,
    M4PerformanceTrendPoint,
    M4PerformanceTrendSeries,
    M4PublishedLongitudinalRelease,
    M4PublishResult,
    build_m4_longitudinal_release,
    load_m4_longitudinal_authority,
)
from tpaa_storage.audit_ledger import AuditLogRow, AuditLogWrite, PersistentAuditLedger

from .durable_repositories import RuntimeUnitOfWorkFactory


def _json(value: object, field: str) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise M4LongitudinalError("M4_DURABLE_JSON_INVALID", field) from exc
    return value


def _object(value: object, field: str) -> dict[str, object]:
    decoded = _json(value, field)
    if not isinstance(decoded, dict):
        raise M4LongitudinalError("M4_DURABLE_JSON_OBJECT_REQUIRED", field)
    return {str(key): item for key, item in decoded.items()}


def _canonical_json_text(value: object, field: str) -> str:
    decoded = _json(value, field)
    try:
        return json.dumps(
            decoded,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise M4LongitudinalError(
            "M4_DURABLE_JSON_CANONICALIZATION_FAILED",
            field,
        ) from exc


def _array(value: object, field: str) -> tuple[object, ...]:
    decoded = _json(value, field)
    if not isinstance(decoded, (list, tuple)):
        raise M4LongitudinalError("M4_DURABLE_JSON_ARRAY_REQUIRED", field)
    return tuple(decoded)


def _strings(value: object, field: str) -> tuple[str, ...]:
    result: list[str] = []
    for item in _array(value, field):
        if not isinstance(item, str):
            item = str(item)
        if not item:
            raise M4LongitudinalError("M4_DURABLE_TEXT_INVALID", field)
        result.append(item)
    return tuple(result)


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        value = str(value) if value is not None else ""
    if not value:
        raise M4LongitudinalError("M4_DURABLE_TEXT_INVALID", field)
    return value


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool):
        raise M4LongitudinalError("M4_DURABLE_INTEGER_INVALID", field)
    if isinstance(value, int):
        return value
    if isinstance(value, (float, Decimal, str)):
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise M4LongitudinalError("M4_DURABLE_INTEGER_INVALID", field) from exc
        try:
            if float(parsed) != float(value):
                raise M4LongitudinalError("M4_DURABLE_INTEGER_INVALID", field)
        except ValueError as exc:
            raise M4LongitudinalError("M4_DURABLE_INTEGER_INVALID", field) from exc
        return parsed
    raise M4LongitudinalError("M4_DURABLE_INTEGER_INVALID", field)


def _optional_float(value: object, field: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise M4LongitudinalError("M4_DURABLE_FLOAT_INVALID", field)
    return float(value)


def _time(value: object, field: str) -> str:
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is None:
            normalized = normalized.replace(tzinfo=UTC)
        normalized = normalized.astimezone(UTC)
        return normalized.isoformat().replace("+00:00", "Z")
    text = _text(value, field)
    if "T" not in text:
        raise M4LongitudinalError("M4_DURABLE_TIME_INVALID", field)
    if text.endswith("+00:00"):
        return text[:-6] + "Z"
    if not text.endswith("Z"):
        raise M4LongitudinalError("M4_DURABLE_TIME_INVALID", field)
    return text


def _utc_now() -> str:
    return datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")


def _baseline_root(authority_root: Path) -> Path:
    return authority_root.parent if authority_root.name == "canonical" else authority_root


class DurableM4LongitudinalReleaseRepository(M4LongitudinalReleaseRepository):
    """Exact M4 read authority reconstructed from normalized DB 1.9 relations."""

    def __init__(
        self,
        read_uow_factory: RuntimeUnitOfWorkFactory,
        *,
        authority_root: Path,
    ) -> None:
        self._read_uow_factory = read_uow_factory
        self._authority = load_m4_longitudinal_authority(
            _baseline_root(authority_root)
        )

    def publish(
        self,
        release: M4LongitudinalReleaseSnapshot,
        *,
        idempotency_key: str,
        expected_version_token: int,
        published_at_utc: str,
    ) -> M4PublishResult:
        del idempotency_key, expected_version_token, published_at_utc
        raise M4LongitudinalError(
            "M4_PRODUCTION_PUBLICATION_REQUIRES_GOVERNED_WORKER",
            release.release_id,
        )

    def get_release(self, release_id: str) -> M4PublishedLongitudinalRelease:
        with self._read_uow_factory() as uow:
            release = uow.canonical_rows.one(
                "registry.analysis_release",
                where={"release_id": release_id},
                columns=(
                    "release_id",
                    "scope_type",
                    "scope_key",
                    "longitudinal_scope_id",
                    "release_no",
                    "compute_job_id",
                    "catalog_version",
                    "catalog_hash",
                    "context_binding_hash",
                    "status",
                    "parent_release_id",
                    "manifest_hash",
                    "created_at",
                    "published_at",
                ),
            )
            if release is None:
                raise M4LongitudinalError("M4_RELEASE_NOT_FOUND", release_id)
            if (
                str(release["scope_type"]) != "LONGITUDINAL"
                or str(release["status"]) != "PUBLISHED"
                or release["longitudinal_scope_id"] is None
                or release["published_at"] is None
            ):
                raise M4LongitudinalError(
                    "M4_DURABLE_RELEASE_NOT_PUBLISHED",
                    release_id,
                )

            scope_id = str(release["longitudinal_scope_id"])
            scope = uow.canonical_rows.one(
                "registry.longitudinal_scope",
                where={"longitudinal_scope_id": scope_id},
                columns=(
                    "longitudinal_scope_id",
                    "longitudinal_scope_key",
                    "subject_type",
                    "subject_id",
                    "metric_semantic_id",
                    "metric_semantic_version",
                    "comparison_key_hash",
                    "session_order_scope_id",
                    "trend_profile_version",
                    "descriptor_json",
                    "descriptor_hash",
                ),
            )
            if scope is None:
                raise M4LongitudinalError(
                    "M4_DURABLE_SCOPE_NOT_FOUND",
                    scope_id,
                )
            scope_key = _text(scope["longitudinal_scope_key"], "scope_key")
            if scope_key != str(release["scope_key"]):
                raise M4LongitudinalError(
                    "M4_DURABLE_SCOPE_RELEASE_MISMATCH",
                    release_id,
                )
            session_order_scope_id = _optional_text(
                scope["session_order_scope_id"]
            )
            if session_order_scope_id is None:
                raise M4LongitudinalError(
                    "M4_DURABLE_SESSION_ORDER_SCOPE_REQUIRED",
                    scope_id,
                )
            descriptor_json = _canonical_json_text(
                scope["descriptor_json"],
                "scope.descriptor_json",
            )
            descriptor_hash = hashlib.sha256(
                descriptor_json.encode("utf-8")
            ).hexdigest()
            persisted_descriptor_hash = _text(
                scope["descriptor_hash"],
                "scope.descriptor_hash",
            )
            trend_profile_version = _text(
                scope["trend_profile_version"],
                "scope.trend_profile_version",
            )
            if (
                descriptor_hash != persisted_descriptor_hash
                or descriptor_hash != scope_key
                or trend_profile_version
                != self._authority.trend_profile_version
            ):
                raise M4LongitudinalError(
                    "M4_DURABLE_SCOPE_HASH_MISMATCH",
                    scope_id,
                )
            longitudinal_scope = M4LongitudinalScope(
                longitudinal_scope_key=scope_key,
                subject_type=_text(
                    scope["subject_type"],
                    "scope.subject_type",
                ),
                subject_id=_text(scope["subject_id"], "scope.subject_id"),
                metric_semantic_id=_text(
                    scope["metric_semantic_id"],
                    "scope.metric_semantic_id",
                ),
                metric_semantic_version=_integer(
                    scope["metric_semantic_version"],
                    "scope.metric_semantic_version",
                ),
                comparison_key_hash=_text(
                    scope["comparison_key_hash"],
                    "scope.comparison_key_hash",
                ),
                session_order_scope_id=session_order_scope_id,
                trend_profile_version=trend_profile_version,
                descriptor_json=descriptor_json,
                descriptor_hash=descriptor_hash,
            )

            trend_rows = uow.canonical_rows.many(
                "metric.performance_trend_series",
                where={"release_id": release_id},
                columns=(
                    "trend_id",
                    "release_id",
                    "longitudinal_scope_id",
                    "subject_type",
                    "subject_id",
                    "metric_definition_id",
                    "metric_semantic_id",
                    "metric_semantic_version",
                    "comparison_key_hash",
                    "trend_semantics",
                    "x_axis_semantics",
                    "session_order_scope_id",
                    "as_of_session_order",
                    "as_of_occurred_at_utc",
                    "sample_count_total",
                    "sample_count_valid",
                    "current_value",
                    "ewma_value",
                    "slope",
                    "slope_unit",
                    "stability_mad",
                    "trend_status",
                    "status",
                    "reason_codes",
                    "trend_profile_version",
                    "input_hash",
                    "created_at",
                    "supersedes_trend_id",
                ),
                order_by=("trend_id",),
            )
            if len(trend_rows) != 1:
                raise M4LongitudinalError(
                    "M4_DURABLE_TREND_CARDINALITY",
                    f"{release_id}:{len(trend_rows)}",
                )
            trend_row = trend_rows[0]
            trend_id = str(trend_row["trend_id"])
            definition_id = str(trend_row["metric_definition_id"])
            definition = uow.canonical_rows.one(
                "metric.metric_definition",
                where={"metric_definition_id": definition_id},
                columns=("metric_code",),
            )
            if definition is None:
                raise M4LongitudinalError(
                    "M4_DURABLE_METRIC_DEFINITION_NOT_FOUND",
                    definition_id,
                )

            point_rows = uow.canonical_rows.many(
                "metric.performance_trend_point",
                where={"trend_id": trend_id},
                columns=(
                    "trend_id",
                    "point_order",
                    "sample_id",
                    "subject_type",
                    "subject_id",
                    "session_order",
                    "occurred_at_utc",
                    "value",
                    "sample_status",
                    "configuration_key",
                    "lifecycle_marker_refs",
                ),
                order_by=("point_order",),
            )
            points: list[M4PerformanceTrendPoint] = []
            input_membership: list[tuple[str, str]] = []
            for point_row in point_rows:
                sample_id = str(point_row["sample_id"])
                sample = uow.canonical_rows.one(
                    "metric.longitudinal_sample",
                    where={"sample_id": sample_id},
                    columns=(
                        "release_id",
                        "session_id",
                        "subject_type",
                        "subject_id",
                        "session_order",
                        "configuration_key",
                    ),
                )
                if sample is None:
                    raise M4LongitudinalError(
                        "M4_DURABLE_SAMPLE_NOT_FOUND",
                        sample_id,
                    )
                if (
                    str(sample["subject_type"]) != str(point_row["subject_type"])
                    or str(sample["subject_id"]) != str(point_row["subject_id"])
                    or _integer(sample["session_order"], "sample.session_order")
                    != _integer(point_row["session_order"], "point.session_order")
                    or str(sample["configuration_key"])
                    != str(point_row["configuration_key"])
                ):
                    raise M4LongitudinalError(
                        "M4_DURABLE_POINT_SAMPLE_MISMATCH",
                        sample_id,
                    )
                source_release_id = str(sample["release_id"])
                input_membership.append((source_release_id, sample_id))
                marker_refs_raw = _array(
                    point_row["lifecycle_marker_refs"],
                    "point.lifecycle_marker_refs",
                )
                marker_refs: list[dict[str, object]] = []
                for marker in marker_refs_raw:
                    if not isinstance(marker, dict):
                        raise M4LongitudinalError(
                            "M4_DURABLE_MARKER_INVALID",
                            sample_id,
                        )
                    marker_refs.append(
                        {str(key): value for key, value in marker.items()}
                    )
                points.append(
                    M4PerformanceTrendPoint(
                        trend_id=trend_id,
                        point_order=_integer(
                            point_row["point_order"],
                            "point.point_order",
                        ),
                        sample_id=sample_id,
                        source_release_id=source_release_id,
                        session_id=str(sample["session_id"]),
                        subject_type=str(point_row["subject_type"]),
                        subject_id=str(point_row["subject_id"]),
                        session_order=_integer(
                            point_row["session_order"],
                            "point.session_order",
                        ),
                        occurred_at_utc=(
                            None
                            if point_row["occurred_at_utc"] is None
                            else _time(
                                point_row["occurred_at_utc"],
                                "point.occurred_at_utc",
                            )
                        ),
                        value=_optional_float(point_row["value"], "point.value"),
                        sample_status=str(point_row["sample_status"]),
                        configuration_key=str(point_row["configuration_key"]),
                        lifecycle_marker_refs=tuple(marker_refs),
                    )
                )

            release_inputs = uow.canonical_rows.many(
                "registry.longitudinal_release_input",
                where={"longitudinal_release_id": release_id},
                columns=(
                    "input_session_release_id",
                    "input_sample_id",
                ),
                order_by=("input_sample_id",),
            )
            persisted_membership = tuple(
                (
                    str(item["input_session_release_id"]),
                    str(item["input_sample_id"]),
                )
                for item in release_inputs
            )
            if sorted(persisted_membership) != sorted(input_membership):
                raise M4LongitudinalError(
                    "M4_DURABLE_INPUT_MEMBERSHIP_MISMATCH",
                    release_id,
                )

            bridge_rows = uow.canonical_rows.many(
                "metric.trend_input_bridge",
                where={"trend_id": trend_id},
                columns=("trend_bridge_id",),
                order_by=("trend_bridge_id",),
            )
            bridge_hashes: list[str] = []
            for bridge_row in bridge_rows:
                bridge_id = str(bridge_row["trend_bridge_id"])
                bridge = uow.canonical_rows.one(
                    "metric.trend_bridge",
                    where={"trend_bridge_id": bridge_id},
                    columns=("bridge_hash",),
                )
                if bridge is None:
                    raise M4LongitudinalError(
                        "M4_DURABLE_BRIDGE_NOT_FOUND",
                        bridge_id,
                    )
                bridge_hashes.append(str(bridge["bridge_hash"]))

            if (
                str(trend_row["trend_profile_version"])
                != self._authority.trend_profile_version
            ):
                raise M4LongitudinalError(
                    "M4_DURABLE_TREND_PROFILE_VERSION_MISMATCH",
                    trend_id,
                )
            trend = M4PerformanceTrendSeries(
                trend_id=trend_id,
                release_id=release_id,
                longitudinal_scope_id=scope_id,
                longitudinal_scope_key=scope_key,
                subject_type=str(trend_row["subject_type"]),
                subject_id=str(trend_row["subject_id"]),
                metric_definition_id=definition_id,
                metric_code=str(definition["metric_code"]),
                metric_semantic_id=str(trend_row["metric_semantic_id"]),
                metric_semantic_version=_integer(
                    trend_row["metric_semantic_version"],
                    "trend.metric_semantic_version",
                ),
                comparison_key_hash=str(trend_row["comparison_key_hash"]),
                trend_semantics=str(trend_row["trend_semantics"]),
                x_axis_semantics=str(trend_row["x_axis_semantics"]),
                session_order_scope_id=_text(
                    trend_row["session_order_scope_id"],
                    "trend.session_order_scope_id",
                ),
                as_of_session_order=_integer(
                    trend_row["as_of_session_order"],
                    "trend.as_of_session_order",
                ),
                as_of_occurred_at_utc=(
                    None
                    if trend_row["as_of_occurred_at_utc"] is None
                    else _time(
                        trend_row["as_of_occurred_at_utc"],
                        "trend.as_of_occurred_at_utc",
                    )
                ),
                sample_count_total=_integer(
                    trend_row["sample_count_total"],
                    "trend.sample_count_total",
                ),
                sample_count_valid=_integer(
                    trend_row["sample_count_valid"],
                    "trend.sample_count_valid",
                ),
                current_value=_optional_float(
                    trend_row["current_value"],
                    "trend.current_value",
                ),
                ewma_value=_optional_float(
                    trend_row["ewma_value"],
                    "trend.ewma_value",
                ),
                slope=_optional_float(trend_row["slope"], "trend.slope"),
                slope_unit=_optional_text(trend_row["slope_unit"]),
                stability_mad=_optional_float(
                    trend_row["stability_mad"],
                    "trend.stability_mad",
                ),
                trend_status=str(trend_row["trend_status"]),
                status=str(trend_row["status"]),
                reason_codes=_strings(
                    trend_row["reason_codes"],
                    "trend.reason_codes",
                ),
                trend_profile_id=self._authority.trend_profile_id,
                trend_profile_version=self._authority.trend_profile_version,
                trend_profile_hash=self._authority.trend_profile_hash,
                input_hash=str(trend_row["input_hash"]),
                bridge_hashes=tuple(bridge_hashes),
                input_membership=tuple(input_membership),
                created_at_utc=_time(
                    trend_row["created_at"],
                    "trend.created_at",
                ),
                supersedes_trend_id=_optional_text(
                    trend_row["supersedes_trend_id"]
                ),
                points=tuple(points),
            )

            job = uow.canonical_rows.one(
                "registry.compute_job",
                where={"job_id": release["compute_job_id"]},
                columns=("input_hash",),
            )
            if job is None:
                raise M4LongitudinalError(
                    "M4_DURABLE_COMPUTE_JOB_NOT_FOUND",
                    str(release["compute_job_id"]),
                )
            candidate = build_m4_longitudinal_release(
                release_id=release_id,
                request_hash=str(job["input_hash"]),
                release_no=_integer(release["release_no"], "release.release_no"),
                parent_release_id=_optional_text(release["parent_release_id"]),
                compute_job_id=str(release["compute_job_id"]),
                catalog_version=str(release["catalog_version"]),
                catalog_hash=str(release["catalog_hash"]),
                context_binding_hash=str(release["context_binding_hash"]),
                longitudinal_scope_id=scope_id,
                scope=longitudinal_scope,
                trend_series=trend,
                created_at_utc=_time(release["created_at"], "release.created_at"),
            )
            if candidate.manifest_hash != str(release["manifest_hash"]):
                raise M4LongitudinalError(
                    "M4_DURABLE_RELEASE_MANIFEST_MISMATCH",
                    release_id,
                )
            result = M4PublishedLongitudinalRelease(
                release=candidate,
                version_token=candidate.release_no,
                published_at_utc=_time(
                    release["published_at"],
                    "release.published_at",
                ),
            )
            uow.commit()
            return result

    def current(
        self,
        longitudinal_scope_key: str,
    ) -> M4PublishedLongitudinalRelease | None:
        with self._read_uow_factory() as uow:
            pointer = uow.canonical_rows.one(
                "registry.release_scope_pointer",
                where={
                    "scope_type": "LONGITUDINAL",
                    "scope_key": longitudinal_scope_key,
                },
                columns=("current_release_id",),
            )
            uow.commit()
        if pointer is None:
            return None
        return self.get_release(str(pointer["current_release_id"]))

    def version_token(self, longitudinal_scope_key: str) -> int:
        with self._read_uow_factory() as uow:
            pointer = uow.canonical_rows.one(
                "registry.release_scope_pointer",
                where={
                    "scope_type": "LONGITUDINAL",
                    "scope_key": longitudinal_scope_key,
                },
                columns=("version_token",),
            )
            uow.commit()
        return (
            0
            if pointer is None
            else _integer(pointer["version_token"], "release_pointer.version_token")
        )


class DurableM4DebriefRepository:
    """Debrief state in canonical annotation/audit tables; timeline is derived."""

    def __init__(
        self,
        read_uow_factory: RuntimeUnitOfWorkFactory,
        write_uow_factory: RuntimeUnitOfWorkFactory,
        *,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self._read_uow_factory = read_uow_factory
        self._write_uow_factory = write_uow_factory
        self._clock = clock

    @staticmethod
    def _fingerprint(command: M4AnnotationCommand) -> str:
        return hashlib.sha256(
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
                ensure_ascii=True,
            ).encode("ascii")
        ).hexdigest()

    @staticmethod
    def _audit_for(
        audits: tuple[AuditLogRow, ...],
        annotation_id: str,
    ) -> AuditLogRow:
        matches = tuple(
            item
            for item in audits
            if item.object_type == "M4_DEBRIEF_ANNOTATION"
            and item.object_id == annotation_id
        )
        if len(matches) != 1:
            raise M4ApplicationError(
                "M4_DURABLE_ANNOTATION_AUDIT_CARDINALITY",
                f"{annotation_id}:{len(matches)}",
            )
        return matches[0]

    @classmethod
    def _annotation(
        cls,
        row: dict[str, object],
        audits: tuple[AuditLogRow, ...],
    ) -> M4DebriefAnnotation:
        annotation_id = str(row["annotation_id"])
        audit = cls._audit_for(audits, annotation_id)
        return M4DebriefAnnotation(
            annotation_id=annotation_id,
            base_release_id=str(row["base_release_id"]),
            session_id=str(row["session_id"]),
            episode_id=_optional_text(row["episode_id"]),
            stage_id=_optional_text(row["stage_id"]),
            author_id=str(row["author_id"]),
            annotation_type=str(row["annotation_type"]),
            start_session_time_us=(
                None
                if row["start_session_time_us"] is None
                else _integer(
                    row["start_session_time_us"],
                    "annotation.start_session_time_us",
                )
            ),
            end_session_time_us=(
                None
                if row["end_session_time_us"] is None
                else _integer(
                    row["end_session_time_us"],
                    "annotation.end_session_time_us",
                )
            ),
            body_text=str(row["body_text"]),
            visibility=str(row["visibility"]),
            status=str(row["status"]),
            revision_no=_integer(row["revision_no"], "annotation.revision_no"),
            supersedes_annotation_id=_optional_text(
                row["supersedes_annotation_id"]
            ),
            evidence_set_id=_optional_text(row["evidence_set_id"]),
            reason=audit.reason or "",
            audit_id=audit.audit_id,
            request_id=audit.request_id or "",
            created_at=_time(row["created_at"], "annotation.created_at"),
        )

    def register_timeline(
        self,
        release_id: str,
        items: Sequence[M4DebriefTimelineItem],
    ) -> None:
        if tuple(items) != self.timeline(release_id):
            raise M4ApplicationError(
                "M4_DURABLE_TIMELINE_IS_DERIVED",
                release_id,
            )

    def timeline(self, release_id: str) -> tuple[M4DebriefTimelineItem, ...]:
        with self._read_uow_factory() as uow:
            release = uow.canonical_rows.one(
                "registry.analysis_release",
                where={"release_id": release_id},
                columns=("scope_type", "status"),
            )
            if (
                release is None
                or str(release["scope_type"]) != "LONGITUDINAL"
                or str(release["status"]) != "PUBLISHED"
            ):
                raise M4ApplicationError(
                    "M4_DURABLE_RELEASE_NOT_PUBLISHED",
                    release_id,
                )
            inputs = uow.canonical_rows.many(
                "registry.longitudinal_release_input",
                where={"longitudinal_release_id": release_id},
                columns=("input_session_release_id", "input_sample_id"),
                order_by=("input_sample_id",),
            )
            items: list[M4DebriefTimelineItem] = []
            for item in inputs:
                sample_id = str(item["input_sample_id"])
                sample = uow.canonical_rows.one(
                    "metric.longitudinal_sample",
                    where={"sample_id": sample_id},
                    columns=("session_id", "release_id"),
                )
                if sample is None:
                    raise M4ApplicationError(
                        "M4_DURABLE_SAMPLE_NOT_FOUND",
                        sample_id,
                    )
                source_release_id = str(item["input_session_release_id"])
                if str(sample["release_id"]) != source_release_id:
                    raise M4ApplicationError(
                        "M4_DURABLE_TIMELINE_MEMBERSHIP_MISMATCH",
                        sample_id,
                    )
                session_id = str(sample["session_id"])
                session = uow.canonical_rows.one(
                    "registry.training_session",
                    where={"session_id": session_id},
                    columns=(
                        "start_session_time_us",
                        "end_session_time_us",
                    ),
                )
                if session is None:
                    raise M4ApplicationError(
                        "M4_DURABLE_SESSION_NOT_FOUND",
                        session_id,
                    )
                items.append(
                    M4DebriefTimelineItem(
                        item_id=sample_id,
                        item_type="METRIC",
                        session_id=session_id,
                        episode_id=None,
                        stage_id=None,
                        start_session_time_us=_integer(
                            session["start_session_time_us"],
                            "session.start_session_time_us",
                        ),
                        end_session_time_us=_integer(
                            session["end_session_time_us"],
                            "session.end_session_time_us",
                        ),
                        evidence_set_id=None,
                        source_release_id=source_release_id,
                    )
                )
            uow.commit()
            return tuple(items)

    def apply_annotation(
        self,
        command: M4AnnotationCommand,
    ) -> M4DebriefAnnotation:
        validate_m4_annotation_command(command)
        fingerprint = self._fingerprint(command)
        with self._write_uow_factory() as uow:
            audit = PersistentAuditLedger(uow.canonical_rows)
            existing_request = tuple(
                item
                for item in audit.rows()
                if item.request_id == command.request_id
                and item.object_type == "M4_DEBRIEF_ANNOTATION"
            )
            if existing_request:
                if len(existing_request) != 1:
                    raise M4ApplicationError(
                        "M4_ANNOTATION_REQUEST_CARDINALITY",
                        command.request_id,
                    )
                prior = existing_request[0]
                if prior.details.get("fingerprint") != fingerprint:
                    raise M4ApplicationError(
                        "M4_ANNOTATION_REQUEST_CONFLICT",
                        command.request_id,
                    )
                row = uow.canonical_rows.one(
                    "debrief.annotation",
                    where={"annotation_id": prior.object_id},
                    columns=(
                        "annotation_id",
                        "base_release_id",
                        "session_id",
                        "episode_id",
                        "stage_id",
                        "author_id",
                        "annotation_type",
                        "start_session_time_us",
                        "end_session_time_us",
                        "body_text",
                        "visibility",
                        "status",
                        "revision_no",
                        "supersedes_annotation_id",
                        "evidence_set_id",
                        "created_at",
                    ),
                )
                if row is None:
                    raise M4ApplicationError(
                        "M4_ANNOTATION_TARGET_NOT_FOUND",
                        prior.object_id,
                    )
                value = self._annotation(row, audit.rows())
                uow.commit()
                return value

            if not command.request_id.strip() or not command.reason.strip():
                raise M4ApplicationError(
                    "FAIL_CLOSED_AUDIT_REASON_REQUIRED",
                    command.request_id,
                )
            if command.operation not in {"CREATE", "SUPERSEDE", "DELETE"}:
                raise M4ApplicationError(
                    "M4_ANNOTATION_OPERATION_INVALID",
                    command.operation,
                )
            target: dict[str, object] | None = None
            if command.target_annotation_id is not None:
                target = uow.canonical_rows.one(
                    "debrief.annotation",
                    where={"annotation_id": command.target_annotation_id},
                    columns=(
                        "annotation_id",
                        "base_release_id",
                        "revision_no",
                        "status",
                    ),
                )
                if target is None:
                    raise M4ApplicationError(
                        "M4_ANNOTATION_TARGET_NOT_FOUND",
                        command.target_annotation_id,
                    )
                if (
                    str(target["base_release_id"]) != command.base_release_id
                    or str(target["status"]) != "ACTIVE"
                ):
                    raise M4ApplicationError(
                        "M4_ANNOTATION_TARGET_NOT_ACTIVE",
                        command.target_annotation_id,
                    )
            elif command.operation != "CREATE":
                raise M4ApplicationError(
                    "M4_ANNOTATION_TARGET_REQUIRED",
                    command.operation,
                )
            if command.operation == "CREATE" and command.target_annotation_id is not None:
                raise M4ApplicationError(
                    "M4_ANNOTATION_CREATE_TARGET_FORBIDDEN",
                    command.target_annotation_id,
                )

            revision_no = (
                1
                if target is None
                else _integer(target["revision_no"], "annotation.revision_no") + 1
            )
            annotation_id = str(
                uuid5(
                    M4_ANNOTATION_NAMESPACE,
                    f"{command.request_id}|{fingerprint}",
                )
            )
            if target is not None:
                uow.canonical_rows.update_exact(
                    "debrief.annotation",
                    where={"annotation_id": str(target["annotation_id"])},
                    values={"status": "SUPERSEDED"},
                )
            created_at = _time(self._clock(), "annotation.created_at")
            uow.canonical_rows.insert(
                "debrief.annotation",
                {
                    "annotation_id": annotation_id,
                    "base_release_id": command.base_release_id,
                    "session_id": command.session_id,
                    "episode_id": command.episode_id,
                    "stage_id": command.stage_id,
                    "author_id": command.author_id,
                    "annotation_type": command.annotation_type,
                    "start_session_time_us": command.start_session_time_us,
                    "end_session_time_us": command.end_session_time_us,
                    "body_text": command.body_text,
                    "visibility": command.visibility,
                    "status": (
                        "DELETED"
                        if command.operation == "DELETE"
                        else "ACTIVE"
                    ),
                    "revision_no": revision_no,
                    "supersedes_annotation_id": (
                        None if target is None else str(target["annotation_id"])
                    ),
                    "evidence_set_id": command.evidence_set_id,
                    "created_at": created_at,
                },
            )
            audit.append(
                AuditLogWrite(
                    actor_id=command.author_id,
                    principal_key=f"M4:{command.author_id}",
                    action=f"M4_ANNOTATION_{command.operation}",
                    object_type="M4_DEBRIEF_ANNOTATION",
                    object_id=annotation_id,
                    outcome="SUCCEEDED",
                    request_id=command.request_id,
                    reason=command.reason,
                    details={
                        "fingerprint": fingerprint,
                        "base_release_id": command.base_release_id,
                        "operation": command.operation,
                    },
                )
            )
            row = uow.canonical_rows.one(
                "debrief.annotation",
                where={"annotation_id": annotation_id},
                columns=(
                    "annotation_id",
                    "base_release_id",
                    "session_id",
                    "episode_id",
                    "stage_id",
                    "author_id",
                    "annotation_type",
                    "start_session_time_us",
                    "end_session_time_us",
                    "body_text",
                    "visibility",
                    "status",
                    "revision_no",
                    "supersedes_annotation_id",
                    "evidence_set_id",
                    "created_at",
                ),
            )
            if row is None:
                raise M4ApplicationError(
                    "M4_ANNOTATION_TARGET_NOT_FOUND",
                    annotation_id,
                )
            value = self._annotation(row, audit.rows())
            uow.commit()
            return value

    def annotations_for(
        self,
        query: M4DebriefQuery,
    ) -> tuple[M4DebriefAnnotation, ...]:
        if query.annotation_view == "NONE":
            return ()
        with self._read_uow_factory() as uow:
            rows = uow.canonical_rows.many(
                "debrief.annotation",
                where={"base_release_id": query.base_release_id},
                columns=(
                    "annotation_id",
                    "base_release_id",
                    "session_id",
                    "episode_id",
                    "stage_id",
                    "author_id",
                    "annotation_type",
                    "start_session_time_us",
                    "end_session_time_us",
                    "body_text",
                    "visibility",
                    "status",
                    "revision_no",
                    "supersedes_annotation_id",
                    "evidence_set_id",
                    "created_at",
                ),
                order_by=("created_at", "annotation_id"),
            )
            audits = PersistentAuditLedger(uow.canonical_rows).rows()
            values = tuple(self._annotation(row, audits) for row in rows)
            uow.commit()
        if query.annotation_view == "AS_OF_UTC":
            if query.annotation_as_of_utc is None:
                raise M4ApplicationError(
                    "M4_ANNOTATION_AS_OF_REQUIRED",
                    "annotation_as_of_utc",
                )
            return tuple(
                item
                for item in values
                if item.created_at <= query.annotation_as_of_utc
            )
        selected = set(query.annotation_ids)
        result = tuple(item for item in values if item.annotation_id in selected)
        if {item.annotation_id for item in result} != selected:
            raise M4ApplicationError(
                "M4_ANNOTATION_REVISION_SET_INCOMPLETE",
                repr(query.annotation_ids),
            )
        return result
