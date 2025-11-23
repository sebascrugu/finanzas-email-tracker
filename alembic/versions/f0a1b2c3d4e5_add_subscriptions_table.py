"""add subscriptions table

Revision ID: f0a1b2c3d4e5
Revises: e9f1a2b3c4d5
Create Date: 2025-11-22 21:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = 'f0a1b2c3d4e5'
down_revision: Union[str, None] = 'e9f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create subscriptions table
    op.create_table(
        'subscriptions',
        sa.Column('id', sa.String(length=26), nullable=False),
        sa.Column('profile_id', sa.String(length=26), nullable=False),
        sa.Column('merchant_id', sa.String(length=26), nullable=True),
        sa.Column('comercio', sa.String(length=255), nullable=False),
        sa.Column('monto_promedio', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('monto_min', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('monto_max', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('frecuencia_dias', sa.Integer(), nullable=False),
        sa.Column('primera_fecha_cobro', sa.Date(), nullable=False),
        sa.Column('ultima_fecha_cobro', sa.Date(), nullable=False),
        sa.Column('proxima_fecha_estimada', sa.Date(), nullable=False),
        sa.Column('occurrences_count', sa.Integer(), nullable=False),
        sa.Column('confidence_score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_confirmed', sa.Boolean(), nullable=False),
        sa.Column('notas', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for better query performance
    op.create_index('ix_subscriptions_profile_id', 'subscriptions', ['profile_id'])
    op.create_index('ix_subscriptions_merchant_id', 'subscriptions', ['merchant_id'])
    op.create_index('ix_subscriptions_is_active', 'subscriptions', ['is_active'])
    op.create_index('ix_subscriptions_proxima_fecha_estimada', 'subscriptions', ['proxima_fecha_estimada'])
    op.create_index('ix_subscriptions_deleted_at', 'subscriptions', ['deleted_at'])

    # Create foreign keys
    op.create_foreign_key(
        'fk_subscriptions_profile_id',
        'subscriptions',
        'profiles',
        ['profile_id'],
        ['id']
    )
    op.create_foreign_key(
        'fk_subscriptions_merchant_id',
        'subscriptions',
        'merchants',
        ['merchant_id'],
        ['id']
    )


def downgrade() -> None:
    # Drop foreign keys first
    op.drop_constraint('fk_subscriptions_merchant_id', 'subscriptions', type_='foreignkey')
    op.drop_constraint('fk_subscriptions_profile_id', 'subscriptions', type_='foreignkey')

    # Drop indexes
    op.drop_index('ix_subscriptions_deleted_at', table_name='subscriptions')
    op.drop_index('ix_subscriptions_proxima_fecha_estimada', table_name='subscriptions')
    op.drop_index('ix_subscriptions_is_active', table_name='subscriptions')
    op.drop_index('ix_subscriptions_merchant_id', table_name='subscriptions')
    op.drop_index('ix_subscriptions_profile_id', table_name='subscriptions')

    # Drop table
    op.drop_table('subscriptions')
