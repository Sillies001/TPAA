from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest

from tpaa_application import M4AnnotationCommand, M4ApplicationError, M4DebriefQuery
from tpaa_longitudinal import (
    M4LongitudinalScope,
    M4PerformanceTrendPoint,
    M4PerformanceTrendSeries,
    allocate_m4_longitudinal_release_id,
    build_m4_longitudinal_release,
    load_m4_longitudinal_authority,
)
from tpaa_runtime.durable_longitudinal import (
    DurableM4DebriefRepository,
    DurableM4LongitudinalReleaseRepository,
)
from tpaa_storage.canonical_rows import SQLiteCanonicalRowRepository

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY = ROOT / "baseline" / "CB-1.4.0"


def _u(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"urn:tpaa:prcb:m4:{label}"))


class _Rows:
    def __init__(self, tables: dict[str, list[dict[str, object]]]) -> None:
        self._tables = tables

    def one(
        self,
        table: str,
        *,
        where: dict[str, object],
        columns: tuple[str, ...],
    ) -> dict[str, object] | None:
        rows = self.many(table, where=where, columns=columns)
        if not rows:
            return None
        assert len(rows) == 1
        return rows[0]

    def many(
        self,
        table: str,
        *,
        where: dict[str, object],
        columns: tuple[str, ...],
        order_by: tuple[str, ...] = (),
    ) -> tuple[dict[str, object], ...]:
        matches = [
            row
            for row in self._tables.get(table, [])
            if all(row.get(key) == value for key, value in where.items())
        ]
        for key in reversed(order_by):
            matches.sort(key=lambda row: str(row.get(key)))
        return tuple(
            {column: row.get(column) for column in columns}
            for row in matches
        )

    def insert(self, *args, **kwargs) -> None:
        raise AssertionError("read test does not insert")

    def update_exact(self, *args, **kwargs) -> None:
        raise AssertionError("read test does not update")


