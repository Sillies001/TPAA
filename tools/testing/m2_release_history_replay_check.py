#!/usr/bin/env python3
"""Formal M2-TST-004 Release/history/replay/idempotency evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import cast

REPO_ROOT = Path(__file__).resolve().parents[2]


def _git_revision() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    value = completed.stdout.strip()
    return value if len(value) == 40 else "UNKNOWN"


def _mapping(value: object, *, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(
        isinstance(key, str) for key in value
    ):
        raise ValueError(f"{field} must be a string-keyed object")
    return cast(dict[str, object], value)


def _canonical_hash(value: object) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def verify() -> dict[str, object]:
    from tools.testing.m2_idempotent_publication_check import (
        verify as publication_verify,
    )
    from tools.testing.m2_immutable_release_check import (
        verify as release_verify,
    )
    from tools.testing.m2_metric_batch_replay_incremental_check import (
        verify as replay_verify,
    )

    release = release_verify()
    publication = publication_verify()
    replay = replay_verify()

    release_acceptance = _mapping(
        release.get("acceptance"),
        field="release.acceptance",
    )
    publication_acceptance = _mapping(
        publication.get("acceptance"),
        field="publication.acceptance",
    )
    replay_acceptance = _mapping(
        replay.get("acceptance"),
        field="replay.acceptance",
    )
    release_product = _mapping(
        release.get("logical_product"),
        field="release.logical_product",
    )
    publication_product = _mapping(
        publication.get("logical_product"),
        field="publication.logical_product",
    )
    replay_product = _mapping(
        replay.get("logical_product"),
        field="replay.logical_product",
    )
    revision = _git_revision()

    acceptance = {
        "immutable_release_source_pass": (
            release.get("status") == "PASS"
            and release.get("task_complete") is True
            and release.get("implementation_complete") is True
            and release.get("failed_acceptance") == []
            and all(value is True for value in release_acceptance.values())
        ),
        "idempotent_publication_source_pass": (
            publication.get("status") == "PASS"
            and publication.get("task_complete") is True
            and publication.get("implementation_complete") is True
            and publication.get("failed_acceptance") == []
            and all(value is True for value in publication_acceptance.values())
        ),
        "batch_replay_source_pass": (
            replay.get("status") == "PASS"
            and replay.get("task_complete") is True
            and replay.get("replay_contract_complete") is True
            and replay.get("implementation_complete") is True
            and replay.get("failed_acceptance") == []
            and all(value is True for value in replay_acceptance.values())
        ),
        "source_revisions_exact": (
            release.get("source_revision")
            == publication.get("source_revision")
            == replay.get("source_revision")
            == revision
        ),
        "immutable_release_membership_exact_32": (
            release_acceptance.get("foundation_definitions_exact_32") is True
            and release_acceptance.get(
                "foundation_execution_records_exact_32"
            )
            is True
            and release_acceptance.get(
                "release_definition_binding_exact_32"
            )
            is True
            and release_acceptance.get(
                "release_execution_binding_exact_32"
            )
            is True
        ),
        "release_snapshot_replay_exact": (
            release_acceptance.get("release_snapshot_replay_exact") is True
            and release_acceptance.get("input_mapping_order_independent")
            is True
            and release_acceptance.get("release_id_deterministic") is True
        ),
        "release_mutation_sensitivity_exact": (
            release_acceptance.get("context_mutation_changes_manifest") is True
            and release_acceptance.get(
                "binding_snapshot_is_deeply_frozen"
            )
            is True
        ),
        "release_history_never_uses_latest_authority": (
            release_acceptance.get("no_latest_authority_resolution") is True
            and publication_acceptance.get(
                "no_latest_authority_lookup_in_repository_or_replay"
            )
            is True
        ),
        "publication_exact_retry_idempotent": (
            publication_acceptance.get("first_publish_installs_token_1") is True
            and publication_acceptance.get(
                "exact_retry_is_idempotently_reused"
            )
            is True
            and publication_acceptance.get(
                "second_release_advances_token_2"
            )
            is True
        ),
        "publication_conflicts_fail_closed": (
            publication_acceptance.get(
                "idempotency_key_reuse_with_different_request_fails_closed"
            )
            is True
            and publication_acceptance.get("stale_cas_fails_closed") is True
        ),
        "release_history_chain_exact": (
            publication_acceptance.get("release_chain_exact") is True
            and publication_acceptance.get("current_pointer_is_second_release")
            is True
            and publication_acceptance.get(
                "historical_read_remains_first_release"
            )
            is True
            and publication_acceptance.get(
                "historical_read_is_explicit_release_bound"
            )
            is True
        ),
        "release_replay_detects_mutation": (
            publication_acceptance.get("exact_release_replay_passes") is True
            and publication_acceptance.get("mutated_release_replay_fails")
            is True
            and publication_acceptance.get(
                "replay_identity_remains_release_bound"
            )
            is True
        ),
        "batch_replay_exact_32": (
            replay_acceptance.get("catalog_membership_exact_32") is True
            and replay_acceptance.get("execution_membership_exact_32") is True
            and replay_acceptance.get("batch_replay_exact") is True
            and replay_acceptance.get("input_mapping_order_independent") is True
            and replay_acceptance.get("request_order_independent") is True
        ),
        "batch_replay_hash_lineage_exact": (
            replay_acceptance.get(
                "dependency_manifest_hash_binding_exact_32"
            )
            is True
            and replay_acceptance.get(
                "plugin_output_hash_replay_exact_32"
            )
            is True
            and replay_acceptance.get(
                "record_logical_hash_replay_exact_32"
            )
            is True
            and replay_acceptance.get("batch_logical_hash_binding_exact") is True
        ),
        "batch_replay_mutation_sensitivity_exact": (
            replay_acceptance.get("tampered_input_changes_batch_hash") is True
            and replay_acceptance.get(
                "input_mutation_propagates_exact_transitive_dependents"
            )
            is True
            and replay_acceptance.get(
                "plugin_identity_tamper_changes_batch_hash"
            )
            is True
            and replay_acceptance.get("plan_hash_mutation_changes_batch_hash")
            is True
        ),
        "batch_replay_request_fail_closed": all(
            replay_acceptance.get(name) is True
            for name in (
                "duplicate_request_fails_closed",
                "unknown_request_fails_closed",
                "missing_plugin_fails_closed",
                "plugin_version_mismatch_fails_closed",
                "unversioned_plugin_fails_closed",
                "opaque_input_lineage_fails_closed",
                "nonfinite_input_lineage_fails_closed",
            )
        ),
    }
    failed = sorted(key for key, passed in acceptance.items() if not passed)
    complete = not failed

    return {
        "schema": (
            "TPAA_M2_TST_004_RELEASE_HISTORY_REPLAY_IDEMPOTENCY_EVIDENCE_V1"
        ),
        "task_id": "M2-TST-004",
        "tracking_issue": 99,
        "status": "PASS" if complete else "FAIL",
        "task_complete": complete,
        "implementation_complete": complete,
        "source_revision": revision,
        "logical_product": {
            "release_source_schema": release.get("schema"),
            "publication_source_schema": publication.get("schema"),
            "replay_source_schema": replay.get("schema"),
            "release_logical_product_hash": _canonical_hash(release_product),
            "publication_logical_product_hash": _canonical_hash(
                publication_product
            ),
            "replay_logical_product_hash": _canonical_hash(replay_product),
            "first_release_id": publication_product.get("first_release_id"),
            "second_release_id": publication_product.get("second_release_id"),
            "current_release_id": publication_product.get("current_release_id"),
            "historical_first_release_id": publication_product.get(
                "historical_first_release_id"
            ),
            "first_version_token": publication_product.get(
                "first_version_token"
            ),
            "second_version_token": publication_product.get(
                "second_version_token"
            ),
            "batch_replay_manifest_hash": replay_product.get(
                "replay_manifest_hash"
            ),
            "batch_logical_hash": replay_product.get("batch_logical_hash"),
            "execution_metric_codes": replay_product.get(
                "execution_metric_codes"
            ),
        },
        "acceptance": acceptance,
        "failed_acceptance": failed,
        "scope": {
            "release_history_replay_idempotency_qualification_only": True,
            "immutable_release_snapshot_executed": True,
            "idempotent_publication_executed": True,
            "historical_release_read_executed": True,
            "batch_replay_contract_executed": True,
            "mutation_sensitivity_executed": True,
            "business_metric_semantics_executed": False,
            "database_persistence_executed": False,
            "latest_authority_resolution_used": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    try:
        payload = verify()
        return_code = 0 if payload["status"] == "PASS" else 2
    except Exception as exc:
        payload = {
            "schema": (
                "TPAA_M2_TST_004_RELEASE_HISTORY_REPLAY_"
                "IDEMPOTENCY_EVIDENCE_V1"
            ),
            "task_id": "M2-TST-004",
            "tracking_issue": 99,
            "status": "FAIL",
            "task_complete": False,
            "implementation_complete": False,
            "source_revision": _git_revision(),
            "error": f"{type(exc).__name__}: {exc}",
        }
        return_code = 2
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    print(rendered, end="")
    if args.evidence is not None:
        args.evidence.parent.mkdir(parents=True, exist_ok=True)
        args.evidence.write_text(rendered, encoding="utf-8", newline="\n")
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
