from __future__ import annotations

import json
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = REPO_ROOT / "tools" / "storage" / "REPOSITORY_DB_ACCESS_POLICY.json"
ARCHITECTURE_PATH = REPO_ROOT / "tools" / "architecture" / "ARCHITECTURE_POLICY.json"
ADR_PATH = REPO_ROOT / "docs" / "adr" / "ADR-M0-004-repository-db-access-implementation.md"


def _policy() -> dict[str, object]:
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def test_adr_m0_004_is_closed_and_machine_policy_is_frozen() -> None:
    adr = ADR_PATH.read_text(encoding="utf-8")
    policy = _policy()

    assert "**Status:** CLOSED" in adr
    assert policy["schema"] == "TPAA_REPOSITORY_DB_ACCESS_POLICY_V1"
    assert policy["status"] == "FROZEN"
    assert policy["decision_id"] == "ADR-M0-004"


def test_selected_repository_technology_is_exact_and_driver_isolated() -> None:
    policy = _policy()
    sqlite = policy["sqlite"]
    postgres = policy["postgresql"]
    ports = policy["repository_ports"]

    assert isinstance(sqlite, dict)
    assert isinstance(postgres, dict)
    assert isinstance(ports, dict)
    assert sqlite["driver"] == "python_stdlib.sqlite3"
    assert sqlite["api_mode"] == "synchronous_dbapi"
    assert sqlite["journal_mode"] == "WAL"
    assert sqlite["writer_model"] == "single_backend_writer"
    assert postgres["driver"] == "psycopg"
    assert postgres["driver_generation"] == 3
    assert postgres["decision_reference_version"] == "3.3.6"
    assert postgres["api_mode"] == "synchronous_dbapi"
    assert ports["package"] == "tpaa_storage.ports"
    assert ports["driver_types_forbidden"] is True
    assert ports["dialect_branches_forbidden"] is True


def test_unit_of_work_contract_is_explicit_commit_and_fail_closed() -> None:
    policy = _policy()
    uow = policy["unit_of_work"]
    assert isinstance(uow, dict)
    assert uow["required"] is True
    assert uow["repository_commit_forbidden"] is True
    assert uow["success_requires_explicit_commit"] is True
    assert uow["exception_rolls_back"] is True
    assert uow["uncommitted_exit_rolls_back"] is True
    assert uow["connection_scope"] == "one_connection_per_unit_of_work"


def test_sqlite_transaction_spike_proves_commit_and_rollback_primitives() -> None:
    connection = sqlite3.connect(":memory:")
    try:
        connection.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")

        connection.execute("BEGIN")
        connection.execute("INSERT INTO probe(value) VALUES (?)", ("rollback",))
        connection.rollback()
        assert connection.execute("SELECT COUNT(*) FROM probe").fetchone() == (0,)

        connection.execute("BEGIN")
        connection.execute("INSERT INTO probe(value) VALUES (?)", ("commit",))
        connection.commit()
        assert connection.execute("SELECT value FROM probe").fetchall() == [("commit",)]
    finally:
        connection.close()


def test_runtime_storage_layer_rejects_rejected_database_abstractions() -> None:
    architecture = json.loads(ARCHITECTURE_PATH.read_text(encoding="utf-8"))
    forbidden = architecture["forbidden_external_prefixes"]
    assert set(forbidden["tpaa_storage"]) == {"sqlalchemy", "alembic", "asyncpg"}

    # The selected concrete drivers belong at the Storage adapter boundary and
    # therefore must not be banned from tpaa_storage itself.
    assert "sqlite3" not in forbidden["tpaa_storage"]
    assert "psycopg" not in forbidden["tpaa_storage"]

    # Existing upper-layer bans are part of the ADR contract: Application and
    # GUI must not bypass ports and import concrete DB technologies.
    assert "sqlite3" in forbidden["tpaa_application"]
    assert "psycopg" in forbidden["tpaa_application"]
    assert "sqlite3" in forbidden["tpaa_gui"]
    assert "psycopg" in forbidden["tpaa_gui"]


def test_migration_tooling_is_not_schema_authority_or_runtime_access() -> None:
    policy = _policy()
    migration = policy["migration"]
    assert isinstance(migration, dict)
    assert migration["service_ci_mechanism"] == "Alembic"
    assert migration["decision_reference_version"] == "1.20.0"
    assert migration["authority_role"] == "execution/history mechanism only"
    assert migration["autogenerate_as_authority_forbidden"] is True
    assert migration["runtime_repository_auto_migrate_forbidden"] is True


def test_developer_cli_exposes_repository_policy_gate() -> None:
    cli = (REPO_ROOT / "tools" / "dev" / "tpaa_dev.py").read_text(encoding="utf-8")
    assert 'CommandSpec("verify-repository-policy", "ADR-M0-004", "IMPLEMENTED"' in cli
    assert 'sub.add_parser("verify-repository-policy"' in cli
