"""Modelo de presupuesto."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


class Budget(Base):
    """
    Modelo para almacenar presupuestos de usuarios.

    Permite tener múltiples presupuestos en el tiempo (historial).
    Ejemplo: Nov-2025 con ₡280k, Ene-2026 con ₡400k, etc.
    """

    __tablename__ = "budgets"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único del presupuesto",
    )
    user_email: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.email", ondelete="CASCADE"),
        index=True,
        comment="Email del usuario propietario",
    )

    # Información del presupuesto
    salario_mensual: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Salario o ingreso mensual neto en colones",
    )

    # Vigencia del presupuesto
    fecha_inicio: Mapped[date] = mapped_column(
        Date,
        index=True,
        comment="Fecha de inicio de vigencia del presupuesto",
    )
    fecha_fin: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        index=True,
        comment="Fecha de fin (None si es el presupuesto actual)",
    )

    # Distribución del presupuesto (porcentajes)
    porcentaje_necesidades: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2),
        default=Decimal("50.00"),
        comment="% del salario para necesidades (ej: 50.00)",
    )
    porcentaje_gustos: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2),
        default=Decimal("30.00"),
        comment="% del salario para gustos (ej: 30.00)",
    )
    porcentaje_ahorros: Mapped[Decimal] = mapped_column(
        Numeric(precision=5, scale=2),
        default=Decimal("20.00"),
        comment="% del salario para ahorros (ej: 20.00)",
    )

    # Metadatos
    notas: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Notas sobre este presupuesto (ej: 'Cambio por nuevo trabajo')",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Fecha de creación del presupuesto",
    )

    # Relaciones
    user: Mapped["User"] = relationship("User", back_populates="budgets")

    # Constraints e índices
    __table_args__ = (
        CheckConstraint("salario_mensual > 0", name="check_budget_salario_positive"),
        CheckConstraint(
            "porcentaje_necesidades + porcentaje_gustos + porcentaje_ahorros = 100",
            name="check_budget_porcentajes_sum_100",
        ),
        CheckConstraint(
            "fecha_fin IS NULL OR fecha_fin > fecha_inicio",
            name="check_budget_fechas_validas",
        ),
        Index("ix_budgets_user_fechas", "user_email", "fecha_inicio", "fecha_fin"),
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<Budget(user={self.user_email}, "
            f"salario=₡{self.salario_mensual:,.0f}, "
            f"desde={self.fecha_inicio})>"
        )

    @property
    def monto_necesidades(self) -> Decimal:
        """Calcula el monto para necesidades."""
        return self.salario_mensual * (self.porcentaje_necesidades / 100)

    @property
    def monto_gustos(self) -> Decimal:
        """Calcula el monto para gustos."""
        return self.salario_mensual * (self.porcentaje_gustos / 100)

    @property
    def monto_ahorros(self) -> Decimal:
        """Calcula el monto para ahorros."""
        return self.salario_mensual * (self.porcentaje_ahorros / 100)

    @property
    def esta_activo(self) -> bool:
        """Verifica si este presupuesto está activo actualmente."""
        return self.fecha_fin is None

    def validar_porcentajes(self) -> bool:
        """
        Valida que los porcentajes sumen 100%.

        Returns:
            bool: True si suman 100%, False si no
        """
        total = self.porcentaje_necesidades + self.porcentaje_gustos + self.porcentaje_ahorros
        return abs(total - Decimal("100.00")) < Decimal("0.01")
