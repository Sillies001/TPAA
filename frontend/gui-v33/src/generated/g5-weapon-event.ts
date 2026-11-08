// @generated from CB-1.10.0 Canonical DTO/Weapon-Event authorities; DO NOT EDIT.

export interface WeaponEventDetailDTO {
  readonly schema: string;
  readonly provenance: Readonly<Record<string, unknown>>;
  readonly weapon_event_id: string;
  readonly batch_id: string;
  readonly release_id: string | null;
  readonly category: string;
  readonly category_rule_version: string;
  readonly classification_exception: boolean;
  readonly shooter_entity_id: string;
  readonly target_entity_id: string | null;
  readonly episode_id: string | null;
  readonly t1_session_time_us: string;
  readonly weapon_terminal_state: string;
  readonly adjudication_state: string;
  readonly observation_window_state: string;
  readonly cluster_id: string | null;
}

export interface WeaponEventWindowDTO {
  readonly schema: string;
  readonly provenance: Readonly<Record<string, unknown>>;
  readonly weapon_event_id: string;
  readonly perspective: string;
  readonly resolver_version: string;
  readonly start_session_time_us: string;
  readonly end_session_time_us: string | null;
  readonly t0s_session_time_us: string | null;
  readonly t0t_session_time_us: string | null;
  readonly t1_session_time_us: string;
  readonly t2_session_time_us: string | null;
  readonly t3_session_time_us: string | null;
  readonly cue_session_time_us: string | null;
  readonly response_session_time_us: string | null;
  readonly j_session_time_us: string | null;
  readonly terminal_state: string;
  readonly adjudication_state: string;
  readonly window_state: string;
  readonly alignment_state: string;
  readonly coverage: string;
  readonly reason: string | null;
}

export interface WeaponEventPerspectiveDTO {
  readonly schema: string;
  readonly provenance: Readonly<Record<string, unknown>>;
  readonly weapon_event_id: string;
  readonly perspective: string;
  readonly projection_version: string;
  readonly allowed: boolean;
  readonly denial_reason: string | null;
  readonly geometry_available: boolean;
  readonly series_available: boolean;
}

export const G5_WEAPON_EVENT_ROUTES = {
  "gui.event.detail": {
    "method": "GET",
    "path": "/api/v1/gui/weapon-events/{weapon_event_id}",
    "responseDto": "WeaponEventDetailDTO"
  },
  "gui.event.perspective": {
    "method": "GET",
    "path": "/api/v1/gui/weapon-events/{weapon_event_id}/perspectives/{perspective}",
    "responseDto": "WeaponEventPerspectiveDTO"
  },
  "gui.event.window": {
    "method": "GET",
    "path": "/api/v1/gui/weapon-events/{weapon_event_id}/windows/{perspective}",
    "responseDto": "WeaponEventWindowDTO"
  }
} as const;
export const G5_WEAPON_EVENT_AUTHORITY = {
  "activation_status": "ACTIVE",
  "adjudication_states": [
    "ADJUDICATED",
    "ADJUDICATION_PENDING"
  ],
  "alignment_states": [
    "ALIGNED",
    "ALIGNMENT_UNRESOLVED"
  ],
  "approval_id": "G5-CB-1.10.0-LOCAL-IMPLEMENTATION-2026-11-07",
  "authority_id": "GUI_WEAPON_EVENT_AUTHORITY",
  "authority_version": "1.0.0",
  "capability_status": {
    "api_routes_registration": "ACTIVE",
    "atomic_activation_rollback": "ACTIVE",
    "canonical_source_store_adapter": "ACTIVE",
    "cluster_stability_and_query": "ACTIVE",
    "cross_batch_ingress_rejection": "ACTIVE",
    "cross_batch_rejection_audit": "ACTIVE",
    "direct_api_negative_tests": "ACTIVE",
    "dto_single_source_generation": "ACTIVE",
    "event_window_resolver": "ACTIVE",
    "exact_we_release_context_scope": "ACTIVE",
    "four_state_read_model": "ACTIVE",
    "identity_supersession": "ACTIVE",
    "perspective_projection": "ACTIVE",
    "trusted_capability_resolver": "ACTIVE",
    "we_detection_identity_linker_category_cluster": "ACTIVE"
  },
  "categories": [
    "WVR",
    "BVR",
    "STRIKE",
    "UNKNOWN"
  ],
  "core_baseline": "CB-1.10.0",
  "database": {
    "migration_required": false,
    "reason": "WE via existing Event subtype/relations; Cluster via existing Relation subtype; Window/Perspective are rebuildable non-persistent projections.",
    "schema": "1.10.0"
  },
  "decision_id": "G5-V33-WEAPON-EVENT-2026-11-07",
  "parent_core_baseline": "CB-1.9.0",
  "release_claim": false,
  "rules": {
    "capability_states": [
      "CAPABILITY_DISABLED",
      "ADAPTER_UNAVAILABLE",
      "EMPTY",
      "READY"
    ],
    "cluster_cardinality": "RELATION_ONLY_MULTIPLE_WE",
    "cluster_identity_stability": "UUID_FROM_SORTED_WE_ID_SET_ONLY",
    "cross_batch_ingress_rejection": "DETECTOR_IDENTITY_IMMEDIATE_AUDITED",
    "cross_batch_we_borrowing": "FORBIDDEN",
    "dto_single_source": "CANONICAL_CONTRACT_GENERATES_PYTHON_AND_TYPESCRIPT",
    "exact_identity_no_latest_fallback": true,
    "historical_revision_reproducible": true,
    "http_404_semantics": "EXACT_WEAPON_EVENT_ABSENT_UNDER_READY_BACKEND",
    "identity_supersession": "SOURCE_REVISION_YIELDS_NEW_UUID_SUPERSEDES_OLD_NO_INPLACE_MUTATION",
    "t2_unknown_semantics": "TERMINAL_UNKNOWN",
    "terminal_adjudication_window_independent": true,
    "we_cardinality": "ONE_PER_WEAPON_LAUNCH",
    "window_interval": "HALF_OPEN_START_INCLUSIVE",
    "window_overlap": "ALLOWED_WITHIN_EPISODE"
  },
  "single_owner_rules": {
    "attack_cluster_resolver": "tpaa_application.weapon_event",
    "browser_business_storage": "FORBIDDEN",
    "event_window_resolver": "tpaa_application.event_window",
    "gui_business_recomputation": "FORBIDDEN",
    "perspective_projection": "tpaa_application.perspective",
    "weapon_category_resolver": "tpaa_application.weapon_event",
    "weapon_event_detector": "tpaa_application.weapon_event",
    "weapon_event_episode_linker": "tpaa_application.weapon_event",
    "weapon_event_identity": "tpaa_application.weapon_event"
  },
  "terminal_states": [
    "TERMINAL_KNOWN",
    "TERMINAL_UNKNOWN"
  ],
  "window_states": [
    "WINDOW_OPEN",
    "WINDOW_PARTIAL",
    "WINDOW_CLOSED"
  ]
} as const;
