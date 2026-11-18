"""plan3d_jobs: which user and project a PlanTo3D job belongs to

Revision ID: 20261118_0001
Revises:
Create Date: 2026-11-18

The 3D gateway (app/modules/plan3d) records every job it starts on the private PlanTo3D
service here, and checks each request against it. Not applied automatically: run

    uv --directory backend run alembic upgrade head

with DATABASE_URL pointing at the database, or paste the SQL of docs/08-3d.md into the
Supabase SQL editor.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261118_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plan3d_jobs",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.Text(), nullable=False, server_default="upload"),
        sa.Column("quality", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("id ~ '^[a-f0-9]{12}$'", name="plan3d_jobs_id_format"),
        sa.CheckConstraint("source in ('upload', 'sample')", name="plan3d_jobs_source"),
        sa.CheckConstraint(
            "quality is null or quality in ('low', 'medium', 'high')", name="plan3d_jobs_quality"
        ),
    )
    op.create_index("plan3d_jobs_user_created", "plan3d_jobs", ["user_id", "created_at"])
    op.create_index("plan3d_jobs_project", "plan3d_jobs", ["project_id"])
    # The backend uses the service key, which is not subject to row-level security. The
    # policy is for any other client: a user can read only their own rows.
    op.execute("alter table plan3d_jobs enable row level security")
    op.execute(
        "create policy plan3d_jobs_owner_read on plan3d_jobs "
        "for select using (auth.uid() = user_id)"
    )


def downgrade() -> None:
    op.execute("drop policy if exists plan3d_jobs_owner_read on plan3d_jobs")
    op.drop_index("plan3d_jobs_project", table_name="plan3d_jobs")
    op.drop_index("plan3d_jobs_user_created", table_name="plan3d_jobs")
    op.drop_table("plan3d_jobs")
