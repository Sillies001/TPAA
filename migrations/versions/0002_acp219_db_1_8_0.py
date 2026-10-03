"""ACP-219 governed DB schema 1.7.0 -> 1.8.0 correction."""

from __future__ import annotations

revision = "0002_acp219_db_1_8_0"
down_revision: str | None = "0001_acp216_db_1_7_0"
branch_labels: str | None = None
depends_on: str | None = None

SOURCE_DB_SCHEMA_VERSION = "1.7.0"
TARGET_DB_SCHEMA_VERSION = "1.8.0"
NEW_RELATIONS = (
    "assessment.actor_assessment_machine_evidence_ref",
    "assessment.mission_assessment_objective_ref",
)
UPGRADE_SQL = (
    'CREATE TABLE "assessment"."actor_assessment_machine_evidence_ref" (\n'
    '  actor_assessment_id uuid NOT NULL REFERENCES assessment.actor_assessment(actor_assessment_id),\n'
    '  ref_order integer NOT NULL,\n'
    '  evidence_ref text NOT NULL,\n'
    '  PRIMARY KEY (actor_assessment_id, ref_order),\n'
    '  UNIQUE (actor_assessment_id, evidence_ref)\n'
    ')',
    'CREATE TABLE "assessment"."mission_assessment_objective_ref" (\n'
    '  mission_assessment_id uuid NOT NULL REFERENCES assessment.mission_assessment(mission_assessment_id),\n'
    '  ref_order integer NOT NULL,\n'
    '  objective_ref text NOT NULL,\n'
    '  PRIMARY KEY (mission_assessment_id, ref_order),\n'
    '  UNIQUE (mission_assessment_id, objective_ref)\n'
    ')',
)


def upgrade() -> None:
    from alembic import op
    for statement in UPGRADE_SQL:
        op.execute(statement)


def downgrade() -> None:
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
                f"ACP219_DOWNGRADE_NONEMPTY relation={qualified_name}"
            )
    for qualified_name in reversed(NEW_RELATIONS):
        schema, relation = qualified_name.split(".", 1)
        op.execute(f'DROP TABLE "{schema}"."{relation}"')
