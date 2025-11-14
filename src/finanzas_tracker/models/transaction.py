"""Modelo de transacción bancaria."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import (
    BankName,
    Currency,
    SpecialTransactionType,
    TransactionType,
)


class Transaction(Base):
    """
    Modelo para almacenar transacciones bancarias extraídas de correos.

    Cada transacción representa una compra, pago, transferencia u otro
    movimiento financiero detectado en los correos bancarios.
    """

    __tablename__ = "transactions"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único de la transacción",
    )
    email_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        comment="ID del correo de origen (para evitar duplicados)",
    )

    # Relación con perfil
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        comment="ID del perfil al que pertenece esta transacción",
    )

    # DEPRECATED: Se mantiene por compatibilidad
    user_email: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.email", ondelete="CASCADE"),
        index=True,
        comment="[DEPRECATED] Email del usuario - usar profile.owner_email",
    )

    # Información del banco
    banco: Mapped[BankName] = mapped_column(
        String(50),
        index=True,
        comment="Banco origen: bac o popular",
    )

    # Tarjeta usada
    card_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("cards.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID de la tarjeta usada en la transacción",
    )

    # Información de la transacción
    tipo_transaccion: Mapped[TransactionType] = mapped_column(
        String(50),
        index=True,
        comment="Tipo: compra, transferencia, retiro, pago_servicio, etc.",
    )
    comercio: Mapped[str] = mapped_column(
        String(255),
        comment="Nombre del comercio o destino de la transacción",
    )

    # Tipo especial (para casos como alquiler, reembolsos, etc.)
    tipo_especial: Mapped[SpecialTransactionType | None] = mapped_column(
        String(20),
        nullable=True,
        index=True,
        comment="Tipo especial: intermediaria, reembolso, compartida, etc.",
    )
    excluir_de_presupuesto: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        comment="Si se debe excluir del cálculo de presupuesto (ej: alquiler intermediario)",
    )
    relacionada_con: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Descripción de la relación (ej: 'Alquiler Nov-2025', 'Compra compartida con Juan')",
    )

    # Refunds y transacciones relacionadas
    refund_transaction_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID de la transacción original si esto es un refund",
    )

    # Flags para casos edge
    es_desconocida: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        comment="Si la transacción no se reconoce o no se documentó bien",
    )
    confianza_categoria: Mapped[int] = mapped_column(
        default=100,
        comment="Nivel de confianza en la categorización (0-100)",
    )

    # Montos
    monto_original: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Monto en la moneda original",
    )
    moneda_original: Mapped[Currency] = mapped_column(
        String(3),
        default=Currency.CRC,
        comment="Moneda original: USD o CRC",
    )
    monto_crc: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        index=True,
        comment="Monto convertido a colones (para unificar)",
    )
    tipo_cambio_usado: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=4),
        nullable=True,
        comment="Tipo de cambio usado si se hizo conversión USD→CRC",
    )

    # Fecha y ubicación
    fecha_transaccion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        comment="Fecha y hora de la transacción",
    )
    ciudad: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Ciudad donde se realizó la transacción",
    )
    pais: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="País donde se realizó la transacción",
    )

    # Categorización y confirmación
    subcategory_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("subcategories.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID de la subcategoría asignada",
    )
    categoria_sugerida_por_ia: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Subcategoría sugerida por Claude AI antes de confirmar",
    )
    necesita_revision: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        comment="Si la transacción necesita revisión manual de categoría",
    )
    confirmada: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment="Si la transacción está confirmada por el usuario",
    )
    notas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notas adicionales del usuario",
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
        comment="Fecha de creación del registro",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Fecha de última actualización",
    )

    # Relaciones
    profile: Mapped["Profile"] = relationship("Profile", back_populates="transactions")
    user: Mapped["User"] = relationship("User", back_populates="transactions")  # DEPRECATED
    card: Mapped["Card | None"] = relationship("Card", back_populates="transactions")
    subcategory: Mapped["Subcategory | None"] = relationship(
        "Subcategory",
        back_populates="transactions",
    )
    refund_of: Mapped["Transaction | None"] = relationship(
        "Transaction",
        remote_side="Transaction.id",
        foreign_keys=[refund_transaction_id],
    )

    # Constraints e índices
    __table_args__ = (
        CheckConstraint("monto_crc > 0", name="check_transaction_monto_positive"),
        CheckConstraint("monto_original > 0", name="check_transaction_original_positive"),
        CheckConstraint(
            "confianza_categoria >= 0 AND confianza_categoria <= 100",
            name="check_transaction_confianza_valid",
        ),
        Index("ix_transactions_user_fecha", "user_email", "fecha_transaccion"),
        Index("ix_transactions_user_tipo", "user_email", "tipo_transaccion"),
        Index("ix_transactions_user_categoria", "user_email", "subcategory_id"),
        Index("ix_transactions_comercio", "comercio"),
        Index("ix_transactions_desconocidas", "es_desconocida"),
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<Transaction(id={self.id[:8]}, "
            f"comercio={self.comercio}, "
            f"monto=₡{self.monto_crc:,.2f}, "
            f"fecha={self.fecha_transaccion.date()})>"
        )

    @property
    def monto_display(self) -> str:
        """
        Retorna el monto formateado para display.

        Si era USD, muestra: "₡13,000.00 (originalmente $25.00 USD)"
        Si era CRC, muestra: "₡13,000.00"
        """
        if self.moneda_original == Currency.USD:
            return (
                f"₡{self.monto_crc:,.2f} "
                f"(originalmente ${self.monto_original:,.2f} USD @ ₡{self.tipo_cambio_usado:.2f})"
            )
        return f"₡{self.monto_crc:,.2f}"

    @property
    def es_internacional(self) -> bool:
        """Retorna True si la transacción fue fuera de Costa Rica."""
        return self.pais is not None and self.pais.lower() not in ["costa rica", "cr"]

    @property
    def es_especial(self) -> bool:
        """Retorna True si es una transacción especial (intermediaria, reembolso, etc.)."""
        return self.tipo_especial is not None

    @property
    def es_refund(self) -> bool:
        """Retorna True si es un refund de otra transacción."""
        return self.refund_transaction_id is not None

    @property
    def necesita_atencion(self) -> bool:
        """Retorna True si la transacción necesita atención (desconocida o baja confianza)."""
        return self.es_desconocida or self.confianza_categoria < 70

    @property
    def debe_contar_en_presupuesto(self) -> bool:
        """Retorna True si la transacción debe contar en el presupuesto."""
        return not self.excluir_de_presupuesto and self.deleted_at is None

    @property
    def esta_activa(self) -> bool:
        """Verifica si la transacción no ha sido eliminada (soft delete)."""
        return self.deleted_at is None

    def soft_delete(self) -> None:
        """Marca la transacción como eliminada (soft delete)."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restaura una transacción eliminada."""
        self.deleted_at = None

    def marcar_como_refund(self, transaction_id: str) -> None:
        """
        Marca esta transacción como refund de otra.

        Args:
            transaction_id: ID de la transacción original
        """
        self.refund_transaction_id = transaction_id
        self.tipo_especial = SpecialTransactionType.REIMBURSEMENT
        self.relacionada_con = f"Refund de transacción {transaction_id[:8]}"
