// @generated from CB-1.9.0 GUI_BATCH_IMPORT_AUTHORITY; DO NOT EDIT.

export type BatchTrainingType =
  | "SIMPLE_OPPOSITION"
  | "MIXED_OPPOSITION"
  | "COMPREHENSIVE_OPPOSITION"
  | "UNCLASSIFIED";
export type BatchQualificationStatus =
  | "PENDING_CONFIRMATION"
  | "PARSING"
  | "QUALIFIED"
  | "FAILED";

export interface ImportTicketDTO {
  readonly schema: "TPAA_G4_IMPORT_TICKET_V1";
  readonly ticket_id: string;
  readonly kind: "FILE" | "DIRECTORY";
  readonly entry_count: number;
  readonly size_bytes: number;
  readonly manifest_sha256: string;
  readonly expires_at: string;
  readonly local_path: null;
}

export interface BatchRegistrationDTO {
  readonly schema: "TPAA_G4_BATCH_REGISTRATION_V1";
  readonly batch_id: string;
  readonly session_id: string;
  readonly batch_date: string;
  readonly batch_training_type: BatchTrainingType;
  readonly training_type_confirmed: boolean;
  readonly context_id: string | null;
  readonly release_id: string | null;
  readonly qualification_status: BatchQualificationStatus;
  readonly source_manifest_sha256: string;
  readonly revision_no: number;
  readonly created_by: string;
  readonly created_at: string;
  readonly reason_code: string | null;
  readonly v01_eligible: boolean;
}

export interface BatchListDTO {
  readonly schema: "TPAA_G4_BATCH_LIST_V1";
  readonly items: readonly BatchRegistrationDTO[];
  readonly total_count: number;
}

export interface ForceFormationMemberDTO {
  readonly aircraft_id: string;
  readonly formation_id: string | null;
  readonly side: "RED" | "BLUE" | "NEUTRAL" | "UNASSIGNED" | "CONFLICT";
  readonly member_role: string;
  readonly independent_target: boolean;
}

export interface ForceFormationContextDTO {
  readonly schema: "TPAA_G4_FORCE_FORMATION_CONTEXT_V1";
  readonly context_revision_id: string;
  readonly context_id: string;
  readonly revision_no: number;
  readonly valid_from_session_time_us: number;
  readonly valid_to_session_time_us: number | null;
  readonly source: string;
  readonly reason: string;
  readonly changed_by: string;
  readonly members: readonly ForceFormationMemberDTO[];
}

export const G4_BATCH_ROUTES = {
  "gui.batch.detail": {
    "method": "GET",
    "path": "/api/v1/gui/batches/{batch_id}",
    "responseDto": "BatchRegistrationDTO"
  },
  "gui.batch.register": {
    "method": "POST",
    "path": "/api/v1/gui/batches",
    "responseDto": "BatchRegistrationDTO"
  },
  "gui.batch.training_type": {
    "method": "POST",
    "path": "/api/v1/gui/batches/{batch_id}/training-type-revisions",
    "responseDto": "BatchRegistrationDTO"
  },
  "gui.batches": {
    "method": "GET",
    "path": "/api/v1/gui/batches",
    "responseDto": "BatchListDTO"
  },
  "gui.context": {
    "method": "GET",
    "path": "/api/v1/gui/contexts/{context_id}/force-formation",
    "responseDto": "ForceFormationContextDTO"
  },
  "gui.context.revise": {
    "method": "POST",
    "path": "/api/v1/gui/contexts/{context_id}/force-formation-revisions",
    "responseDto": "ForceFormationContextDTO"
  },
  "gui.import.ticket": {
    "method": "POST",
    "path": "/api/v1/gui/import-tickets",
    "responseDto": "ImportTicketDTO"
  }
} as const;
export const G4_BATCH_AUTHORITY = {
  "activation_status": "ACTIVE",
  "approval_id": "G4-CB-1.9.0-LOCAL-IMPLEMENTATION-2026-11-06",
  "authority_id": "GUI_BATCH_IMPORT_AUTHORITY",
  "authority_version": "1.0.0",
  "core_baseline": "CB-1.9.0",
  "database": {
    "migration_required": false,
    "reason": "G1 DB 1.10.0 already admitted all four G4 physical tables.",
    "schema": "1.10.0"
  },
  "decision_id": "G4-V33-BATCH-IMPORT-2026-11-06",
  "parent_core_baseline": "CB-1.8.0",
  "qualification_states": [
    "PENDING_CONFIRMATION",
    "PARSING",
    "QUALIFIED",
    "FAILED"
  ],
  "release_claim": false,
  "rules": {
    "default_training_type_forbidden": true,
    "failure_retry": "SAME_IDEMPOTENCY_KEY_AND_IMMUTABLE_MANIFEST",
    "force_formation_revision": "AUDITED_EFFECTIVE_TIME_APPEND_ONLY",
    "local_path_exposure": "FORBIDDEN",
    "stable_batch_id": "UUID5(actor,idempotency_key)",
    "ticket_max_bytes": 67108864,
    "ticket_storage": "PROCESS_MEMORY_ONLY",
    "ticket_ttl_seconds": 600,
    "training_type_explicit_confirmation": true,
    "training_type_revision": "AUDITED_APPEND_ONLY",
    "unconfirmed_training_type": "UNCLASSIFIED",
    "v01_admission": "QUALIFIED_ONLY"
  },
  "state_transitions": {
    "FAILED": [
      "PARSING"
    ],
    "PARSING": [
      "QUALIFIED",
      "FAILED"
    ],
    "PENDING_CONFIRMATION": [
      "PARSING"
    ],
    "QUALIFIED": []
  },
  "training_types": [
    "SIMPLE_OPPOSITION",
    "MIXED_OPPOSITION",
    "COMPREHENSIVE_OPPOSITION",
    "UNCLASSIFIED"
  ]
} as const;