class _ReadUow:
    def __init__(self, rows: _Rows) -> None:
        self.canonical_rows = rows

    def __enter__(self):
        return self

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def _release_tables() -> tuple[dict[str, list[dict[str, object]]], str, object]:
    authority = load_m4_longitudinal_authority(AUTHORITY)
    subject_id = _u("subject")
    scope_id = _u("scope")
    order_scope = _u("order-scope")
    metric_definition_id = _u("definition")
    comparison_hash = "1" * 64
    descriptor = {
        "schema": "TPAA_M4_LONGITUDINAL_SCOPE_DESCRIPTOR_V1",
        "subject_type": "AIRCRAFT",
        "subject_id": subject_id,
        "metric_semantic_id": "metric.prcb.m4",
        "metric_semantic_version": 1,
        "comparison_key_hash": comparison_hash,
        "session_order_scope_id": order_scope,
        "x_axis_semantics": "SESSION_ORDER",
        "trend_profile_id": authority.trend_profile_id,
        "trend_profile_version": authority.trend_profile_version,
        "trend_profile_hash": authority.trend_profile_hash,
    }
    descriptor_json = json.dumps(
        descriptor,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    scope_key = hashlib.sha256(descriptor_json.encode("utf-8")).hexdigest()
    scope = M4LongitudinalScope(
        longitudinal_scope_key=scope_key,
        subject_type="AIRCRAFT",
        subject_id=subject_id,
        metric_semantic_id="metric.prcb.m4",
        metric_semantic_version=1,
        comparison_key_hash=comparison_hash,
        session_order_scope_id=order_scope,
        trend_profile_version=authority.trend_profile_version,
        descriptor_json=descriptor_json,
        descriptor_hash=scope_key,
    )
    request_hash = "2" * 64
    release_id = allocate_m4_longitudinal_release_id(
        longitudinal_scope_key=scope_key,
        request_hash=request_hash,
    )
    points: list[M4PerformanceTrendPoint] = []
    membership: list[tuple[str, str]] = []
    samples: list[dict[str, object]] = []
    release_inputs: list[dict[str, object]] = []
    point_rows: list[dict[str, object]] = []
    for index in range(1, 3):
        sample_id = _u(f"sample-{index}")
        source_release = _u(f"source-release-{index}")
        session_id = _u(f"session-{index}")
        membership.append((source_release, sample_id))
        point = M4PerformanceTrendPoint(
            trend_id=_u("trend"),
            point_order=index,
            sample_id=sample_id,
            source_release_id=source_release,
            session_id=session_id,
            subject_type="AIRCRAFT",
            subject_id=subject_id,
            session_order=index,
            occurred_at_utc=f"2026-10-0{index}T00:00:00Z",
            value=100.0 + index,
            sample_status="VALID",
            configuration_key="CFG-A",
            lifecycle_marker_refs=(),
        )
        points.append(point)
        samples.append(
            {
                "sample_id": sample_id,
                "release_id": source_release,
                "session_id": session_id,
                "subject_type": "AIRCRAFT",
                "subject_id": subject_id,
                "session_order": index,
                "configuration_key": "CFG-A",
            }
        )
        release_inputs.append(
            {
                "longitudinal_release_id": release_id,
                "input_session_release_id": source_release,
                "input_sample_id": sample_id,
            }
        )
        point_rows.append(
            {
                "trend_id": point.trend_id,
                "point_order": point.point_order,
                "sample_id": point.sample_id,
                "subject_type": point.subject_type,
                "subject_id": point.subject_id,
                "session_order": point.session_order,
                "occurred_at_utc": point.occurred_at_utc,
                "value": point.value,
                "sample_status": point.sample_status,
                "configuration_key": point.configuration_key,
                "lifecycle_marker_refs": [],
            }
        )
    trend = M4PerformanceTrendSeries(
        trend_id=_u("trend"),
        release_id=release_id,
        longitudinal_scope_id=scope_id,
        longitudinal_scope_key=scope_key,
        subject_type="AIRCRAFT",
        subject_id=subject_id,
        metric_definition_id=metric_definition_id,
        metric_code="P1-PRCB-M4",
        metric_semantic_id="metric.prcb.m4",
        metric_semantic_version=1,
        comparison_key_hash=comparison_hash,
        trend_semantics="OBSERVED_PERFORMANCE",
        x_axis_semantics="SESSION_ORDER",
        session_order_scope_id=order_scope,
        as_of_session_order=2,
        as_of_occurred_at_utc="2026-10-02T00:00:00Z",
        sample_count_total=2,
        sample_count_valid=2,
        current_value=102.0,
        ewma_value=101.5,
        slope=1.0,
        slope_unit="1/session",
        stability_mad=0.5,
        trend_status="INCREASING",
        status="VALID",
        reason_codes=(),
        trend_profile_id=authority.trend_profile_id,
        trend_profile_version=authority.trend_profile_version,
        trend_profile_hash=authority.trend_profile_hash,
        input_hash="3" * 64,
        bridge_hashes=(),
        input_membership=tuple(membership),
        created_at_utc="2026-10-02T00:01:00Z",
        supersedes_trend_id=None,
        points=tuple(points),
    )
    release = build_m4_longitudinal_release(
        release_id=release_id,
        request_hash=request_hash,
        release_no=1,
        parent_release_id=None,
        compute_job_id=_u("job"),
        catalog_version="P1-METRIC-CATALOG-1.0",
        catalog_hash="4" * 64,
        context_binding_hash="5" * 64,
        longitudinal_scope_id=scope_id,
        scope=scope,
        trend_series=trend,
        created_at_utc="2026-10-02T00:02:00Z",
    )
    tables = {
        "registry.analysis_release": [
            {
                "release_id": release.release_id,
                "scope_type": "LONGITUDINAL",
                "scope_key": scope_key,
                "longitudinal_scope_id": scope_id,
                "release_no": 1,
                "compute_job_id": release.compute_job_id,
                "catalog_version": release.catalog_version,
                "catalog_hash": release.catalog_hash,
                "context_binding_hash": release.context_binding_hash,
                "status": "PUBLISHED",
                "parent_release_id": None,
                "manifest_hash": release.manifest_hash,
                "created_at": release.created_at_utc,
                "published_at": "2026-10-02T00:03:00Z",
            }
        ],
        "registry.longitudinal_scope": [
            {
                "longitudinal_scope_id": scope_id,
                "longitudinal_scope_key": scope_key,
                "subject_type": scope.subject_type,
                "subject_id": scope.subject_id,
                "metric_semantic_id": scope.metric_semantic_id,
                "metric_semantic_version": scope.metric_semantic_version,
                "comparison_key_hash": scope.comparison_key_hash,
                "session_order_scope_id": scope.session_order_scope_id,
                "trend_profile_version": scope.trend_profile_version,
                "descriptor_json": descriptor,
                "descriptor_hash": scope.descriptor_hash,
            }
        ],
        "metric.performance_trend_series": [
            {
                **trend.projection(),
                "reason_codes": [],
            }
        ],
        "metric.metric_definition": [
            {
                "metric_definition_id": metric_definition_id,
                "metric_code": trend.metric_code,
            }
        ],
        "metric.performance_trend_point": point_rows,
        "metric.longitudinal_sample": samples,
        "registry.longitudinal_release_input": release_inputs,
        "metric.trend_input_bridge": [],
        "registry.compute_job": [
            {
                "job_id": release.compute_job_id,
                "input_hash": request_hash,
            }
        ],
        "registry.release_scope_pointer": [
            {
                "scope_type": "LONGITUDINAL",
                "scope_key": scope_key,
                "current_release_id": release_id,
                "version_token": 1,
            }
        ],
    }
    return tables, release_id, release


def test_prcb_m4_longitudinal_release_reconstructs_exact_domain_product() -> None:
    tables, release_id, expected = _release_tables()
    rows = _Rows(tables)
    repository = DurableM4LongitudinalReleaseRepository(
        lambda: _ReadUow(rows),
        authority_root=AUTHORITY,
    )
    published = repository.get_release(release_id)
    assert published.release == expected
    assert published.version_token == 1
    assert repository.current(expected.scope_key) == published
    assert repository.version_token(expected.scope_key) == 1


class _SqliteUow:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.canonical_rows = SQLiteCanonicalRowRepository(connection)
        self._connection = connection

    def __enter__(self):
        return self

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def __exit__(self, exc_type, exc, traceback) -> None:
        if exc is not None:
            self._connection.rollback()


def _annotation_connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE "debrief.annotation" (
            annotation_id TEXT PRIMARY KEY,
            base_release_id TEXT NOT NULL,
            session_id TEXT NOT NULL,
            episode_id TEXT NULL,
            stage_id TEXT NULL,
            author_id TEXT NOT NULL,
            annotation_type TEXT NOT NULL,
            start_session_time_us INTEGER NULL,
            end_session_time_us INTEGER NULL,
            body_text TEXT NOT NULL,
            visibility TEXT NOT NULL,
            status TEXT NOT NULL,
            revision_no INTEGER NOT NULL,
            supersedes_annotation_id TEXT NULL,
            evidence_set_id TEXT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE "audit.audit_log" (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor_id TEXT NULL,
            action TEXT NOT NULL,
            object_type TEXT NOT NULL,
            object_id TEXT NOT NULL,
            old_value TEXT NULL,
            new_value TEXT NOT NULL,
            reason TEXT NULL,
            request_id TEXT NULL,
            created_at TEXT NOT NULL DEFAULT '2026-10-05T00:00:00Z'
        );
        """
    )
    return connection


def test_prcb_m4_annotation_is_durable_idempotent_and_audited() -> None:
    connection = _annotation_connection()
    repository = DurableM4DebriefRepository(
        lambda: _SqliteUow(connection),
        lambda: _SqliteUow(connection),
        clock=lambda: "2026-10-05T00:00:00Z",
    )
    command = M4AnnotationCommand(
        request_id="prcb-m4-create-1",
        operation="CREATE",
        base_release_id=_u("annotation-release"),
        target_annotation_id=None,
        session_id=_u("annotation-session"),
        episode_id=None,
        stage_id=None,
        author_id=_u("annotation-author"),
        annotation_type="COMMENT",
        start_session_time_us=None,
        end_session_time_us=None,
        body_text="Production debrief note",
        visibility="INSTRUCTOR",
        reason="PRCB durable annotation qualification",
        evidence_set_id=None,
    )
    first = repository.apply_annotation(command)
    second = repository.apply_annotation(command)
    assert second == first
    query = M4DebriefQuery(
        base_release_id=command.base_release_id,
        view_mode="ORIGINAL_AS_KNOWN",
        retrospective_release_id=None,
        annotation_view="EXACT_REVISION_SET",
        annotation_as_of_utc=None,
        annotation_ids=(first.annotation_id,),
    )
    assert repository.annotations_for(query) == (first,)

    with pytest.raises(M4ApplicationError, match="M4_ANNOTATION_REQUEST_CONFLICT"):
        repository.apply_annotation(
            M4AnnotationCommand(
                **{
                    **command.__dict__,
                    "body_text": "Conflicting replay",
                }
            )
        )


def test_prcb_m4_durable_source_has_no_shadow_table_or_inmemory_fallback() -> None:
    source = (
        ROOT / "src" / "tpaa_runtime" / "durable_longitudinal.py"
    ).read_text(encoding="utf-8")
    assert "CREATE TABLE" not in source
    assert "InMemory" not in source
    assert "tests/fixtures" not in source
    assert "M4_PRODUCTION_PUBLICATION_REQUIRES_GOVERNED_WORKER" in source
