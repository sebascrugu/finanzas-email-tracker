"""Modelo de tarjetas bancarias."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import BankName, CardType


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

    # Relación con perfil
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        comment="ID del perfil al que pertenece esta tarjeta",
    )

    # DEPRECATED: Se mantiene por compatibilidad
    user_email: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.email", ondelete="CASCADE"),
        index=True,
        comment="[DEPRECATED] Email del usuario - usar profile.owner_email",
    )

    # Información de la tarjeta
    ultimos_4_digitos: Mapped[str] = mapped_column(
        String(4),
        comment="Últimos 4 dígitos de la tarjeta (ej: 3640)",
    )
    tipo: Mapped[CardType] = mapped_column(
        String(10),
        index=True,
        comment="Tipo: debito o credito",
    )
    banco: Mapped[BankName] = mapped_column(
        String(50),
        comment="Banco emisor: bac, popular",
    )
    marca: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Marca: visa, mastercard, etc.",
    )

    # Límite de crédito (solo para tarjetas de crédito)
    limite_credito: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=True,
        comment="Límite de crédito en colones (solo para tarjetas de crédito)",
    )
    fecha_corte: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Día del mes de corte (1-31)",
    )
    fecha_vencimiento: Mapped[int | None] = mapped_column(
        nullable=True,
        comment="Día del mes de vencimiento (1-31)",
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

    # Soft delete
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="Fecha de eliminación (soft delete)",
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
    profile: Mapped["Profile"] = relationship("Profile", back_populates="cards")
    user: Mapped["User"] = relationship("User", back_populates="cards")  # DEPRECATED
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="card",
    )

    # Constraints e índices
    __table_args__ = (
        CheckConstraint(
            "limite_credito IS NULL OR limite_credito > 0",
            name="check_card_limite_positive",
        ),
        CheckConstraint(
            "fecha_corte IS NULL OR (fecha_corte >= 1 AND fecha_corte <= 31)",
            name="check_card_fecha_corte_valid",
        ),
        CheckConstraint(
            "fecha_vencimiento IS NULL OR (fecha_vencimiento >= 1 AND fecha_vencimiento <= 31)",
            name="check_card_fecha_venc_valid",
        ),
        Index("ix_cards_user_tipo", "user_email", "tipo"),
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

        tipo_display = "Débito" if self.tipo == CardType.DEBIT else "Crédito"
        return f"{tipo_display} {self.banco.value.upper()} ****{self.ultimos_4_digitos}"

    @property
    def es_credito(self) -> bool:
        """Verifica si es tarjeta de crédito."""
        return self.tipo == CardType.CREDIT

    @property
    def es_debito(self) -> bool:
        """Verifica si es tarjeta de débito."""
        return self.tipo == CardType.DEBIT

    @property
    def esta_activa(self) -> bool:
        """Verifica si la tarjeta no ha sido eliminada (soft delete)."""
        return self.deleted_at is None and self.activa

    def calcular_gasto_mensual(self, mes: int, anio: int) -> Decimal:
        """
        Calcula el gasto total de esta tarjeta en un mes específico.

        Args:
            mes: Mes (1-12)
            anio: Año (ej: 2025)

        Returns:
            Decimal: Gasto total en colones
        """
        from decimal import Decimal as D

        total = D("0")
        for tx in self.transactions:
            if (
                tx.fecha_transaccion.month == mes
                and tx.fecha_transaccion.year == anio
                and tx.debe_contar_en_presupuesto
            ):
                total += tx.monto_crc
        return total

    def calcular_disponible_credito(self, mes: int, anio: int) -> Decimal | None:
        """
        Calcula el crédito disponible en un mes específico.

        Args:
            mes: Mes (1-12)
            anio: Año (ej: 2025)

        Returns:
            Decimal | None: Crédito disponible o None si no es tarjeta de crédito
        """
        if not self.es_credito or not self.limite_credito:
            return None

        gasto_mensual = self.calcular_gasto_mensual(mes, anio)
        return self.limite_credito - gasto_mensual

    def soft_delete(self) -> None:
        """Marca la tarjeta como eliminada (soft delete)."""
        self.deleted_at = datetime.now(UTC)
        self.activa = False

    def restore(self) -> None:
        """Restaura una tarjeta eliminada."""
        self.deleted_at = None
        self.activa = True
