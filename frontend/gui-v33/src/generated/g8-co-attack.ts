// @generated from CB-1.13.0 Canonical DTO/Co-attack authorities; DO NOT EDIT.

export interface CoAttackAnalysisDTO {
  readonly schema: string;
  readonly provenance: Readonly<Record<string, unknown>>;
  readonly request_id: string;
  readonly query_context_id: string;
  readonly cluster_id: string;
  readonly batch_id: string;
  readonly context_id: string | null;
  readonly batch_context_id: string | null;
  readonly filter: Readonly<Record<string, unknown>>;
  readonly weapon_events: Readonly<Record<string, unknown>>;
  readonly formation: Readonly<Record<string, unknown>>;
  readonly dimensions: Readonly<Record<string, unknown>>;
}

export const G8_CO_ATTACK_ROUTES = {
  "gui.coattack": {
    "method": "GET",
    "path": "/api/v1/gui/attack-clusters/{cluster_id}/co-attack-analysis",
    "responseDto": "CoAttackAnalysisDTO"
  }
} as const;
export const G8_CO_ATTACK_AUTHORITY = {
  "activation_status": "ACTIVE",
  "approval_id": "G8-CB-1.13.0-LOCAL-IMPLEMENTATION-2026-11-07",
  "approved_at": "2026-11-07T00:00:00+08:00",
  "approved_core_baseline": "CB-1.13.0",
  "approver": "PROJECT_OWNER_G8_IMPLEMENTATION_DIRECTIVE",
  "authority_id": "GUI_CO_ATTACK_AUTHORITY",
  "authority_version": "1.0.0",
  "core_baseline": "CB-1.13.0",
  "database": {
    "migration_required": false,
    "reason": "Co-attack analysis is an exact cluster read model over existing Cluster/WE/Context relations; no new physical tables.",
    "schema": "1.10.0"
  },
  "decision_id": "G8-V33-CO-ATTACK-2026-11-07",
  "parent_core_baseline": "CB-1.12.0",
  "release_claim": false,
  "restrictions": {
    "production_deployment": false,
    "push": false,
    "release_claim": false
  },
  "rules": {
    "browser_business_storage": "FORBIDDEN",
    "bvr_only": true,
    "cluster_scope": "EXACT_CLUSTER_RELATION_ONLY",
    "cross_batch_cluster": "FORBIDDEN",
    "gui_business_recomputation": "FORBIDDEN",
    "latest_fallback": "FORBIDDEN",
    "missing_context": "HONEST_EMPTY_FORMATION",
    "no_total_score": true,
    "strike_cluster_rejected": "FAIL_CLOSED"
  },
  "schema": "TPAA_G8_CO_ATTACK_APPROVAL_V1",
  "single_owner_rules": {
    "attack_cluster_resolver": "tpaa_application.weapon_event",
    "browser_business_storage": "FORBIDDEN",
    "co_attack_analysis_query": "tpaa_application.co_attack",
    "force_formation_context": "tpaa_application.batch_import",
    "gui_business_recomputation": "FORBIDDEN"
  },
  "status": "APPROVED_LOCAL"
} as const;
