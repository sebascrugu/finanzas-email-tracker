"""Modelo de Cuenta Bancaria para tracking de patrimonio."""

__all__ = ["Account"]

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import AccountType, BankName, Currency


class Account(Base):
    """
    Cuenta bancaria con saldo para tracking de patrimonio.

    Representa una cuenta en un banco (corriente, ahorro, planilla).
    El saldo se actualiza manualmente o cuando llegan transacciones.

    Ejemplo:
        - Cuenta corriente BAC: ₡500,000
        - Cuenta ahorro Popular: ₡1,200,000
        - Cuenta planilla: ₡0 (se vacía cada quincena)
    """

    __tablename__ = "accounts"

    # Identificadores
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
    )

    # Relación con Profile
    profile_id: Mapped[str] = mapped_column(
        String(36),
        index=True,
        nullable=False,
        comment="ID del perfil dueño de esta cuenta",
    )

    # Multi-tenancy (futuro)
    tenant_id: Mapped[str | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
    )

    # Información de la cuenta
    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Nombre descriptivo (ej: Cuenta corriente BAC)",
    )
    banco: Mapped[BankName] = mapped_column(
        String(20),
        nullable=False,
        comment="Banco de la cuenta",
    )
    tipo: Mapped[AccountType] = mapped_column(
        String(20),
        nullable=False,
        default=AccountType.CHECKING,
        comment="Tipo de cuenta",
    )
    numero_cuenta: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Últimos 4 dígitos del número de cuenta",
    )

    # Saldo
    saldo: Mapped[Decimal] = mapped_column(
        Numeric(14, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Saldo actual de la cuenta",
    )
    moneda: Mapped[Currency] = mapped_column(
        String(3),
        nullable=False,
        default=Currency.CRC,
        comment="Moneda de la cuenta",
    )
    saldo_actualizado_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Última vez que se actualizó el saldo",
    )

    # Notas
    notas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Notas adicionales",
    )

    # Estado
    activa: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment="Si la cuenta está activa",
    )
    incluir_en_patrimonio: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="Si se incluye en el cálculo de patrimonio",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Soft delete",
    )

    def __repr__(self) -> str:
        return f"<Account(id={self.id[:8]}, nombre={self.nombre}, saldo={self.saldo})>"

    @property
    def saldo_display(self) -> str:
        """Retorna el saldo formateado."""
        symbol = "₡" if self.moneda == Currency.CRC else "$"
        return f"{symbol}{self.saldo:,.2f}"

    def actualizar_saldo(self, nuevo_saldo: Decimal) -> None:
        """Actualiza el saldo y la fecha de actualización."""
        self.saldo = nuevo_saldo
        self.saldo_actualizado_at = datetime.now(UTC)
