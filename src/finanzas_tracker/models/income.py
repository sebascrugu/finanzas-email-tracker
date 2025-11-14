"""Modelo de ingresos."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import Currency, IncomeType, RecurrenceFrequency


class Income(Base):
    """
    Modelo para registrar ingresos de dinero.

    Permite rastrear salarios, ventas, freelance, etc. para tener
    un panorama completo de ingresos vs gastos.
    """

    __tablename__ = "incomes"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único del ingreso",
    )

    # Relación con perfil
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        comment="ID del perfil al que pertenece este ingreso",
    )

    # Información del ingreso
    tipo: Mapped[IncomeType] = mapped_column(
        String(20),
        index=True,
        comment="Tipo de ingreso: salario, freelance, venta, etc.",
    )
    descripcion: Mapped[str] = mapped_column(
        String(255),
        comment="Descripción del ingreso (ej: 'Salario Noviembre 2025', 'Venta PS5')",
    )

    # Monto
    monto_original: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Monto en la moneda original",
    )
    moneda_original: Mapped[Currency] = mapped_column(
        String(3),
        default=Currency.CRC,
        comment="Moneda: CRC o USD",
    )
    monto_crc: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        index=True,
        comment="Monto convertido a colones",
    )
    tipo_cambio_usado: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=4),
        nullable=True,
        comment="Tipo de cambio si se hizo conversión",
    )

    # Fecha
    fecha: Mapped[date] = mapped_column(
        Date,
        index=True,
        comment="Fecha en que se recibió el ingreso",
    )

    # Recurrencia (para ingresos regulares como salario)
    es_recurrente: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        comment="Si es un ingreso recurrente (ej: salario mensual)",
    )
    frecuencia: Mapped[RecurrenceFrequency | None] = mapped_column(
        String(15),
        nullable=True,
        comment="Frecuencia si es recurrente: mensual, quincenal, etc.",
    )
    proximo_ingreso_esperado: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha esperada del próximo ingreso (si es recurrente)",
    )

    # Email relacionado (si proviene de un correo)
    email_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
        comment="ID del correo de origen (si aplica)",
    )

    # Confirmación y notas
    confirmado: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment="Si el ingreso está confirmado",
    )
    notas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notas adicionales",
    )

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Fecha de eliminación (soft delete)",
    )

    # Metadatos
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Fecha de creación del registro",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Fecha de última actualización",
    )

    # Relaciones
    profile: Mapped["Profile"] = relationship("Profile", back_populates="incomes")
    user: Mapped["User"] = relationship("User", back_populates="incomes")  # DEPRECATED

    # Constraints
    __table_args__ = (
        CheckConstraint("monto_crc > 0", name="check_income_monto_positive"),
        CheckConstraint("monto_original > 0", name="check_income_original_positive"),
        Index("ix_incomes_profile_fecha", "profile_id", "fecha"),
        Index("ix_incomes_profile_tipo", "profile_id", "tipo"),
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<Income(id={self.id[:8]}, "
            f"tipo={self.tipo.value}, "
            f"monto=₡{self.monto_crc:,.2f}, "
            f"fecha={self.fecha})>"
        )

    @property
    def monto_display(self) -> str:
        """Retorna el monto formateado para display."""
        if self.moneda_original == Currency.USD:
            return f"₡{self.monto_crc:,.2f} " f"(originalmente ${self.monto_original:,.2f} USD)"
        return f"₡{self.monto_crc:,.2f}"

    @property
    def esta_activo(self) -> bool:
        """Verifica si el ingreso no ha sido eliminado (soft delete)."""
        return self.deleted_at is None

    def soft_delete(self) -> None:
        """Marca el ingreso como eliminado (soft delete)."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restaura un ingreso eliminado."""
        self.deleted_at = None
