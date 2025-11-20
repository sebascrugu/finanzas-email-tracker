"""add accounts table

Revision ID: c7d4e5f6a1b2
Revises: b580073c8e12
Create Date: 2025-11-20 02:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c7d4e5f6a1b2"
down_revision: Union[str, None] = "b580073c8e12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create accounts table for financial asset management."""
    op.create_table(
        "accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False, comment="Nombre de la cuenta"),
        sa.Column(
            "tipo",
            sa.String(length=20),
            nullable=False,
            comment="Tipo de cuenta: checking, savings, investment, cdp, cash",
        ),
        sa.Column(
            "banco",
            sa.String(length=50),
            nullable=True,
            comment="Banco o institución financiera",
        ),
        sa.Column("descripcion", sa.Text(), nullable=True, comment="Descripción o notas adicionales"),
        sa.Column(
            "saldo_actual",
            sa.Numeric(precision=15, scale=2),
            nullable=False,
            server_default="0",
            comment="Saldo actual de la cuenta en su moneda",
        ),
        sa.Column(
            "moneda", sa.String(length=3), nullable=False, server_default="CRC", comment="Moneda de la cuenta (CRC, USD)"
        ),
        sa.Column(
            "tasa_interes",
            sa.Numeric(precision=5, scale=2),
            nullable=True,
            comment="Tasa de interés anual (ej: 6.00 para 6%)",
        ),
        sa.Column(
            "tipo_interes",
            sa.String(length=20),
            nullable=True,
            server_default="simple",
            comment="Tipo de interés: simple o compuesto",
        ),
        sa.Column(
            "fecha_apertura",
            sa.Date(),
            nullable=True,
            comment="Fecha de apertura o inicio de la inversión",
        ),
        sa.Column(
            "fecha_vencimiento",
            sa.Date(),
            nullable=True,
            comment="Fecha de vencimiento (para CDPs)",
        ),
        sa.Column("plazo_meses", sa.Integer(), nullable=True, comment="Plazo en meses (para CDPs)"),
        sa.Column(
            "activa", sa.Boolean(), nullable=False, server_default="1", comment="Si la cuenta está activa"
        ),
        sa.Column(
            "incluir_en_patrimonio",
            sa.Boolean(),
            nullable=False,
            server_default="1",
            comment="Si se incluye en el cálculo de patrimonio total",
        ),
        sa.Column(
            "deleted_at", sa.DateTime(timezone=True), nullable=True, comment="Soft delete"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["profiles.id"], name=op.f("fk_accounts_profile_id_profiles")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
    )
    op.create_index(op.f("ix_accounts_profile_id"), "accounts", ["profile_id"], unique=False)


def downgrade() -> None:
    """Drop accounts table."""
    op.drop_index(op.f("ix_accounts_profile_id"), table_name="accounts")
    op.drop_table("accounts")
