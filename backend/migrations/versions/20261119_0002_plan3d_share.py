"""plan3d_jobs.share_id: the current share link of a job's walkthrough (null: not shared)

Revision ID: 20261119_0002
Revises: 20261119_0001
Create Date: 2026-11-19

A share link carries the job and a share id; it works while the job's row holds the same id.
Revoking sets it to null, a new link replaces it, so older links stop working at once.
Not applied automatically: run

    uv --directory backend run alembic upgrade head
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261119_0002"
down_revision: str | None = "20261119_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("plan3d_jobs", sa.Column("share_id", sa.Text(), nullable=True))
    op.create_check_constraint(
        "plan3d_jobs_share_id", "plan3d_jobs", "share_id is null or share_id ~ '^[a-f0-9]{24}$'"
    )


def downgrade() -> None:
    op.drop_constraint("plan3d_jobs_share_id", "plan3d_jobs", type_="check")
    op.drop_column("plan3d_jobs", "share_id")
