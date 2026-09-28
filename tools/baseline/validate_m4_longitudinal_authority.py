from __future__ import annotations
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any
from tpaa_canonical import ArtifactExpectation, CanonicalArtifactLoader

ROOT = Path(__file__).resolve().parents[2]
BASELINE = ROOT / "baseline" / "CB-1.4.0"
FIXTURE = ROOT / "tests" / "fixtures" / "m4" / "C3_LONGITUDINAL_DEBRIEF_AUTHORITY_V1"
EXPECTED_DTO_CONTRACTS = {"LongitudinalScopeDTO","LongitudinalTrendQueryDTO","LongitudinalTrendSeriesDTO","LongitudinalTrendPointDTO","LongitudinalReleaseDTO","DebriefQueryDTO","DebriefTimelineItemDTO","DebriefAnnotationDTO","DebriefAnnotationCommandDTO","DebriefBundleDTO"}

def _canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("ascii")

def _hash(value: object) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest()

def _authority() -> dict[str, Any]:
    loader = CanonicalArtifactLoader(BASELINE)
    artifact = loader.load("M4_LONGITUDINAL_DEBRIEF_AUTHORITY", expectation=ArtifactExpectation(version="1.0.0", schema_version="1.6.0", required_top_level_keys=("sample_profile","comparison_key_contract","trend_profile","release_replay_contract","dto_contracts","golden_vectors")))
    return dict(artifact.payload)

def _normalized_comparison(value: dict[str, Any], authority: dict[str, Any]) -> dict[str, Any]:
    required = list(authority["comparison_key_contract"]["required_fields"])
    if set(value) != set(required):
        raise ValueError("comparison key exact field set required")
    result = dict(value)
    training = result["training_type_set"]
    if not isinstance(training, list) or not all(isinstance(item, str) and item for item in training):
        raise ValueError("training_type_set invalid")
    if len(set(training)) != len(training):
        raise ValueError("training_type_set duplicate")
    result["training_type_set"] = sorted(training)
    world = result["world_product_versions"]
    if not isinstance(world, dict) or not all(isinstance(key, str) and isinstance(item, str) for key, item in world.items()):
        raise ValueError("world_product_versions invalid")
    return result

def _trend(points: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    valid = sorted((item for item in points if item["status"] == profile["valid_sample_status"] and isinstance(item["value"], (int, float)) and not isinstance(item["value"], bool) and math.isfinite(float(item["value"]))), key=lambda item: int(item["session_order"]))
    orders = [int(item["session_order"]) for item in valid]
    if len(set(orders)) != len(orders):
        raise ValueError("duplicate session_order")
    current = float(valid[-1]["value"]) if valid else None
    ewma = None
    alpha = float(profile["ewma"]["alpha"])
    for item in valid:
        value = float(item["value"])
        ewma = value if ewma is None else alpha * value + (1.0 - alpha) * ewma
    if len(valid) < int(profile["slope"]["min_valid_points"]):
        return {"current_value": current, "ewma_value": ewma, "slope": None, "stability_mad": None, "trend_status": "INSUFFICIENT_DATA"}
    window = valid[-int(profile["slope"]["max_valid_points"]):]
    x0 = int(window[0]["session_order"])
    xs = [int(item["session_order"]) - x0 for item in window]
    ys = [float(item["value"]) for item in window]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    denominator = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / denominator
    center = statistics.median(ys)
    mad = statistics.median(abs(y - center) for y in ys)
    projected = slope * (xs[-1] - xs[0])
    if mad == 0.0:
        status = "INCREASING" if slope > 0 else "DECREASING" if slope < 0 else "STABLE"
    elif abs(projected) <= mad:
        status = "STABLE"
    else:
        status = "INCREASING" if projected > 0 else "DECREASING"
    return {"current_value": current, "ewma_value": ewma, "slope": slope, "stability_mad": mad, "trend_status": status}

def _close(actual: float | None, expected: float | None) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-12)

