"""add_tenant_id_and_pgvector_support

Revision ID: b8e4f7d92a31
Revises: 256a23c3cec4
Create Date: 2025-11-30 08:00:00.000000

Esta migración:
1. Agrega tenant_id (UUID nullable) a todas las tablas principales para multi-tenancy futuro
2. Prepara soporte para pgvector (embeddings) cuando se use PostgreSQL
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import context, op


# revision identifiers, used by Alembic.
revision: str = 'b8e4f7d92a31'
down_revision: str | Sequence[str] | None = '256a23c3cec4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def is_postgres() -> bool:
    """Detecta si estamos corriendo en PostgreSQL."""
    return context.get_context().dialect.name == 'postgresql'


def upgrade() -> None:
    """Agrega tenant_id a todas las tablas principales."""
    
    # Determinar el tipo de columna según la base de datos
    if is_postgres():
        uuid_type = postgresql.UUID(as_uuid=True)
        
        # Habilitar extensión pgvector si no existe
        op.execute('CREATE EXTENSION IF NOT EXISTS vector')
    else:
        # SQLite no tiene UUID nativo, usamos String
        uuid_type = sa.String(36)
    
    # Tablas que necesitan tenant_id
    tables_with_tenant = [
        'transactions',
        'profiles',
        'cards',
        'budgets',
        'incomes',
        'merchants',
        'merchant_variants',
    ]
    
    for table in tables_with_tenant:
        # Agregar columna tenant_id
        op.add_column(
            table,
            sa.Column(
                'tenant_id',
                uuid_type,
                nullable=True,
                comment='ID del tenant para multi-tenancy (futuro)',
            )
        )
        
        # Crear índice para tenant_id
        op.create_index(
            f'ix_{table}_tenant_id',
            table,
            ['tenant_id'],
            unique=False,
        )
    
    # Para PostgreSQL, crear tabla de embeddings para RAG
    if is_postgres():
        op.create_table(
            'transaction_embeddings',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('transaction_id', sa.String(36), sa.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=False, unique=True),
            sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=True, index=True),
            sa.Column('embedding', postgresql.ARRAY(sa.Float), nullable=False, comment='Vector embedding 1536-dim para Claude'),
            sa.Column('text_content', sa.Text(), nullable=False, comment='Texto usado para generar el embedding'),
            sa.Column('model_version', sa.String(50), nullable=False, default='claude-3-haiku', comment='Modelo usado para generar embedding'),
            sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
            sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        )
        
        op.create_index('ix_transaction_embeddings_transaction_id', 'transaction_embeddings', ['transaction_id'])


def downgrade() -> None:
    """Remueve tenant_id de todas las tablas."""
    
    # Determinar si estamos en PostgreSQL
    is_pg = is_postgres()
    
    # Si PostgreSQL, eliminar tabla de embeddings
    if is_pg:
        op.drop_table('transaction_embeddings')
    
    # Tablas que tienen tenant_id
    tables_with_tenant = [
        'transactions',
        'profiles', 
        'cards',
        'budgets',
        'incomes',
        'merchants',
        'merchant_variants',
    ]
    
    for table in tables_with_tenant:
        # Eliminar índice
        op.drop_index(f'ix_{table}_tenant_id', table_name=table)
        
        # Eliminar columna
        op.drop_column(table, 'tenant_id')
