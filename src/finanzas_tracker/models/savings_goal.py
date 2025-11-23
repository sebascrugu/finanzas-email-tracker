"""Modelo de Meta de Ahorro."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


class SavingsGoal(Base):
    """
    Modelo de Meta de Ahorro.

    Representa las metas de ahorro del usuario para generar alertas
    de progreso y motivación.
    """

    __tablename__ = "savings_goals"

    # IDs
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único de la meta",
    )

    profile_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        comment="ID del perfil propietario",
    )

    # Información de la meta
    name: Mapped[str] = mapped_column(
        String(200),
        comment="Nombre de la meta (ej: 'Vacaciones', 'Fondo de emergencia')",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        comment="Descripción opcional de la meta",
    )

    # Montos
    target_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        comment="Monto objetivo en CRC",
    )

    current_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("0"),
        comment="Monto actual ahorrado en CRC",
    )

    # Fechas
    deadline: Mapped[date | None] = mapped_column(
        Date,
        comment="Fecha límite para alcanzar la meta",
    )

    # Estado
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment="Meta activa",
    )

    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        comment="Meta completada",
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Fecha de completado",
    )

    # Categoría/Tipo
    category: Mapped[str | None] = mapped_column(
        String(100),
        comment="Categoría de la meta (ej: 'Vacaciones', 'Emergencia', 'Compra')",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Fecha de creación",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Fecha de última actualización",
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Fecha de borrado lógico",
    )

    # Relaciones
    profile: Mapped["Profile"] = relationship("Profile", back_populates="savings_goals")

    @property
    def progress_percentage(self) -> float:
        """Porcentaje de progreso hacia la meta (0-100)."""
        if self.target_amount <= 0:
            return 0.0

        percentage = float((self.current_amount / self.target_amount) * 100)
        return min(percentage, 100.0)  # Cap at 100%

    @property
    def amount_remaining(self) -> Decimal:
        """Monto faltante para alcanzar la meta."""
        remaining = self.target_amount - self.current_amount
        return max(remaining, Decimal("0"))  # No negativo

    @property
    def days_remaining(self) -> int | None:
        """Días restantes hasta el deadline."""
        if not self.deadline:
            return None

        today = date.today()
        if self.deadline < today:
            return 0  # Ya pasó

        return (self.deadline - today).days

    @property
    def is_overdue(self) -> bool:
        """True si pasó el deadline sin completar."""
        if not self.deadline or self.is_completed:
            return False

        return date.today() > self.deadline

    @property
    def required_monthly_savings(self) -> Decimal | None:
        """
        Ahorro mensual requerido para alcanzar la meta.

        Returns None si no hay deadline.
        """
        if not self.deadline or self.is_completed:
            return None

        days_left = self.days_remaining
        if days_left is None or days_left <= 0:
            return None

        months_left = max(days_left / 30, 1)  # Al menos 1 mes
        return self.amount_remaining / Decimal(str(months_left))

    def mark_as_completed(self) -> None:
        """Marca la meta como completada."""
        self.is_completed = True
        self.completed_at = datetime.now(UTC)
        self.current_amount = self.target_amount  # Asegurar que llegó a la meta

    def add_savings(self, amount: Decimal) -> None:
        """
        Agrega ahorro a la meta.

        Args:
            amount: Monto a agregar
        """
        self.current_amount += amount

        # Auto-completar si alcanzó la meta
        if self.current_amount >= self.target_amount and not self.is_completed:
            self.mark_as_completed()

    def __repr__(self) -> str:
        """Representación en string."""
        return f"<SavingsGoal(id={self.id}, name={self.name}, progress={self.progress_percentage:.1f}%)>"
