"""asset_library: the 3D asset library

Room kits, furniture, appliances, fixtures, materials, lighting rigs and parametric builders,
including the assets the creator agent makes.

Revision ID: 20261119_0001
Revises: 20261118_0001
Create Date: 2026-11-19

Until this table exists, services/planto3d/library/index.json is the index (the same fields).
Not applied automatically: run `uv --directory backend run alembic upgrade head` with
DATABASE_URL pointing at the database.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20261119_0001"
down_revision: str | None = "20261118_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

KINDS = ("room_kit", "furniture", "appliance", "fixture", "material", "lighting", "parametric")
SHAPES = ("rectangular", "l_shaped", "irregular", "circular")
REVIEW = ("unreviewed", "approved", "rejected")


def upgrade() -> None:
    op.create_table(
        "asset_library",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("room_types", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        # the sizes it fits, metres: {"w": [min, max], "d": [min, max], "h": [min, max]}
        sa.Column("fits", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("shape", sa.Text(), nullable=False, server_default="rectangular"),
        sa.Column("style_tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("browser_model", sa.Text(), nullable=True),  # path or storage key of the .glb
        sa.Column("detailed_model", sa.Text(), nullable=True),  # path or storage key of the .blend
        sa.Column("tris_browser", sa.Integer(), nullable=True),
        sa.Column("tris_detailed", sa.Integer(), nullable=True),
        sa.Column("preview", sa.Text(), nullable=True),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("licence", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("review", sa.Text(), nullable=False, server_default="unreviewed"),
        # the creator agent's prompt and cost, for assets it made
        sa.Column("prompt", sa.Text(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(f"kind IN {KINDS}", name="asset_library_kind"),
        sa.CheckConstraint(f"shape IN {SHAPES}", name="asset_library_shape"),
        sa.CheckConstraint(f"review IN {REVIEW}", name="asset_library_review"),
    )
    op.create_index("asset_library_kind_review", "asset_library", ["kind", "review"])
    op.create_index(
        "asset_library_room_types", "asset_library", ["room_types"], postgresql_using="gin"
    )


def downgrade() -> None:
    op.drop_index("asset_library_room_types", table_name="asset_library")
    op.drop_index("asset_library_kind_review", table_name="asset_library")
    op.drop_table("asset_library")
