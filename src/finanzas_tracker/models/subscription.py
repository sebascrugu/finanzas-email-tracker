"""Modelo de suscripción recurrente detectada automáticamente."""

__all__ = ["Subscription"]

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from finanzas_tracker.core.database import Base


class Subscription(Base):
    """
    Modelo para almacenar suscripciones recurrentes detectadas automáticamente.

    Una suscripción es un gasto que se repite con regularidad:
    - Mismo comercio (ej: Netflix, Spotify, gimnasio)
    - Monto similar (±10%)
    - Frecuencia regular (~30 días para mensual)

    El sistema detecta estos patrones automáticamente y alerta al usuario.
    """

    __tablename__ = "subscriptions"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único de la suscripción",
    )

    # Relación con perfil
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        comment="ID del perfil al que pertenece esta suscripción",
    )

    # Comercio (merchant normalizado)
    merchant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("merchants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID del comercio normalizado",
    )
    comercio: Mapped[str] = mapped_column(
        String(255),
        comment="Nombre del comercio (para display)",
    )

    # Patrón de pago
    monto_promedio: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Monto promedio de los cobros (en CRC)",
    )
    monto_min: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Monto mínimo detectado",
    )
    monto_max: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Monto máximo detectado",
    )

    # Frecuencia
    frecuencia_dias: Mapped[int] = mapped_column(
        Integer,
        comment="Frecuencia promedio en días (ej: 30 para mensual, 7 para semanal)",
    )

    # Fechas
    primera_fecha_cobro: Mapped[date] = mapped_column(
        Date,
        comment="Fecha del primer cobro detectado",
    )
    ultima_fecha_cobro: Mapped[date] = mapped_column(
        Date,
        comment="Fecha del último cobro detectado",
    )
    proxima_fecha_estimada: Mapped[date] = mapped_column(
        Date,
        comment="Fecha estimada del próximo cobro (última + frecuencia)",
    )

    # Detección y confianza
    occurrences_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Cantidad de veces que se ha cobrado esta suscripción",
    )
    confidence_score: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2),
        comment="Score de confianza (0-100) de que es realmente una suscripción",
    )

    # Estado
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment="Si la suscripción está activa (no cancelada)",
    )
    is_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Si el usuario confirmó manualmente que es una suscripción",
    )

    # Categoría (opcional, para mejor tracking)
    subcategory_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("subcategories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Categoría de la suscripción (streaming, gym, etc.)",
    )

    # Notas
    notas: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Notas del usuario sobre esta suscripción",
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
        index=True,
        comment="Fecha de creación del registro",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Fecha de última actualización",
    )

    # Relaciones
    profile: Mapped["Profile"] = relationship("Profile", back_populates="subscriptions")
    merchant: Mapped["Merchant | None"] = relationship("Merchant")
    subcategory: Mapped["Subcategory | None"] = relationship("Subcategory")
    alerts: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="subscription", cascade="all, delete-orphan"
    )

    # Constraints e índices
    __table_args__ = (
        CheckConstraint("monto_promedio > 0", name="check_subscription_monto_positive"),
        CheckConstraint("monto_min <= monto_max", name="check_subscription_monto_range"),
        CheckConstraint(
            "frecuencia_dias > 0 AND frecuencia_dias <= 365",
            name="check_subscription_frecuencia_valid",
        ),
        CheckConstraint(
            "occurrences_count >= 0",
            name="check_subscription_occurrences_positive",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 100",
            name="check_subscription_confidence_valid",
        ),
        Index("ix_subscriptions_profile_active", "profile_id", "is_active"),
        Index("ix_subscriptions_comercio", "comercio"),
        Index("ix_subscriptions_proxima_fecha", "proxima_fecha_estimada"),
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<Subscription(id={self.id[:8]}, "
            f"comercio={self.comercio}, "
            f"monto=₡{self.monto_promedio:,.0f}, "
            f"frecuencia={self.frecuencia_dias} días)>"
        )

    @property
    def monto_display(self) -> str:
        """Retorna el monto formateado para display."""
        if self.monto_min == self.monto_max:
            return f"₡{self.monto_promedio:,.2f}"
        else:
            return f"₡{self.monto_promedio:,.2f} (₡{self.monto_min:,.0f} - ₡{self.monto_max:,.0f})"

    @property
    def frecuencia_display(self) -> str:
        """Retorna la frecuencia en formato legible."""
        if self.frecuencia_dias <= 7:
            return "Semanal"
        elif self.frecuencia_dias <= 15:
            return "Quincenal"
        elif self.frecuencia_dias <= 35:
            return "Mensual"
        elif self.frecuencia_dias <= 95:
            return "Trimestral"
        elif self.frecuencia_dias <= 185:
            return "Semestral"
        else:
            return "Anual"

    @property
    def dias_hasta_proximo_cobro(self) -> int:
        """Retorna cuántos días faltan para el próximo cobro estimado."""
        hoy = date.today()
        if self.proxima_fecha_estimada > hoy:
            return (self.proxima_fecha_estimada - hoy).days
        else:
            return 0  # Ya pasó o es hoy

    @property
    def esta_vencida(self) -> bool:
        """Retorna True si la fecha estimada ya pasó (posible cancelación)."""
        return date.today() > self.proxima_fecha_estimada

    @property
    def esta_proxima(self) -> bool:
        """Retorna True si el cobro es en los próximos 3 días."""
        return 0 <= self.dias_hasta_proximo_cobro <= 3

    @property
    def esta_activa(self) -> bool:
        """Verifica si la suscripción no ha sido eliminada."""
        return self.deleted_at is None and self.is_active

    @property
    def total_gastado(self) -> Decimal:
        """Retorna el total gastado en esta suscripción (estimado)."""
        return self.monto_promedio * Decimal(self.occurrences_count)

    def soft_delete(self) -> None:
        """Marca la suscripción como eliminada."""
        self.deleted_at = datetime.now(UTC)
        self.is_active = False

    def restore(self) -> None:
        """Restaura una suscripción eliminada."""
        self.deleted_at = None
        self.is_active = True

    def cancelar(self) -> None:
        """Marca la suscripción como cancelada (no eliminada)."""
        self.is_active = False

    def activar(self) -> None:
        """Activa una suscripción cancelada."""
        self.is_active = True

    def actualizar_proximo_cobro(self) -> None:
        """Actualiza la fecha del próximo cobro estimado."""
        from datetime import timedelta

        self.proxima_fecha_estimada = self.ultima_fecha_cobro + timedelta(days=self.frecuencia_dias)

    # Validators
    @validates("comercio")
    def validate_comercio(self, key: str, value: str) -> str:
        """Valida que el comercio no esté vacío."""
        if not value or not value.strip():
            raise ValueError("El nombre del comercio no puede estar vacío")
        return value.strip()

    @validates("monto_promedio", "monto_min", "monto_max")
    def validate_monto(self, key: str, value: Decimal) -> Decimal:
        """Valida que los montos sean positivos."""
        if value <= 0:
            raise ValueError(f"{key} debe ser positivo, recibido: ₡{value:,.2f}")
        return value

    @validates("frecuencia_dias")
    def validate_frecuencia(self, key: str, value: int) -> int:
        """Valida que la frecuencia esté en rango válido."""
        if value <= 0 or value > 365:
            raise ValueError(f"Frecuencia debe estar entre 1-365 días, recibido: {value}")
        return value

    @validates("occurrences_count")
    def validate_occurrences(self, key: str, value: int) -> int:
        """Valida que las ocurrencias sean >= 0."""
        if value < 0:
            raise ValueError(f"Occurrences debe ser >= 0, recibido: {value}")
        return value

    @validates("confidence_score")
    def validate_confidence(self, key: str, value: Decimal) -> Decimal:
        """Valida que el score esté entre 0-100."""
        if value < 0 or value > 100:
            raise ValueError(f"Confidence debe estar entre 0-100, recibido: {value}")
        return value
