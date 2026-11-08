// @generated from CB-1.14.0 Canonical DTO/Replay authorities; DO NOT EDIT.

export interface ReplayContextDTO {
  readonly schema: string;
  readonly reason_code: string;
  readonly release_id: string;
  readonly context_id: string;
  readonly ranges: Readonly<Record<string, unknown>>;
  readonly weapon_event_id: string;
  readonly batch_id: string;
  readonly perspective: string;
  readonly t1_session_time_us: string;
  readonly t2_session_time_us: string | null;
  readonly t3_session_time_us: string | null;
  readonly window_state: string;
  readonly media_ranges: Readonly<Record<string, unknown>>;
}

export const G9_REPLAY_ROUTES = {
  "gui.replay": {
    "method": "GET",
    "path": "/api/v1/gui/weapon-events/{weapon_event_id}/replay-context",
    "responseDto": "ReplayContextDTO"
  }
} as const;
export const G9_REPLAY_AUTHORITY = {
  "activation_status": "ACTIVE",
  "approval_id": "G9-CB-1.14.0-LOCAL-IMPLEMENTATION-2026-11-07",
  "approved_at": "2026-11-07T00:00:00+08:00",
  "approved_core_baseline": "CB-1.14.0",
  "approver": "PROJECT_OWNER_G9_IMPLEMENTATION_DIRECTIVE",
  "authority_id": "GUI_REPLAY_AUTHORITY",
  "authority_version": "1.0.0",
  "core_baseline": "CB-1.14.0",
  "database": {
    "migration_required": false,
    "reason": "Replay context is an exact-WE read model over existing WE/Window facts; media ranges are honest-empty until the media pipeline is admitted.",
    "schema": "1.10.0"
  },
  "decision_id": "G9-V33-REPLAY-2026-11-07",
  "parent_core_baseline": "CB-1.13.0",
  "release_claim": false,
  "restrictions": {
    "production_deployment": false,
    "push": false,
    "release_claim": false
  },
  "rules": {
    "browser_business_storage": "FORBIDDEN",
    "drift": "EXPLICIT_STATE",
    "exact_we_scope": true,
    "gui_business_recomputation": "FORBIDDEN",
    "latest_fallback": "FORBIDDEN",
    "media_unavailable": "HONEST_EMPTY_RANGES",
    "unknown_we": "HTTP_404_UNDER_READY_BACKEND"
  },
  "schema": "TPAA_G9_REPLAY_APPROVAL_V1",
  "single_owner_rules": {
    "browser_business_storage": "FORBIDDEN",
    "event_window_resolver": "tpaa_application.event_window",
    "gui_business_recomputation": "FORBIDDEN",
    "replay_context_query": "tpaa_application.replay_context",
    "weapon_event_read_model": "tpaa_application.weapon_event"
  },
  "status": "APPROVED_LOCAL"
} as const;
