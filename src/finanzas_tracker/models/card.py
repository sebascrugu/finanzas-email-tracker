"""Modelo de tarjetas bancarias."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from finanzas_tracker.core.database import Base
from finanzas_tracker.models.enums import BankName, CardType


if TYPE_CHECKING:
    from finanzas_tracker.models.billing_cycle import BillingCycle
    from finanzas_tracker.models.card_payment import CardPayment
    from finanzas_tracker.models.profile import Profile
    from finanzas_tracker.models.transaction import Transaction


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

    # Multi-tenancy (futuro)
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="ID del tenant para multi-tenancy (futuro)",
    )

    # Relación con perfil
    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        comment="ID del perfil al que pertenece esta tarjeta",
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

    # Información adicional para tarjetas de crédito
    current_balance: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=2),
        nullable=True,
        comment="Saldo actual de la tarjeta de crédito en colones",
    )
    interest_rate_annual: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Tasa de interés anual en % (ej: 52.00 para 52%)",
    )
    minimum_payment_percentage: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=5, scale=2),
        nullable=True,
        comment="Porcentaje de pago mínimo (ej: 2.50 para 2.5%)",
    )

    # Fecha de vencimiento de la tarjeta física
    card_expiration_date: Mapped[date | None] = mapped_column(
        Date,
        nullable=True,
        comment="Fecha de vencimiento del plástico (mes/año)",
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
    transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        back_populates="card",
    )
    billing_cycles: Mapped[list["BillingCycle"]] = relationship(
        "BillingCycle",
        back_populates="card",
        cascade="all, delete-orphan",
        order_by="desc(BillingCycle.fecha_corte)",
    )
    payments: Mapped[list["CardPayment"]] = relationship(
        "CardPayment",
        back_populates="card",
        cascade="all, delete-orphan",
        order_by="desc(CardPayment.fecha_pago)",
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
        Index("ix_cards_profile_tipo", "profile_id", "tipo"),
    )

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<Card(profile_id={self.profile_id[:8]}..., "
            f"****{self.ultimos_4_digitos}, "
            f"tipo={self.tipo})>"
        )

    @property
    def nombre_display(self) -> str:
        """Retorna el nombre para mostrar en la UI."""
        if self.alias:
            return f"{self.alias} (****{self.ultimos_4_digitos})"

        tipo_display = "Débito" if self.tipo == CardType.DEBIT else "Crédito"
        banco_display = (
            self.banco.upper() if isinstance(self.banco, str) else self.banco.value.upper()
        )
        return f"{tipo_display} {banco_display} ****{self.ultimos_4_digitos}"

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

    # Validators
    @validates("ultimos_4_digitos")
    def validate_ultimos_4_digitos(self, key: str, value: str) -> str:
        """Valida que sean exactamente 4 dígitos numéricos."""
        if not value:
            raise ValueError("Los últimos 4 dígitos son obligatorios")

        # Eliminar espacios
        value = value.strip()

        # Validar longitud
        if len(value) != 4:
            raise ValueError(
                f"Deben ser exactamente 4 dígitos, recibido: '{value}' ({len(value)} caracteres)"
            )

        # Validar que sean solo números
        if not value.isdigit():
            raise ValueError(f"Los últimos 4 dígitos deben ser solo números, recibido: '{value}'")

        return value

    @validates("limite_credito")
    def validate_limite_credito(self, key: str, value: Decimal | None) -> Decimal | None:
        """Valida que el límite de crédito sea positivo."""
        if value is not None and value <= 0:
            raise ValueError(f"El límite de crédito debe ser positivo, recibido: ₡{value:,.2f}")
        return value

    @validates("alias")
    def validate_alias(self, key: str, value: str | None) -> str | None:
        """Valida que el alias no esté vacío si se proporciona."""
        if value is not None:
            value = value.strip()
            if not value:
                return None  # Si está vacío, retornar None
        return value

    @validates("current_balance")
    def validate_current_balance(self, key: str, value: Decimal | None) -> Decimal | None:
        """Valida que el saldo actual sea no negativo."""
        if value is not None and value < 0:
            raise ValueError(f"El saldo actual no puede ser negativo, recibido: ₡{value:,.2f}")
        return value

    @validates("interest_rate_annual")
    def validate_interest_rate(self, key: str, value: Decimal | None) -> Decimal | None:
        """Valida que la tasa de interés esté en rango válido (0-100%)."""
        if value is not None:
            if value < 0 or value > 100:
                raise ValueError(
                    f"La tasa de interés debe estar entre 0% y 100%, recibido: {value}%"
                )
        return value

    @validates("minimum_payment_percentage")
    def validate_minimum_payment_percentage(
        self, key: str, value: Decimal | None
    ) -> Decimal | None:
        """Valida que el porcentaje de pago mínimo esté en rango válido (0-100%)."""
        if value is not None:
            if value < 0 or value > 100:
                raise ValueError(
                    f"El porcentaje de pago mínimo debe estar entre 0% y 100%, recibido: {value}%"
                )
        return value
