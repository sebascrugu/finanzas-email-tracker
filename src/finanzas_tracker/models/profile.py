"""Modelo de Perfil para sistema multi-perfil."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


class Profile(Base):
    """
    Modelo de Perfil.

    Un usuario (email de Outlook) puede tener múltiples perfiles:
    - Personal
    - Negocio
    - Familia (ej: mamá, papá)

    Cada perfil tiene:
    - Sus propias tarjetas
    - Su propio presupuesto
    - Sus propias transacciones
    - Sus propios ingresos

    Esto permite:
    - Separar finanzas personales de negocio
    - Gestionar finanzas de familiares en cuentas separadas
    - Buscar correos solo de los bancos relevantes por perfil
    """

    __tablename__ = "profiles"

    # Identificadores
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_email: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.email", ondelete="CASCADE"),
        index=True,
        comment="Email del propietario (usuario de Outlook)",
    )

    # Información del perfil
    nombre: Mapped[str] = mapped_column(
        String(100), comment="Nombre del perfil (ej: Personal, Negocio, Mamá)"
    )
    descripcion: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Descripción opcional del perfil"
    )
    icono: Mapped[str | None] = mapped_column(
        String(10), nullable=True, default="👤", comment="Icono emoji del perfil"
    )

    # Estado
    es_activo: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment="Si este es el perfil actualmente activo en el dashboard",
    )
    activo: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="Si el perfil está habilitado (soft delete)"
    )

    # Metadatos
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    owner: Mapped["User"] = relationship("User", back_populates="profiles")
    cards: Mapped[list["Card"]] = relationship(
        "Card", back_populates="profile", cascade="all, delete-orphan"
    )
    budgets: Mapped[list["Budget"]] = relationship(
        "Budget", back_populates="profile", cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction", back_populates="profile", cascade="all, delete-orphan"
    )
    incomes: Mapped[list["Income"]] = relationship(
        "Income", back_populates="profile", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return f"<Profile(id={self.id[:8]}..., nombre={self.nombre}, owner={self.owner_email})>"

    @property
    def nombre_completo(self) -> str:
        """Retorna el nombre con icono."""
        return f"{self.icono} {self.nombre}" if self.icono else self.nombre

    @property
    def bancos_asociados(self) -> list[str]:
        """Retorna lista de bancos únicos de las tarjetas del perfil."""
        if not self.cards:
            return []
        return list(
            set(
                card.banco.value if hasattr(card.banco, "value") else card.banco
                for card in self.cards
                if card.activa
            )
        )

    def activar(self) -> None:
        """Marca este perfil como activo (desactiva los demás del mismo usuario)."""
        self.es_activo = True

    def desactivar(self) -> None:
        """Marca este perfil como inactivo."""
        self.es_activo = False
