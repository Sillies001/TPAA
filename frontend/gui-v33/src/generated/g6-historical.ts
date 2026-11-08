// @generated from CB-1.11.0 Canonical DTO/Historical-overview authorities; DO NOT EDIT.

export interface BatchOverviewSummaryDTO {
  readonly schema: string;
  readonly provenance: Readonly<Record<string, unknown>>;
  readonly batch_id: string;
  readonly batch_date: string;
  readonly batch_training_type: string;
  readonly sortie_count: number;
  readonly episode_count: number;
  readonly weapon_event_count: number;
  readonly adjudicated_event_count: number;
  readonly qualification_status: string;
  readonly has_event_detail: boolean;
}

export interface TaskMetricTrendDTO {
  readonly schema: string;
  readonly provenance: Readonly<Record<string, unknown>>;
  readonly metric_id: string;
  readonly label: string;
  readonly unit: string | null;
  readonly definition_version: string | null;
  readonly status: string;
  readonly numerator: number | null;
  readonly denominator: number | null;
  readonly value: string | null;
  readonly reason: string | null;
  readonly points: Readonly<Record<string, unknown>>;
}

export interface EquipmentMetricTrendDTO {
  readonly schema: string;
  readonly provenance: Readonly<Record<string, unknown>>;
  readonly metric_id: string;
  readonly label: string;
  readonly unit: string;
  readonly comparable: boolean;
  readonly eligibility: string;
  readonly reason: string | null;
  readonly points: Readonly<Record<string, unknown>>;
}

export interface HistoricalTrainingOverviewDTO {
  readonly schema: string;
  readonly provenance: Readonly<Record<string, unknown>>;
  readonly query_context_id: string;
  readonly filter: Readonly<Record<string, unknown>>;
  readonly kpi: Readonly<Record<string, unknown>>;
  readonly task_metric_trends: Readonly<Record<string, unknown>>;
  readonly activity_trend: Readonly<Record<string, unknown>>;
  readonly outcome_trend: Readonly<Record<string, unknown>>;
  readonly category_composition: Readonly<Record<string, unknown>>;
  readonly equipment_trends: Readonly<Record<string, unknown>>;
  readonly batches: Readonly<Record<string, unknown>>;
  readonly batch_set_fingerprint: string;
  readonly aggregation_cutoff: string;
}

export const G6_HISTORICAL_ROUTES = {
  "gui.overview": {
    "method": "GET",
    "path": "/api/v1/gui/historical-overview",
    "responseDto": "HistoricalTrainingOverviewDTO"
  }
} as const;
export const G6_HISTORICAL_AUTHORITY = {
  "activation_status": "ACTIVE",
  "approval_id": "G6-CB-1.11.0-LOCAL-IMPLEMENTATION-2026-11-07",
  "approved_at": "2026-11-07T00:00:00+08:00",
  "approved_core_baseline": "CB-1.11.0",
  "approver": "PROJECT_OWNER_G6_IMPLEMENTATION_DIRECTIVE",
  "authority_id": "GUI_HISTORICAL_OVERVIEW_AUTHORITY",
  "authority_version": "1.0.0",
  "core_baseline": "CB-1.11.0",
  "database": {
    "migration_required": false,
    "reason": "Historical overview is an exact-batch-set read model over existing Batch/WE tables; no new physical tables.",
    "schema": "1.10.0"
  },
  "decision_id": "G6-V33-HISTORICAL-OVERVIEW-2026-11-07",
  "parent_core_baseline": "CB-1.10.0",
  "release_claim": false,
  "restrictions": {
    "production_deployment": false,
    "push": false,
    "release_claim": false
  },
  "rules": {
    "equipment_comparability": "FAIL_CLOSED",
    "invalid_date_range": "FAIL_CLOSED_EMPTY_WITH_WARNING",
    "latest_fallback": "FORBIDDEN",
    "missing_j": "EXCLUDED_FROM_ADJUDICATED",
    "query_context_traceable": true,
    "ratio_recompute": "AGGREGATE_NUMERATOR_DENOMINATOR",
    "simple_average": "FORBIDDEN",
    "single_batch_workset": true,
    "unclassified_batch_type": "LISTED_SEPARATELY",
    "zero_denominator": "FAIL_CLOSED_NULL_REASON"
  },
  "schema": "TPAA_G6_HISTORICAL_OVERVIEW_APPROVAL_V1",
  "single_owner_rules": {
    "browser_business_storage": "FORBIDDEN",
    "gui_business_recomputation": "FORBIDDEN",
    "historical_overview_query": "tpaa_application.historical_overview",
    "task_metric_aggregation": "tpaa_application.historical_overview"
  },
  "status": "APPROVED_LOCAL",
  "task_metric_authority": "SEPARATE_METRIC_ADMISSION_NOT_AUTO_P1"
} as const;