def run() -> dict[str, Any]:
    authority = _authority()
    profile = dict(authority["trend_profile"])
    profile_hash = profile.pop("profile_hash")
    profile.pop("profile_hash_algorithm")
    golden = authority["golden_vectors"]
    comparison = golden["comparison_key"]
    canonical = _normalized_comparison(dict(comparison["canonical_input"]), authority)
    permuted = _normalized_comparison(dict(comparison["permutation_input"]), authority)
    changed = _normalized_comparison(dict(comparison["material_change_input"]), authority)
    trend = _trend(list(golden["trend"]["points"]), authority["trend_profile"])
    expected_trend = golden["trend"]["expected"]
    sample = golden["sample_aggregation"]
    valid_sources = [item for item in sample["sources"] if item["status"] == "VALID" and isinstance(item["value_numeric"], (int, float))]
    sample_value = statistics.median(float(item["value_numeric"]) for item in valid_sources)
    sample_coverage = min(float(item["coverage"]) for item in valid_sources)
    sample_confidence = min(float(item["confidence"]) for item in valid_sources)
    sample_episode_count = len({item["episode_id"] for item in valid_sources if item["episode_id"] is not None})
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    source_path = FIXTURE / manifest["files"]["source"]["path"]
    source_bytes = source_path.read_bytes()
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    source = json.loads(source_bytes.decode("utf-8"))
    dto = authority["dto_contracts"]
    trend_query = {item["field"]: item for item in dto["LongitudinalTrendQueryDTO"]["fields"]}
    debrief_query = {item["field"]: item for item in dto["DebriefQueryDTO"]["fields"]}
    annotation = {item["field"]: item for item in dto["DebriefAnnotationCommandDTO"]["fields"]}
    duplicate = [dict(item) for item in golden["trend"]["points"]]
    duplicate[-1]["session_order"] = 40
    duplicate_fails = False
    try:
        _trend(duplicate, authority["trend_profile"])
    except ValueError:
        duplicate_fails = True
    broken = dict(comparison["canonical_input"])
    broken.pop("scenario_version")
    missing_fails = False
    try:
        _normalized_comparison(broken, authority)
    except ValueError:
        missing_fails = True
    acceptance = {
        "authority_status_adoption_gated": authority["status"] == "APPROVED_FOR_PROTECTED_MAIN_ADOPTION",
        "db_schema_frozen_1_6_0": authority["db_schema_version"] == "1.6.0" and authority["scope"]["db_schema_change"] is False,
        "p1_only_subject_boundary": authority["scope"]["admitted_capability_phase"] == ["P1"] and authority["scope"]["admitted_subject_types"] == ["AIRCRAFT", "MISSION_SYSTEM_INSTANCE"],
        "p4_p5_inactive": authority["scope"]["p4_p5_human_team_assessment_active"] is False,
        "profile_hash_exact": _hash(profile) == profile_hash,
        "comparison_key_hash_exact": _hash(canonical) == comparison["expected_hash"],
        "comparison_permutation_stable": _hash(permuted) == comparison["expected_hash"],
        "comparison_material_change_segments": _hash(changed) == comparison["expected_material_change_hash"] != comparison["expected_hash"],
        "comparison_missing_field_fails_closed": missing_fails,
        "scope_descriptor_hash_exact": _hash(golden["longitudinal_scope"]["descriptor"]) == golden["longitudinal_scope"]["expected_descriptor_hash"] == golden["longitudinal_scope"]["expected_longitudinal_scope_key"],
        "sample_median_exact": _close(sample_value, sample["expected"]["value_numeric"]),
        "sample_coverage_confidence_exact": _close(sample_coverage, sample["expected"]["coverage"]) and _close(sample_confidence, sample["expected"]["confidence"]),
        "sample_episode_count_exact": sample_episode_count == sample["expected"]["source_episode_count"],
        "trend_current_exact": _close(trend["current_value"], expected_trend["current_value"]),
        "trend_ewma_exact": _close(trend["ewma_value"], expected_trend["ewma_value"]),
        "trend_slope_exact": _close(trend["slope"], expected_trend["slope"]),
        "trend_mad_exact": _close(trend["stability_mad"], expected_trend["stability_mad"]),
        "trend_status_exact": trend["trend_status"] == expected_trend["trend_status"],
        "duplicate_session_order_fails_closed": duplicate_fails,
        "trend_input_hash_exact": _hash(golden["trend"]["input_manifest"]) == golden["trend"]["expected_input_hash"],
        "dto_contract_set_exact": set(dto) == EXPECTED_DTO_CONTRACTS,
        "trend_query_exact_release_required": trend_query["release_id"]["required"] is True,
        "debrief_query_exact_release_required": debrief_query["base_release_id"]["required"] is True,
        "retrospective_release_is_explicit": "RETROSPECTIVE requires an explicit retrospective_release_id and never resolves current/latest." in dto["DebriefQueryDTO"]["rules"],
        "annotation_reason_required": annotation["reason"]["required"] is True and "audit.audit_log.reason" in annotation["reason"]["source"],
        "api_gui_no_recomputation": authority["scope"]["api_gui_business_recomputation_permitted"] is False,
        "gui_no_persistence": authority["scope"]["gui_direct_persistence_access_permitted"] is False,
        "fixture_source_hash_exact": source_hash == manifest["files"]["source"]["sha256"],
        "fixture_input_hash_exact": hashlib.sha256(f"source/c3-authority-golden.json={source_hash}\n".encode("ascii")).hexdigest() == manifest["input_sha256"],
        "fixture_binds_authority": source["authority_sha256"] == manifest["authority_refs"]["authority_sha256"],
    }
    failed = sorted(name for name, passed in acceptance.items() if not passed)
    return {"schema":"TPAA_M4_C3_LONGITUDINAL_DEBRIEF_AUTHORITY_VALIDATION_V1","task_id":"M4-GOV-001","tracking_issue":122,"status":"PASS" if not failed else "FAIL","authority_id":authority["authority_id"],"authority_version":authority["version"],"trend_profile_hash":authority["trend_profile"]["profile_hash"],"acceptance":acceptance,"failed_acceptance":failed}

def main() -> int:
    payload = run()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 2

if __name__ == "__main__":
    raise SystemExit(main())
