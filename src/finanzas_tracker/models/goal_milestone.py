"""Modelo de Hitos de Progreso de Metas."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


class GoalMilestone(Base):
    """
    Modelo de Hitos de Progreso de Metas.

    Registra puntos importantes en el progreso hacia una meta financiera,
    permitiendo tracking histórico y análisis de tendencias.

    Ejemplos:
    - "Alcanzaste 25% de tu meta"
    - "Agregaste ₡50,000 manualmente"
    - "Meta en riesgo: vas atrasado según proyección"
    """

    __tablename__ = "goal_milestones"

    # IDs
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único del hito",
    )

    goal_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("savings_goals.id", ondelete="CASCADE"),
        index=True,
        comment="ID de la meta asociada",
    )

    # Información del hito
    milestone_type: Mapped[str] = mapped_column(
        String(50),
        comment="Tipo de hito: 'progress', 'contribution', 'alert', 'achievement'",
    )

    title: Mapped[str] = mapped_column(
        String(200),
        comment="Título del hito (ej: 'Alcanzaste 25%')",
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        comment="Descripción opcional del hito",
    )

    # Datos del momento
    amount_at_milestone: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        comment="Monto ahorrado al momento del hito",
    )

    percentage_at_milestone: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        comment="Porcentaje de progreso al momento del hito (0-100)",
    )

    contribution_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        comment="Monto de la contribución (si aplica)",
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Fecha del hito",
    )

    # Relaciones
    goal: Mapped["SavingsGoal"] = relationship("SavingsGoal", back_populates="milestones")

    def __repr__(self) -> str:
        """Representación en string."""
        return f"<GoalMilestone(id={self.id}, type={self.milestone_type}, title={self.title})>"
