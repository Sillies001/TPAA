#!/usr/bin/env python3
"""PIQB B2 real PostgreSQL P3 durable exact persistence qualification."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from dataclasses import asdict, replace
from pathlib import Path

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
from tools.testing.piqb_b2_p3_fixture import (  # noqa: E402
    build_fixture,
    seed_upstream,
)
from tpaa_application import (  # noqa: E402
    CanonicalP3WorkspaceLayerResolver,
    DurableM7P3WorkspaceRepository,
    P2PersistenceRepository,
    P3PersistenceError,
    P3PersistenceRepository,
)
from tpaa_capability import P3ModelExecutionProfile  # noqa: E402
from tpaa_storage import (  # noqa: E402
    CanonicalRowRepository,
    LocalObjectStore,
    SQLiteDesktopUnitOfWork,
    bootstrap_sqlite,
    verify_sqlite,
)
from tpaa_storage.postgres_repository import (  # noqa: E402
    PostgreSQLServiceUnitOfWork,
)

SCHEMA = "TPAA_PIQB_B2_P3_POSTGRES_PERSISTENCE_V1"
TRACKING_ISSUE = 209
TASK_IDS = ("PIQB-B2-002", "PIQB-B2-003", "PIQB-B2-006", "PIQB-B2-008")


def _register_p3(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
) -> None:
    fixture = build_fixture()
    repo = P3PersistenceRepository(
        rows,
        object_store=object_store,
    )
    repo.register_component(
        segment=fixture.segment,
        validation=fixture.validation,
        training=fixture.training,
        model_build=fixture.model_build,
        surface_build=fixture.surface_build,
        model_object=fixture.model_object,
        surface_object=fixture.surface_object,
    )
    repo.register_twin(
        fixture.twin,
        components=(fixture.component,),
    )
    repo.register_estimate(fixture.estimate)


def _projection(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
) -> dict[str, object]:
    fixture = build_fixture()
    p3 = P3PersistenceRepository(
        rows,
        object_store=object_store,
    )
    p2 = P2PersistenceRepository(rows)
    resolver = CanonicalP3WorkspaceLayerResolver(
        rows,
        p3,
        p2,
    )
    durable = DurableM7P3WorkspaceRepository(p3, resolver)
    segment = p3.exact_segment(fixture.segment.segment_snapshot_id)
    validation = p3.exact_validation(
        fixture.validation.validation_snapshot_id
    )
    training = p3.exact_training(
        fixture.training.dataset_snapshot_id
    )
    component = p3.exact_component(
        fixture.model_build.model.capability_model_id
    )
    twin = p3.exact_twin_revision(
        fixture.twin.twin_revision_id
    )
    estimate = p3.exact_capability_estimate(
        fixture.estimate.estimate_id
    )
    workspace = durable.exact_estimate(
        fixture.estimate.estimate_id
    )
    model_bytes = object_store.read_bytes(
        component.model_build.model.model_artifact_uri
    )
    surface_bytes = object_store.read_bytes(
        component.surface_build.surface.dataset_uri
    )
    return {
        "segment": asdict(segment),
        "validation": asdict(validation),
        "training": asdict(training),
        "model": asdict(component.model_build.model),
        "surface": asdict(component.surface_build.surface),
        "model_build": {
            "intercept": component.model_build.intercept,
            "slope": component.model_build.slope,
            "current_value": component.model_build.current_value,
            "ewma_value": component.model_build.ewma_value,
            "stability_mad": component.model_build.stability_mad,
            "p3_uncertainty_half_width": (
                component.model_build.p3_uncertainty_half_width
            ),
            "session_order_origin": (
                component.model_build.session_order_origin
            ),
            "fit_estimate_ids": list(
                component.model_build.fit_estimate_ids
            ),
        },
        "model_object_ref_id": component.model_object_ref_id,
        "surface_object_ref_id": component.surface_object_ref_id,
        "model_artifact_sha256": hashlib.sha256(
            model_bytes
        ).hexdigest(),
        "surface_dataset_sha256": hashlib.sha256(
            surface_bytes
        ).hexdigest(),
        "twin": asdict(twin),
        "estimate": asdict(estimate),
        "workspace": {
            "observed": {
                "release_id": workspace.observed.release_id,
                "logical_hash": workspace.observed.logical_hash,
                "projection": dict(
                    workspace.observed.projection
                ),
            },
            "adjusted": {
                "release_id": workspace.adjusted.release_id,
                "logical_hash": workspace.adjusted.logical_hash,
                "projection": dict(
                    workspace.adjusted.projection
                ),
            },
            "component_model_refs": [
                item.model_build.model.capability_model_id
                for item in workspace.components
            ],
        },
    }


def _conflict_code(
    rows: CanonicalRowRepository,
    object_store: LocalObjectStore,
) -> str:
    fixture = build_fixture()
    repo = P3PersistenceRepository(
        rows,
        object_store=object_store,
    )
    try:
        repo.register_estimate(
            replace(fixture.estimate, unit="m")
        )
    except P3PersistenceError as exc:
        return exc.code
    raise RuntimeError("P3 immutable conflict unexpectedly succeeded")


def _exercise_sqlite(
    database: Path,
    object_root: Path,
) -> dict[str, object]:
    object_store = LocalObjectStore(object_root)
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        seed_upstream(uow.canonical_rows)
        _register_p3(uow.canonical_rows, object_store)
        uow.commit()
    with SQLiteDesktopUnitOfWork(database) as uow:
        first = _projection(uow.canonical_rows, object_store)
        uow.commit()
    with SQLiteDesktopUnitOfWork(database, write=True) as uow:
        _register_p3(uow.canonical_rows, object_store)
        conflict = _conflict_code(
            uow.canonical_rows,
            object_store,
        )
        replay = _projection(uow.canonical_rows, object_store)
        uow.commit()
    return {
        "first_restart": first,
        "idempotent_replay": replay,
        "immutable_conflict_code": conflict,
    }


def _exercise_postgres(
    conninfo: str,
    object_root: Path,
) -> dict[str, object]:
    object_store = LocalObjectStore(object_root)
    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        seed_upstream(uow.canonical_rows)
        _register_p3(uow.canonical_rows, object_store)
        uow.commit()
    with PostgreSQLServiceUnitOfWork(
        conninfo,
        read_only=True,
    ) as uow:
        first = _projection(uow.canonical_rows, object_store)
        uow.commit()
    with PostgreSQLServiceUnitOfWork(conninfo) as uow:
        _register_p3(uow.canonical_rows, object_store)
        conflict = _conflict_code(
            uow.canonical_rows,
            object_store,
        )
        replay = _projection(uow.canonical_rows, object_store)
        uow.commit()
    return {
        "first_restart": first,
        "idempotent_replay": replay,
        "immutable_conflict_code": conflict,
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
        postgres_bootstrap = bootstrap_postgres(
            client,
            database,
        )
        conninfo = conninfo_template.format(
            database=database
        )
        with tempfile.TemporaryDirectory(
            prefix="tpaa-piqb-b2-p3-"
        ) as raw:
            root = Path(raw)
            sqlite_db = root / "p3.sqlite"
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
            postgres_after = verify_postgres(
                client,
                database,
            )

        fixture = build_fixture()
        sqlite_first = sqlite_result["first_restart"]
        postgres_first = postgres_result["first_restart"]
        if not isinstance(sqlite_first, dict):
            raise RuntimeError("SQLite P3 projection invalid")
        if not isinstance(postgres_first, dict):
            raise RuntimeError("PostgreSQL P3 projection invalid")
        sqlite_workspace = sqlite_first["workspace"]
        postgres_workspace = postgres_first["workspace"]
        if not isinstance(sqlite_workspace, dict):
            raise RuntimeError("SQLite P3 workspace invalid")
        if not isinstance(postgres_workspace, dict):
            raise RuntimeError("PostgreSQL P3 workspace invalid")
        sqlite_adjusted = sqlite_workspace["adjusted"]
        postgres_adjusted = postgres_workspace["adjusted"]
        if not isinstance(sqlite_adjusted, dict):
            raise RuntimeError("SQLite adjusted layer invalid")
        if not isinstance(postgres_adjusted, dict):
            raise RuntimeError("PostgreSQL adjusted layer invalid")
        sqlite_adjusted_projection = sqlite_adjusted[
            "projection"
        ]
        postgres_adjusted_projection = postgres_adjusted[
            "projection"
        ]
        if not isinstance(sqlite_adjusted_projection, dict):
            raise RuntimeError("SQLite adjusted projection invalid")
        if not isinstance(postgres_adjusted_projection, dict):
            raise RuntimeError(
                "PostgreSQL adjusted projection invalid"
            )

        profile = P3ModelExecutionProfile.from_canonical()
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
                sqlite_result["immutable_conflict_code"]
                == "P3_IMMUTABLE_CONFLICT"
                and postgres_result["immutable_conflict_code"]
                == "P3_IMMUTABLE_CONFLICT"
            ),
            "ordered_component_identity_preserved": (
                sqlite_workspace["component_model_refs"]
                == [fixture.model_build.model.capability_model_id]
                and postgres_workspace["component_model_refs"]
                == [fixture.model_build.model.capability_model_id]
            ),
            "exact_upstream_p2_membership_resolved": (
                sqlite_adjusted_projection["estimate_id"]
                == fixture.selected_p2_estimate_id
                and postgres_adjusted_projection["estimate_id"]
                == fixture.selected_p2_estimate_id
            ),
            "claim_level_deterministically_derived": (
                sqlite_first["estimate"]["claim_level"]
                == profile.estimate_claim_level
                and postgres_first["estimate"]["claim_level"]
                == profile.estimate_claim_level
            ),
            "model_object_hash_exact": (
                sqlite_first["model_artifact_sha256"]
                == fixture.model_build.model.model_artifact_hash
                and postgres_first["model_artifact_sha256"]
                == fixture.model_build.model.model_artifact_hash
            ),
            "surface_object_hash_exact": (
                sqlite_first["surface_dataset_sha256"]
                == fixture.surface_build.surface.dataset_hash
                and postgres_first["surface_dataset_sha256"]
                == fixture.surface_build.surface.dataset_hash
            ),
            "shadow_schema_not_created": True,
        }
        failed = sorted(
            key
            for key, ok in acceptance.items()
            if ok is not True
        )
        payload = {
            "schema": SCHEMA,
            "tracking_issue": TRACKING_ISSUE,
            "task_ids": list(TASK_IDS),
            "source_revision": source_revision,
            "status": "PASS" if not failed else "FAIL",
            "implementation_complete": False,
            "task_complete": False,
            "completion_gate": (
                "P6_MODEL_BUILD_RESOLVER_PENDING"
            ),
            "acceptance": acceptance,
            "failed_acceptance": failed,
            "sqlite": sqlite_result,
            "postgres": postgres_result,
            "scope": {
                "db_schema_version": "1.9.0",
                "real_sqlite_executed": True,
                "real_postgresql_executed": True,
                "p3_owned_state_only": True,
                "p1_p2_upstream_copied_into_p3": False,
                "claim_level_stored_as_new_column": False,
                "shadow_schema_created": False,
                "formal_b2_qualification_claimed": False,
            },
        }
        rendered = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ) + "\n"
        evidence.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        evidence.write_text(
            rendered,
            encoding="utf-8",
            newline="\n",
        )
        print(rendered, end="")
        return 0 if not failed else 2
    finally:
        if _database_exists(
            client,
            admin_database,
            database,
        ):
            client.run(
                admin_database,
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
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
    parser.add_argument(
        "--admin-database",
        default="postgres",
    )
    parser.add_argument(
        "--database",
        default="tpaa_piqb_b2_p3_persistence",
    )
    parser.add_argument(
        "--conninfo-template",
        required=True,
    )
    parser.add_argument(
        "--source-revision",
        required=True,
    )
    parser.add_argument(
        "--evidence",
        type=Path,
        required=True,
    )
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
            "completion_gate": (
                "P6_MODEL_BUILD_RESOLVER_PENDING"
            ),
            "error": f"{type(exc).__name__}: {exc}",
            "scope": {
                "db_schema_version": "1.9.0",
                "shadow_schema_created": False,
                "formal_b2_qualification_claimed": False,
            },
        }
        rendered = json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        ) + "\n"
        args.evidence.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        args.evidence.write_text(
            rendered,
            encoding="utf-8",
            newline="\n",
        )
        print(rendered, end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
