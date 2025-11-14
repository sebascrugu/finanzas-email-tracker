"""Modelo de usuario."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


class User(Base):
    """
    Modelo para almacenar usuarios del sistema.

    Cada usuario tiene su propio presupuesto, tarjetas y transacciones.
    """

    __tablename__ = "users"

    # Identificador
    email: Mapped[str] = mapped_column(
        String(255),
        primary_key=True,
        comment="Email del usuario (Outlook/Hotmail)",
    )

    # Información personal
    nombre: Mapped[str] = mapped_column(
        String(100),
        comment="Nombre completo del usuario",
    )

    # Estado
    activo: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment="Si el usuario está activo en el sistema",
    )

    # Metadatos
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Fecha de creación del usuario",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Fecha de última actualización",
    )

    # Relaciones
    budgets: Mapped[list["Budget"]] = relationship(
        "Budget",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    cards: Mapped[list["Card"]] = relationship(
        "Card",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    incomes: Mapped[list["Income"]] = relationship(
        "Income",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return f"<User(email={self.email}, nombre={self.nombre})>"

    @property
    def presupuesto_actual(self) -> "Budget | None":
        """
        Retorna el presupuesto actualmente vigente.

        Returns:
            Budget | None: El presupuesto actual o None si no hay
        """
        if not self.budgets:
            return None

        # Buscar el presupuesto sin fecha_fin (el actual)
        for budget in self.budgets:
            if budget.fecha_fin is None:
                return budget

        # Si todos tienen fecha_fin, retornar el más reciente
        return max(self.budgets, key=lambda b: b.fecha_inicio)
