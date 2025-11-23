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

    # Nuevas features para Fase 3 🚀
    icon: Mapped[str | None] = mapped_column(
        String(10),
        comment="Emoji/icono de la meta (ej: '✈️', '🏠', '⚽')",
    )

    priority: Mapped[int] = mapped_column(
        default=3,
        comment="Prioridad de la meta (1=Alta, 2=Media, 3=Baja)",
    )

    savings_type: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        comment="Tipo de ahorro: 'manual', 'automatic', 'monthly_target'",
    )

    monthly_contribution_target: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        comment="Meta de contribución mensual sugerida/configurada",
    )

    success_probability: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        comment="Probabilidad de éxito calculada por ML (0-100)",
    )

    last_ml_prediction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Última vez que se calculó la predicción ML",
    )

    ai_recommendations: Mapped[str | None] = mapped_column(
        Text,
        comment="Recomendaciones personalizadas generadas por Claude AI",
    )

    last_ai_analysis_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Última vez que Claude analizó esta meta",
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
    milestones: Mapped[list["GoalMilestone"]] = relationship(
        "GoalMilestone",
        back_populates="goal",
        cascade="all, delete-orphan",
        order_by="GoalMilestone.created_at.desc()",
    )

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

    @property
    def display_name(self) -> str:
        """Nombre con icono para display."""
        return f"{self.icon} {self.name}" if self.icon else self.name

    @property
    def is_at_risk(self) -> bool:
        """
        True si la meta está en riesgo de no cumplirse.

        Una meta está en riesgo si:
        - Tiene deadline
        - No está completada
        - El progreso actual es menor al esperado según tiempo transcurrido
        """
        if not self.deadline or self.is_completed:
            return False

        today = date.today()
        if self.deadline <= today:
            return not self.is_completed  # Ya pasó y no se completó

        # Calcular progreso esperado según tiempo
        total_days = (self.deadline - self.created_at.date()).days
        days_passed = (today - self.created_at.date()).days

        if total_days <= 0:
            return False

        expected_progress = (days_passed / total_days) * 100
        actual_progress = self.progress_percentage

        # En riesgo si va 15% o más atrasado
        return actual_progress < (expected_progress - 15)

    @property
    def health_status(self) -> str:
        """
        Estado de salud de la meta: 'excellent', 'good', 'warning', 'critical'.

        - excellent: >90% probabilidad de éxito o completada
        - good: 70-90% probabilidad
        - warning: 50-70% probabilidad o en riesgo
        - critical: <50% probabilidad o vencida
        """
        if self.is_completed:
            return "excellent"

        if self.is_overdue:
            return "critical"

        if self.success_probability is not None:
            prob = float(self.success_probability)
            if prob >= 90:
                return "excellent"
            elif prob >= 70:
                return "good"
            elif prob >= 50:
                return "warning"
            else:
                return "critical"

        # Sin predicción ML, usar progreso vs tiempo
        if self.is_at_risk:
            return "warning"

        return "good"

    def __repr__(self) -> str:
        """Representación en string."""
        return f"<SavingsGoal(id={self.id}, name={self.name}, progress={self.progress_percentage:.1f}%)>"
