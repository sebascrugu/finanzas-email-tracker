"""Modelo de embeddings para transacciones - RAG con pgvector."""

__all__ = ["TransactionEmbedding"]

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


class TransactionEmbedding(Base):
    """
    Embedding vectorial de una transacción para búsqueda semántica.

    Almacena:
    - El vector embedding (1024 dims para voyage-3-lite o 1536 para text-embedding-3-small)
    - El texto usado para generar el embedding
    - Metadata del modelo usado

    Permite búsqueda semántica tipo:
    - "Cuánto gasté en comida rápida?"
    - "Mis compras más grandes del mes"
    - "Transacciones en Starbucks"
    """

    __tablename__ = "transaction_embeddings"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    transaction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Multi-tenancy
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Vector embedding usando pgvector
    # all-MiniLM-L6-v2: 384 dims, voyage-3-lite: 1024, text-embedding-3-small: 1536
    # Usamos 384 como default para el modelo local
    embedding: Mapped[list[float]] = mapped_column(
        Vector(384),  # pgvector Vector type
        nullable=False,
        comment="Vector embedding para búsqueda semántica",
    )

    # Texto que se usó para generar el embedding
    text_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Texto usado para generar el embedding",
    )

    # Metadata del modelo
    model_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="voyage-3-lite",
        comment="Modelo usado: voyage-3-lite, text-embedding-3-small, etc.",
    )

    # Dimensión del embedding (para validación)
    embedding_dim: Mapped[int] = mapped_column(
        nullable=False,
        default=1024,
        comment="Dimensión del vector",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relación con Transaction
    transaction: Mapped["Transaction"] = relationship(
        "Transaction",
        back_populates="embedding",
    )

    def __repr__(self) -> str:
        """Representación del embedding."""
        return f"<TransactionEmbedding(id={self.id[:8]}..., txn={self.transaction_id[:8]}..., dim={self.embedding_dim})>"
