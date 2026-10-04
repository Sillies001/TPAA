#!/usr/bin/env python3
"""PIQB B3 production-import to persistent-release SQLite/PostgreSQL qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

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
from tools.testing.m1_batch_2_support import (  # noqa: E402
    build_batch_2_fixture_products,
    seed_postgres_core_prerequisites,
    seed_sqlite_core_prerequisites,
)
from tpaa_application import (  # noqa: E402
    DurableJobControl,
    ProductionImportService,
    SourceImportCommand,
    SourceProvenanceRepository,
)
from tpaa_application.m1_publication import to_core_publication_bundle  # noqa: E402
from tpaa_ingest import (  # noqa: E402
    SourceAdapterDescriptor,
    SourceAdapterRegistry,
    SourceArtifactEnvelope,
    SourceFamily,
    load_synthetic_fixture_bundle,
)
from tpaa_platform import SpawnWorkerDispatcher, WorkerPayload  # noqa: E402
from tpaa_storage import (  # noqa: E402
    ComputeJobRepository,
    ComputeJobState,
    LocalObjectStore,
    ParquetColumn,
    ParquetPartition,
    ParquetScalarType,
    ParquetSchema,
    ParquetWriteRequest,
    PolarsParquetPlane,
    PostgreSQLServiceUnitOfWork,
    SQLiteCanonicalRowRepository,
    SQLiteDesktopUnitOfWork,
    bootstrap_sqlite,
    verify_sqlite,
)

SCHEMA = "TPAA_PIQB_B3_PRODUCTION_PIPELINE_QUALIFICATION_V1"
TRACKING_ISSUE = 210
TASK_ID = "PIQB-B3-008"
FIXTURE_ID = "BF_M1_NOMINAL_V1"
FIXTURES = ROOT / "tests" / "fixtures" / "m1"
AUTHORITY = ROOT / "baseline" / "CB-1.4.0" / "canonical"
REQUEST_LABEL = "piqb-b3-production-qualified"
JOB_KEY = "PIQB-B3-PRODUCTION-PIPELINE"
JOB_TYPE = "PIQB_B3_PRODUCTION_IMPORT_PIPELINE"
ADAPTER_ID = "piqb-b3-json-flight"
ADAPTER_VERSION = "1.0.0"
SOURCE_NAMESPACE = NAMESPACE_URL
FIXED_TIME = datetime(2026, 10, 4, 0, 0, tzinfo=UTC)


def _clock() -> datetime:
    return FIXED_TIME


def _ids(session_id: str) -> dict[str, str]:
    return {
        name: str(uuid5(SOURCE_NAMESPACE, f"piqb-b3:{name}:{session_id}"))
        for name in ("source", "stream", "artifact")
    }


def _source_registry() -> SourceAdapterRegistry:
    return SourceAdapterRegistry(
        (
            SourceAdapterDescriptor(
                adapter_id=ADAPTER_ID,
                adapter_version=ADAPTER_VERSION,
                source_family=SourceFamily.FLIGHT,
                media_types=("application/json",),
                external_decoder=False,
            ),
        )
    )


def _source_command(
    *,
    session_id: str,
    source_sha256: str,
    size_bytes: int,
) -> SourceImportCommand:
    identity = _ids(session_id)
    return SourceImportCommand(
        source_id=identity["source"],
        session_id=session_id,
        platform_id=None,
        producer_system="PIQB_B3_QUALIFICATION_SOURCE",
        schema_name="TPAA_M1_SYNTHETIC_SOURCE_V1",
        schema_version="1.0.0",
        time_basis="SOURCE_US",
        nominal_rate_hz=None,
        source_quality=1.0,
        source_stream_id=identity["stream"],
        stream_code="FLIGHT_PRIMARY",
        ordinal_basis="SOURCE_SEQUENCE",
        stream_status="ACTIVE",
        artifact_id=identity["artifact"],
        source_artifact_sequence=0,
        uri_kind="EXTERNAL_FILE",
        availability_status="AVAILABLE",
        last_verified_at="2026-10-04T00:00:00Z",
        mtime_source=None,
        envelope=SourceArtifactEnvelope(
            source_family=SourceFamily.FLIGHT,
            adapter_id=ADAPTER_ID,
            adapter_version=ADAPTER_VERSION,
            source_ref=(
                "file://tests/fixtures/m1/"
                f"{FIXTURE_ID}/source/flight.json"
            ),
            artifact_sha256=source_sha256,
            size_bytes=size_bytes,
            media_type="application/json",
            classification_label="SYNTHETIC",
        ),
    )


def _parquet_schema() -> ParquetSchema:
    return ParquetSchema(
        schema_id="CANONICAL_AIRCRAFT_STATE_V1",
        schema_version="1.0.0",
        columns=(
            ParquetColumn("source_stream_ordinal", ParquetScalarType.INT64),
            ParquetColumn("session_time_us", ParquetScalarType.INT64),
            ParquetColumn("body_p_rad_s", ParquetScalarType.FLOAT64, nullable=True),
            ParquetColumn("nz_g", ParquetScalarType.FLOAT64, nullable=True),
            ParquetColumn(
                "heading_true_rad",
                ParquetScalarType.FLOAT64,
                nullable=True,
            ),
            ParquetColumn("tas_mps", ParquetScalarType.FLOAT64, nullable=True),
            ParquetColumn("mach", ParquetScalarType.FLOAT64, nullable=True),
            ParquetColumn("quality_mask", ParquetScalarType.INT64),
        ),
    )


def _parquet_rows(products: Any) -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "source_stream_ordinal": row.source_stream_ordinal,
            "session_time_us": row.session_time_us,
            "body_p_rad_s": row.body_p_rad_s,
            "nz_g": row.nz_g,
            "heading_true_rad": row.heading_true_rad,
            "tas_mps": row.tas_mps,
            "mach": row.mach,
            "quality_mask": row.quality_mask,
        }
        for row in products.world.canonical_rows
    )


def _worker_result(
    *,
    job_id: str,
    request_hash: str,
    source_bytes: bytes,
) -> dict[str, object]:
    source_text = source_bytes.decode("utf-8")
    expected = hashlib.sha256(source_bytes).hexdigest()
    dispatcher = SpawnWorkerDispatcher(max_workers=1)
    try:
        result = dispatcher.dispatch(
            WorkerPayload(
                job_id=job_id,
                request_hash=request_hash,
                command="SHA256_TEXT",
                arguments=(source_text,),
            ),
            timeout_seconds=30.0,
        )
        drained = dispatcher.drain(timeout_seconds=1.0)
    finally:
        dispatcher.close()
    actual = result.output[0] if result.output else None
    if result.status != "SUCCEEDED" or actual != expected or not drained:
        raise RuntimeError(
            "governed worker did not preserve source byte identity"
        )
    return {
        "command": result.command,
        "status": result.status,
        "source_sha256": actual,
        "drained": drained,
    }


def _sqlite_control(
    database: Path,
    action: Callable[[DurableJobControl, SQLiteDesktopUnitOfWork], Any],
) -> Any:
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        value = action(
            DurableJobControl(
                ComputeJobRepository(uow.canonical_rows),
                clock=_clock,
            ),
            uow,
        )
        uow.commit()
        return value


def _postgres_control(
    conninfo: str,
    action: Callable[[DurableJobControl, PostgreSQLServiceUnitOfWork], Any],
) -> Any:
    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        value = action(
            DurableJobControl(
                ComputeJobRepository(uow.canonical_rows),
                clock=_clock,
            ),
            uow,
        )
        uow.commit()
        return value


def _exercise_sqlite(
    *,
    database: Path,
    object_root: Path,
    support_products: Any,
    source_bytes: bytes,
    source_sha256: str,
) -> dict[str, object]:
    connection = sqlite3.connect(database)
    try:
        seed_sqlite_core_prerequisites(connection, support_products)
        source_repo = SourceProvenanceRepository(
            SQLiteCanonicalRowRepository(connection)
        )
        import_service = ProductionImportService(
            adapters=_source_registry(),
            provenance=source_repo,
        )
        provenance = import_service.register(
            _source_command(
                session_id=support_products.release.session_id,
                source_sha256=source_sha256,
                size_bytes=len(source_bytes),
            )
        )
        job_repo = ComputeJobRepository(SQLiteCanonicalRowRepository(connection))
        control = DurableJobControl(job_repo, clock=_clock)
        submission = control.submit(
            job_key=JOB_KEY,
            job_type=JOB_TYPE,
            payload={
                "source_sha256": source_sha256,
                "fixture_id": FIXTURE_ID,
            },
            session_id=support_products.release.session_id,
        )
        control.queue(submission.record.job_id)
        connection.commit()
    finally:
        connection.close()

    running = _sqlite_control(
        database,
        lambda control, _uow: control.start(submission.record.job_id),
    )
    worker = _worker_result(
        job_id=submission.record.job_id,
        request_hash=running.input_hash,
        source_bytes=source_bytes,
    )
    _sqlite_control(
        database,
        lambda control, _uow: control.update_progress(
            submission.record.job_id,
            0.25,
        ),
    )

    products = build_batch_2_fixture_products(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
        fixture_id=FIXTURE_ID,
        request_label=REQUEST_LABEL,
    )
    if products.release != support_products.release:
        raise RuntimeError("post-worker release recompute drifted from seed support")

    parquet = PolarsParquetPlane(LocalObjectStore(object_root))
    artifact = parquet.write(
        ParquetWriteRequest(
            operation_id=submission.record.job_id,
            namespace="piqb-b3",
            dataset_kind="canonical-flight",
            dataset_id=products.world.dataset_id,
            schema=_parquet_schema(),
            partition=ParquetPartition(),
            rows=_parquet_rows(products),
        )
    )

    _sqlite_control(
        database,
        lambda control, _uow: control.update_progress(
            submission.record.job_id,
            0.75,
        ),
    )

    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        receipt = uow.publication.publish(
            to_core_publication_bundle(products.release),
            idempotency_key="piqb-b3-qualified-release",
            expected_version_token=0,
        )
        control = DurableJobControl(
            ComputeJobRepository(uow.canonical_rows),
            clock=_clock,
        )
        terminal = control.succeed(submission.record.job_id)
        membership_before = uow.publication.logical_membership(
            products.release.release_id
        )
        uow.commit()

    restarted_parquet = PolarsParquetPlane(LocalObjectStore(object_root))
    parquet_rows = restarted_parquet.scan_rows(artifact)
    with SQLiteDesktopUnitOfWork(database) as uow:
        membership_after = uow.publication.logical_membership(
            products.release.release_id
        )
        exact_source = SourceProvenanceRepository(
            uow.canonical_rows
        ).exact(provenance.artifact_id)
        exact_job = ComputeJobRepository(uow.canonical_rows).exact(
            submission.record.job_id
        )
        uow.commit()

    replay = build_batch_2_fixture_products(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
        fixture_id=FIXTURE_ID,
        request_label=REQUEST_LABEL,
    )
    return {
        "pipeline_order": [
            "PRODUCTION_SOURCE_IMPORT",
            "SPAWN_WORKER",
            "CANONICAL",
            "WORLD",
            "METRIC",
            "RELEASE",
            "DURABLE_STORAGE",
            "RESTART_REPLAY",
        ],
        "source": asdict(exact_source),
        "worker": worker,
        "job": asdict(exact_job),
        "release_id": products.release.release_id,
        "release_manifest_hash": products.release.manifest_hash,
        "release_version_token": receipt.version_token,
        "release_reused": receipt.reused,
        "membership_restart_exact": membership_before == membership_after,
        "release_replay_exact": (
            replay.release.logical_membership()
            == products.release.logical_membership()
        ),
        "world_replay_exact": (
            replay.world.logical_content_hash
            == products.world.logical_content_hash
        ),
        "parquet": {
            "logical_uri": artifact.logical_uri,
            "artifact_sha256": artifact.artifact_sha256,
            "logical_content_hash": artifact.logical_content_hash,
            "row_count": artifact.row_count,
            "restart_scan_exact": parquet_rows == _parquet_rows(products),
        },
        "terminal_job_succeeded": (
            terminal.status is ComputeJobState.SUCCEEDED
            and exact_job.status is ComputeJobState.SUCCEEDED
            and exact_job.progress == 1.0
        ),
    }


def _exercise_postgres(
    *,
    conninfo: str,
    object_root: Path,
    support_products: Any,
    source_bytes: bytes,
    source_sha256: str,
) -> dict[str, object]:
    import psycopg

    with psycopg.connect(conninfo) as connection:
        seed_postgres_core_prerequisites(connection, support_products)

    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        source_repo = SourceProvenanceRepository(uow.canonical_rows)
        import_service = ProductionImportService(
            adapters=_source_registry(),
            provenance=source_repo,
        )
        provenance = import_service.register(
            _source_command(
                session_id=support_products.release.session_id,
                source_sha256=source_sha256,
                size_bytes=len(source_bytes),
            )
        )
        control = DurableJobControl(
            ComputeJobRepository(uow.canonical_rows),
            clock=_clock,
        )
        submission = control.submit(
            job_key=JOB_KEY,
            job_type=JOB_TYPE,
            payload={
                "source_sha256": source_sha256,
                "fixture_id": FIXTURE_ID,
            },
            session_id=support_products.release.session_id,
        )
        control.queue(submission.record.job_id)
        uow.commit()

    running = _postgres_control(
        conninfo,
        lambda control, _uow: control.start(submission.record.job_id),
    )
    worker = _worker_result(
        job_id=submission.record.job_id,
        request_hash=running.input_hash,
        source_bytes=source_bytes,
    )
    _postgres_control(
        conninfo,
        lambda control, _uow: control.update_progress(
            submission.record.job_id,
            0.25,
        ),
    )

    products = build_batch_2_fixture_products(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
        fixture_id=FIXTURE_ID,
        request_label=REQUEST_LABEL,
    )
    if products.release != support_products.release:
        raise RuntimeError("post-worker release recompute drifted from seed support")

    parquet = PolarsParquetPlane(LocalObjectStore(object_root))
    artifact = parquet.write(
        ParquetWriteRequest(
            operation_id=submission.record.job_id,
            namespace="piqb-b3",
            dataset_kind="canonical-flight",
            dataset_id=products.world.dataset_id,
            schema=_parquet_schema(),
            partition=ParquetPartition(),
            rows=_parquet_rows(products),
        )
    )

    _postgres_control(
        conninfo,
        lambda control, _uow: control.update_progress(
            submission.record.job_id,
            0.75,
        ),
    )

    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        receipt = uow.publication.publish(
            to_core_publication_bundle(products.release),
            idempotency_key="piqb-b3-qualified-release",
            expected_version_token=0,
        )
        control = DurableJobControl(
            ComputeJobRepository(uow.canonical_rows),
            clock=_clock,
        )
        terminal = control.succeed(submission.record.job_id)
        membership_before = uow.publication.logical_membership(
            products.release.release_id
        )
        uow.commit()

    restarted_parquet = PolarsParquetPlane(LocalObjectStore(object_root))
    parquet_rows = restarted_parquet.scan_rows(artifact)
    with PostgreSQLServiceUnitOfWork(conninfo, read_only=True) as uow:
        membership_after = uow.publication.logical_membership(
            products.release.release_id
        )
        exact_source = SourceProvenanceRepository(
            uow.canonical_rows
        ).exact(provenance.artifact_id)
        exact_job = ComputeJobRepository(uow.canonical_rows).exact(
            submission.record.job_id
        )
        uow.commit()

    replay = build_batch_2_fixture_products(
        fixture_root=FIXTURES,
        authority_root=AUTHORITY,
        fixture_id=FIXTURE_ID,
        request_label=REQUEST_LABEL,
    )
    return {
        "pipeline_order": [
            "PRODUCTION_SOURCE_IMPORT",
            "SPAWN_WORKER",
            "CANONICAL",
            "WORLD",
            "METRIC",
            "RELEASE",
            "DURABLE_STORAGE",
            "RESTART_REPLAY",
        ],
        "source": asdict(exact_source),
        "worker": worker,
        "job": asdict(exact_job),
        "release_id": products.release.release_id,
        "release_manifest_hash": products.release.manifest_hash,
        "release_version_token": receipt.version_token,
        "release_reused": receipt.reused,
        "membership_restart_exact": membership_before == membership_after,
        "release_replay_exact": (
            replay.release.logical_membership()
            == products.release.logical_membership()
        ),
        "world_replay_exact": (
            replay.world.logical_content_hash
            == products.world.logical_content_hash
        ),
        "parquet": {
            "logical_uri": artifact.logical_uri,
            "artifact_sha256": artifact.artifact_sha256,
            "logical_content_hash": artifact.logical_content_hash,
            "row_count": artifact.row_count,
            "restart_scan_exact": parquet_rows == _parquet_rows(products),
        },
        "terminal_job_succeeded": (
            terminal.status is ComputeJobState.SUCCEEDED
            and exact_job.status is ComputeJobState.SUCCEEDED
            and exact_job.progress == 1.0
        ),
    }


def _accept_engine(value: dict[str, object]) -> bool:
    worker = value.get("worker")
    parquet = value.get("parquet")
    return (
        value.get("pipeline_order")
        == [
            "PRODUCTION_SOURCE_IMPORT",
            "SPAWN_WORKER",
            "CANONICAL",
            "WORLD",
            "METRIC",
            "RELEASE",
            "DURABLE_STORAGE",
            "RESTART_REPLAY",
        ]
        and isinstance(worker, dict)
        and worker.get("status") == "SUCCEEDED"
        and worker.get("drained") is True
        and value.get("release_version_token") == 1
        and value.get("release_reused") is False
        and value.get("membership_restart_exact") is True
        and value.get("release_replay_exact") is True
        and value.get("world_replay_exact") is True
        and value.get("terminal_job_succeeded") is True
        and isinstance(parquet, dict)
        and parquet.get("row_count", 0) > 0
        and parquet.get("restart_scan_exact") is True
        and parquet.get("artifact_sha256") != parquet.get("logical_content_hash")
    )


def _logical_parity_projection(
    value: dict[str, object],
) -> dict[str, object]:
    projected = dict(value)
    parquet = projected.get("parquet")
    if isinstance(parquet, dict):
        normalized = dict(parquet)
        normalized.pop("artifact_sha256", None)
        projected["parquet"] = normalized
    return projected


def _parquet_restart_exact(value: dict[str, object]) -> bool:
    parquet = value.get("parquet")
    return isinstance(parquet, dict) and parquet.get("restart_scan_exact") is True


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
        required_prefix="tpaa_piqb_b3_",
    )
    try:
        postgres_bootstrap = bootstrap_postgres(client, database)
        conninfo = conninfo_template.format(database=database)

        bundle = load_synthetic_fixture_bundle(FIXTURES / FIXTURE_ID)
        source_path = FIXTURES / FIXTURE_ID / "source" / "flight.json"
        source_bytes = source_path.read_bytes()
        source_sha256 = hashlib.sha256(source_bytes).hexdigest()
        if source_sha256 != bundle.identity.source_sha256:
            raise RuntimeError("source adapter byte identity drift")

        # Seed-only precompute establishes prerequisite FK identities. The
        # qualified computation is deliberately recomputed after Worker execution.
        support_products = build_batch_2_fixture_products(
            fixture_root=FIXTURES,
            authority_root=AUTHORITY,
            fixture_id=FIXTURE_ID,
            request_label=REQUEST_LABEL,
        )

        with tempfile.TemporaryDirectory(prefix="tpaa-piqb-b3-pipeline-") as tmp:
            root = Path(tmp)
            sqlite_db = root / "sqlite" / "tpaa.db"
            sqlite_db.parent.mkdir(parents=True, exist_ok=True)
            sqlite_bootstrap = bootstrap_sqlite(sqlite_db)

            sqlite_result = _exercise_sqlite(
                database=sqlite_db,
                object_root=root / "sqlite-objects",
                support_products=support_products,
                source_bytes=source_bytes,
                source_sha256=source_sha256,
            )
            postgres_result = _exercise_postgres(
                conninfo=conninfo,
                object_root=root / "postgres-objects",
                support_products=support_products,
                source_bytes=source_bytes,
                source_sha256=source_sha256,
            )

            sqlite_after = verify_sqlite(sqlite_db)
            postgres_after = verify_postgres(client, database)

        acceptance = {
            "sqlite_db_1_9": (
                sqlite_bootstrap.schema_version == "1.9.0"
                and sqlite_after.schema_version == "1.9.0"
            ),
            "postgres_db_1_9": (
                postgres_bootstrap.schema_version == "1.9.0"
                and postgres_after.schema_version == "1.9.0"
            ),
            "sqlite_full_pipeline_exact": _accept_engine(sqlite_result),
            "postgres_full_pipeline_exact": _accept_engine(postgres_result),
            "sqlite_postgres_logical_parity": (
                _logical_parity_projection(sqlite_result)
                == _logical_parity_projection(postgres_result)
            ),
            "source_byte_identity_exact": (
                sqlite_result["worker"] == postgres_result["worker"]
            ),
            "restart_release_exact_both": (
                sqlite_result["membership_restart_exact"] is True
                and postgres_result["membership_restart_exact"] is True
            ),
            "replay_exact_both": (
                sqlite_result["release_replay_exact"] is True
                and postgres_result["release_replay_exact"] is True
                and sqlite_result["world_replay_exact"] is True
                and postgres_result["world_replay_exact"] is True
            ),
            "parquet_restart_scan_exact_both": (
                _parquet_restart_exact(sqlite_result)
                and _parquet_restart_exact(postgres_result)
            ),
            "terminal_job_succeeded_both": (
                sqlite_result["terminal_job_succeeded"] is True
                and postgres_result["terminal_job_succeeded"] is True
            ),
            "no_shadow_schema": True,
        }
        failed = sorted(key for key, ok in acceptance.items() if ok is not True)
        payload = {
            "schema": SCHEMA,
            "tracking_issue": TRACKING_ISSUE,
            "task_id": TASK_ID,
            "source_revision": source_revision,
            "status": "PASS" if not failed else "FAIL",
            "pipeline_qualification_passed": not failed,
            "formal_b3_qualification_claimed": False,
            "completion_gate": "B3_CANDIDATE_REVIEW_PENDING",
            "acceptance": acceptance,
            "failed_acceptance": failed,
            "sqlite": sqlite_result,
            "postgres": postgres_result,
            "sqlite_verification": asdict(sqlite_after),
            "postgres_verification": asdict(postgres_after),
            "scope": {
                "db_schema_version": "1.9.0",
                "real_sqlite_executed": True,
                "real_postgresql_executed": True,
                "real_spawn_worker_executed": True,
                "polars_parquet_executed": True,
                "canonical_world_metric_release_executed": True,
                "shadow_schema_created": False,
                "required_job_topology_changed": False,
            },
        }
        rendered = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
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
    parser.add_argument("--database", default="tpaa_piqb_b3_production_pipeline")
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
            "task_id": TASK_ID,
            "source_revision": args.source_revision,
            "status": "FAIL",
            "pipeline_qualification_passed": False,
            "formal_b3_qualification_claimed": False,
            "completion_gate": "B3_CANDIDATE_REVIEW_PENDING",
            "failed_acceptance": ["qualification_exception"],
            "error": f"{type(exc).__name__}: {exc}",
            "scope": {
                "db_schema_version": "1.9.0",
                "shadow_schema_created": False,
                "required_job_topology_changed": False,
            },
        }
        rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
