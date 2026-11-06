"""G1 v33 governed DB schema 1.9.0 -> 1.10.0."""

from __future__ import annotations

revision = "0004_g1_v33_db_1_10_0"
down_revision: str | None = "0003_acp221_db_1_9_0"
branch_labels: str | None = None
depends_on: str | None = None

SOURCE_DB_SCHEMA_VERSION = "1.9.0"
TARGET_DB_SCHEMA_VERSION = "1.10.0"
NEW_RELATIONS = (
    "registry.batch_registration",
    "registry.batch_training_type_revision",
    "context.force_formation_context_revision",
    "context.force_formation_member",
)


def upgrade() -> None:
    from alembic import op

    op.execute(
        """CREATE TABLE registry.batch_registration (
        batch_id uuid PRIMARY KEY,
        session_id uuid NOT NULL REFERENCES registry.training_session(session_id),
        batch_date date NOT NULL,
        batch_training_type text NOT NULL CHECK (batch_training_type IN
          ('SIMPLE_OPPOSITION','MIXED_OPPOSITION','COMPREHENSIVE_OPPOSITION','UNCLASSIFIED')),
        training_type_confirmed boolean NOT NULL DEFAULT false,
        context_id uuid NULL,
        release_id uuid NULL,
        qualification_status text NOT NULL,
        source_manifest_sha256 char(64) NOT NULL,
        revision_no integer NOT NULL CHECK (revision_no >= 1),
        created_by text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (session_id, batch_id), UNIQUE (batch_id, revision_no))"""
    )
    op.execute(
        """CREATE TABLE registry.batch_training_type_revision (
        revision_id uuid PRIMARY KEY,
        batch_id uuid NOT NULL REFERENCES registry.batch_registration(batch_id),
        revision_no integer NOT NULL CHECK (revision_no >= 1),
        old_training_type text NULL, new_training_type text NOT NULL,
        reason text NOT NULL, changed_by text NOT NULL,
        changed_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (batch_id, revision_no))"""
    )
    op.execute(
        """CREATE TABLE context.force_formation_context_revision (
        context_revision_id uuid PRIMARY KEY, context_id uuid NOT NULL,
        revision_no integer NOT NULL CHECK (revision_no >= 1),
        valid_from_session_time_us bigint NOT NULL,
        valid_to_session_time_us bigint NULL, source text NOT NULL,
        reason text NOT NULL, changed_by text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (context_id, revision_no))"""
    )
    op.execute(
        """CREATE TABLE context.force_formation_member (
        context_revision_id uuid NOT NULL REFERENCES
          context.force_formation_context_revision(context_revision_id),
        aircraft_id uuid NOT NULL, formation_id text NULL,
        side text NOT NULL CHECK (side IN ('RED','BLUE','NEUTRAL','UNASSIGNED','CONFLICT')),
        member_role text NOT NULL, independent_target boolean NOT NULL DEFAULT false,
        PRIMARY KEY (context_revision_id, aircraft_id))"""
    )


def downgrade() -> None:
    from alembic import op
    from sqlalchemy import text

    bind = op.get_bind()
    for qualified_name in reversed(NEW_RELATIONS):
        schema, relation = qualified_name.split(".", 1)
        count = bind.execute(text(f'SELECT COUNT(*) FROM "{schema}"."{relation}"')).scalar_one()
        if int(count) != 0:
            raise RuntimeError(f"G1_DOWNGRADE_NONEMPTY relation={qualified_name}")
    for qualified_name in reversed(NEW_RELATIONS):
        schema, relation = qualified_name.split(".", 1)
        op.execute(f'DROP TABLE "{schema}"."{relation}"')
