// @generated from CB-1.12.0 Canonical DTO/Batch-events authorities; DO NOT EDIT.

export interface BatchEventWorkbenchDTO {
  readonly schema: string;
  readonly provenance: Readonly<Record<string, unknown>>;
  readonly request_id: string;
  readonly query_context_id: string;
  readonly batch_id: string;
  readonly filter: Readonly<Record<string, unknown>>;
  readonly summary: Readonly<Record<string, unknown>>;
  readonly items: Readonly<Record<string, unknown>>;
  readonly next_cursor: string | null;
  readonly total_count: number;
}

export interface WeaponEventListItemDTO {
  readonly schema: string;
  readonly reason_code: string;
  readonly weapon_event_id: string;
  readonly revision_no: number;
  readonly cluster_id: string | null;
  readonly category: string;
  readonly batch_id: string;
  readonly t1_session_time_us: string;
  readonly shooter_entity_id: string;
  readonly target_entity_id: string | null;
  readonly episode_id: string | null;
  readonly weapon_terminal_state: string;
  readonly adjudication_state: string;
  readonly observation_window_state: string;
  readonly classification_exception: boolean;
}

export const G7_BATCH_EVENTS_ROUTES = {
  "gui.batch.events": {
    "method": "GET",
    "path": "/api/v1/gui/batches/{batch_id}/weapon-events",
    "responseDto": "BatchEventWorkbenchDTO"
  }
} as const;
export const G7_BATCH_EVENTS_AUTHORITY = {
  "activation_status": "ACTIVE",
  "approval_id": "G7-CB-1.12.0-LOCAL-IMPLEMENTATION-2026-11-07",
  "approved_at": "2026-11-07T00:00:00+08:00",
  "approved_core_baseline": "CB-1.12.0",
  "approver": "PROJECT_OWNER_G7_IMPLEMENTATION_DIRECTIVE",
  "authority_id": "GUI_BATCH_EVENTS_AUTHORITY",
  "authority_version": "1.0.0",
  "core_baseline": "CB-1.12.0",
  "database": {
    "migration_required": false,
    "reason": "Batch events is an exact-batch read model over existing Batch/WE/Cluster relations; no new physical tables.",
    "schema": "1.10.0"
  },
  "decision_id": "G7-V33-BATCH-EVENTS-2026-11-07",
  "parent_core_baseline": "CB-1.11.0",
  "release_claim": false,
  "restrictions": {
    "production_deployment": false,
    "push": false,
    "release_claim": false
  },
  "rules": {
    "browser_business_storage": "FORBIDDEN",
    "cluster_relation_only": true,
    "cross_batch_borrowing": "FORBIDDEN",
    "cursor": "OPAQUE_VERSIONED_CHECKSUMMED",
    "gui_business_recomputation": "FORBIDDEN",
    "latest_fallback": "FORBIDDEN",
    "non_launch_behavior_source": "NOT_ADMITTED_G10_SOURCE_MATRIX",
    "single_exact_batch_scope": true,
    "unknown_batch": "HTTP_404_UNDER_READY_BACKEND"
  },
  "schema": "TPAA_G7_BATCH_EVENTS_APPROVAL_V1",
  "single_owner_rules": {
    "attack_cluster_resolver": "tpaa_application.weapon_event",
    "batch_events_query": "tpaa_application.batch_events",
    "browser_business_storage": "FORBIDDEN",
    "gui_business_recomputation": "FORBIDDEN",
    "weapon_event_detector": "tpaa_application.weapon_event",
    "weapon_event_identity": "tpaa_application.weapon_event"
  },
  "status": "APPROVED_LOCAL"
} as const;
