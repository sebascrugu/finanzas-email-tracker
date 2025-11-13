"""Modelo de transacción bancaria."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


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
    user_email: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("users.email", ondelete="CASCADE"),
        index=True,
        comment="Email del usuario propietario de la transacción",
    )

    # Información del banco
    banco: Mapped[str] = mapped_column(
        String(50),
        index=True,
        comment="Banco origen: 'bac' o 'popular'",
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
    tipo_transaccion: Mapped[str] = mapped_column(
        String(50),
        index=True,
        comment="Tipo: 'compra', 'transferencia', 'retiro', 'pago_servicio', etc.",
    )
    comercio: Mapped[str] = mapped_column(
        String(255),
        comment="Nombre del comercio o destino de la transacción",
    )

    # Montos
    monto_original: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=2),
        comment="Monto en la moneda original",
    )
    moneda_original: Mapped[str] = mapped_column(
        String(3),
        comment="Moneda original: 'USD' o 'CRC'",
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
    user: Mapped["User"] = relationship("User", back_populates="transactions")
    card: Mapped["Card | None"] = relationship("Card", back_populates="transactions")
    subcategory: Mapped["Subcategory | None"] = relationship(
        "Subcategory",
        back_populates="transactions",
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
        if self.moneda_original == "USD":
            return (
                f"₡{self.monto_crc:,.2f} "
                f"(originalmente ${self.monto_original:,.2f} USD @ ₡{self.tipo_cambio_usado:.2f})"
            )
        return f"₡{self.monto_crc:,.2f}"

    @property
    def es_internacional(self) -> bool:
        """Retorna True si la transacción fue fuera de Costa Rica."""
        return self.pais is not None and self.pais.lower() not in ["costa rica", "cr"]


