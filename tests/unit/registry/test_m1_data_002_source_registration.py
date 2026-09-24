from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tpaa_registry import (
    SourceRegistryError,
    SourceRegistryIndex,
    register_all_synthetic_fixtures,
    register_synthetic_fixture,
)

FIXTURE_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "m1"


def test_nominal_registration_is_deterministic_and_immutable() -> None:
    path = FIXTURE_ROOT / "BF_M1_NOMINAL_V1"
    first = register_synthetic_fixture(path)
    second = register_synthetic_fixture(path)

    assert first == second
    assert first.bundle_ref.immutable is True
    assert first.source_artifact.immutable is True
    assert first.context_artifact.immutable is True
    assert first.source_time_basis == "SOURCE_US"
    assert len(first.bundle_ref.sha256) == 64
    assert len(first.source_artifact.sha256) == 64
    assert len(first.context_artifact.sha256) == 64
    assert first.persistence_executed is False
    assert first.canonical_context_artifact_row_executed is False


def test_all_governed_fixtures_have_unique_bundle_and_context_refs() -> None:
    index, registrations = register_all_synthetic_fixtures(FIXTURE_ROOT)

    assert len(registrations) == 8
    assert index.ref_count == 24
    assert len({item.bundle_ref.logical_ref for item in registrations}) == 8
    assert len({item.context_artifact.logical_ref for item in registrations}) == 8


def test_context_file_ref_uses_fixture_context_version_and_hash() -> None:
    registration = register_synthetic_fixture(
        FIXTURE_ROOT / "BF_M1_NOMINAL_V1"
    )

    assert registration.context_version == "M1-BASIC-CONTEXT-1.0.0"
    assert registration.context_artifact.logical_ref.startswith(
        "M1_CONTEXT_FILE:BF_M1_NOMINAL_V1:M1-BASIC-CONTEXT-1.0.0:"
    )
    assert registration.context_artifact.logical_ref.endswith(
        registration.context_artifact.sha256
    )


def test_registry_index_is_idempotent_for_same_ref_and_hash() -> None:
    registration = register_synthetic_fixture(
        FIXTURE_ROOT / "BF_M1_NOMINAL_V1"
    )
    index = SourceRegistryIndex()

    index.register(registration)
    index.register(registration)

    assert index.ref_count == 3
    assert (
        index.resolve_sha256(registration.bundle_ref.logical_ref)
        == registration.bundle_ref.sha256
    )


def test_context_tamper_fails_closed_before_registration(
    tmp_path: Path,
) -> None:
    source = FIXTURE_ROOT / "BF_M1_NOMINAL_V1"
    target = tmp_path / "BF_M1_NOMINAL_V1"
    shutil.copytree(source, target)
    context_path = target / "context" / "evaluation-context.json"
    payload = json.loads(context_path.read_text(encoding="utf-8"))
    payload["context_version"] = "M1-TAMPERED"
    context_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SourceRegistryError) as caught:
        register_synthetic_fixture(target)

    assert caught.value.code == "M1_SOURCE_REGISTRY_SOURCE_REJECTED"


def test_unknown_ref_lookup_fails_closed() -> None:
    index = SourceRegistryIndex()

    with pytest.raises(SourceRegistryError) as caught:
        index.resolve_sha256("M1_CONTEXT_FILE:UNKNOWN")

    assert caught.value.code == "M1_SOURCE_REGISTRY_REF_UNKNOWN"
