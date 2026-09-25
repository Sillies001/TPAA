"""Core-model M1 SESSION publication ledger for SQLite and PostgreSQL.

The ledger writes only tables frozen by CORE_LOGICAL_MODEL. It never creates or
repairs schema, and it refuses to synthesize prerequisite Session/Context/subject/
Episode/Stage/MetricDefinition authority. Those rows must already exist and must
match the immutable Release being published.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid5

from tpaa_observation import SessionRelease

COMPUTE_JOB_NAMESPACE = UUID("a682e684-0645-4bc2-b886-e62a20f0e08b")
CONTEXT_REF_NAMESPACE = UUID("b3306367-f022-4567-a9e9-55feb71b2f25")
PUBLICATION_COMPONENT_VERSION = "M1-BATCH-2-1.0.0"


class CorePublicationLedgerError(RuntimeError):
    """Deterministic persistence failure at the Core publication boundary."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


@dataclass(frozen=True)
class CorePublishReceipt:
    release_id: str
    session_id: str
    request_hash: str
    manifest_hash: str
    version_token: int
    reused: bool
    status: str = "PUBLISHED"


class _Executor(Protocol):
    def table(self, logical_name: str) -> str: ...
    def execute(self, sql: str, params: tuple[object, ...] = ()) -> Any: ...
    def fetchone(self, sql: str, params: tuple[object, ...] = ()) -> Any | None: ...
    def fetchall(self, sql: str, params: tuple[object, ...] = ()) -> list[Any]: ...
    def json(self, value: object) -> object: ...
    def text_array(self, values: tuple[str, ...]) -> object: ...
    def lock_idempotency(self, key: str) -> None: ...
    def lock_session(self, session_id: str) -> None: ...


class _SQLiteExecutor:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def table(self, logical_name: str) -> str:
        return f'"{logical_name}"'

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> sqlite3.Cursor:
        try:
            return self.connection.execute(sql, params)
        except sqlite3.DatabaseError as exc:
            raise CorePublicationLedgerError("SQLITE_PUBLICATION_SQL_FAILED", str(exc)) from exc

    def fetchone(self, sql: str, params: tuple[object, ...] = ()) -> Any | None:
        return self.execute(sql, params).fetchone()

    def fetchall(self, sql: str, params: tuple[object, ...] = ()) -> list[Any]:
        return list(self.execute(sql, params).fetchall())

    def json(self, value: object) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

    def text_array(self, values: tuple[str, ...]) -> str:
        return self.json(list(values))

    def lock_idempotency(self, key: str) -> None:
        del key

    def lock_session(self, session_id: str) -> None:
        del session_id


