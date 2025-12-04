"""Modelo de Meta Financiera para tracking de patrimonio."""

__all__ = ["Goal"]

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import Currency, GoalPriority, GoalStatus


class Goal(Base):
    """
    Meta financiera para tracking de progreso.

    Ejemplos:
        - Mundial 2026: ₡5,000,000 para Junio 2026
        - Fondo emergencia: ₡1,500,000
        - Marchamo 2026: ₡350,000 para Enero 2026
        - Laptop nueva: ₡800,000
    """

    __tablename__ = "goals"

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
        comment="ID del perfil dueño de esta meta",
    )

    # Multi-tenancy (futuro)
    tenant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
    )

    # Información de la meta
    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Nombre de la meta (ej: Mundial 2026)",
    )
    descripcion: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Descripción detallada de la meta",
    )
    icono: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        default="🎯",
        comment="Emoji/icono de la meta",
    )

    # Montos
    monto_objetivo: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        comment="Monto objetivo a alcanzar",
    )
    monto_actual: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Monto actualmente ahorrado para esta meta",
    )
    moneda: Mapped[Currency] = mapped_column(
        String(3),
        nullable=False,
        default=Currency.CRC,
        comment="Moneda de la meta",
    )

    # Fechas
    fecha_objetivo: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha objetivo para completar la meta",
    )
    fecha_completada: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha en que se completó la meta",
    )

    # Prioridad y estado
    prioridad: Mapped[GoalPriority] = mapped_column(
        String(20),
        nullable=False,
        default=GoalPriority.MEDIA,
        comment="Prioridad (alta, media, baja)",
    )
    estado: Mapped[GoalStatus] = mapped_column(
        String(20),
        nullable=False,
        default=GoalStatus.ACTIVA,
        comment="Estado de la meta",
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
        return f"<Goal(id={self.id[:8]}, nombre={self.nombre}, progreso={self.porcentaje_completado:.0f}%)>"

    @property
    def porcentaje_completado(self) -> float:
        """Retorna el porcentaje de la meta completado."""
        if self.monto_objetivo == 0:
            return 0.0
        return float(self.monto_actual / self.monto_objetivo * 100)

    @property
    def monto_faltante(self) -> Decimal:
        """Retorna cuánto falta para completar la meta."""
        faltante = self.monto_objetivo - self.monto_actual
        return max(faltante, Decimal("0.00"))

    @property
    def esta_completada(self) -> bool:
        """Retorna si la meta está completada."""
        return self.monto_actual >= self.monto_objetivo

    @property
    def dias_restantes(self) -> int | None:
        """Retorna días hasta la fecha objetivo."""
        if not self.fecha_objetivo:
            return None
        delta = self.fecha_objetivo - date.today()
        return max(delta.days, 0)

    @property
    def progreso_display(self) -> str:
        """Retorna una barra de progreso visual."""
        filled = int(self.porcentaje_completado / 10)
        empty = 10 - filled
        return "█" * filled + "░" * empty

    @property
    def monto_display(self) -> str:
        """Retorna el progreso formateado."""
        symbol = "₡" if self.moneda == Currency.CRC else "$"
        return f"{symbol}{self.monto_actual:,.0f} / {symbol}{self.monto_objetivo:,.0f}"

    def agregar_monto(self, monto: Decimal) -> None:
        """Agrega un monto al ahorro de esta meta."""
        self.monto_actual += monto
        if self.esta_completada and not self.fecha_completada:
            self.fecha_completada = date.today()
            self.estado = GoalStatus.COMPLETADA

    def calcular_ahorro_mensual_requerido(self) -> Decimal | None:
        """
        Calcula cuánto hay que ahorrar por mes para llegar a la meta.

        Returns:
            Monto mensual requerido, o None si no hay fecha objetivo
        """
        if not self.fecha_objetivo or self.esta_completada:
            return None

        dias = self.dias_restantes
        if dias is None or dias <= 0:
            return self.monto_faltante  # Ya pasó la fecha

        meses = Decimal(dias) / Decimal(30)
        if meses <= 0:
            return self.monto_faltante

        return round(self.monto_faltante / meses, 2)
