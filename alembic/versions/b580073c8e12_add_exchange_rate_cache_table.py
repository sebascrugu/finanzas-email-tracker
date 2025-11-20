"""add_exchange_rate_cache_table

Esta migración agrega la tabla de caché para tipos de cambio USD a CRC.
El caché permite evitar llamadas repetidas a APIs externas y persiste
entre sesiones de la aplicación.

Revision ID: b580073c8e12
Revises: a052c6fc5837
Create Date: 2025-11-20 00:12:20.100835

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b580073c8e12"
down_revision: str | Sequence[str] | None = "a052c6fc5837"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create exchange_rate_cache table
    op.create_table(
        "exchange_rate_cache",
        sa.Column(
            "date",
            sa.Date(),
            nullable=False,
            comment="Fecha del tipo de cambio (YYYY-MM-DD)",
        ),
        sa.Column(
            "rate",
            sa.Numeric(precision=10, scale=4),
            nullable=False,
            comment="Tipo de cambio USD a CRC (ej: 530.50)",
        ),
        sa.Column(
            "source",
            sa.String(length=50),
            nullable=False,
            comment="Fuente: hacienda_cr, exchangerate_api, default",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            comment="Fecha de creación del registro",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            comment="Fecha de última actualización",
        ),
        sa.PrimaryKeyConstraint("date", name=op.f("pk_exchange_rate_cache")),
        sa.CheckConstraint("rate > 0", name=op.f("check_rate_positive")),
        sa.CheckConstraint(
            "source IN ('hacienda_cr', 'exchangerate_api', 'default')",
            name=op.f("check_valid_source"),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop exchange_rate_cache table
    op.drop_table("exchange_rate_cache")
