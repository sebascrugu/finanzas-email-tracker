"""add smart learning ML tables

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2025-01-15 12:00:00.000000

Tablas avanzadas para el sistema de ML/Embeddings:
- transaction_patterns: Patrones aprendidos con embeddings
- user_learning_profiles: Perfiles de aprendizaje por usuario
- global_patterns: Patrones crowdsourced de Costa Rica
- pattern_clusters: Clusters de patrones similares
- learning_events: Log de eventos de aprendizaje

Requiere:
- PostgreSQL 16+
- pgvector extension
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "123e1ab89fe0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Crea las tablas de Smart Learning."""
    
    # Crear ENUMs primero
    pattern_type_enum = sa.Enum(
        "beneficiario", "comercio", "descripcion", "monto", "recurrente", "combinado",
        name="pattern_type_enum",
        create_type=True,
    )
    pattern_source_enum = sa.Enum(
        "user_explicit", "user_confirmed", "auto_detected", "crowdsourced", "imported",
        name="pattern_source_enum",
        create_type=True,
    )
    learning_event_type_enum = sa.Enum(
        "categorization", "correction", "confirmation", "rejection", "alias_created", "pattern_merged",
        name="learning_event_type_enum",
        create_type=True,
    )
    
    # 1. Tabla: transaction_patterns
    # Patrones aprendidos con embeddings para similarity search
    op.create_table(
        "transaction_patterns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("is_global", sa.Boolean, default=False, comment="True = aplica a todos los usuarios"),
        
        # El patrón
        sa.Column("pattern_text", sa.String(500), nullable=False, comment="Texto del patrón"),
        sa.Column("pattern_text_normalized", sa.String(500), nullable=False, comment="Texto normalizado"),
        sa.Column("pattern_type", pattern_type_enum, nullable=False),
        
        # Embedding para similarity search (1536 dims = OpenAI compatible)
        # pgvector se carga con: CREATE EXTENSION IF NOT EXISTS vector;
        sa.Column("embedding", Vector(1536), nullable=True, comment="Vector embedding (serializado)"),
        sa.Column("embedding_model", sa.String(100), nullable=True, default="text-embedding-3-small"),
        
        # Categorización
        sa.Column("subcategory_id", sa.String(36), sa.ForeignKey("subcategories.id", ondelete="CASCADE"), nullable=False),
        
        # Metadatos del usuario
        sa.Column("user_label", sa.String(200), nullable=True, comment="Etiqueta del usuario"),
        sa.Column("user_description", sa.Text, nullable=True),
        
        # Métricas de confianza
        sa.Column("confidence", sa.Numeric(5, 4), default=0.9000),
        sa.Column("times_matched", sa.Integer, default=1),
        sa.Column("times_confirmed", sa.Integer, default=1),
        sa.Column("times_rejected", sa.Integer, default=0),
        
        # Origen
        sa.Column("source", pattern_source_enum, default="user_explicit"),
        
        # Estadísticas de monto
        sa.Column("avg_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("min_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("max_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("total_amount", sa.Numeric(15, 2), default=0),
        
        # Recurrencia
        sa.Column("is_recurring", sa.Boolean, default=False),
        sa.Column("recurring_day", sa.Integer, nullable=True),
        sa.Column("recurring_frequency", sa.String(20), nullable=True),
        
        # Timestamps
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    
    # Índices para transaction_patterns
    op.create_index("ix_txn_pattern_profile_text", "transaction_patterns", ["profile_id", "pattern_text_normalized"])
    op.create_index("ix_txn_pattern_global", "transaction_patterns", ["is_global", "pattern_text_normalized"])
    op.create_index("ix_txn_pattern_type", "transaction_patterns", ["pattern_type"])
    op.create_index("ix_txn_pattern_active", "transaction_patterns", ["deleted_at"])
    
    # 2. Tabla: user_learning_profiles
    # Perfil de aprendizaje del usuario con métricas
    op.create_table(
        "user_learning_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, unique=True),
        
        # Estadísticas
        sa.Column("total_transactions_categorized", sa.Integer, default=0),
        sa.Column("total_auto_categorized", sa.Integer, default=0),
        sa.Column("total_manual_categorized", sa.Integer, default=0),
        sa.Column("total_corrections", sa.Integer, default=0),
        
        # Tasa de acierto
        sa.Column("auto_categorization_accuracy", sa.Numeric(5, 4), default=0.8000),
        
        # Preferencias
        sa.Column("preferred_categories", JSONB, nullable=True),
        sa.Column("spending_patterns", JSONB, nullable=True),
        
        # Clustering
        sa.Column("cluster_id", sa.Integer, nullable=True),
        sa.Column("cluster_confidence", sa.Numeric(5, 4), nullable=True),
        
        # Embedding del perfil (256 dims)
        sa.Column("profile_embedding", Vector(256), nullable=True),
        
        # Timestamps
        sa.Column("last_learning_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # 3. Tabla: global_patterns
    # Patrones crowdsourced de Costa Rica
    op.create_table(
        "global_patterns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        
        # El patrón
        sa.Column("pattern_text", sa.String(500), nullable=False),
        sa.Column("pattern_text_normalized", sa.String(500), nullable=False, unique=True),
        sa.Column("pattern_type", pattern_type_enum, nullable=False),
        
        # Categoría más votada
        sa.Column("primary_subcategory_id", sa.String(36), sa.ForeignKey("subcategories.id", ondelete="CASCADE"), nullable=False),
        
        # Embedding
        sa.Column("embedding", Vector(1536), nullable=True),
        
        # Crowdsourcing
        sa.Column("user_count", sa.Integer, default=1),
        sa.Column("vote_distribution", JSONB, nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), default=0.5000),
        
        # Estado
        sa.Column("is_approved", sa.Boolean, default=False),
        sa.Column("is_auto_approved", sa.Boolean, default=False),
        
        # Geografía
        sa.Column("country_code", sa.String(2), default="CR"),
        
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    op.create_index("ix_global_pattern_country", "global_patterns", ["country_code", "is_approved"])
    op.create_index("ix_global_pattern_text", "global_patterns", ["pattern_text_normalized"])
    
    # 4. Tabla: pattern_clusters
    # Clusters de patrones similares
    op.create_table(
        "pattern_clusters",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        
        # Descripción
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        
        # Centroide
        sa.Column("centroid", Vector(1536), nullable=True),
        
        # Categoría predominante
        sa.Column("primary_subcategory_id", sa.String(36), sa.ForeignKey("subcategories.id", ondelete="SET NULL"), nullable=True),
        
        # Estadísticas
        sa.Column("pattern_count", sa.Integer, default=0),
        sa.Column("avg_confidence", sa.Numeric(5, 4), nullable=True),
        
        # Timestamps
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    
    # 5. Tabla: learning_events
    # Log de eventos de aprendizaje
    op.create_table(
        "learning_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True, index=True),
        sa.Column("profile_id", sa.String(36), sa.ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        
        # Tipo de evento
        sa.Column("event_type", learning_event_type_enum, nullable=False),
        
        # Contexto
        sa.Column("transaction_id", sa.String(36), nullable=True),
        sa.Column("pattern_id", UUID(as_uuid=True), nullable=True),
        
        # Datos
        sa.Column("input_text", sa.String(500), nullable=True),
        sa.Column("old_subcategory_id", sa.String(36), nullable=True),
        sa.Column("new_subcategory_id", sa.String(36), nullable=True),
        sa.Column("user_label", sa.String(200), nullable=True),
        
        # Metadata
        sa.Column("extra_data", JSONB, nullable=True),
        
        # Timestamp
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), index=True),
    )
    
    op.create_index("ix_learning_event_profile_time", "learning_events", ["profile_id", "created_at"])
    op.create_index("ix_learning_event_type", "learning_events", ["event_type", "created_at"])
    
    # Crear índices HNSW para búsqueda vectorial rápida
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_txn_pattern_embedding_hnsw 
        ON transaction_patterns 
        USING hnsw (embedding vector_cosine_ops)
    """)
    
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_global_pattern_embedding_hnsw 
        ON global_patterns 
        USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    """Elimina las tablas de Smart Learning."""
    
    # Eliminar índices HNSW
    op.execute("DROP INDEX IF EXISTS ix_txn_pattern_embedding_hnsw")
    op.execute("DROP INDEX IF EXISTS ix_global_pattern_embedding_hnsw")
    
    # Eliminar tablas en orden inverso (por FKs)
    op.drop_table("learning_events")
    op.drop_table("pattern_clusters")
    op.drop_table("global_patterns")
    op.drop_table("user_learning_profiles")
    op.drop_table("transaction_patterns")
    
    # Eliminar ENUMs
    op.execute("DROP TYPE IF EXISTS learning_event_type_enum")
    op.execute("DROP TYPE IF EXISTS pattern_source_enum")
    op.execute("DROP TYPE IF EXISTS pattern_type_enum")
