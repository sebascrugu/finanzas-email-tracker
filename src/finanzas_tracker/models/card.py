"""Modelo de tarjetas bancarias."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


class Card(Base):
    """
    Modelo para almacenar tarjetas bancarias (débito/crédito).

    Permite rastrear con qué tarjeta se hizo cada transacción y
    alertar cuando se gasta más de lo que se tiene (crédito).
    """

    __tablename__ = "cards"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único de la tarjeta",
    )
    user_email: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.email", ondelete="CASCADE"),
        index=True,
        comment="Email del usuario propietario",
    )

    # Información de la tarjeta
    ultimos_4_digitos: Mapped[str] = mapped_column(
        String(4),
        comment="Últimos 4 dígitos de la tarjeta (ej: 3640)",
    )
    tipo: Mapped[str] = mapped_column(
        String(10),
        index=True,
        comment="Tipo: debito o credito",
    )
    banco: Mapped[str] = mapped_column(
        String(50),
        comment="Banco emisor: bac, popular",
    )
    marca: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Marca: visa, mastercard, etc.",
    )

    # Alias/nombre personalizado
    alias: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Alias personalizado (ej: 'Tarjeta principal', 'Débito BAC')",
    )

    # Estado
    activa: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment="Si la tarjeta está activa",
    )

    # Metadatos
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Fecha de registro de la tarjeta",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Fecha de última actualización",
    )

    # Relaciones
    user: Mapped["User"] = relationship("User", back_populates="cards")
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="card",
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<Card(user={self.user_email}, "
            f"****{self.ultimos_4_digitos}, "
            f"tipo={self.tipo})>"
        )

    @property
    def nombre_display(self) -> str:
        """Retorna el nombre para mostrar en la UI."""
        if self.alias:
            return f"{self.alias} (****{self.ultimos_4_digitos})"
        
        tipo_display = "Débito" if self.tipo == "debito" else "Crédito"
        return f"{tipo_display} {self.banco.upper()} ****{self.ultimos_4_digitos}"

    @property
    def es_credito(self) -> bool:
        """Verifica si es tarjeta de crédito."""
        return self.tipo == "credito"

    @property
    def es_debito(self) -> bool:
        """Verifica si es tarjeta de débito."""
        return self.tipo == "debito"

