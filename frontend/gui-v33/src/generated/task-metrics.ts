/* Generated from Canonical CB-1.18.0-candidate; do not edit. */

export type DecimalString = string;
export type TaskMetricStatus =
  | "READY"
  | "PENDING"
  | "N_A"
  | "INSUFFICIENT"
  | "INVALID"
  | "ERROR"
  | "INCOMPARABLE";

export type TaskMetricAdmissionStatus =
  | "CANDIDATE_TEST_ONLY"
  | "CANDIDATE_AWAITING_BUSINESS_APPROVAL"
  | "ADMITTED"
  | "RETIRED";

export interface TaskMetricDefinitionDTO {
  semantic_id: string;
  definition_version: string;
  definition_sha256: string;
  name_zh: string;
  name_en: string;
  value_kind: string;
  unit: string;
  direction: string;
  applicable_training_types: readonly string[];
  admission_status: TaskMetricAdmissionStatus;
  display_decimal_places: number;
}

export interface TaskMetricResultDTO {
  result_id: string;
  semantic_id: string;
  definition_version: string;
  definition_sha256: string;
  batch_id: string;
  session_id: string;
  release_id: string;
  context_id: string;
  evaluated_side: "RED" | "BLUE";
  numerator: DecimalString | null;
  denominator: DecimalString | null;
  value: DecimalString | null;
  status: TaskMetricStatus;
  reason_codes: readonly string[];
  coverage: number;
  j_state: string;
  source_refs: readonly Readonly<Record<string, unknown>>[];
  evidence_refs: readonly Readonly<Record<string, unknown>>[];
  computed_at: string;
  algorithm_contract_sha256: string;
}

export interface ExactBatchScopeDTO {
  batch_id: string;
  session_id: string;
  release_id: string;
  context_id: string;
}

export interface TaskMetricCompareRequestDTO {
  semantic_id: string;
  definition_version: string;
  batch_scopes: readonly ExactBatchScopeDTO[];
  evaluated_side: "RED" | "BLUE";
  phase_scope: string;
  start_session_time_us: DecimalString;
  end_session_time_us: DecimalString;
}

export interface TaskMetricEvidenceDTO {
  semantic_id: string;
  definition_sha256: string;
  source_refs: readonly Readonly<Record<string, unknown>>[];
  evidence_refs: readonly Readonly<Record<string, unknown>>[];
  scope_hash: string;
  result_sha256: string;
}
