"""DB 1.7 exact P2 domain persistence adapters for SQLite and PostgreSQL."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from tpaa_assessment import (
    P2AdjustedCapabilityEstimate,
    P2AttributionRunProduct,
    P2ExecutionProfile,
)

from .object_store import LocalObjectStore


class P2DomainPersistenceError(RuntimeError):
    """Fail-closed P2 persistence or exact-reconstruction error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}:{detail}")


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    )


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("ascii")).hexdigest()


def _json_object(value: object, field: str) -> dict[str, object]:
    decoded: object
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P2DomainPersistenceError("P2_DB_JSON_INVALID", field) from exc
    else:
        decoded = value
    if not isinstance(decoded, dict):
        raise P2DomainPersistenceError("P2_DB_JSON_INVALID", field)
    return {str(key): item for key, item in decoded.items()}


def _text_array(value: object, field: str) -> tuple[str, ...]:
    decoded: object = value
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise P2DomainPersistenceError("P2_DB_ARRAY_INVALID", field) from exc
    if not isinstance(decoded, (list, tuple)):
        raise P2DomainPersistenceError("P2_DB_ARRAY_INVALID", field)
    if not all(isinstance(item, str) for item in decoded):
        raise P2DomainPersistenceError("P2_DB_ARRAY_INVALID", field)
    return tuple(decoded)


def _time_text(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        normalized = value
        if normalized.tzinfo is not None:
            normalized = normalized.astimezone(timezone.utc)
        return normalized.isoformat().replace("+00:00", "Z")
    raise P2DomainPersistenceError(
        "P2_DB_TIME_INVALID",
        type(value).__name__,
    )


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)


def _estimate_logical_hash(
    estimate: P2AdjustedCapabilityEstimate,
    *,
    model_artifact_hash: str | None,
    profile: P2ExecutionProfile,
) -> str:
    if estimate.status == "NOT_IDENTIFIABLE":
        logical: dict[str, object] = {
            "source_observation_id": estimate.source_observation_id,
            "source_release_id": estimate.source_release_id,
            "p2_release_id": estimate.p2_release_id,
            "attribution_run_id": estimate.attribution_run_id,
            "reference_condition_id": estimate.reference_condition_id,
            "status": estimate.status,
            "reason_codes": list(estimate.reason_codes),
            "claim_level": estimate.claim_level,
            "evidence_set_id": estimate.evidence_set_id,
        }
        return _canonical_hash(logical)

    if estimate.status != "IDENTIFIABLE":
        raise P2DomainPersistenceError(
            "P2_ESTIMATE_STATUS_INVALID",
            estimate.status,
        )
    if model_artifact_hash is None:
        raise P2DomainPersistenceError(
            "P2_MODEL_ARTIFACT_REQUIRED",
            estimate.estimate_id,
        )
    required = (
        estimate.adjusted_value,
        estimate.uncertainty_lower,
        estimate.uncertainty_upper,
        estimate.residual,
    )
    if any(value is None for value in required):
        raise P2DomainPersistenceError(
            "P2_IDENTIFIABLE_ESTIMATE_INCOMPLETE",
            estimate.estimate_id,
        )

    def q(value: float | None) -> str:
        if value is None:
            raise P2DomainPersistenceError(
                "P2_IDENTIFIABLE_ESTIMATE_INCOMPLETE",
                estimate.estimate_id,
            )
        return profile.qstr(Decimal(str(value)))

    logical = {
        "source_observation_id": estimate.source_observation_id,
        "source_release_id": estimate.source_release_id,
        "p2_release_id": estimate.p2_release_id,
        "attribution_run_id": estimate.attribution_run_id,
        "reference_condition_id": estimate.reference_condition_id,
        "adjusted_value": q(estimate.adjusted_value),
        "unit": estimate.unit,
        "uncertainty_lower": q(estimate.uncertainty_lower),
        "uncertainty_upper": q(estimate.uncertainty_upper),
        "residual": q(estimate.residual),
        "factor_effects": [
            {"factor": factor, "effect": q(value)}
            for factor, value in estimate.factor_effects
        ],
        "claim_level": estimate.claim_level,
        "status": estimate.status,
        "reason_codes": list(estimate.reason_codes),
        "evidence_set_id": estimate.evidence_set_id,
        "model_artifact_hash": model_artifact_hash,
    }
    return _canonical_hash(logical)


