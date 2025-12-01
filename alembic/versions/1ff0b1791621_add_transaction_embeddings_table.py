"""add_transaction_embeddings_table

Revision ID: 1ff0b1791621
Revises: b8e4f7d92a31
Create Date: 2025-11-30 09:09:06.978545

Tabla para almacenar embeddings vectoriales de transacciones.
Usa pgvector para búsqueda semántica con índice HNSW.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '1ff0b1791621'
down_revision: str | Sequence[str] | None = 'b8e4f7d92a31'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema - Crear tabla transaction_embeddings con pgvector."""
    # Crear extensión pgvector si no existe
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    
    # Crear tabla si no existe (para nuevas instalaciones)
    op.execute("""
        CREATE TABLE IF NOT EXISTS transaction_embeddings (
            id SERIAL PRIMARY KEY,
            transaction_id UUID NOT NULL UNIQUE,
            embedding vector(384) NOT NULL,
            model_version VARCHAR(50) NOT NULL,
            embedding_dim INTEGER NOT NULL DEFAULT 384,
            text_content TEXT,
            tenant_id UUID,
            deleted_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            CONSTRAINT fk_transaction 
                FOREIGN KEY (transaction_id) 
                REFERENCES transactions(id) 
                ON DELETE CASCADE
        )
    """)
    
    # Crear índice HNSW para búsqueda vectorial rápida
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_embedding_hnsw 
        ON transaction_embeddings 
        USING hnsw (embedding vector_cosine_ops)
    """)
    
    # Índice para tenant_id (multi-tenancy futuro)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_transaction_embeddings_tenant_id 
        ON transaction_embeddings (tenant_id)
    """)
    
    # Comentarios para documentación
    op.execute("COMMENT ON COLUMN transaction_embeddings.embedding IS 'Vector embedding para búsqueda semántica'")
    op.execute("COMMENT ON COLUMN transaction_embeddings.model_version IS 'Modelo usado: voyage-3-lite, text-embedding-3-small, all-MiniLM-L6-v2'")
    op.execute("COMMENT ON COLUMN transaction_embeddings.embedding_dim IS 'Dimensión del vector (384 para MiniLM, 1024 para Voyage, 1536 para OpenAI)'")


def downgrade() -> None:
    """Downgrade schema - Eliminar tabla transaction_embeddings."""
    op.execute("DROP INDEX IF EXISTS idx_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_transaction_embeddings_tenant_id")
    op.execute("DROP TABLE IF EXISTS transaction_embeddings")
