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
    profiles: Mapped[list["Profile"]] = relationship(
        "Profile",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    # DEPRECATED: Estas relaciones se mantienen por compatibilidad
    # pero deberían accederse a través de profiles
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
    def perfil_activo(self) -> "Profile | None":
        """
        Retorna el perfil actualmente activo.

        Returns:
            Profile | None: El perfil activo o None si no hay
        """
        if not self.profiles:
            return None

        # Buscar el perfil activo
        for profile in self.profiles:
            if profile.es_activo and profile.activo:
                return profile

        # Si ninguno está marcado como activo, retornar el primero
        return self.profiles[0] if self.profiles else None

    @property
    def presupuesto_actual(self) -> "Budget | None":
        """
        DEPRECATED: Usar perfil_activo.budgets en su lugar.

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
