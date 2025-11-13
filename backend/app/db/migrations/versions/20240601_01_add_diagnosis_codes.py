"""Add diagnosis codes catalog"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20240601_01_add_diagnosis_codes"
down_revision: str | None = "20240521_01_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "diagnosis_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("normalized_code", sa.String(length=32), nullable=False),
        sa.Column("short_description", sa.String(length=255), nullable=False),
        sa.Column("long_description", sa.String(length=2048), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("code", name="uq_diagnosis_codes_code"),
        sa.UniqueConstraint("normalized_code", name="uq_diagnosis_codes_normalized_code"),
    )
    op.create_index("ix_diagnosis_codes_code", "diagnosis_codes", ["code"], unique=True)
    op.create_index(
        "ix_diagnosis_codes_normalized_code",
        "diagnosis_codes",
        ["normalized_code"],
        unique=True,
    )
    op.create_index(
        "ix_diagnosis_codes_is_deleted",
        "diagnosis_codes",
        ["is_deleted"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_diagnosis_codes_is_deleted", table_name="diagnosis_codes")
    op.drop_index("ix_diagnosis_codes_normalized_code", table_name="diagnosis_codes")
    op.drop_index("ix_diagnosis_codes_code", table_name="diagnosis_codes")
    op.drop_table("diagnosis_codes")
