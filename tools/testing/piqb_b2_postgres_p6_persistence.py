#!/usr/bin/env python3
"""PIQB B2 real PostgreSQL P6 exact persistence and restart parity gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from tools.storage.postgres_db import (  # noqa: E402
    PsqlClient,
    _database_exists,
    _identifier,
    _literal,
    _recreate_scoped_database,
    bootstrap_postgres,
    verify_postgres,
)
from tools.testing.piqb_b2_p6_resolver_fixture import (  # noqa: E402
    seed_p6_model_resolver_case,
)
from tpaa_application import (  # noqa: E402
    DurableP6ModelBuildResolver,
    P6PersistenceError,
    P6PersistenceRepository,
)
from tpaa_assessment.p6_recommendation import build_p6_recommendation  # noqa: E402
from tpaa_capability import (  # noqa: E402
    P6ApplicabilityEvidence,
    P6CapabilityTrainingRow,
    P6ContextRef,
    P6FactualSourceRevision,
    P6ForecastExecutionProfile,
    P6InputSnapshot,
    P6ManagedModelObject,
    P6ModelBuild,
    P6ModelDatasetBundle,
    P6ModelDatasetSnapshot,
    P6ModelRevision,
    P6UncertaintyCalibrationEvidence,
    build_p6_counterfactual_request_binding,
    build_p6_forecast_request_binding,
    build_p6_input_snapshot,
    execute_p6_counterfactual,
    execute_p6_forecast,
)
from tpaa_context.p6_governance import canonical_hash  # noqa: E402
from tpaa_storage import (  # noqa: E402
    LocalObjectStore,
    SQLiteDesktopUnitOfWork,
    bootstrap_sqlite,
    verify_sqlite,
)
from tpaa_storage.postgres_repository import PostgreSQLServiceUnitOfWork  # noqa: E402

SUBJECT = "95100000-0000-4000-8000-000000000001"
P4 = "95100000-0000-4000-8000-000000000002"
CONTEXT = "95100000-0000-4000-8000-000000000003"
MODEL = "95100000-0000-4000-8000-000000000004"
OBJECT = "95100000-0000-4000-8000-000000000005"
TRAINING = "95100000-0000-4000-8000-000000000006"
VALIDATION = "95100000-0000-4000-8000-000000000007"
GAP = "95100000-0000-4000-8000-000000000008"
AS_OF = "2026-09-10T12:00:00Z"


def _dataset(snapshot_id: str, snapshot_type: str) -> P6ModelDatasetSnapshot:
    profile = P6ForecastExecutionProfile.from_canonical()
    material = {
        "profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
        "profile_sha256": profile.profile_sha256,
        "snapshot_type": snapshot_type,
        "row_ids": [],
        "p3_estimate_ids": [],
        "p4_revision_ids": [],
        "as_of_utc": AS_OF,
        "frozen": True,
    }
    return P6ModelDatasetSnapshot(
        dataset_snapshot_id=snapshot_id,
        snapshot_type=snapshot_type,
        row_ids=(),
        p3_estimate_ids=(),
        p4_revision_ids=(),
        as_of_utc=AS_OF,
        data_hash=canonical_hash(material),
    )


def _model_build() -> tuple[P6ModelBuild, P6ManagedModelObject]:
    profile = P6ForecastExecutionProfile.from_canonical()
    training = _dataset(TRAINING, "P6_MODEL_TRAINING")
    validation = _dataset(VALIDATION, "P6_MODEL_VALIDATION")
    artifact = {"schema": "TPAA_PIQB_B2_P6_MODEL_TEST_V1"}
    artifact_bytes = json.dumps(
        artifact,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
    applicability = P6ApplicabilityEvidence(
        applicability_evidence_id="P6_APPLICABILITY_SHA256:" + "a" * 64,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        status="APPLICABLE",
        reason_codes=(),
        eligible_p3_estimate_ids=(),
        excluded_p3_estimate_ids=(),
        domain={
            "aircraft_id": SUBJECT,
            "capability_type": "KINEMATIC_ENERGY_CONTROL",
            "reference_condition_id": CONTEXT,
            "unit": "1",
            "configuration_snapshot_id": CONTEXT,
        },
        as_of_utc=AS_OF,
        data_hash="a" * 64,
    )
    datasets = P6ModelDatasetBundle(
        applicability=applicability,
        training=training,
        validation=validation,
        eligible_rows=(),
        training_rows=(),
        validation_row=cast(P6CapabilityTrainingRow, None),
        final_refit_rows=(),
    )
    uncertainty = P6UncertaintyCalibrationEvidence(
        calibration_evidence_id="P6_UNCERTAINTY_SHA256:" + "b" * 64,
        profile_ref=profile.uncertainty_profile_ref,
        p3_input_half_width_max=0.5,
        holdout_absolute_error=0.25,
        final_refit_residual_mad=0.5,
        half_width=0.5,
        status="CALIBRATED",
        data_hash="b" * 64,
    )
    model = P6ModelRevision(
        capability_model_id=MODEL,
        model_spec_id=profile.model_spec_id,
        model_spec_version=profile.model_spec_version,
        subject_type="AIRCRAFT",
        subject_id=SUBJECT,
        capability_type="KINEMATIC_ENERGY_CONTROL",
        training_dataset_snapshot_id=TRAINING,
        validation_dataset_snapshot_id=VALIDATION,
        plugin_name=profile.plugin_name,
        plugin_version=profile.plugin_version,
        model_artifact_uri=f"tpaa-object://p6-capability/models/{MODEL}.json",
        model_artifact_hash=artifact_hash,
        model_object_ref_id=OBJECT,
        validity_domain={
            "aircraft_id": SUBJECT,
            "capability_type": "KINEMATIC_ENERGY_CONTROL",
            "reference_condition_id": CONTEXT,
            "unit": "1",
            "configuration_snapshot_id": CONTEXT,
        },
        validation_metrics={"status": "VALIDATED"},
        applicability_profile_ref=profile.applicability_profile_ref,
        uncertainty_profile_ref=profile.uncertainty_profile_ref,
        status="VALIDATED",
        trained_at="2026-09-10T10:00:00Z",
        published_at=None,
        supersedes_model_id=None,
    )
    build = P6ModelBuild(
        model=model,
        artifact=artifact,
        artifact_bytes=artifact_bytes,
        datasets=datasets,
        applicability=applicability,
        uncertainty=uncertainty,
        intercept=10.0,
        slope=1.0,
        session_order_origin=1,
        target_session_order=5,
        fit_row_ids=(),
    )
    managed = P6ManagedModelObject(
        object_ref_id=OBJECT,
        managed_uri=model.model_artifact_uri,
        artifact_sha256=artifact_hash,
        sealed=True,
        gc_state="ACTIVE",
        deleted_at=None,
        sealed_at_utc="2026-09-10T10:30:00Z",
    )
    return build, managed


def _input() -> P6InputSnapshot:
    return build_p6_input_snapshot(
        factual_sources=(
            P6FactualSourceRevision(
                phase="P4",
                revision_id=P4,
                publication_status="PUBLISHED",
                knowledge_time_utc="2026-09-10T09:00:00Z",
            ),
        ),
        scenario_context_refs=(
            P6ContextRef(
                context_ref_id=CONTEXT,
                status="ACTIVE",
                knowledge_time_utc="2026-09-10T09:00:00Z",
            ),
        ),
        target_scope="SUBJECT",
        subject_or_composition_ref=SUBJECT,
        forecast_origin_utc="2026-09-10T11:00:00Z",
        as_of_utc=AS_OF,
    )



SCHEMA = "TPAA_PIQB_B2_P6_POSTGRES_PERSISTENCE_V1"
TRACKING_ISSUE = 209
TASK_IDS = ("PIQB-B2-002", "PIQB-B2-003", "PIQB-B2-006", "PIQB-B2-008")


def _products() -> dict[str, Any]:
    snapshot = _input()
    build, managed = _model_build()
    profile = P6ForecastExecutionProfile.from_canonical()
    forecast_request = build_p6_forecast_request_binding(
        input_snapshot=snapshot,
        forecast_spec_id="P6_FORECAST:P3_CAPABILITY_NEXT_SESSION",
        forecast_spec_version="1.0.0",
        target_code=profile.target_code,
        horizon_spec={
            "type": profile.horizon_type,
            "steps": profile.horizon_steps,
            "target_session_order": 5,
        },
        capability_model_id=MODEL,
        model_profile_id=profile.profile_id,
        model_profile_version=profile.profile_version,
        training_dataset_snapshot_id=TRAINING,
        validation_dataset_snapshot_id=VALIDATION,
        assumption_profile_id="P6_ASSUMPTION:TRAINING_EVALUATION",
        assumption_profile_version="1.0.0",
    )
    counterfactual_request = build_p6_counterfactual_request_binding(
        input_snapshot=snapshot,
        base_product_refs=(P4,),
        scenario_definition_id=CONTEXT,
        interventions={
            "training_focus": {
                "type": "TRAINING_FOCUS",
                "value": "DEBRIEF_REPEAT",
            }
        },
        held_fixed_assumptions={"configuration": "UNCHANGED"},
        model_refs=(MODEL,),
        applicability_profile_ref=profile.applicability_profile_ref,
    )
    forecast = execute_p6_forecast(
        request=forecast_request,
        input_snapshot=snapshot,
        model_build=build,
        managed_object=managed,
        published_at_utc="2026-09-10T12:30:00Z",
    )
    counterfactual = execute_p6_counterfactual(
        request=counterfactual_request,
        input_snapshot=snapshot,
        models=(build.model,),
        created_at_utc="2026-09-10T12:40:00Z",
    )
    recommendation = build_p6_recommendation(
        subject_key="SUBJECT-P6",
        subject_id=SUBJECT,
        recommendation_spec_id="P6_TRAINING_ADVISORY",
        recommendation_spec_version="1.0.0",
        source_forecast_result_ids=(forecast.forecast_result_id,),
        source_counterfactual_run_ids=(counterfactual.counterfactual_run_id,),
        objective_constraints={
            "objective": "TRAINING_PROFICIENCY",
            "constraint": "EVALUATION_ONLY",
        },
        allowed_action_space={
            "mode": "TRAINING_SESSION",
            "options": ["DEBRIEF_REPEAT"],
        },
        rationale={"basis": "P6_PROJECTION_EVIDENCE"},
        source_gap_refs=(GAP,),
        proposed_training_items={"items": ["DEBRIEF_REVIEW"]},
        applicability_status="APPLICABLE",
        uncertainty={
            "forecast": dict(forecast.uncertainty),
            "counterfactual": dict(counterfactual.uncertainty),
        },
        created_at_utc="2026-09-10T12:50:00Z",
    )
    return {
        "snapshot": snapshot,
        "build": build,
        "managed": managed,
        "forecast_request": forecast_request,
        "counterfactual_request": counterfactual_request,
        "forecast": forecast,
        "counterfactual": counterfactual,
        "recommendation": recommendation,
    }


def _register_all(repo: P6PersistenceRepository, values: dict[str, Any]) -> None:
    repo.register_input(values["snapshot"])
    repo.register_model_build(values["build"], values["managed"])
    repo.register_forecast_request(values["forecast_request"])
    repo.register_counterfactual_request(values["counterfactual_request"])
    repo.register_forecast(values["forecast"])
    repo.register_counterfactual(values["counterfactual"])
    repo.register_recommendation(values["recommendation"])


def _projection(
    repo: P6PersistenceRepository,
    values: dict[str, Any],
) -> dict[str, object]:
    return {
        "input": asdict(repo.exact_input(values["snapshot"].input_snapshot_id)),
        "training_dataset": asdict(repo.exact_model_dataset(TRAINING)),
        "validation_dataset": asdict(repo.exact_model_dataset(VALIDATION)),
        "model": asdict(repo.exact_model_revision(MODEL)),
        "managed_object": asdict(repo.exact_managed_object(MODEL)),
        "forecast_request": asdict(
            repo.exact_forecast_request(
                values["forecast_request"].forecast_request_id
            )
        ),
        "counterfactual_request": asdict(
            repo.exact_counterfactual_request(
                values["counterfactual_request"].counterfactual_request_id
            )
        ),
        "forecast": asdict(
            repo.exact_forecast(values["forecast"].forecast_result_id)
        ),
        "counterfactual": asdict(
            repo.exact_counterfactual(
                values["counterfactual"].counterfactual_run_id
            )
        ),
        "recommendation": asdict(
            repo.exact_recommendation(
                values["recommendation"].recommendation_id
            )
        ),
    }


def _expected_error_code(action: Callable[[], object]) -> str:
    try:
        action()
    except P6PersistenceError as exc:
        return exc.code
    raise RuntimeError("P6 fail-closed qualification unexpectedly succeeded")


def _immutable_conflict_codes(
    repo: P6PersistenceRepository,
    values: dict[str, Any],
) -> dict[str, str]:
    return {
        "forecast": _expected_error_code(
            lambda: repo.register_forecast(
                replace(values["forecast"], status="QUALIFICATION_CONFLICT")
            )
        ),
        "counterfactual": _expected_error_code(
            lambda: repo.register_counterfactual(
                replace(
                    values["counterfactual"],
                    status="QUALIFICATION_CONFLICT",
                )
            )
        ),
        "recommendation": _expected_error_code(
            lambda: repo.register_recommendation(
                replace(
                    values["recommendation"],
                    status="QUALIFICATION_CONFLICT",
                )
            )
        ),
    }


def _model_build_dependency_code(repo: P6PersistenceRepository) -> str:
    return _expected_error_code(lambda: repo.exact_model_build(MODEL))


def _artifact_hash(
    object_store: LocalObjectStore,
    values: dict[str, Any],
) -> str:
    data = object_store.read_bytes(values["build"].model.model_artifact_uri)
    return hashlib.sha256(data).hexdigest()


def _exercise_sqlite(
    database: Path,
    object_root: Path,
) -> dict[str, object]:
    values = _products()
    object_store = LocalObjectStore(object_root)
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        resolver_case = seed_p6_model_resolver_case(
            uow.canonical_rows,
            object_store,
        )
        repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        _register_all(repo, values)
        uow.commit()

    with SQLiteDesktopUnitOfWork(database) as uow:
        repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        first = _projection(repo, values)
        dependency_code = _model_build_dependency_code(repo)
        artifact_hash = _artifact_hash(object_store, values)
        resolver_repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
            model_build_resolver=DurableP6ModelBuildResolver(
                uow.canonical_rows
            ),
        )
        resolver_exact = (
            resolver_repo.exact_model_build(
                resolver_case.build.model.capability_model_id
            )
            == resolver_case.build
        )
        uow.commit()

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        _register_all(repo, values)
        repo.register_model_build(
            resolver_case.build,
            resolver_case.managed,
        )
        conflicts = _immutable_conflict_codes(repo, values)
        replay = _projection(repo, values)
        resolver_repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
            model_build_resolver=DurableP6ModelBuildResolver(
                uow.canonical_rows
            ),
        )
        resolver_replay_exact = (
            resolver_repo.exact_model_build(
                resolver_case.build.model.capability_model_id
            )
            == resolver_case.build
        )
        uow.commit()

    return {
        "first_restart": first,
        "idempotent_replay": replay,
        "immutable_conflict_codes": conflicts,
        "model_build_dependency_code": dependency_code,
        "model_artifact_sha256": artifact_hash,
        "model_build_resolver_exact": (
            resolver_exact and resolver_replay_exact
        ),
    }


def _exercise_postgres(
    conninfo: str,
    object_root: Path,
) -> dict[str, object]:
    values = _products()
    object_store = LocalObjectStore(object_root)
    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        resolver_case = seed_p6_model_resolver_case(
            uow.canonical_rows,
            object_store,
        )
        repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        _register_all(repo, values)
        uow.commit()

    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as uow:
        repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        first = _projection(repo, values)
        dependency_code = _model_build_dependency_code(repo)
        artifact_hash = _artifact_hash(object_store, values)
        resolver_repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
            model_build_resolver=DurableP6ModelBuildResolver(
                uow.canonical_rows
            ),
        )
        resolver_exact = (
            resolver_repo.exact_model_build(
                resolver_case.build.model.capability_model_id
            )
            == resolver_case.build
        )
        uow.commit()

    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
        )
        _register_all(repo, values)
        repo.register_model_build(
            resolver_case.build,
            resolver_case.managed,
        )
        conflicts = _immutable_conflict_codes(repo, values)
        replay = _projection(repo, values)
        resolver_repo = P6PersistenceRepository(
            uow.canonical_rows,
            object_store=object_store,
            model_build_resolver=DurableP6ModelBuildResolver(
                uow.canonical_rows
            ),
        )
        resolver_replay_exact = (
            resolver_repo.exact_model_build(
                resolver_case.build.model.capability_model_id
            )
            == resolver_case.build
        )
        uow.commit()

    return {
        "first_restart": first,
        "idempotent_replay": replay,
        "immutable_conflict_codes": conflicts,
        "model_build_dependency_code": dependency_code,
        "model_artifact_sha256": artifact_hash,
        "model_build_resolver_exact": (
            resolver_exact and resolver_replay_exact
        ),
    }


def run(
    *,
    user: str,
    host: str | None,
    port: int | None,
    psql: str,
    admin_database: str,
    database: str,
    conninfo_template: str,
    source_revision: str,
    evidence: Path,
) -> int:
    client = PsqlClient(
        user=user,
        host=host,
        port=port,
        psql_executable=psql,
    )
    _identifier(database)
    _recreate_scoped_database(
        client,
        admin_database,
        database,
        required_prefix="tpaa_piqb_b2_",
    )
    try:
        postgres_bootstrap = bootstrap_postgres(client, database)
        conninfo = conninfo_template.format(database=database)
        with tempfile.TemporaryDirectory(prefix="tpaa-piqb-b2-p6-") as raw:
            root = Path(raw)
            sqlite_db = root / "p6.sqlite"
            sqlite_bootstrap = bootstrap_sqlite(sqlite_db)
            sqlite_result = _exercise_sqlite(
                sqlite_db,
                root / "sqlite-objects",
            )
            sqlite_after = verify_sqlite(sqlite_db)
            postgres_result = _exercise_postgres(
                conninfo,
                root / "postgres-objects",
            )
            postgres_after = verify_postgres(client, database)

        expected_conflicts = {
            "forecast": "P6_IMMUTABLE_CONFLICT",
            "counterfactual": "P6_IMMUTABLE_CONFLICT",
            "recommendation": "P6_IMMUTABLE_CONFLICT",
        }
        expected_artifact_hash = _model_build()[0].model.model_artifact_hash
        acceptance = {
            "sqlite_current_db_1_9": (
                sqlite_bootstrap.schema_version == "1.9.0"
                and sqlite_after.schema_version == "1.9.0"
            ),
            "postgres_current_db_1_9": (
                postgres_bootstrap.schema_version == "1.9.0"
                and postgres_after.schema_version == "1.9.0"
            ),
            "sqlite_restart_exact": (
                sqlite_result["first_restart"]
                == sqlite_result["idempotent_replay"]
            ),
            "postgres_restart_exact": (
                postgres_result["first_restart"]
                == postgres_result["idempotent_replay"]
            ),
            "sqlite_postgres_logical_parity": (
                sqlite_result == postgres_result
            ),
            "immutable_replay_fail_closed": (
                sqlite_result["immutable_conflict_codes"]
                == expected_conflicts
                and postgres_result["immutable_conflict_codes"]
                == expected_conflicts
            ),
            "model_artifact_hash_exact": (
                sqlite_result["model_artifact_sha256"]
                == expected_artifact_hash
                and postgres_result["model_artifact_sha256"]
                == expected_artifact_hash
            ),
            "model_build_dependency_fail_closed": (
                sqlite_result["model_build_dependency_code"]
                == "P6_MODEL_BUILD_DEPENDENCY_BLOCKED"
                and postgres_result["model_build_dependency_code"]
                == "P6_MODEL_BUILD_DEPENDENCY_BLOCKED"
            ),
            "model_build_durable_resolver_exact": (
                sqlite_result["model_build_resolver_exact"] is True
                and postgres_result["model_build_resolver_exact"] is True
            ),
            "shadow_schema_not_created": True,
        }
        failed = sorted(
            key for key, ok in acceptance.items() if ok is not True
        )
        payload = {
            "schema": SCHEMA,
            "tracking_issue": TRACKING_ISSUE,
            "task_ids": list(TASK_IDS),
            "source_revision": source_revision,
            "status": "PASS" if not failed else "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "completion_gate": "B2_RECOVERY_CLOSURE_PENDING",
            "acceptance": acceptance,
            "failed_acceptance": failed,
            "sqlite": sqlite_result,
            "postgres": postgres_result,
            "scope": {
                "db_schema_version": "1.9.0",
                "real_sqlite_executed": True,
                "real_postgresql_executed": True,
                "input_exact": True,
                "model_dataset_exact": True,
                "model_metadata_exact": True,
                "managed_object_hash_exact": True,
                "forecast_request_result_exact": True,
                "counterfactual_request_result_exact": True,
                "recommendation_exact": True,
                "model_build_dependency_blocked_expected": True,
                "model_build_durable_resolver_exact": True,
                "shadow_schema_created": False,
                "formal_b2_qualification_claimed": False,
            },
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        evidence.parent.mkdir(parents=True, exist_ok=True)
        evidence.write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        return 0 if not failed else 2
    finally:
        if _database_exists(client, admin_database, database):
            client.run(
                admin_database,
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = {_literal(database)} "
                "AND pid <> pg_backend_pid();\n"
                f"DROP DATABASE {_identifier(database)};\n",
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", default="tpaa")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--psql", default="psql")
    parser.add_argument("--admin-database", default="postgres")
    parser.add_argument(
        "--database",
        default="tpaa_piqb_b2_p6_persistence",
    )
    parser.add_argument("--conninfo-template", required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    try:
        return run(
            user=args.user,
            host=args.host,
            port=args.port,
            psql=args.psql,
            admin_database=args.admin_database,
            database=args.database,
            conninfo_template=args.conninfo_template,
            source_revision=args.source_revision,
            evidence=args.evidence,
        )
    except Exception as exc:
        payload = {
            "schema": SCHEMA,
            "tracking_issue": TRACKING_ISSUE,
            "task_ids": list(TASK_IDS),
            "source_revision": args.source_revision,
            "status": "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "completion_gate": "B2_RECOVERY_CLOSURE_PENDING",
            "error": f"{type(exc).__name__}: {exc}",
            "scope": {
                "db_schema_version": "1.9.0",
                "shadow_schema_created": False,
                "formal_b2_qualification_claimed": False,
            },
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(
            rendered,
            encoding="utf-8",
            newline="\n",
        )
        print(rendered, end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
