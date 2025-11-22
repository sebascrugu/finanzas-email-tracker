"""Modelo de transacción bancaria."""

__all__ = ["Transaction"]

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import (
    BankName,
    Currency,
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

    # Comercio normalizado
    merchant_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("merchants.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="ID del comercio normalizado (ej: todas las variantes de Subway apuntan al mismo merchant)",
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

    # Tipo especial (para casos como dinero ajeno, intermediaria, etc.)
    # Campo de texto libre - el usuario puede poner lo que quiera
    tipo_especial: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Tipo especial: dinero_ajeno, intermediaria, transferencia_propia, etc.",
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

    # NUEVO CAMPO - Contexto para desgl ose
    contexto: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Contexto del gasto en lenguaje natural (ej: 'Compré carne con plata de mamá')",
    )

    # Anomaly Detection (ML)
    is_anomaly: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        comment="Si la transacción fue detectada como anómala por ML",
    )
    anomaly_score: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=5, scale=4),
        nullable=True,
        comment="Score de anomalía (-1 a 1, donde < 0 es anómalo). Isolation Forest output.",
    )
    anomaly_reason: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Razón de por qué se marcó como anómala (ej: 'Monto inusualmente alto')",
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
        index=True,
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
    card: Mapped["Card | None"] = relationship("Card", back_populates="transactions")
    merchant: Mapped["Merchant | None"] = relationship("Merchant", back_populates="transacciones")
    subcategory: Mapped["Subcategory | None"] = relationship(
        "Subcategory",
        back_populates="transactions",
    )
    refund_of: Mapped["Transaction | None"] = relationship(
        "Transaction",
        remote_side="Transaction.id",
        foreign_keys=[refund_transaction_id],
    )
    income_splits: Mapped[list["IncomeSplit"]] = relationship(
        "IncomeSplit", back_populates="transaction", cascade="all, delete-orphan"
    )

    # Constraints e índices
    __table_args__ = (
        CheckConstraint("monto_crc > 0", name="check_transaction_monto_positive"),
        CheckConstraint("monto_original > 0", name="check_transaction_original_positive"),
        CheckConstraint(
            "confianza_categoria >= 0 AND confianza_categoria <= 100",
            name="check_transaction_confianza_valid",
        ),
        Index("ix_transactions_profile_fecha", "profile_id", "fecha_transaccion"),
        Index("ix_transactions_profile_tipo", "profile_id", "tipo_transaccion"),
        Index("ix_transactions_profile_categoria", "profile_id", "subcategory_id"),
        Index("ix_transactions_comercio", "comercio"),
        Index("ix_transactions_desconocidas", "es_desconocida"),
        Index("ix_transactions_created_at", "created_at"),
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
        """Retorna True si la transacción necesita atención (desconocida, baja confianza o anómala)."""
        return self.es_desconocida or self.confianza_categoria < 70 or self.is_anomaly

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
        self.tipo_especial = "reembolso"
        self.relacionada_con = f"Refund de transacción {transaction_id[:8]}"

    def calcular_monto_patrimonio(self) -> Decimal:
        """
        Calcula el monto real que cuenta para el patrimonio.

        Si está excluido de presupuesto (gasto ajeno, intermediaria, etc.), no cuenta.
        De lo contrario, es un gasto normal que reduce el patrimonio.
        """
        if self.excluir_de_presupuesto:
            # No cuenta en patrimonio (ej: gasto con plata de mamá)
            return Decimal("0")

        # Gasto normal, reduce patrimonio
        return self.monto_crc

    # Validators
    @validates("comercio")
    def validate_comercio(self, key: str, value: str) -> str:
        """Valida que el comercio no esté vacío."""
        if not value or not value.strip():
            raise ValueError("El nombre del comercio no puede estar vacío")
        return value.strip()

    @validates("email_id")
    def validate_email_id(self, key: str, value: str) -> str:
        """Valida que el email_id no esté vacío."""
        if not value or not value.strip():
            raise ValueError("El email_id es obligatorio para evitar duplicados")
        return value.strip()

    @validates("monto_crc")
    def validate_monto_crc(self, key: str, value: Decimal) -> Decimal:
        """Valida que el monto en CRC sea positivo."""
        if value <= 0:
            raise ValueError(f"El monto en CRC debe ser positivo, recibido: ₡{value:,.2f}")
        return value

    @validates("monto_original")
    def validate_monto_original(self, key: str, value: Decimal) -> Decimal:
        """Valida que el monto original sea positivo."""
        if value <= 0:
            raise ValueError(f"El monto original debe ser positivo, recibido: {value}")
        return value

    @validates("tipo_cambio_usado")
    def validate_tipo_cambio(self, key: str, value: Decimal | None) -> Decimal | None:
        """Valida que el tipo de cambio sea positivo si existe."""
        if value is not None and value <= 0:
            raise ValueError(f"El tipo de cambio debe ser positivo, recibido: {value}")
        return value
