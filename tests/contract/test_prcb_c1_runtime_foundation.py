from __future__ import annotations

from pathlib import Path

import pytest

from tpaa_runtime.admission import (
    FeatureAvailabilityState,
    ProductAdmissionResolver,
    ProductFeatureAvailability,
)
from tpaa_runtime.config import ProductionRuntimeConfig, RuntimeProfile


def _flags(value: bool) -> dict[str, bool]:
    return {phase: value for phase in ("P1", "P2", "P3", "P4", "P5", "P6")}


def test_prcb_feature_availability_is_dependency_aware() -> None:
    dependency = _flags(True)
    dependency["P2"] = False
    configured = _flags(True)
    configured["P1"] = False
    availability = ProductFeatureAvailability(
        ProductAdmissionResolver(),
        configured=configured,
        dependency_ready=dependency,
    ).execute()
    states = {item["phase"]: item["state"] for item in availability["items"]}
    assert states["P1"] == FeatureAvailabilityState.NOT_CONFIGURED.value
    assert states["P2"] == FeatureAvailabilityState.DEPENDENCY_MISSING.value
    assert states["P3"] == FeatureAvailabilityState.AVAILABLE.value


def test_prcb_production_desktop_config_requires_real_db(
    tmp_path: Path,
) -> None:
    authority = tmp_path / "authority"
    authority.mkdir()
    database = tmp_path / "tpaa.db"
    database.write_bytes(b"not-yet-verified-here")
    config = ProductionRuntimeConfig(
        profile=RuntimeProfile.DESKTOP,
        product_build_version="1.0.1",
        authority_root=authority,
        object_root=tmp_path / "objects",
        desktop_database_path=database,
    )
    assert config.desktop_database_path == database
    assert config.service_conninfo is None

    with pytest.raises(ValueError, match="database_path"):
        ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.1",
            authority_root=authority,
            object_root=tmp_path / "objects",
        )


def test_prcb_production_service_config_requires_conninfo(
    tmp_path: Path,
) -> None:
    authority = tmp_path / "authority"
    authority.mkdir()
    config = ProductionRuntimeConfig(
        profile=RuntimeProfile.SERVICE,
        product_build_version="1.0.1",
        authority_root=authority,
        object_root=tmp_path / "objects",
        service_conninfo="dbname=tpaa user=tpaa",
    )
    assert config.desktop_database_path is None
    assert config.service_conninfo == "dbname=tpaa user=tpaa"

    with pytest.raises(ValueError, match="conninfo"):
        ProductionRuntimeConfig(
            profile=RuntimeProfile.SERVICE,
            product_build_version="1.0.1",
            authority_root=authority,
            object_root=tmp_path / "objects",
        )


def test_prcb_durable_runtime_adapters_do_not_use_inmemory_or_test_fixtures() -> None:
    root = Path(__file__).resolve().parents[2]
    sources = [
        root / "src" / "tpaa_runtime" / "durable_repositories.py",
        root / "src" / "tpaa_runtime" / "config.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in sources)
    assert "InMemory" not in text
    assert "tests/fixtures" not in text
    assert "m1_fixture_root" not in text
