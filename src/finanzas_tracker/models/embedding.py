"""Modelo de embeddings para transacciones - RAG con pgvector."""

__all__ = ["TransactionEmbedding"]

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


if TYPE_CHECKING:
    from finanzas_tracker.models.transaction import Transaction


class TransactionEmbedding(Base):
    """
    Embedding vectorial de una transacción para búsqueda semántica.

    Almacena:
    - El vector embedding (384 dims para all-MiniLM-L6-v2)
    - El texto usado para generar el embedding
    - Metadata del modelo usado

    Permite búsqueda semántica tipo:
    - "Cuánto gasté en comida rápida?"
    - "Mis compras más grandes del mes"
    - "Transacciones en Starbucks"
    
    Modelo por defecto: all-MiniLM-L6-v2 (SentenceTransformers)
    - Gratis y local
    - 384 dimensiones
    - Multilingüe (incluye español)
    - ~14,000 embeddings/segundo en CPU
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
    # all-MiniLM-L6-v2: 384 dims (modelo local gratuito)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(384),  # pgvector Vector type - all-MiniLM-L6-v2
        nullable=False,
        comment="Vector embedding para búsqueda semántica (384 dims)",
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
        default="all-MiniLM-L6-v2",  # Modelo local gratuito
        comment="Modelo usado: all-MiniLM-L6-v2, voyage-3-lite, etc.",
    )

    # Dimensión del embedding (para validación)
    embedding_dim: Mapped[int] = mapped_column(
        nullable=False,
        default=384,  # all-MiniLM-L6-v2 = 384 dimensiones
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
