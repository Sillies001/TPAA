from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tpaa_application import W7_EXTERNAL_CAPABILITIES
from tpaa_qualification import W9_EVIDENCE_CATEGORIES, load_m5_qualification_authority
from tpaa_runtime import (
    FORMAL_EVIDENCE_ENVELOPE_SCHEMA,
    FORMAL_EVIDENCE_PAYLOAD_SCHEMA,
    W8_EVIDENCE_CATEGORIES,
    W8_TARGET_PROFILES,
    FormalEvidenceError,
    FormalQualificationEvidenceConfig,
    ProductionRuntimeConfig,
    RuntimeProfile,
    build_desktop_production_runtime,
    load_formal_runtime_evidence,
)
from tpaa_storage import bootstrap_sqlite

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / "baseline" / "CB-1.5.0"
CANDIDATE = "a" * 64
REVISION = "b" * 40


def _payload() -> dict[str, object]:
    return {
        "schema": FORMAL_EVIDENCE_PAYLOAD_SCHEMA,
        "candidate_identity_sha256": CANDIDATE,
        "source_revision": REVISION,
        "w7_external_capabilities": [
            {
                "capability": capability,
                "state": "AVAILABLE",
                "reason_code": "FORMALLY_ACCEPTED",
                "endpoint_ref": f"https://accepted.example/{index}",
                "acceptance_evidence_sha256": f"{index:x}" * 64,
            }
            for index, capability in enumerate(W7_EXTERNAL_CAPABILITIES, start=1)
        ],
        "w8_target_profiles": [
            {
                "profile_id": profile,
                "state": "ACCEPTED",
                "endpoint_ref": f"target://accepted/{index}",
                "evidence_sha256": f"{index + 4:x}" * 64,
                "categories": {
                    category: "PASS" for category in W8_EVIDENCE_CATEGORIES
                },
            }
            for index, profile in enumerate(W8_TARGET_PROFILES, start=1)
        ],
        "w9": {
            "gates": [
                {
                    "category": category,
                    "state": "ACCEPTED",
                    "reason_code": "FORMALLY_ACCEPTED",
                    "candidate_identity_sha256": CANDIDATE,
                    "evidence_sha256": f"{index:x}" * 64,
                }
                for index, category in enumerate(W9_EVIDENCE_CATEGORIES, start=1)
            ],
            "unwaived_findings": {"blocker": 0, "high": 0},
            "protected_main_exact": True,
            "hosted_ci_success": True,
            "independent_approval_complete": True,
        },
    }


def _write_signed(
    tmp_path: Path,
    payload: dict[str, object],
) -> FormalQualificationEvidenceConfig:
    tmp_path.mkdir(parents=True, exist_ok=True)
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key()
    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")
    envelope = {
        "schema": FORMAL_EVIDENCE_ENVELOPE_SCHEMA,
        "payload": payload,
        "signature": {
            "algorithm": "Ed25519",
            "key_id": "test-release-authority",
            "value_base64": base64.b64encode(private_key.sign(canonical)).decode("ascii"),
        },
    }
    manifest = tmp_path / "formal-evidence.json"
    trust_root = tmp_path / "release-authority.pem"
    manifest.write_text(json.dumps(envelope), encoding="utf-8")
    trust_root.write_bytes(
        public_key.public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    return FormalQualificationEvidenceConfig(
        manifest_path=manifest,
        trust_root_path=trust_root,
        key_id="test-release-authority",
        candidate_identity_sha256=CANDIDATE,
        source_revision=REVISION,
    )


def test_signed_formal_evidence_constructs_all_three_runtime_gates(
    tmp_path: Path,
) -> None:
    config = _write_signed(tmp_path, _payload())
    evidence = load_formal_runtime_evidence(
        config,
        authority=load_m5_qualification_authority(BASELINE),
    )

    assert evidence.w7_external_capabilities.execute()["all_external_actions_gated"] is False
    assert evidence.w8_operations_status.execute()["production_activation_allowed"] is True
    assert evidence.w9_final_qualification_status.execute()["decision"] == "GO"
    assert len(evidence.signature_sha256) == 64


def test_formal_evidence_rejects_tamper_candidate_drift_and_string_booleans(
    tmp_path: Path,
) -> None:
    config = _write_signed(tmp_path, _payload())
    document = json.loads(config.manifest_path.read_text(encoding="utf-8"))
    document["payload"]["w9"]["hosted_ci_success"] = False
    config.manifest_path.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(FormalEvidenceError, match="SIGNATURE_INVALID"):
        load_formal_runtime_evidence(
            config,
            authority=load_m5_qualification_authority(BASELINE),
        )

    invalid = _payload()
    invalid["w9"]["hosted_ci_success"] = "false"  # type: ignore[index]
    invalid_config = _write_signed(tmp_path / "invalid", invalid)
    with pytest.raises(FormalEvidenceError, match="BOOLEAN_INVALID"):
        load_formal_runtime_evidence(
            invalid_config,
            authority=load_m5_qualification_authority(BASELINE),
        )

    drifted = FormalQualificationEvidenceConfig(
        manifest_path=invalid_config.manifest_path,
        trust_root_path=invalid_config.trust_root_path,
        key_id=invalid_config.key_id,
        candidate_identity_sha256="c" * 64,
        source_revision=REVISION,
    )
    with pytest.raises(FormalEvidenceError, match="CANDIDATE_MISMATCH"):
        load_formal_runtime_evidence(
            drifted,
            authority=load_m5_qualification_authority(BASELINE),
        )


def test_production_composition_uses_verified_formal_status(tmp_path: Path) -> None:
    evidence_config = _write_signed(tmp_path, _payload())
    database = tmp_path / "tpaa.sqlite3"
    bootstrap_sqlite(database)
    runtime = build_desktop_production_runtime(
        ProductionRuntimeConfig(
            profile=RuntimeProfile.DESKTOP,
            product_build_version="1.0.1",
            authority_root=BASELINE / "canonical",
            object_root=tmp_path / "objects",
            desktop_database_path=database,
            formal_qualification=evidence_config,
        )
    )

    assert runtime.application.w9_final_qualification_status()["decision"] == "GO"
    assert runtime.application.w8_operations_status()["production_activation_allowed"] is True
