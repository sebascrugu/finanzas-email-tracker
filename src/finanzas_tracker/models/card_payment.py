"""
Modelo CardPayment para historial de pagos a tarjetas de crédito.

Este modelo registra cada pago realizado a una tarjeta de crédito,
permitiendo tracking de:
- Montos pagados y fechas
- Tipo de pago (total, mínimo, parcial)
- Relación con ciclos de facturación
- Intereses evitados/generados
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
import uuid

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import CardPaymentType


if TYPE_CHECKING:
    from finanzas_tracker.models.billing_cycle import BillingCycle
    from finanzas_tracker.models.card import Card


class CardPayment(Base):
    """
    Modelo para pagos realizados a tarjetas de crédito.

    Cada pago puede estar asociado a un ciclo de facturación específico,
    aunque también pueden existir pagos "extra" fuera de ciclo.

    Attributes:
        id: Identificador único del pago.
        card_id: ID de la tarjeta a la que se realizó el pago.
        billing_cycle_id: ID del ciclo de facturación (opcional).
        monto: Monto pagado.
        tipo: Tipo de pago (total, mínimo, parcial, extra).
        fecha_pago: Fecha en que se realizó el pago.
        referencia: Número de referencia bancaria (opcional).
        notas: Notas adicionales sobre el pago.
        created_at: Timestamp de creación.
    """

    __tablename__ = "card_payments"

    # Primary Key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Foreign Keys
    card_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cards.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    billing_cycle_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("billing_cycles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Multi-tenancy (futuro)
    tenant_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        index=True,
    )

    # Datos del pago
    monto: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    tipo: Mapped[CardPaymentType] = mapped_column(
        String(20),
        nullable=False,
        default=CardPaymentType.PARTIAL,
    )

    fecha_pago: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        default=date.today,
    )

    # Referencia bancaria (para reconciliación)
    referencia: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # Notas
    notas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships
    card: Mapped[Card] = relationship(
        "Card",
        back_populates="payments",
    )

    billing_cycle: Mapped[BillingCycle | None] = relationship(
        "BillingCycle",
        back_populates="payments",
    )

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def descripcion_tipo(self) -> str:
        """Descripción legible del tipo de pago."""
        descripciones = {
            CardPaymentType.FULL: "Pago total",
            CardPaymentType.MINIMUM: "Pago mínimo",
            CardPaymentType.PARTIAL: "Pago parcial",
            CardPaymentType.EXTRA: "Abono extra",
        }
        return descripciones.get(self.tipo, "Pago")

    @property
    def es_pago_total(self) -> bool:
        """Indica si fue un pago total."""
        return self.tipo == CardPaymentType.FULL

    @property
    def es_pago_minimo(self) -> bool:
        """Indica si fue solo el pago mínimo."""
        return self.tipo == CardPaymentType.MINIMUM

    # =========================================================================
    # Magic Methods
    # =========================================================================

    def __repr__(self) -> str:
        """Representación del pago."""
        return (
            f"<CardPayment("
            f"id={self.id[:8]}..., "
            f"monto={self.monto}, "
            f"tipo={self.tipo.value}, "
            f"fecha={self.fecha_pago}"
            f")>"
        )

    def __str__(self) -> str:
        """String representation."""
        return f"Pago {self.descripcion_tipo}: ₡{self.monto:,.2f} ({self.fecha_pago})"
