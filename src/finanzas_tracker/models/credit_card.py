"""Modelo de Tarjeta de Crédito."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


class CreditCard(Base):
    """
    Modelo de Tarjeta de Crédito.

    Representa las tarjetas de crédito del usuario para generar alertas
    de cierre de ciclo y control de gastos.
    """

    __tablename__ = "credit_cards"

    # IDs
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid4()),
        comment="UUID único de la tarjeta",
    )

    profile_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        index=True,
        comment="ID del perfil propietario",
    )

    # Información de la tarjeta
    last_four_digits: Mapped[str] = mapped_column(
        String(4),
        comment="Últimos 4 dígitos de la tarjeta",
    )

    card_nickname: Mapped[str | None] = mapped_column(
        String(100),
        comment="Nombre/alias de la tarjeta (ej: 'Personal', 'Trabajo')",
    )

    bank_name: Mapped[str | None] = mapped_column(
        String(100),
        comment="Nombre del banco emisor",
    )

    # Ciclo de facturación
    closing_day: Mapped[int] = mapped_column(
        Integer,
        comment="Día del mes que cierra el ciclo (1-31)",
    )

    payment_due_day: Mapped[int] = mapped_column(
        Integer,
        comment="Día del mes de vencimiento de pago (1-31)",
    )

    # Límites
    credit_limit: Mapped[float | None] = mapped_column(
        Numeric(15, 2),
        comment="Límite de crédito en CRC",
    )

    # Estado
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        comment="Tarjeta activa",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        comment="Fecha de creación",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        comment="Fecha de última actualización",
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="Fecha de borrado lógico",
    )

    # Relaciones
    profile: Mapped["Profile"] = relationship("Profile", back_populates="credit_cards")

    @property
    def display_name(self) -> str:
        """Nombre para mostrar de la tarjeta."""
        if self.card_nickname:
            return f"{self.card_nickname} (X{self.last_four_digits})"
        if self.bank_name:
            return f"{self.bank_name} X{self.last_four_digits}"
        return f"Tarjeta X{self.last_four_digits}"

    @property
    def days_until_closing(self) -> int:
        """Días hasta el cierre del ciclo."""
        from datetime import date

        today = date.today()
        current_day = today.day

        if current_day <= self.closing_day:
            # El cierre es este mes
            return self.closing_day - current_day
        # El cierre es el próximo mes
        # Calcular días restantes del mes + días del próximo mes
        if today.month == 12:
            next_month = date(today.year + 1, 1, self.closing_day)
        else:
            # Manejar el caso donde closing_day > días del próximo mes
            try:
                next_month = date(today.year, today.month + 1, self.closing_day)
            except ValueError:
                # El próximo mes tiene menos días
                import calendar

                last_day = calendar.monthrange(today.year, today.month + 1)[1]
                next_month = date(today.year, today.month + 1, last_day)

        return (next_month - today).days

    @property
    def days_until_payment(self) -> int:
        """Días hasta el vencimiento del pago."""
        from datetime import date

        today = date.today()
        current_day = today.day

        if current_day <= self.payment_due_day:
            # El pago es este mes
            return self.payment_due_day - current_day
        # El pago es el próximo mes
        if today.month == 12:
            next_month = date(today.year + 1, 1, self.payment_due_day)
        else:
            try:
                next_month = date(today.year, today.month + 1, self.payment_due_day)
            except ValueError:
                import calendar

                last_day = calendar.monthrange(today.year, today.month + 1)[1]
                next_month = date(today.year, today.month + 1, last_day)

        return (next_month - today).days

    def __repr__(self) -> str:
        """Representación en string."""
        return f"<CreditCard(id={self.id}, display_name={self.display_name})>"