class _P2DomainRepository:
    def __init__(
        self,
        connection: Any,
        *,
        postgres: bool,
        object_store: LocalObjectStore | None = None,
    ) -> None:
        self._connection = connection
        self._postgres = postgres
        self._object_store = object_store

    def _table(self, name: str) -> str:
        if self._postgres:
            schema, relation = name.split(".", 1)
            return f'"{schema}"."{relation}"'
        return f'"{name}"'

    def _placeholder(self, kind: str = "scalar") -> str:
        if not self._postgres:
            return "?"
        if kind == "json":
            return "%s::jsonb"
        if kind == "text_array":
            return "%s::text[]"
        return "%s"

    def _adapt(self, value: object, kind: str = "scalar") -> object:
        if kind == "json":
            return _canonical_json(value)
        if kind == "text_array":
            if self._postgres:
                return list(value) if isinstance(value, (tuple, list)) else value
            return _canonical_json(value)
        return value

    def _execute(self, sql: str, params: tuple[object, ...] = ()) -> Any:
        try:
            if self._postgres:
                cursor = self._connection.cursor()
                cursor.execute(sql, params)
                return cursor
            return self._connection.execute(sql, params)
        except Exception as exc:
            raise P2DomainPersistenceError(
                "P2_DB_EXECUTION_FAILED",
                str(exc),
            ) from exc

    def _fetchone(self, sql: str, params: tuple[object, ...]) -> Any | None:
        cursor = self._execute(sql, params)
        try:
            return cursor.fetchone()
        finally:
            if self._postgres:
                cursor.close()

    def _artifact_factor_order(
        self,
        run: P2AttributionRunProduct,
        factor_effects: dict[str, object],
    ) -> tuple[str, ...]:
        if not factor_effects:
            return ()
        if run.model_artifact_uri is None or run.model_artifact_hash is None:
            raise P2DomainPersistenceError(
                "P2_MODEL_ARTIFACT_REQUIRED",
                run.attribution_run_id,
            )
        if self._object_store is None:
            raise P2DomainPersistenceError(
                "P2_OBJECT_STORE_REQUIRED",
                run.attribution_run_id,
            )
        data = self._object_store.read_bytes(run.model_artifact_uri)
        actual = hashlib.sha256(data).hexdigest()
        if actual != run.model_artifact_hash:
            raise P2DomainPersistenceError(
                "P2_MODEL_ARTIFACT_HASH_MISMATCH",
                run.attribution_run_id,
            )
        try:
            payload: object = json.loads(data.decode("ascii"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise P2DomainPersistenceError(
                "P2_MODEL_ARTIFACT_INVALID",
                run.attribution_run_id,
            ) from exc
        if not isinstance(payload, dict):
            raise P2DomainPersistenceError(
                "P2_MODEL_ARTIFACT_INVALID",
                run.attribution_run_id,
            )
        order = payload.get("factor_order")
        if (
            not isinstance(order, list)
            or not all(isinstance(item, str) for item in order)
            or set(order) != set(factor_effects)
            or len(order) != len(factor_effects)
        ):
            raise P2DomainPersistenceError(
                "P2_MODEL_FACTOR_ORDER_MISMATCH",
                run.attribution_run_id,
            )
        return tuple(order)

    def _run_equivalent(
        self,
        left: P2AttributionRunProduct,
        right: P2AttributionRunProduct,
    ) -> bool:
        return (
            left.as_record() == right.as_record()
            and left.run_request_hash == right.run_request_hash
        )

    def register_attribution_run(
        self,
        value: P2AttributionRunProduct,
        *,
        compute_job_id: str | None = None,
    ) -> None:
        current = self._try_exact_attribution_run(value.attribution_run_id)
        if current is not None:
            if not self._run_equivalent(current, value):
                raise P2DomainPersistenceError(
                    "P2_IMMUTABLE_CONFLICT",
                    value.attribution_run_id,
                )
            return

        diagnostics = value.diagnostics()
        if diagnostics.get("run_request_hash") != value.run_request_hash:
            raise P2DomainPersistenceError(
                "P2_RUN_REQUEST_HASH_MISMATCH",
                value.attribution_run_id,
            )
        base = self._table("assessment.attribution_run")
        request = self._table("assessment.attribution_run_request_binding")
        p = self._placeholder()
        jp = self._placeholder("json")
        self._execute(
            f"""INSERT INTO {base} (
                attribution_run_id, attribution_spec_id,
                attribution_spec_version, model_plugin,
                model_plugin_version, training_dataset_snapshot_id,
                reference_condition_id, status, diagnostics,
                model_artifact_uri, model_artifact_hash, started_at,
                completed_at, created_by
            ) VALUES (
                {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {jp},
                {p}, {p}, {p}, {p}, {p}
            )""",
            (
                value.attribution_run_id,
                value.attribution_spec_id,
                value.attribution_spec_version,
                value.model_plugin,
                value.model_plugin_version,
                value.training_dataset_snapshot_id,
                value.reference_condition_id,
                value.status,
                self._adapt(diagnostics, "json"),
                value.model_artifact_uri,
                value.model_artifact_hash,
                value.started_at,
                value.completed_at,
                value.created_by,
            ),
        )
        self._execute(
            f"""INSERT INTO {request} (
                attribution_run_id, run_request_hash, compute_job_id
            ) VALUES ({p}, {p}, {p})""",
            (
                value.attribution_run_id,
                value.run_request_hash,
                compute_job_id,
            ),
        )

    def _try_exact_attribution_run(
        self,
        attribution_run_id: str,
    ) -> P2AttributionRunProduct | None:
        base = self._table("assessment.attribution_run")
        request = self._table("assessment.attribution_run_request_binding")
        p = self._placeholder()
        row = self._fetchone(
            f"""SELECT
                r.attribution_run_id, r.attribution_spec_id,
                r.attribution_spec_version, r.model_plugin,
                r.model_plugin_version, r.training_dataset_snapshot_id,
                r.reference_condition_id, r.status, r.diagnostics,
                r.model_artifact_uri, r.model_artifact_hash, r.started_at,
                r.completed_at, r.created_by, b.run_request_hash
            FROM {base} AS r
            JOIN {request} AS b
              ON b.attribution_run_id = r.attribution_run_id
            WHERE r.attribution_run_id = {p}""",
            (attribution_run_id,),
        )
        if row is None:
            return None
        diagnostics = _json_object(row[8], "attribution_run.diagnostics")
        return P2AttributionRunProduct(
            attribution_run_id=str(row[0]),
            attribution_spec_id=str(row[1]),
            attribution_spec_version=str(row[2]),
            model_plugin=str(row[3]),
            model_plugin_version=str(row[4]),
            training_dataset_snapshot_id=str(row[5]),
            reference_condition_id=str(row[6]),
            status=str(row[7]),
            diagnostics_json=_canonical_json(diagnostics),
            model_artifact_uri=_optional_text(row[9]),
            model_artifact_hash=_optional_text(row[10]),
            started_at=_time_text(row[11]),
            completed_at=_time_text(row[12]),
            created_by=_optional_text(row[13]),
            run_request_hash=str(row[14]),
        )

    def exact_attribution_run(
        self,
        attribution_run_id: str,
    ) -> P2AttributionRunProduct:
        value = self._try_exact_attribution_run(attribution_run_id)
        if value is None:
            raise P2DomainPersistenceError(
                "P2_ATTRIBUTION_RUN_NOT_FOUND",
                attribution_run_id,
            )
        return value

    def register_adjusted_estimate(
        self,
        value: P2AdjustedCapabilityEstimate,
    ) -> None:
        current = self._try_exact_adjusted_estimate(value.estimate_id)
        if current is not None:
            if current != value:
                raise P2DomainPersistenceError(
                    "P2_IMMUTABLE_CONFLICT",
                    value.estimate_id,
                )
            return

        profile = P2ExecutionProfile.from_canonical()
        if (
            value.uncertainty_method != profile.uncertainty_method
            or value.uncertainty_level != profile.uncertainty_level
        ):
            raise P2DomainPersistenceError(
                "P2_UNCERTAINTY_PROFILE_MISMATCH",
                value.estimate_id,
            )
        run = self.exact_attribution_run(value.attribution_run_id)
        if run.status != value.status:
            raise P2DomainPersistenceError(
                "P2_RUN_ESTIMATE_STATUS_MISMATCH",
                value.estimate_id,
            )
        diagnostics = run.diagnostics()
        if tuple(diagnostics.get("reason_codes", ())) != value.reason_codes:
            raise P2DomainPersistenceError(
                "P2_REASON_CODES_MISMATCH",
                value.estimate_id,
            )
        observation = self._table("metric.capability_observation")
        p = self._placeholder()
        release_row = self._fetchone(
            f"""SELECT release_id FROM {observation}
                WHERE observation_id = {p}""",
            (value.source_observation_id,),
        )
        if release_row is None or str(release_row[0]) != value.source_release_id:
            raise P2DomainPersistenceError(
                "P2_SOURCE_RELEASE_MISMATCH",
                value.estimate_id,
            )
        expected_hash = _estimate_logical_hash(
            value,
            model_artifact_hash=run.model_artifact_hash,
            profile=profile,
        )
        if expected_hash != value.logical_hash:
            raise P2DomainPersistenceError(
                "P2_LOGICAL_HASH_MISMATCH",
                value.estimate_id,
            )

        base = self._table("capability.adjusted_capability_estimate")
        revision = self._table(
            "capability.adjusted_capability_estimate_revision"
        )
        jp = self._placeholder("json")
        ap = self._placeholder("text_array")
        self._execute(
            f"""INSERT INTO {base} (
                estimate_id, source_observation_id, attribution_run_id,
                aircraft_id, capability_type, reference_condition_id,
                adjusted_value, unit, uncertainty_lower, uncertainty_upper,
                residual, factor_effects, claim_level, status,
                evidence_set_id, estimate_time, created_at,
                supersedes_estimate_id
            ) VALUES (
                {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p}, {p},
                {p}, {jp}, {p}, {p}, {p}, {p}, {p}, {p}
            )""",
            (
                value.estimate_id,
                value.source_observation_id,
                value.attribution_run_id,
                value.aircraft_id,
                value.capability_type,
                value.reference_condition_id,
                value.adjusted_value,
                value.unit,
                value.uncertainty_lower,
                value.uncertainty_upper,
                value.residual,
                self._adapt(dict(value.factor_effects), "json"),
                value.claim_level,
                value.status,
                value.evidence_set_id,
                value.estimate_time,
                value.created_at,
                value.supersedes_estimate_id,
            ),
        )
        self._execute(
            f"""INSERT INTO {revision} (
                estimate_id, p2_release_id, reason_codes
            ) VALUES ({p}, {p}, {ap})""",
            (
                value.estimate_id,
                value.p2_release_id,
                self._adapt(value.reason_codes, "text_array"),
            ),
        )

    def _try_exact_adjusted_estimate(
        self,
        estimate_id: str,
    ) -> P2AdjustedCapabilityEstimate | None:
        base = self._table("capability.adjusted_capability_estimate")
        revision = self._table(
            "capability.adjusted_capability_estimate_revision"
        )
        observation = self._table("metric.capability_observation")
        p = self._placeholder()
        row = self._fetchone(
            f"""SELECT
                e.estimate_id, e.source_observation_id,
                e.attribution_run_id, e.aircraft_id, e.capability_type,
                e.reference_condition_id, e.adjusted_value, e.unit,
                e.uncertainty_lower, e.uncertainty_upper, e.residual,
                e.factor_effects, e.claim_level, e.status,
                e.evidence_set_id, e.estimate_time, e.created_at,
                e.supersedes_estimate_id, r.p2_release_id,
                r.reason_codes, o.release_id
            FROM {base} AS e
            JOIN {revision} AS r ON r.estimate_id = e.estimate_id
            JOIN {observation} AS o
              ON o.observation_id = e.source_observation_id
            WHERE e.estimate_id = {p}""",
            (estimate_id,),
        )
        if row is None:
            return None

        run = self.exact_attribution_run(str(row[2]))
        effects_raw = _json_object(row[11], "estimate.factor_effects")
        order = self._artifact_factor_order(run, effects_raw)
        factor_effects = tuple(
            (factor, float(effects_raw[factor])) for factor in order
        )
        reason_codes = _text_array(row[19], "estimate.reason_codes")
        profile = P2ExecutionProfile.from_canonical()
        value = P2AdjustedCapabilityEstimate(
            estimate_id=str(row[0]),
            source_observation_id=str(row[1]),
            source_release_id=str(row[20]),
            p2_release_id=str(row[18]),
            attribution_run_id=str(row[2]),
            aircraft_id=str(row[3]),
            capability_type=str(row[4]),
            reference_condition_id=str(row[5]),
            adjusted_value=_optional_float(row[6]),
            unit=str(row[7]),
            uncertainty_lower=_optional_float(row[8]),
            uncertainty_upper=_optional_float(row[9]),
            uncertainty_method=profile.uncertainty_method,
            uncertainty_level=profile.uncertainty_level,
            residual=_optional_float(row[10]),
            factor_effects=factor_effects,
            claim_level=str(row[12]),
            status=str(row[13]),
            reason_codes=reason_codes,
            evidence_set_id=str(row[14]),
            estimate_time=_time_text(row[15]),
            created_at=_time_text(row[16]),
            supersedes_estimate_id=_optional_text(row[17]),
            logical_hash="",
        )
        logical_hash = _estimate_logical_hash(
            value,
            model_artifact_hash=run.model_artifact_hash,
            profile=profile,
        )
        return P2AdjustedCapabilityEstimate(
            estimate_id=value.estimate_id,
            source_observation_id=value.source_observation_id,
            source_release_id=value.source_release_id,
            p2_release_id=value.p2_release_id,
            attribution_run_id=value.attribution_run_id,
            aircraft_id=value.aircraft_id,
            capability_type=value.capability_type,
            reference_condition_id=value.reference_condition_id,
            adjusted_value=value.adjusted_value,
            unit=value.unit,
            uncertainty_lower=value.uncertainty_lower,
            uncertainty_upper=value.uncertainty_upper,
            uncertainty_method=value.uncertainty_method,
            uncertainty_level=value.uncertainty_level,
            residual=value.residual,
            factor_effects=value.factor_effects,
            claim_level=value.claim_level,
            status=value.status,
            reason_codes=value.reason_codes,
            evidence_set_id=value.evidence_set_id,
            estimate_time=value.estimate_time,
            created_at=value.created_at,
            supersedes_estimate_id=value.supersedes_estimate_id,
            logical_hash=logical_hash,
        )

    def exact_adjusted_estimate(
        self,
        estimate_id: str,
    ) -> P2AdjustedCapabilityEstimate:
        value = self._try_exact_adjusted_estimate(estimate_id)
        if value is None:
            raise P2DomainPersistenceError(
                "P2_ADJUSTED_ESTIMATE_NOT_FOUND",
                estimate_id,
            )
        return value


class SQLiteP2DomainRepository(_P2DomainRepository):
    """SQLite exact P2 domain adapter over adopted DB 1.7.0."""

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        object_store: LocalObjectStore | None = None,
    ) -> None:
        super().__init__(
            connection,
            postgres=False,
            object_store=object_store,
        )


class PostgreSQLP2DomainRepository(_P2DomainRepository):
    """PostgreSQL exact P2 domain adapter over adopted DB 1.7.0."""

    def __init__(
        self,
        connection: Any,
        *,
        object_store: LocalObjectStore | None = None,
    ) -> None:
        super().__init__(
            connection,
            postgres=True,
            object_store=object_store,
        )
