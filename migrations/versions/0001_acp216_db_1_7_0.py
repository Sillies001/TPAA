"""ACP-216 first governed Alembic-compatible DB schema revision."""

from __future__ import annotations

revision = "0001_acp216_db_1_7_0"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None

SOURCE_DB_SCHEMA_VERSION = "1.6.0"
TARGET_DB_SCHEMA_VERSION = "1.7.0"
NEW_RELATIONS = (
    "capability.adjusted_capability_estimate_revision",
    "assessment.attribution_run_request_binding",
    "registry.mutation_idempotency",
    "assessment.p4_subject_context",
    "assessment.actor_assessment_revision",
    "assessment.actor_assessment_annotation_ref",
    "assessment.p5_composition_snapshot",
    "assessment.p5_composition_participant",
    "assessment.mission_assessment_revision",
    "intelligence.forecast_request",
    "capability.p6_model_revision",
    "intelligence.forecast_result_revision",
    "intelligence.counterfactual_request",
    "intelligence.counterfactual_revision",
    "intelligence.training_recommendation_revision",
)
UPGRADE_SQL = (
    "CREATE TABLE \"capability\".\"adjusted_capability_estimate_revision\" (\\n  estimate_id uuid PRIMARY KEY REFERENCES capability.adjusted_capability_estimate(estimate_id),\\n  p2_release_id uuid NOT NULL REFERENCES registry.analysis_release(release_id),\\n  reason_codes text[] NOT NULL DEFAULT '{}'\\n)",
    "CREATE TABLE \"assessment\".\"attribution_run_request_binding\" (\\n  attribution_run_id uuid PRIMARY KEY REFERENCES assessment.attribution_run(attribution_run_id),\\n  run_request_hash char(64) NOT NULL,\\n  compute_job_id uuid NULL REFERENCES registry.compute_job(job_id)\\n)",
    "CREATE TABLE \"registry\".\"mutation_idempotency\" (\\n  operation_code text NOT NULL,\\n  request_id text NOT NULL,\\n  request_hash char(64) NOT NULL,\\n  result_object_type text NOT NULL,\\n  result_object_id text NOT NULL,\\n  actor_id uuid NULL,\\n  created_at timestamptz NOT NULL DEFAULT now(),\\n  PRIMARY KEY (operation_code, request_id)\\n)",
    "CREATE TABLE \"assessment\".\"p4_subject_context\" (\\n  subject_context_id text PRIMARY KEY,\\n  subject_key text NOT NULL,\\n  actor_id uuid NOT NULL,\\n  role_code text NOT NULL,\\n  seat_code text NULL,\\n  function_code text NULL,\\n  session_id uuid NOT NULL REFERENCES registry.training_session(session_id),\\n  episode_id uuid NOT NULL REFERENCES episode.training_episode(episode_id),\\n  stage_id uuid NULL REFERENCES episode.episode_stage(stage_id),\\n  aircraft_id uuid NULL,\\n  twin_revision_id uuid NOT NULL REFERENCES capability.aircraft_twin_revision(twin_revision_id),\\n  p3_estimate_id uuid NULL REFERENCES capability.intrinsic_capability_estimate(estimate_id),\\n  assessment_spec_id text NOT NULL,\\n  assessment_spec_version text NOT NULL,\\n  role_model_context_artifact_id uuid NOT NULL REFERENCES registry.context_artifact(context_artifact_id),\\n  role_model_version text NOT NULL,\\n  world_refs text[] NOT NULL DEFAULT '{}',\\n  evidence_set_id uuid NOT NULL REFERENCES metric.evidence_set(evidence_set_id),\\n  as_of_utc timestamptz NOT NULL,\\n  knowledge_time_utc timestamptz NOT NULL\\n)",
    "CREATE TABLE \"assessment\".\"actor_assessment_revision\" (\\n  actor_assessment_id uuid PRIMARY KEY REFERENCES assessment.actor_assessment(actor_assessment_id),\\n  subject_context_id text NOT NULL REFERENCES assessment.p4_subject_context(subject_context_id),\\n  approval_state text NOT NULL,\\n  p3_claim_level text NOT NULL,\\n  p3_validity_status text NOT NULL,\\n  p3_as_of_utc timestamptz NOT NULL,\\n  uncertainty_lower double precision NULL,\\n  uncertainty_upper double precision NULL,\\n  logical_content_hash char(64) NOT NULL\\n)",
    "CREATE TABLE \"assessment\".\"actor_assessment_annotation_ref\" (\\n  actor_assessment_id uuid NOT NULL REFERENCES assessment.actor_assessment(actor_assessment_id),\\n  ref_order integer NOT NULL,\\n  annotation_id uuid NOT NULL REFERENCES debrief.annotation(annotation_id),\\n  PRIMARY KEY (actor_assessment_id, ref_order),\\n  UNIQUE (actor_assessment_id, annotation_id)\\n)",
    "CREATE TABLE \"assessment\".\"p5_composition_snapshot\" (\\n  composition_id text PRIMARY KEY,\\n  session_id uuid NOT NULL REFERENCES registry.training_session(session_id),\\n  mission_episode_id uuid NOT NULL REFERENCES episode.training_episode(episode_id),\\n  team_id uuid NULL,\\n  world_snapshot_refs text[] NOT NULL DEFAULT '{}',\\n  scenario_context_artifact_id uuid NULL REFERENCES registry.context_artifact(context_artifact_id),\\n  role_model_context_artifact_id uuid NOT NULL REFERENCES registry.context_artifact(context_artifact_id),\\n  assessment_spec_id text NOT NULL,\\n  assessment_spec_version text NOT NULL,\\n  as_of_utc timestamptz NOT NULL,\\n  composition_hash char(64) NOT NULL\\n)",
    "CREATE TABLE \"assessment\".\"p5_composition_participant\" (\\n  composition_id text NOT NULL REFERENCES assessment.p5_composition_snapshot(composition_id),\\n  ref_order integer NOT NULL,\\n  subject_key text NOT NULL,\\n  role_code text NOT NULL,\\n  aircraft_id uuid NULL,\\n  twin_revision_id uuid NULL REFERENCES capability.aircraft_twin_revision(twin_revision_id),\\n  p4_revision_id uuid NOT NULL REFERENCES assessment.actor_assessment(actor_assessment_id),\\n  PRIMARY KEY (composition_id, ref_order),\\n  UNIQUE (composition_id, subject_key)\\n)",
    "CREATE TABLE \"assessment\".\"mission_assessment_revision\" (\\n  mission_assessment_id uuid PRIMARY KEY REFERENCES assessment.mission_assessment(mission_assessment_id),\\n  composition_id text NOT NULL REFERENCES assessment.p5_composition_snapshot(composition_id),\\n  team_performance_evidence_id text NOT NULL,\\n  approval_state text NOT NULL,\\n  claim_level text NOT NULL,\\n  validity_status text NOT NULL,\\n  as_of_utc timestamptz NOT NULL,\\n  logical_content_hash char(64) NOT NULL\\n)",
    "CREATE TABLE \"intelligence\".\"forecast_request\" (\\n  forecast_request_id uuid PRIMARY KEY,\\n  input_snapshot_id uuid NOT NULL REFERENCES registry.dataset_snapshot(dataset_snapshot_id),\\n  forecast_spec_id text NOT NULL,\\n  forecast_spec_version text NOT NULL,\\n  target_scope text NOT NULL,\\n  subject_ref text NOT NULL,\\n  target_code text NOT NULL,\\n  forecast_origin_utc timestamptz NOT NULL,\\n  horizon_spec jsonb NOT NULL,\\n  capability_model_id uuid NOT NULL REFERENCES capability.capability_model(capability_model_id),\\n  model_profile_id text NOT NULL,\\n  model_profile_version text NOT NULL,\\n  training_dataset_snapshot_id uuid NOT NULL REFERENCES registry.dataset_snapshot(dataset_snapshot_id),\\n  validation_dataset_snapshot_id uuid NOT NULL REFERENCES registry.dataset_snapshot(dataset_snapshot_id),\\n  assumption_profile_id text NOT NULL,\\n  assumption_profile_version text NOT NULL,\\n  as_of_utc timestamptz NOT NULL,\\n  request_hash char(64) NOT NULL\\n)",
    "CREATE TABLE \"capability\".\"p6_model_revision\" (\\n  capability_model_id uuid PRIMARY KEY REFERENCES capability.capability_model(capability_model_id),\\n  validation_dataset_snapshot_id uuid NOT NULL REFERENCES registry.dataset_snapshot(dataset_snapshot_id),\\n  applicability_profile_ref text NOT NULL,\\n  uncertainty_profile_ref text NOT NULL\\n)",
    "CREATE TABLE \"intelligence\".\"forecast_result_revision\" (\\n  forecast_result_id uuid PRIMARY KEY REFERENCES intelligence.forecast_result(forecast_result_id),\\n  forecast_identity text NOT NULL,\\n  forecast_request_id uuid NOT NULL REFERENCES intelligence.forecast_request(forecast_request_id),\\n  target_session_order integer NULL,\\n  applicability_status text NOT NULL,\\n  uncertainty jsonb NOT NULL,\\n  factual_source_refs text[] NOT NULL DEFAULT '{}',\\n  model_revision_id uuid NOT NULL REFERENCES capability.capability_model(capability_model_id),\\n  model_artifact_hash char(64) NOT NULL,\\n  as_of_utc timestamptz NOT NULL,\\n  forecast_origin_utc timestamptz NOT NULL,\\n  published_at_utc timestamptz NOT NULL,\\n  supersedes_forecast_result_id uuid NULL REFERENCES intelligence.forecast_result(forecast_result_id),\\n  logical_content_hash char(64) NOT NULL\\n)",
    "CREATE TABLE \"intelligence\".\"counterfactual_request\" (\\n  counterfactual_request_id uuid PRIMARY KEY,\\n  input_snapshot_id uuid NOT NULL REFERENCES registry.dataset_snapshot(dataset_snapshot_id),\\n  base_product_refs text[] NOT NULL DEFAULT '{}',\\n  scenario_definition_id text NOT NULL,\\n  interventions jsonb NOT NULL,\\n  held_fixed_assumptions jsonb NOT NULL,\\n  model_refs text[] NOT NULL DEFAULT '{}',\\n  applicability_profile_ref text NOT NULL,\\n  as_of_utc timestamptz NOT NULL,\\n  request_hash char(64) NOT NULL\\n)",
    "CREATE TABLE \"intelligence\".\"counterfactual_revision\" (\\n  counterfactual_run_id uuid PRIMARY KEY REFERENCES intelligence.counterfactual_run(counterfactual_run_id),\\n  counterfactual_request_id uuid NOT NULL REFERENCES intelligence.counterfactual_request(counterfactual_request_id),\\n  interventions jsonb NOT NULL,\\n  held_fixed_assumptions jsonb NOT NULL,\\n  applicability_profile_ref text NOT NULL,\\n  applicability_status text NOT NULL,\\n  identifiability_status text NOT NULL,\\n  causal_claim_level text NOT NULL,\\n  uncertainty jsonb NOT NULL,\\n  as_of_utc timestamptz NOT NULL,\\n  supersedes_counterfactual_run_id uuid NULL REFERENCES intelligence.counterfactual_run(counterfactual_run_id),\\n  logical_content_hash char(64) NOT NULL\\n)",
    "CREATE TABLE \"intelligence\".\"training_recommendation_revision\" (\\n  recommendation_id uuid PRIMARY KEY REFERENCES intelligence.training_recommendation(recommendation_id),\\n  subject_key text NOT NULL,\\n  source_forecast_result_ids uuid[] NOT NULL DEFAULT '{}',\\n  source_counterfactual_run_ids uuid[] NOT NULL DEFAULT '{}',\\n  objective_constraints jsonb NOT NULL,\\n  allowed_action_space jsonb NOT NULL,\\n  applicability_status text NOT NULL,\\n  uncertainty jsonb NOT NULL,\\n  reviewer_subject_key text NULL,\\n  audit_ref text NULL,\\n  supersedes_recommendation_id uuid NULL REFERENCES intelligence.training_recommendation(recommendation_id),\\n  logical_content_hash char(64) NOT NULL\\n)",
)


def upgrade() -> None:
    """Execute the additive 1.6.0 -> 1.7.0 transition when Alembic is installed."""

    from alembic import op

    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
    """Fail closed unless all 1.7.0 companion relations are empty."""

    from alembic import op
    from sqlalchemy import text

    bind = op.get_bind()
    for qualified_name in NEW_RELATIONS:
        schema, relation = qualified_name.split(".", 1)
        count = bind.execute(
            text(f'SELECT COUNT(*) FROM "{schema}"."{relation}"')
        ).scalar_one()
        if int(count) != 0:
            raise RuntimeError(
                f"ACP216_DOWNGRADE_NONEMPTY relation={qualified_name}"
            )
    for qualified_name in reversed(NEW_RELATIONS):
        schema, relation = qualified_name.split(".", 1)
        op.execute(f'DROP TABLE "{schema}"."{relation}"')
