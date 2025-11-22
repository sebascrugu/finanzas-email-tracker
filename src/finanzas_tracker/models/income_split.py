"""Modelo para desglose de ingresos en múltiples gastos."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


class IncomeSplit(Base):
    """
    Desglose de un ingreso en múltiples gastos.

    Permite asociar un ingreso (ej: mamá te pasa ₡10K) con múltiples
    transacciones (ej: ₡500 en Dunkin, ₡5000 en Walmart).

    Ejemplo de uso:
        Income: ₡10,000 de mamá "para comprar dona y chuletas"

        IncomeSplit 1:
            income_id → Income de ₡10K
            transaction_id → Dunkin Donuts ₡500
            monto_asignado: ₡500
            proposito: "Dona para mamá"

        IncomeSplit 2:
            income_id → mismo Income de ₡10K
            transaction_id → Walmart ₡5,000
            monto_asignado: ₡5,000
            proposito: "Chuletas para mamá"

        Income.monto_sobrante = ₡10,000 - ₡5,500 = ₡4,500 (lo que te quedaste)
    """

    __tablename__ = "income_splits"

    # Identificadores
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Relaciones
    income_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incomes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID del ingreso que se está desglosando",
    )
    transaction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="ID de la transacción asociada",
    )

    # Desglose
    monto_asignado: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        comment="Monto de este ingreso que se usó en esta transacción",
    )
    proposito: Mapped[str] = mapped_column(
        String(255), comment="Para qué se usó (ej: 'Dona para mamá', 'Chuletas')"
    )

    # Confianza del match (para AI)
    confianza_match: Mapped[Decimal] = mapped_column(
        Numeric(3, 2),
        default=1.0,
        comment="Confianza del match (0.0 - 1.0). 1.0 = manual/confirmado",
    )
    sugerido_por_ai: Mapped[bool] = mapped_column(
        default=False, comment="Si fue sugerido automáticamente por IA"
    )
    razonamiento_ai: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Explicación de Claude sobre por qué sugirió este match",
    )

    # Metadatos
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    income: Mapped["Income"] = relationship("Income", back_populates="splits")
    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="income_splits")

    # Índices
    __table_args__ = (Index("ix_income_splits_income_transaction", "income_id", "transaction_id"),)

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<IncomeSplit(id={self.id[:8]}..., "
            f"monto=₡{self.monto_asignado:,.2f}, proposito={self.proposito})>"
        )
