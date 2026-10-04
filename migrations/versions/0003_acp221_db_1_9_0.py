"""ACP-221 governed DB schema 1.8.0 -> 1.9.0 correction."""

from __future__ import annotations

revision = "0003_acp221_db_1_9_0"
down_revision: str | None = "0002_acp219_db_1_8_0"
branch_labels: str | None = None
depends_on: str | None = None

SOURCE_DB_SCHEMA_VERSION = "1.8.0"
TARGET_DB_SCHEMA_VERSION = "1.9.0"
NEW_RELATIONS = (
    "assessment.annotation_subject_context",
)
UPGRADE_SQL = (
    'CREATE TABLE "assessment"."annotation_subject_context" (\n'
    '  annotation_id uuid PRIMARY KEY REFERENCES debrief.annotation(annotation_id),\n'
    '  subject_context_id text NOT NULL REFERENCES assessment.p4_subject_context(subject_context_id)\n'
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
                f"ACP221_DOWNGRADE_NONEMPTY relation={qualified_name}"
            )
    for qualified_name in reversed(NEW_RELATIONS):
        schema, relation = qualified_name.split(".", 1)
        op.execute(f'DROP TABLE "{schema}"."{relation}"')
