"""Modelo de Perfil para sistema multi-perfil simplificado."""

__all__ = ["Profile"]

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from finanzas_tracker.core.database import Base


class Profile(Base):
    """
    Modelo de Perfil - MODELO PRINCIPAL.

    Cada perfil representa un contexto financiero separado:
    -  Personal: Tus finanzas personales
    -  Negocio: Finanzas de tu empresa
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
        unique=True,
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
        String(10), nullable=True, default="", comment="Icono emoji del perfil"
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
    accounts: Mapped[list["Account"]] = relationship(
        "Account", back_populates="profile", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="profile", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["Alert"]] = relationship(
        "Alert", back_populates="profile", cascade="all, delete-orphan"
    )
    alert_config: Mapped["AlertConfig | None"] = relationship(
        "AlertConfig", back_populates="profile", cascade="all, delete-orphan", uselist=False
    )
    credit_cards: Mapped[list["CreditCard"]] = relationship(
        "CreditCard", back_populates="profile", cascade="all, delete-orphan"
    )
    savings_goals: Mapped[list["SavingsGoal"]] = relationship(
        "SavingsGoal", back_populates="profile", cascade="all, delete-orphan"
    )
    bank_statements: Mapped[list["BankStatement"]] = relationship(
        "BankStatement", back_populates="profile", cascade="all, delete-orphan"
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
            {
                card.banco.value if hasattr(card.banco, "value") else card.banco
                for card in self.cards
                if card.activa
            }
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

    # Validators
    @validates("nombre")
    def validate_nombre(self, key: str, value: str) -> str:
        """Valida que el nombre no esté vacío."""
        if not value or not value.strip():
            raise ValueError("El nombre del perfil no puede estar vacío")
        return value.strip()

    @validates("email_outlook")
    def validate_email_outlook(self, key: str, value: str) -> str:
        """Valida formato básico de email."""
        if not value or not value.strip():
            raise ValueError("El email de Outlook no puede estar vacío")

        value = value.strip().lower()

        # Validación básica de formato email
        if "@" not in value or "." not in value.split("@")[-1]:
            raise ValueError(f"Formato de email inválido: '{value}'")

        # Nota: No validamos el dominio específico para permitir flexibilidad
        # en el futuro (otros proveedores de email, testing, etc.)

        return value
