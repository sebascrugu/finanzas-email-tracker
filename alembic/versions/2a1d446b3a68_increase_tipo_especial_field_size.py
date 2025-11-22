"""increase tipo_especial field size

Revision ID: 2a1d446b3a68
Revises: d8e9f0a1b2c3
Create Date: 2025-11-22 12:55:05.461186

Summary:
- Increased tipo_especial field size from String(20) to String(50) in transactions table
- Increased tipo_especial field size from String(30) to String(50) in incomes table
- This allows users to enter custom tipo_especial values without being limited by short field length
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '2a1d446b3a68'
down_revision: str | Sequence[str] | None = 'd8e9f0a1b2c3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Increase tipo_especial field size in transactions table
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.alter_column(
            'tipo_especial',
            existing_type=sa.String(20),
            type_=sa.String(50),
            existing_nullable=True,
            existing_comment="Tipo especial: dinero_ajeno, intermediaria, transferencia_propia, etc.",
        )

    # Increase tipo_especial field size in incomes table
    with op.batch_alter_table('incomes', schema=None) as batch_op:
        batch_op.alter_column(
            'tipo_especial',
            existing_type=sa.String(30),
            type_=sa.String(50),
            existing_nullable=True,
            existing_comment="Tipo especial de movimiento (dinero_ajeno, intermediaria, ajuste_inicial, etc.)",
        )


def downgrade() -> None:
    """Downgrade schema."""
    # Revert tipo_especial field size in incomes table
    with op.batch_alter_table('incomes', schema=None) as batch_op:
        batch_op.alter_column(
            'tipo_especial',
            existing_type=sa.String(50),
            type_=sa.String(30),
            existing_nullable=True,
        )

    # Revert tipo_especial field size in transactions table
    with op.batch_alter_table('transactions', schema=None) as batch_op:
        batch_op.alter_column(
            'tipo_especial',
            existing_type=sa.String(50),
            type_=sa.String(20),
            existing_nullable=True,
        )
