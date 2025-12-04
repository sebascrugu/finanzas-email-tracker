"""Modelo de Inversión para tracking de patrimonio."""

__all__ = ["Investment"]

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import Currency, InvestmentType


class Investment(Base):
    """
    Inversión financiera para tracking de patrimonio.

    Soporta:
    - CDP (Certificado de Depósito a Plazo)
    - Ahorro a plazo
    - Fondos de inversión
    - Acciones, bonos, etc.

    Ejemplo:
        - CDP BAC 6 meses: ₡4,000,000 al 3.73% anual
        - MultiMoney Popular: $6,000 al 2.1% anual
    """

    __tablename__ = "investments"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Relación con Profile
    profile_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
        nullable=False,
        comment="ID del perfil dueño de esta inversión",
    )

    # Multi-tenancy (futuro)
    tenant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
    )

    # Información de la inversión
    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Nombre descriptivo (ej: CDP 6 meses BAC)",
    )
    tipo: Mapped[InvestmentType] = mapped_column(
        String(30),
        nullable=False,
        default=InvestmentType.CDP,
        comment="Tipo de inversión",
    )
    institucion: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Institución donde está la inversión",
    )

    # Montos
    monto_principal: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        comment="Monto inicial invertido",
    )
    moneda: Mapped[Currency] = mapped_column(
        String(3),
        nullable=False,
        default=Currency.CRC,
        comment="Moneda de la inversión",
    )

    # Rendimiento
    tasa_interes_anual: Mapped[Decimal] = mapped_column(
        Numeric(6, 4),
        nullable=False,
        default=Decimal("0.0000"),
        comment="Tasa de interés anual (ej: 0.0373 = 3.73%)",
    )
    rendimiento_acumulado: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Rendimiento acumulado hasta la fecha",
    )

    # Fechas
    fecha_inicio: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha de inicio de la inversión",
    )
    fecha_vencimiento: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha de vencimiento (None si no aplica)",
    )

    # Notas
    notas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notas adicionales",
    )

    # Estado
    activa: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment="Si la inversión está activa",
    )
    incluir_en_patrimonio: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Si se incluye en el cálculo de patrimonio",
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

    def __repr__(self) -> str:
        return f"<Investment(id={self.id[:8]}, nombre={self.nombre}, monto={self.monto_principal})>"

    @property
    def valor_actual(self) -> Decimal:
        """Retorna el valor actual (principal + rendimiento)."""
        return self.monto_principal + self.rendimiento_acumulado

    @property
    def tasa_display(self) -> str:
        """Retorna la tasa formateada como porcentaje."""
        return f"{float(self.tasa_interes_anual) * 100:.2f}%"

    @property
    def valor_display(self) -> str:
        """Retorna el valor actual formateado."""
        symbol = "₡" if self.moneda == Currency.CRC else "$"
        return f"{symbol}{self.valor_actual:,.2f}"

    @property
    def dias_para_vencimiento(self) -> int | None:
        """Retorna días hasta vencimiento, o None si no tiene."""
        if not self.fecha_vencimiento:
            return None
        delta = self.fecha_vencimiento - date.today()
        return delta.days

    def calcular_rendimiento_proyectado(self) -> Decimal:
        """
        Calcula el rendimiento proyectado al vencimiento.

        Para CDP: usa interés simple
        Para otros: puede extenderse con lógica específica
        """
        if not self.fecha_vencimiento:
            return Decimal("0.00")

        dias = (self.fecha_vencimiento - self.fecha_inicio).days
        rendimiento = self.monto_principal * self.tasa_interes_anual * Decimal(dias) / Decimal(365)
        return round(rendimiento, 2)
