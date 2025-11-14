"""Modelo de Perfil para sistema multi-perfil simplificado."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


class Profile(Base):
    """
    Modelo de Perfil - MODELO PRINCIPAL.

    Cada perfil representa un contexto financiero separado:
    - 👤 Personal: Tus finanzas personales
    - 💼 Negocio: Finanzas de tu empresa
    - 👵 Mamá: Finanzas de tu mamá (en su email)

    Cada perfil tiene:
    - Su propio email de Outlook (para buscar correos)
    - Sus propias tarjetas bancarias
    - Su propio presupuesto 50/30/20
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
    email_outlook: Mapped[str] = mapped_column(
        String(255),
        index=True,
        comment="Email de Outlook donde se reciben los correos bancarios",
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
        return f"<Profile(id={self.id[:8]}..., nombre={self.nombre}, email={self.email_outlook})>"

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
        """
        Marca este perfil como activo.

        NOTA: Debes desactivar manualmente los demás perfiles del mismo email
        si quieres que solo uno esté activo a la vez.
        """
        self.es_activo = True

    def desactivar(self) -> None:
        """Marca este perfil como inactivo."""
        self.es_activo = False
