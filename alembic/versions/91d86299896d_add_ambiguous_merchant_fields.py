"""add_ambiguous_merchant_fields

Revision ID: 91d86299896d
Revises: 1ff0b1791621
Create Date: 2025-11-30 15:20:11.880082

Agrega soporte para comercios ambiguos (Walmart, Amazon, etc.) que pueden
tener múltiples categorías dependiendo de lo que se compre.

- merchants.es_ambiguo: Boolean para marcar comercios multi-categoría
- merchants.categorias_posibles: Text (JSON) con lista de categorías posibles
- transactions.es_comercio_ambiguo: Boolean para marcar transacciones ambiguas
- transactions.categorias_opciones: Text (JSON) con opciones de categoría
- transactions.categoria_confirmada_usuario: Categoría elegida por el usuario
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '91d86299896d'
down_revision: str | Sequence[str] | None = '1ff0b1791621'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Agregar campos para manejo de comercios ambiguos."""
    # Merchants - campos para identificar comercios multi-categoría
    op.add_column(
        'merchants',
        sa.Column(
            'es_ambiguo',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='True si el comercio puede tener múltiples categorías (ej: Walmart)',
        ),
    )
    op.add_column(
        'merchants',
        sa.Column(
            'categorias_posibles',
            sa.Text(),
            nullable=True,
            comment='Lista de categorías posibles en formato JSON (ej: ["Supermercado", "Electrónica"])',
        ),
    )
    op.create_index(
        op.f('ix_merchants_es_ambiguo'),
        'merchants',
        ['es_ambiguo'],
        unique=False,
    )

    # Transactions - campos para tracking de confirmación de categoría
    op.add_column(
        'transactions',
        sa.Column(
            'es_comercio_ambiguo',
            sa.Boolean(),
            nullable=False,
            server_default='false',
            comment='True si la transacción es de un comercio ambiguo que requiere confirmación',
        ),
    )
    op.add_column(
        'transactions',
        sa.Column(
            'categorias_opciones',
            sa.Text(),
            nullable=True,
            comment='JSON con opciones de categoría para comercios ambiguos',
        ),
    )
    op.add_column(
        'transactions',
        sa.Column(
            'categoria_confirmada_usuario',
            sa.String(length=100),
            nullable=True,
            comment='Categoría confirmada por el usuario para comercio ambiguo',
        ),
    )
    op.create_index(
        op.f('ix_transactions_es_comercio_ambiguo'),
        'transactions',
        ['es_comercio_ambiguo'],
        unique=False,
    )


def downgrade() -> None:
    """Remover campos de comercios ambiguos."""
    # Transactions
    op.drop_index(
        op.f('ix_transactions_es_comercio_ambiguo'),
        table_name='transactions',
    )
    op.drop_column('transactions', 'categoria_confirmada_usuario')
    op.drop_column('transactions', 'categorias_opciones')
    op.drop_column('transactions', 'es_comercio_ambiguo')

    # Merchants
    op.drop_index(op.f('ix_merchants_es_ambiguo'), table_name='merchants')
    op.drop_column('merchants', 'categorias_posibles')
    op.drop_column('merchants', 'es_ambiguo')
