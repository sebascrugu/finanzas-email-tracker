"""add_transfer_fields_beneficiario_subtipo

Revision ID: e9cec578b152
Revises: f7a8b9c0d1e2
Create Date: 2025-12-07 06:54:21.559073

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'e9cec578b152'
down_revision: str | Sequence[str] | None = 'f7a8b9c0d1e2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - Add transfer-specific fields."""
    # Agregar nuevos campos para transferencias
    op.add_column(
        'transactions',
        sa.Column(
            'beneficiario',
            sa.String(length=255),
            nullable=True,
            comment='Nombre del beneficiario en transferencias (quien recibe el dinero)'
        )
    )
    op.add_column(
        'transactions',
        sa.Column(
            'subtipo_transaccion',
            sa.String(length=50),
            nullable=True,
            comment='Subtipo: sinpe_enviado, sinpe_recibido, transferencia_local, transferencia_propia, pago_tc, retiro_atm'
        )
    )
    op.add_column(
        'transactions',
        sa.Column(
            'concepto_transferencia',
            sa.String(length=500),
            nullable=True,
            comment='Concepto/descripción ingresada en la transferencia SINPE'
        )
    )
    op.add_column(
        'transactions',
        sa.Column(
            'necesita_reconciliacion_sinpe',
            sa.Boolean(),
            nullable=True,
            server_default='false',
            comment='True si es un SINPE/transferencia con descripción ambigua que necesita aclaración'
        )
    )

    # Crear índices para búsquedas eficientes
    op.create_index(
        op.f('ix_transactions_beneficiario'),
        'transactions',
        ['beneficiario'],
        unique=False
    )
    op.create_index(
        op.f('ix_transactions_necesita_reconciliacion_sinpe'),
        'transactions',
        ['necesita_reconciliacion_sinpe'],
        unique=False
    )
    op.create_index(
        op.f('ix_transactions_subtipo_transaccion'),
        'transactions',
        ['subtipo_transaccion'],
        unique=False
    )


def downgrade() -> None:
    """Downgrade schema - Remove transfer-specific fields."""
    op.drop_index(op.f('ix_transactions_subtipo_transaccion'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_necesita_reconciliacion_sinpe'), table_name='transactions')
    op.drop_index(op.f('ix_transactions_beneficiario'), table_name='transactions')
    op.drop_column('transactions', 'necesita_reconciliacion_sinpe')
    op.drop_column('transactions', 'concepto_transferencia')
    op.drop_column('transactions', 'subtipo_transaccion')
    op.drop_column('transactions', 'beneficiario')
