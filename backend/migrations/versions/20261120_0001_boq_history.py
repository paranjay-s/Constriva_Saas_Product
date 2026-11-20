"""boq_history: the saved bills of quantities of each user

Revision ID: 20261120_0001
Revises: 20261119_0002
Create Date: 2026-11-20

Every finished BOQ is saved for its owner (app/modules/sheets/boq_history.py). Rows are read and
deleted only by owner; row-level security allows a signed-in user their own rows (the backend
uses the service key and checks the owner itself). Not applied automatically: run

    uv --directory backend run alembic upgrade head

or paste the SQL listed in docs/pro/SUMMARY.md ("SQL to run") into the Supabase SQL editor.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261120_0001"
down_revision: str | None = "20261119_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "boq_history",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False, server_default=""),
        sa.Column("source", sa.Text(), nullable=False, server_default="upload"),
        sa.Column(
            "summary", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("result", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("source in ('upload', 'floorplan', '3d')", name="boq_history_source"),
    )
    op.create_index(
        "boq_history_user_created", "boq_history", ["user_id", sa.text("created_at desc")]
    )
    op.execute("alter table boq_history enable row level security")
    op.execute(
        "create policy boq_history_owner on boq_history for all "
        "using (auth.uid() = user_id) with check (auth.uid() = user_id)"
    )


def downgrade() -> None:
    op.execute("drop policy if exists boq_history_owner on boq_history")
    op.drop_index("boq_history_user_created", table_name="boq_history")
    op.drop_table("boq_history")
