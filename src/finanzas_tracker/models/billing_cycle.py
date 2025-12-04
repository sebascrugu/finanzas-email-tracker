"""Modelo de Ciclo de Facturación de Tarjeta de Crédito."""

__all__ = ["BillingCycle"]

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import BillingCycleStatus


if TYPE_CHECKING:
    from finanzas_tracker.models.card import Card
    from finanzas_tracker.models.card_payment import CardPayment


class BillingCycle(Base):
    """
    Ciclo de facturación de una tarjeta de crédito.

    Cada ciclo representa un período de facturación específico,
    con fechas de corte y pago, y el total gastado en ese período.

    Ejemplo:
        - Ciclo Noviembre 2025: 16 Oct → 15 Nov (corte), pago 28 Nov
        - Total gastado: ₡127,000
        - Pago mínimo: ₡12,700 (10%)
        - Estado: cerrado (esperando pago)
    """

    __tablename__ = "billing_cycles"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Multi-tenancy (futuro)
    tenant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
    )

    # Relación con Card
    card_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("cards.id", ondelete="CASCADE"),
        index=True,
        comment="ID de la tarjeta a la que pertenece este ciclo",
    )

    # Período del ciclo
    fecha_inicio: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha de inicio del período (día después del corte anterior)",
    )
    fecha_corte: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha de corte del período",
    )
    fecha_pago: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha límite de pago para evitar intereses",
    )

    # Montos
    total_periodo: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total gastado en este período",
    )
    saldo_anterior: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Saldo arrastrado del período anterior (si no se pagó total)",
    )
    intereses_periodo: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Intereses cobrados por saldo anterior",
    )
    total_a_pagar: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total a pagar (periodo + anterior + intereses)",
    )
    pago_minimo: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Pago mínimo requerido",
    )

    # Pagos realizados
    monto_pagado: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total pagado en este ciclo",
    )

    # Estado
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=BillingCycleStatus.OPEN,
        index=True,
        comment="Estado: abierto, cerrado, pagado, parcial, vencido",
    )

    # Metadatos
    notas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notas adicionales",
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
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Soft delete",
    )

    # Relaciones
    card: Mapped["Card"] = relationship("Card", back_populates="billing_cycles")
    payments: Mapped[list["CardPayment"]] = relationship(
        "CardPayment",
        back_populates="billing_cycle",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<BillingCycle(card={self.card_id[:8]}..., "
            f"corte={self.fecha_corte}, total=₡{self.total_periodo:,.0f})>"
        )

    @property
    def saldo_pendiente(self) -> Decimal:
        """Calcula el saldo pendiente de pago."""
        return self.total_a_pagar - self.monto_pagado

    @property
    def esta_pagado(self) -> bool:
        """Verifica si el ciclo está completamente pagado."""
        return self.monto_pagado >= self.total_a_pagar

    @property
    def dias_para_pago(self) -> int | None:
        """Días restantes hasta la fecha de pago."""
        if self.status == BillingCycleStatus.OPEN:
            return None  # Aún no cierra
        delta = self.fecha_pago - date.today()
        return delta.days

    @property
    def esta_vencido(self) -> bool:
        """Verifica si ya pasó la fecha de pago sin pagar el total."""
        if self.esta_pagado:
            return False
        return date.today() > self.fecha_pago

    @property
    def porcentaje_pagado(self) -> float:
        """Porcentaje del total que ya se pagó."""
        if self.total_a_pagar == 0:
            return 100.0
        return float(self.monto_pagado / self.total_a_pagar * 100)

    def calcular_pago_minimo(self, porcentaje: Decimal = Decimal("0.10")) -> Decimal:
        """Calcula el pago mínimo basado en porcentaje del total."""
        return (self.total_a_pagar * porcentaje).quantize(Decimal("0.01"))

    def registrar_pago(self, monto: Decimal) -> None:
        """Registra un pago y actualiza el estado."""
        self.monto_pagado += monto

        if self.monto_pagado >= self.total_a_pagar:
            self.status = BillingCycleStatus.PAID
        elif self.monto_pagado > 0:
            self.status = BillingCycleStatus.PARTIAL

    def cerrar_ciclo(self) -> None:
        """Cierra el ciclo (ya pasó la fecha de corte)."""
        if self.status == BillingCycleStatus.OPEN:
            self.total_a_pagar = self.total_periodo + self.saldo_anterior + self.intereses_periodo
            self.pago_minimo = self.calcular_pago_minimo()
            self.status = BillingCycleStatus.CLOSED

    def marcar_vencido(self) -> None:
        """Marca el ciclo como vencido."""
        if not self.esta_pagado and date.today() > self.fecha_pago:
            self.status = BillingCycleStatus.OVERDUE
