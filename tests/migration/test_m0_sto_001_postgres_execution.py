from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tools.storage import postgres_db as postgres_tool

from tpaa_storage.bootstrap import (
    BOOTSTRAP_MANIFEST_TABLE,
    POSTGRES_ENGINE_PROFILE,
    postgres_bootstrap_script,
    postgres_verify_script,
)

class FakeClient:
    def __init__(self, outputs: list[Any]) -> None:
        self.outputs = list(outputs)
        self.calls: list[tuple[str, str, bool]] = []

    def run(self, database: str, sql: str, *, expect_failure: bool = False) -> str:
        self.calls.append((database, sql, expect_failure))
        if not self.outputs:
            raise AssertionError("unexpected client call")
        value = self.outputs.pop(0)
        if isinstance(value, BaseException):
            raise value
        return str(value)


def _verification_line() -> str:
    return "|".join(
        (
            POSTGRES_ENGINE_PROFILE,
            "1.6.0",
            "CB-1.4.0",
            "CORE_LOGICAL_MODEL",
            "a" * 64,
            "b" * 64,
            "c" * 64,
            "d" * 64,
            "77",
        )
    )


def test_postgres_bootstrap_script_is_transactional_and_records_provenance() -> None:
    script = postgres_bootstrap_script()

    assert script.startswith("\\set ON_ERROR_STOP on\nBEGIN;")
    assert script.rstrip().endswith("COMMIT;")
    assert f'"public"."{BOOTSTRAP_MANIFEST_TABLE}"' in script
    assert "catalog_schema_sha256" in script
    assert "CORE_LOGICAL_MODEL" in script
    assert "1.6.0" in script
    assert "CB-1.4.0" in script
    assert script.count("CREATE TABLE") == 78  # 77 Canonical + bootstrap manifest


def test_postgres_fault_script_injects_failure_inside_transaction() -> None:
    script = postgres_bootstrap_script(fault_after_tables=4)
    fault = "SELECT tpaa_intentional_bootstrap_fault()"

    assert script.count(fault) == 1
    assert script.index("BEGIN") < script.index(fault) < script.index("COMMIT")


def test_postgres_verify_script_is_read_only_and_checks_catalog_hash() -> None:
    script = postgres_verify_script()

    assert "BEGIN READ ONLY" in script
    assert "TPAA_SCHEMA_INVENTORY_MISMATCH" in script
    assert "TPAA_TABLE_INVENTORY_MISMATCH" in script
    assert "TPAA_BOOTSTRAP_MANIFEST_MISMATCH" in script
    assert "TPAA_PHYSICAL_SCHEMA_MISMATCH" in script
    assert "catalog_schema_sha256" in script
    assert script.rstrip().endswith("ROLLBACK;")


def test_postgres_catalog_projection_casts_internal_char_fields_to_text() -> None:
    script = postgres_verify_script()

    assert "c.relkind::text" in script
    assert "a.attidentity::text" in script
    assert "a.attgenerated::text" in script
    assert "con.contype::text" in script
    assert "|| c.relkind\n" not in script
    assert "|| a.attidentity ||" not in script
    assert "|| a.attgenerated\n" not in script
    assert "|| con.contype ||" not in script


def test_repository_controlled_bootstrap_executes_then_verifies() -> None:
    client = FakeClient(["", _verification_line()])

    result = postgres_tool.bootstrap_postgres(client, "tpaa")

    assert result.engine_profile == POSTGRES_ENGINE_PROFILE
    assert result.schema_version == "1.6.0"
    assert result.table_count == 77
    assert result.catalog_schema_sha256 == "d" * 64
    assert len(client.calls) == 2
    assert "BEGIN" in client.calls[0][1]
    assert "BEGIN READ ONLY" in client.calls[1][1]


def test_fault_injection_requires_rollback_to_zero_relations() -> None:
    client = FakeClient(["0", "ERROR: function tpaa_intentional_bootstrap_fault() does not exist", "0"])

    postgres_tool.fault_inject_postgres(client, "tpaa", after_tables=4)

    assert client.calls[1][2] is True


def test_fault_injection_fails_if_partial_schema_survives() -> None:
    client = FakeClient(["0", "ERROR: tpaa_intentional_bootstrap_fault", "3"])

    with pytest.raises(RuntimeError, match="FAULT_INJECTION_PARTIAL_BOOTSTRAP"):
        postgres_tool.fault_inject_postgres(client, "tpaa")


def test_fault_injection_refuses_dirty_database() -> None:
    client = FakeClient(["1"])

    with pytest.raises(Exception, match="TARGET_NOT_EMPTY"):
        postgres_tool.fault_inject_postgres(client, "tpaa")


def test_acceptance_database_name_is_safely_scoped() -> None:
    client = FakeClient([])

    with pytest.raises(ValueError, match="must start"):
        postgres_tool._recreate_acceptance_database(client, "postgres", "production")


def test_scoped_database_helper_accepts_explicit_task_prefix() -> None:
    client = FakeClient(["0", ""])

    postgres_tool._recreate_scoped_database(
        client,
        "postgres",
        "tpaa_m0_sto_003_acceptance",
        required_prefix="tpaa_m0_sto_003_",
    )

    assert client.calls[-1][1] == 'CREATE DATABASE "tpaa_m0_sto_003_acceptance";\n'


def test_missing_external_client_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*args: object, **kwargs: object) -> object:
        raise FileNotFoundError("psql missing")

    monkeypatch.setattr(postgres_tool.subprocess, "run", missing)
    client = postgres_tool.PsqlClient(user="tpaa", psql_executable="missing-psql")

    with pytest.raises(postgres_tool.PsqlExecutionError, match="psql missing"):
        client.run("tpaa", "SELECT 1;")