class _PostgreSQLExecutor:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def table(self, logical_name: str) -> str:
        schema, table = logical_name.split(".", 1)
        return f'"{schema}"."{table}"'

    def execute(self, sql: str, params: tuple[object, ...] = ()) -> Any:
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, params)
            return cursor
        except Exception as exc:
            raise CorePublicationLedgerError("POSTGRES_PUBLICATION_SQL_FAILED", str(exc)) from exc

    def fetchone(self, sql: str, params: tuple[object, ...] = ()) -> Any | None:
        cursor = self.execute(sql, params)
        try:
            return cursor.fetchone()
        finally:
            cursor.close()

    def fetchall(self, sql: str, params: tuple[object, ...] = ()) -> list[Any]:
        cursor = self.execute(sql, params)
        try:
            return list(cursor.fetchall())
        finally:
            cursor.close()

    def json(self, value: object) -> object:
        try:
            from psycopg.types.json import Jsonb
        except ModuleNotFoundError as exc:
            raise CorePublicationLedgerError(
                "POSTGRES_JSON_ADAPTER_MISSING",
                "psycopg.types.json.Jsonb is required",
            ) from exc
        return Jsonb(value)

    def text_array(self, values: tuple[str, ...]) -> list[str]:
        return list(values)

    def lock_idempotency(self, key: str) -> None:
        cursor = self.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (key,),
        )
        cursor.close()

    def lock_session(self, session_id: str) -> None:
        table = self.table("registry.training_session")
        cursor = self.execute(
            f"SELECT session_id FROM {table} WHERE session_id = %s FOR UPDATE",
            (session_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        if row is None:
            raise CorePublicationLedgerError("SESSION_PREREQUISITE_MISSING", session_id)


def _value(row: Any, index: int) -> Any:
    return row[index]


class CorePublicationLedger:
    """Publish/read exact logical membership through authoritative Core tables."""

    def __init__(self, executor: _Executor) -> None:
        self._db = executor

    def _one(
        self,
        table_name: str,
        where_sql: str,
        params: tuple[object, ...],
        *,
        code: str,
    ) -> Any:
        table = self._db.table(table_name)
        rows = self._db.fetchall(f"SELECT * FROM {table} WHERE {where_sql}", params)
        if len(rows) != 1:
            raise CorePublicationLedgerError(code, f"table={table_name} rows={len(rows)}")
        return rows[0]

    def _require_prerequisites(self, release: SessionRelease) -> None:
        d = self._db
        session = self._one(
            "registry.training_session",
            "session_id = ?" if isinstance(d, _SQLiteExecutor) else "session_id = %s",
            (release.session_id,),
            code="SESSION_PREREQUISITE_CARDINALITY",
        )
        if str(_value(session, 0)) != release.session_id:
            raise CorePublicationLedgerError("SESSION_PREREQUISITE_MISMATCH", release.session_id)

        q = "context_id = ?" if isinstance(d, _SQLiteExecutor) else "context_id = %s"
        context = self._one(
            "context.evaluation_context",
            q,
            (release.context_id,),
            code="CONTEXT_PREREQUISITE_CARDINALITY",
        )
        if (
            str(_value(context, 0)) != release.context_id
            or str(_value(context, 1)) != release.session_id
            or str(_value(context, 2)) != release.context_version
        ):
            raise CorePublicationLedgerError("CONTEXT_PREREQUISITE_MISMATCH", release.context_id)

        if not release.observations:
            raise CorePublicationLedgerError("OBSERVATION_SET_EMPTY", release.release_id)
        identity = release.observations[0].identity
        for observation in release.observations:
            if observation.identity != identity:
                raise CorePublicationLedgerError(
                    "OBSERVATION_IDENTITY_DRIFT",
                    observation.observation_id,
                )

        p = "aircraft_model_id = ?" if isinstance(d, _SQLiteExecutor) else "aircraft_model_id = %s"
        model = self._one(
            "master.aircraft_model",
            p,
            (identity.aircraft_model_id,),
            code="AIRCRAFT_MODEL_PREREQUISITE_CARDINALITY",
        )
        if str(_value(model, 0)) != identity.aircraft_model_id:
            raise CorePublicationLedgerError(
                "AIRCRAFT_MODEL_PREREQUISITE_MISMATCH",
                identity.aircraft_model_id,
            )

        p = "aircraft_id = ?" if isinstance(d, _SQLiteExecutor) else "aircraft_id = %s"
        aircraft = self._one(
            "master.aircraft",
            p,
            (identity.aircraft_id,),
            code="AIRCRAFT_PREREQUISITE_CARDINALITY",
        )
        if (
            str(_value(aircraft, 0)) != identity.aircraft_id
            or str(_value(aircraft, 1)) != identity.aircraft_model_id
        ):
            raise CorePublicationLedgerError("AIRCRAFT_PREREQUISITE_MISMATCH", identity.aircraft_id)

        p = "entity_id = ?" if isinstance(d, _SQLiteExecutor) else "entity_id = %s"
        entity = self._one(
            "master.entity",
            p,
            (identity.subject_entity_id,),
            code="SUBJECT_ENTITY_PREREQUISITE_CARDINALITY",
        )
        if str(_value(entity, 0)) != identity.subject_entity_id:
            raise CorePublicationLedgerError(
                "SUBJECT_ENTITY_PREREQUISITE_MISMATCH",
                identity.subject_entity_id,
            )

        p = (
            "aircraft_instance_id = ?"
            if isinstance(d, _SQLiteExecutor)
            else "aircraft_instance_id = %s"
        )
        instance = self._one(
            "master.aircraft_instance",
            p,
            (identity.aircraft_instance_id,),
            code="AIRCRAFT_INSTANCE_PREREQUISITE_CARDINALITY",
        )
        if (
            str(_value(instance, 0)) != identity.aircraft_instance_id
            or str(_value(instance, 1)) != release.session_id
            or str(_value(instance, 2)) != identity.aircraft_id
            or str(_value(instance, 3)) != identity.subject_entity_id
        ):
            raise CorePublicationLedgerError(
                "AIRCRAFT_INSTANCE_PREREQUISITE_MISMATCH",
                identity.aircraft_instance_id,
            )

        episode_id = release.observations[0].episode_id
        p = "episode_id = ?" if isinstance(d, _SQLiteExecutor) else "episode_id = %s"
        episode = self._one(
            "episode.training_episode",
            p,
            (episode_id,),
            code="EPISODE_PREREQUISITE_CARDINALITY",
        )
        if (
            str(_value(episode, 0)) != episode_id
            or str(_value(episode, 1)) != release.session_id
            or str(_value(episode, 4)) != release.context_id
            or str(_value(episode, 8)) != identity.aircraft_id
        ):
            raise CorePublicationLedgerError("EPISODE_PREREQUISITE_MISMATCH", episode_id)

        stage_ids = {
            item.stage_id
            for item in release.metric_instances
            if item.stage_id is not None
        }
        for stage_id in stage_ids:
            p = "stage_id = ?" if isinstance(d, _SQLiteExecutor) else "stage_id = %s"
            stage = self._one(
                "episode.episode_stage",
                p,
                (stage_id,),
                code="STAGE_PREREQUISITE_CARDINALITY",
            )
            if str(_value(stage, 0)) != stage_id or str(_value(stage, 1)) != episode_id:
                raise CorePublicationLedgerError("STAGE_PREREQUISITE_MISMATCH", str(stage_id))

        definition_table = d.table("metric.metric_definition")
        placeholder = "?" if isinstance(d, _SQLiteExecutor) else "%s"
        for definition in release.definitions:
            rows = d.fetchall(
                f"""SELECT metric_definition_id, catalog_version, catalog_hash,
                           metric_semantic_id, metric_semantic_version, subject_type,
                           observation_lane, publication_route, definition_hash
                    FROM {definition_table}
                    WHERE metric_definition_id = {placeholder}""",
                (definition.metric_definition_id,),
            )
            if len(rows) != 1:
                raise CorePublicationLedgerError(
                    "METRIC_DEFINITION_PREREQUISITE_CARDINALITY",
                    f"{definition.metric_code} rows={len(rows)}",
                )
            row = rows[0]
            actual = (
                str(row[0]),
                str(row[1]),
                str(row[2]),
                str(row[3]),
                int(row[4]),
                str(row[5]),
                str(row[6]),
                str(row[7]),
                str(row[8]),
            )
            expected = (
                definition.metric_definition_id,
                definition.catalog_version,
                definition.catalog_hash,
                definition.semantic_id,
                definition.semantic_version,
                definition.subject_type,
                definition.observation_lane,
                definition.publication_route,
                definition.definition_hash,
            )
            if actual != expected:
                raise CorePublicationLedgerError(
                    "METRIC_DEFINITION_PREREQUISITE_MISMATCH",
                    definition.metric_code,
                )

    def _idempotent_receipt(
        self,
        release: SessionRelease,
        *,
        idempotency_key: str,
    ) -> CorePublishReceipt | None:
        d = self._db
        job = d.table("registry.compute_job")
        rel = d.table("registry.analysis_release")
        p = "?" if isinstance(d, _SQLiteExecutor) else "%s"
        rows = d.fetchall(
            f"""SELECT j.input_hash, r.release_id, r.manifest_hash, r.session_id,
                       r.release_no, r.status
                FROM {job} AS j
                JOIN {rel} AS r ON r.compute_job_id = j.job_id
                WHERE j.job_key = {p}""",
            (idempotency_key,),
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise CorePublicationLedgerError(
                "IDEMPOTENCY_KEY_CARDINALITY",
                f"key={idempotency_key} rows={len(rows)}",
            )
        row = rows[0]
        if (
            str(row[0]) != release.request_hash
            or str(row[1]) != release.release_id
            or str(row[2]) != release.manifest_hash
            or str(row[3]) != release.session_id
        ):
            raise CorePublicationLedgerError("IDEMPOTENCY_KEY_CONFLICT", idempotency_key)
        if str(row[5]) != "PUBLISHED":
            raise CorePublicationLedgerError(
                "IDEMPOTENCY_RELEASE_NOT_PUBLISHED",
                str(row[1]),
            )
        return CorePublishReceipt(
            release_id=release.release_id,
            session_id=release.session_id,
            request_hash=release.request_hash,
            manifest_hash=release.manifest_hash,
            version_token=int(row[4]),
            reused=True,
        )

    def publish(
        self,
        release: SessionRelease,
        *,
        idempotency_key: str,
        expected_version_token: int,
    ) -> CorePublishReceipt:
        if not idempotency_key.strip():
            raise CorePublicationLedgerError("IDEMPOTENCY_KEY_REQUIRED", "")
        if expected_version_token < 0:
            raise CorePublicationLedgerError(
                "EXPECTED_VERSION_TOKEN_INVALID",
                str(expected_version_token),
            )
        d = self._db
        d.lock_idempotency(idempotency_key)
        d.lock_session(release.session_id)

        reused = self._idempotent_receipt(release, idempotency_key=idempotency_key)
        if reused is not None:
            return reused

        self._require_prerequisites(release)

        pointer = d.table("registry.release_scope_pointer")
        p = "?" if isinstance(d, _SQLiteExecutor) else "%s"
        pointer_rows = d.fetchall(
            f"""SELECT current_release_id, version_token
                FROM {pointer}
                WHERE scope_type = {p} AND scope_key = {p}""",
            ("SESSION", release.session_id),
        )
        if len(pointer_rows) > 1:
            raise CorePublicationLedgerError(
                "RELEASE_POINTER_CARDINALITY",
                f"session={release.session_id} rows={len(pointer_rows)}",
            )
        if pointer_rows:
            current_release_id = (
                None if pointer_rows[0][0] is None else str(pointer_rows[0][0])
            )
            actual_token = int(pointer_rows[0][1])
        else:
            current_release_id = None
            actual_token = 0

        if actual_token != expected_version_token:
            raise CorePublicationLedgerError(
                "PUBLISH_CAS_CONFLICT",
                f"expected={expected_version_token} actual={actual_token}",
            )
        if release.release_no != actual_token + 1:
            raise CorePublicationLedgerError(
                "PUBLISH_RELEASE_NO_MISMATCH",
                f"expected={actual_token + 1} actual={release.release_no}",
            )
        if release.parent_release_id != current_release_id:
            raise CorePublicationLedgerError(
                "PUBLISH_PARENT_RELEASE_MISMATCH",
                f"expected={current_release_id!r} actual={release.parent_release_id!r}",
            )

        existing_release = d.fetchall(
            f"SELECT manifest_hash, status FROM {d.table('registry.analysis_release')} "
            f"WHERE release_id = {p}",
            (release.release_id,),
        )
        if existing_release:
            raise CorePublicationLedgerError(
                "RELEASE_ID_ALREADY_EXISTS_WITHOUT_IDEMPOTENCY",
                release.release_id,
            )

        job_id = str(uuid5(COMPUTE_JOB_NAMESPACE, f"{idempotency_key}|{release.request_hash}"))
        job_table = d.table("registry.compute_job")
        now_expr = "CURRENT_TIMESTAMP"
        d.execute(
            f"""INSERT INTO {job_table} (
                    job_id, job_type, session_id, episode_id, job_key, status,
                    component_version, input_hash, progress, reason_codes,
                    error_detail, created_at, started_at, finished_at
                ) VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},
                          {now_expr},{now_expr},{now_expr})""",
            (
                job_id,
                "M1_SESSION_PUBLISH",
                release.session_id,
                release.observations[0].episode_id,
                idempotency_key,
                "SUCCEEDED",
                PUBLICATION_COMPONENT_VERSION,
                release.request_hash,
                1.0,
                d.text_array(()),
                None,
            ),
        )

        release_table = d.table("registry.analysis_release")
        d.execute(
            f"""INSERT INTO {release_table} (
                    release_id, scope_type, scope_key, session_id,
                    longitudinal_scope_id, release_no, compute_job_id,
                    catalog_version, catalog_hash, context_binding_hash,
                    status, parent_release_id, manifest_hash, created_at, published_at
                ) VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},
                          {now_expr},{now_expr})""",
            (
                release.release_id,
                "SESSION",
                release.session_id,
                release.session_id,
                None,
                release.release_no,
                job_id,
                release.catalog_version,
                release.catalog_hash,
                release.context_binding_hash,
                "PUBLISHED",
                release.parent_release_id,
                release.manifest_hash,
            ),
        )

        ref_table = d.table("registry.session_release_context_ref")
        ref_id = str(
            uuid5(
                CONTEXT_REF_NAMESPACE,
                f"{release.release_id}|{release.context_id}|{release.context_version}",
            )
        )
        start_us = min(item.observation_start_session_time_us for item in release.observations)
        end_us = max(item.observation_end_session_time_us for item in release.observations)
        d.execute(
            f"""INSERT INTO {ref_table} (
                    release_context_ref_id, release_id, release_scope_type,
                    context_id, context_version, start_session_time_us,
                    end_session_time_us, ref_order
                ) VALUES ({p},{p},{p},{p},{p},{p},{p},{p})""",
            (
                ref_id,
                release.release_id,
                "SESSION",
                release.context_id,
                release.context_version,
                start_us,
                end_us,
                0,
            ),
        )

        instance_by_evidence = {
            item.evidence_set_id: item for item in release.metric_instances
        }
        if len(instance_by_evidence) != len(release.metric_instances):
            raise CorePublicationLedgerError(
                "EVIDENCE_SET_NOT_ONE_TO_ONE",
                release.release_id,
            )
        evidence_table = d.table("metric.evidence_set")
        for evidence in release.evidence_sets:
            instance = instance_by_evidence[evidence.evidence_set_id]
            series_locator = {
                "logical_hash": evidence.logical_hash,
                "refs": [
                    {
                        "ref_class": ref.ref_class,
                        "ref_id": ref.ref_id,
                        "logical_hash": ref.logical_hash,
                    }
                    for ref in evidence.refs
                ],
                "details": [list(item) for item in evidence.details],
            }
            algorithm_versions = {
                "metric_code": instance.metric_code,
                "compute_version": instance.compute_version,
            }
            d.execute(
                f"""INSERT INTO {evidence_table} (
                        evidence_set_id, release_id, session_id, episode_id,
                        start_session_time_us, end_session_time_us, series_locator,
                        algorithm_versions, created_at
                    ) VALUES ({p},{p},{p},{p},{p},{p},{p},{p},{now_expr})""",
                (
                    evidence.evidence_set_id,
                    release.release_id,
                    release.session_id,
                    evidence.episode_id,
                    evidence.start_session_time_us,
                    evidence.end_session_time_us,
                    d.json(series_locator),
                    d.json(algorithm_versions),
                ),
            )

        observation_by_instance = {
            item.metric_instance_id: item for item in release.observations
        }
        if len(observation_by_instance) != len(release.observations):
            raise CorePublicationLedgerError(
                "OBSERVATION_NOT_ONE_TO_ONE",
                release.release_id,
            )
        metric_table = d.table("metric.metric_instance")
        for instance in release.metric_instances:
            observation = observation_by_instance[instance.metric_instance_id]
            value_structured = (
                None
                if instance.value_structured_json is None
                else d.json(json.loads(instance.value_structured_json))
            )
            metric_scope = "STAGE" if instance.stage_id is not None else "EPISODE"
            d.execute(
                f"""INSERT INTO {metric_table} (
                        metric_instance_id, release_id, metric_definition_id,
                        session_id, metric_scope, episode_id, stage_id,
                        subject_entity_id, mission_system_instance_id, tpaa_chain_id,
                        value_numeric, value_text, value_boolean, value_structured,
                        unit, status, reason_codes, coverage, confidence,
                        confidence_components, evidence_set_id, context_id,
                        world_product_versions, compute_version, input_hash, created_at
                    ) VALUES (
                        {p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},
                        {p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{now_expr}
                    )""",
                (
                    instance.metric_instance_id,
                    release.release_id,
                    instance.metric_definition_id,
                    release.session_id,
                    metric_scope,
                    instance.episode_id,
                    instance.stage_id,
                    instance.subject_entity_id,
                    None,
                    None,
                    instance.value_numeric,
                    None,
                    None,
                    value_structured,
                    instance.unit,
                    instance.status,
                    d.text_array(instance.reason_codes),
                    observation.coverage,
                    observation.confidence,
                    d.json({}),
                    instance.evidence_set_id,
                    instance.context_id,
                    d.json(
                        {
                            "world_product_id": instance.world_product_id,
                            "logical_hash": instance.world_logical_hash,
                        }
                    ),
                    instance.compute_version,
                    instance.input_hash,
                ),
            )

        observation_table = d.table("metric.capability_observation")
        for observation in release.observations:
            structured = (
                None
                if observation.value_structured_json is None
                else d.json(json.loads(observation.value_structured_json))
            )
            d.execute(
                f"""INSERT INTO {observation_table} (
                        observation_id, release_id, session_id, episode_id, stage_id,
                        aircraft_id, aircraft_instance_id, subject_entity_id,
                        aircraft_model_id, aircraft_configuration_snapshot_id,
                        pilot_id, scenario_id, context_id, capability_dimension,
                        capability_type, capability_level, observed_metric_instance_id,
                        observed_value_numeric, observed_value_text,
                        observed_value_boolean, observed_value_structured, unit,
                        observation_start_session_time_us,
                        observation_end_session_time_us, context_tags,
                        evidence_set_id, coverage, confidence, eligibility_status,
                        exclusion_reason_code, correlation_group_id,
                        comparison_key_hash, observation_schema_version, created_at,
                        supersedes_observation_id
                    ) VALUES (
                        {p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},
                        {p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},{p},
                        {p},{p},{p},{p},{p},{now_expr},{p}
                    )""",
                (
                    observation.observation_id,
                    release.release_id,
                    release.session_id,
                    observation.episode_id,
                    observation.stage_id,
                    observation.identity.aircraft_id,
                    observation.identity.aircraft_instance_id,
                    observation.identity.subject_entity_id,
                    observation.identity.aircraft_model_id,
                    None,
                    None,
                    None,
                    observation.context_id,
                    observation.identity.capability_dimension,
                    observation.identity.capability_type,
                    "CAP_L1_OBSERVED",
                    observation.metric_instance_id,
                    observation.value_numeric,
                    None,
                    None,
                    structured,
                    observation.unit,
                    observation.observation_start_session_time_us,
                    observation.observation_end_session_time_us,
                    d.json({}),
                    observation.evidence_set_id,
                    observation.coverage,
                    observation.confidence,
                    observation.eligibility_status,
                    observation.exclusion_reason_code,
                    None,
                    observation.comparison_key_hash,
                    observation.observation_schema_version,
                    None,
                ),
            )

        next_token = actual_token + 1
        if pointer_rows:
            cursor = d.execute(
                f"""UPDATE {pointer}
                    SET current_release_id = {p}, version_token = {p},
                        updated_at = {now_expr}
                    WHERE scope_type = {p} AND scope_key = {p}
                      AND version_token = {p}""",
                (
                    release.release_id,
                    next_token,
                    "SESSION",
                    release.session_id,
                    actual_token,
                ),
            )
            if getattr(cursor, "rowcount", 1) != 1:
                raise CorePublicationLedgerError(
                    "PUBLISH_CAS_UPDATE_LOST",
                    release.session_id,
                )
        else:
            d.execute(
                f"""INSERT INTO {pointer} (
                        scope_type, scope_key, current_release_id, version_token, updated_at
                    ) VALUES ({p},{p},{p},{p},{now_expr})""",
                ("SESSION", release.session_id, release.release_id, next_token),
            )

        d.execute(
            f"""UPDATE {d.table('registry.training_session')}
                SET current_release_id = {p}
                WHERE session_id = {p}""",
            (release.release_id, release.session_id),
        )
        return CorePublishReceipt(
            release_id=release.release_id,
            session_id=release.session_id,
            request_hash=release.request_hash,
            manifest_hash=release.manifest_hash,
            version_token=next_token,
            reused=False,
        )

    def logical_membership(self, release_id: str) -> dict[str, object]:
        """Return a stable engine-neutral Release membership projection."""

        d = self._db
        p = "?" if isinstance(d, _SQLiteExecutor) else "%s"
        release_rows = d.fetchall(
            f"""SELECT release_id, scope_type, scope_key, session_id, release_no,
                       catalog_version, catalog_hash, context_binding_hash,
                       status, parent_release_id, manifest_hash
                FROM {d.table('registry.analysis_release')}
                WHERE release_id = {p}""",
            (release_id,),
        )
        if len(release_rows) != 1:
            raise CorePublicationLedgerError(
                "RELEASE_CARDINALITY",
                f"release_id={release_id} rows={len(release_rows)}",
            )
        r = release_rows[0]
        refs = d.fetchall(
            f"""SELECT context_id, context_version, start_session_time_us,
                       end_session_time_us, ref_order
                FROM {d.table('registry.session_release_context_ref')}
                WHERE release_id = {p}
                ORDER BY ref_order, context_id""",
            (release_id,),
        )
        metrics = d.fetchall(
            f"""SELECT metric_instance_id, metric_definition_id, metric_scope,
                       episode_id, stage_id, subject_entity_id, value_numeric,
                       value_structured, unit, status, reason_codes, coverage,
                       confidence, evidence_set_id, context_id,
                       world_product_versions, compute_version, input_hash
                FROM {d.table('metric.metric_instance')}
                WHERE release_id = {p}
                ORDER BY metric_instance_id""",
            (release_id,),
        )
        evidence = d.fetchall(
            f"""SELECT evidence_set_id, episode_id, start_session_time_us,
                       end_session_time_us, series_locator, algorithm_versions
                FROM {d.table('metric.evidence_set')}
                WHERE release_id = {p}
                ORDER BY evidence_set_id""",
            (release_id,),
        )
        observations = d.fetchall(
            f"""SELECT observation_id, episode_id, stage_id, aircraft_id,
                       aircraft_instance_id, subject_entity_id, aircraft_model_id,
                       context_id, capability_dimension, capability_type,
                       capability_level, observed_metric_instance_id,
                       observed_value_numeric, observed_value_structured, unit,
                       observation_start_session_time_us,
                       observation_end_session_time_us, evidence_set_id,
                       coverage, confidence, eligibility_status,
                       exclusion_reason_code, comparison_key_hash,
                       observation_schema_version
                FROM {d.table('metric.capability_observation')}
                WHERE release_id = {p}
                ORDER BY observation_id""",
            (release_id,),
        )

        def normalize_json(value: Any) -> Any:
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value

        def normalize_array(value: Any) -> list[str]:
            parsed = normalize_json(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
            if isinstance(parsed, tuple):
                return [str(item) for item in parsed]
            return []

        return {
            "release": {
                "release_id": str(r[0]),
                "scope_type": str(r[1]),
                "scope_key": str(r[2]),
                "session_id": str(r[3]),
                "release_no": int(r[4]),
                "catalog_version": str(r[5]),
                "catalog_hash": str(r[6]),
                "context_binding_hash": str(r[7]),
                "status": str(r[8]),
                "parent_release_id": None if r[9] is None else str(r[9]),
                "manifest_hash": str(r[10]),
            },
            "context_refs": [
                {
                    "context_id": str(row[0]),
                    "context_version": str(row[1]),
                    "start_session_time_us": int(row[2]),
                    "end_session_time_us": int(row[3]),
                    "ref_order": int(row[4]),
                }
                for row in refs
            ],
            "metric_instances": [
                {
                    "metric_instance_id": str(row[0]),
                    "metric_definition_id": str(row[1]),
                    "metric_scope": str(row[2]),
                    "episode_id": None if row[3] is None else str(row[3]),
                    "stage_id": None if row[4] is None else str(row[4]),
                    "subject_entity_id": None if row[5] is None else str(row[5]),
                    "value_numeric": row[6],
                    "value_structured": normalize_json(row[7]),
                    "unit": str(row[8]),
                    "status": str(row[9]),
                    "reason_codes": normalize_array(row[10]),
                    "coverage": float(row[11]),
                    "confidence": float(row[12]),
                    "evidence_set_id": str(row[13]),
                    "context_id": str(row[14]),
                    "world_product_versions": normalize_json(row[15]),
                    "compute_version": str(row[16]),
                    "input_hash": str(row[17]),
                }
                for row in metrics
            ],
            "evidence_sets": [
                {
                    "evidence_set_id": str(row[0]),
                    "episode_id": None if row[1] is None else str(row[1]),
                    "start_session_time_us": None if row[2] is None else int(row[2]),
                    "end_session_time_us": None if row[3] is None else int(row[3]),
                    "series_locator": normalize_json(row[4]),
                    "algorithm_versions": normalize_json(row[5]),
                }
                for row in evidence
            ],
            "observations": [
                {
                    "observation_id": str(row[0]),
                    "episode_id": str(row[1]),
                    "stage_id": None if row[2] is None else str(row[2]),
                    "aircraft_id": str(row[3]),
                    "aircraft_instance_id": str(row[4]),
                    "subject_entity_id": str(row[5]),
                    "aircraft_model_id": str(row[6]),
                    "context_id": str(row[7]),
                    "capability_dimension": str(row[8]),
                    "capability_type": str(row[9]),
                    "capability_level": str(row[10]),
                    "observed_metric_instance_id": str(row[11]),
                    "observed_value_numeric": row[12],
                    "observed_value_structured": normalize_json(row[13]),
                    "unit": str(row[14]),
                    "observation_start_session_time_us": int(row[15]),
                    "observation_end_session_time_us": int(row[16]),
                    "evidence_set_id": str(row[17]),
                    "coverage": float(row[18]),
                    "confidence": float(row[19]),
                    "eligibility_status": str(row[20]),
                    "exclusion_reason_code": None if row[21] is None else str(row[21]),
                    "comparison_key_hash": str(row[22]),
                    "observation_schema_version": str(row[23]),
                }
                for row in observations
            ],
        }


class SQLiteCorePublicationLedger(CorePublicationLedger):
    def __init__(self, connection: sqlite3.Connection) -> None:
        super().__init__(_SQLiteExecutor(connection))


class PostgreSQLCorePublicationLedger(CorePublicationLedger):
    def __init__(self, connection: Any) -> None:
        super().__init__(_PostgreSQLExecutor(connection))
