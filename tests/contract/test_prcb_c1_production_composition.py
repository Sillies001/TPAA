from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_application import M6ApplicationError, M6P2ComparisonQuery
from tpaa_runtime import (
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
)
from tpaa_storage import bootstrap_sqlite


def test_prcb_desktop_production_composition_uses_db_1_9(
    tmp_path: Path,
) -> None:
    database = tmp_path / "tpaa.db"
    bootstrap_sqlite(database)
    runtime = build_desktop_production_runtime(
        ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.1",
            authority_root=(
                Path(__file__).resolve().parents[2]
                / "baseline"
                / "CB-1.4.0"
                / "canonical"
            ),
            object_root=tmp_path / "objects",
            desktop_database_path=database,
        )
    )

    storage = runtime.application.storage_baseline_status()
    assert storage.schema_version == "1.9.0"
    assert storage.core_baseline == "CB-1.4.0"

    availability = runtime.application.feature_availability()
    states = {
        item["phase"]: item["state"]
        for item in availability["items"]
    }
    assert states == {
        "P1": "NOT_CONFIGURED",
        "P2": "AVAILABLE",
        "P3": "AVAILABLE",
        "P4": "AVAILABLE",
        "P5": "AVAILABLE",
        "P6": "AVAILABLE",
    }

    with pytest.raises(M6ApplicationError, match="P2_ADJUSTED_ESTIMATE_NOT_FOUND"):
        runtime.application.m6_p2_comparison(
            M6P2ComparisonQuery(
                p2_release_id="96000000-0000-4000-8000-000000000001",
                estimate_id="96000000-0000-4000-8000-000000000002",
            )
        )


def test_prcb_production_composition_has_no_fixture_or_inmemory_fallback() -> None:
    root = Path(__file__).resolve().parents[2]
    paths = [
        root / "src" / "tpaa_runtime" / "production.py",
        root / "src" / "tpaa_runtime" / "durable_p1.py",
        root / "src" / "tpaa_runtime" / "durable_repositories.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "InMemory" not in source
    assert "tests/fixtures" not in source
    assert "m1_fixture_root" not in source


def test_prcb_production_composes_durable_m4_without_claiming_p1_available() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src" / "tpaa_runtime" / "production.py").read_text(
        encoding="utf-8"
    )
    assert "DurableM4LongitudinalReleaseRepository" in source
    assert "DurableM4DebriefRepository" in source
    assert "m4_workspace=m4_workspace" in source
    assert "DurableP1ReleaseReadService" in source
    assert "m1_publication=p1_release_reads" in source
    assert '"P1": False' in source
