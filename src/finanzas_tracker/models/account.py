"""Modelo de Cuenta para gestión de activos financieros."""

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from finanzas_tracker.core.database import Base
from finanzas_tracker.services.exchange_rate import exchange_rate_service


class AccountType(str, Enum):
    """Tipos de cuenta disponibles."""

    CHECKING = "checking"  # Cuenta corriente
    SAVINGS = "savings"  # Cuenta de ahorros (con interés)
    INVESTMENT = "investment"  # Cuenta de inversión
    CDP = "cdp"  # Certificado de depósito a plazo
    CASH = "cash"  # Efectivo


class Account(Base):
    """
    Modelo de Cuenta - Gestión de Activos Financieros.

    Representa cuentas bancarias, inversiones, CDPs, etc.
    Permite calcular patrimonio real y proyecciones de intereses.

    Ejemplos:
    - Cuenta corriente BAC: ₡181,276
    - Cuenta vista Popular (6%): ₡6,000,000
    - CDP 1 mes (3.53%): ₡4,000,000
    """

    __tablename__ = "accounts"

    # Identificadores
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("profiles.id"), nullable=False, index=True
    )

    # Información de la cuenta
    nombre: Mapped[str] = mapped_column(String(100), comment="Nombre de la cuenta")
    tipo: Mapped[str] = mapped_column(
        String(20), comment="Tipo de cuenta: checking, savings, investment, cdp, cash"
    )
    banco: Mapped[str | None] = mapped_column(
        String(50), nullable=True, comment="Banco o institución financiera"
    )
    descripcion: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="Descripción o notas adicionales"
    )

    # Montos y moneda
    saldo_actual: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), default=0, comment="Saldo actual de la cuenta en su moneda"
    )
    moneda: Mapped[str] = mapped_column(
        String(3), default="CRC", comment="Moneda de la cuenta (CRC, USD)"
    )

    # Intereses (para cuentas de ahorro, CDPs, inversiones)
    tasa_interes: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2),
        nullable=True,
        comment="Tasa de interés anual (ej: 6.00 para 6%)",
    )
    tipo_interes: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        default="simple",
        comment="Tipo de interés: simple o compuesto",
    )

    # Para CDPs e inversiones con plazo
    fecha_apertura: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="Fecha de apertura o inicio de la inversión"
    )
    fecha_vencimiento: Mapped[date | None] = mapped_column(
        Date, nullable=True, comment="Fecha de vencimiento (para CDPs)"
    )
    plazo_meses: Mapped[int | None] = mapped_column(
        nullable=True, comment="Plazo en meses (para CDPs)"
    )

    # Estado
    activa: Mapped[bool] = mapped_column(Boolean, default=True, comment="Si la cuenta está activa")
    incluir_en_patrimonio: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="Si se incluye en el cálculo de patrimonio total"
    )

    # Metadatos
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="Soft delete"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    profile: Mapped["Profile"] = relationship("Profile", back_populates="accounts")
    # transactions: Mapped[list["Transaction"]] = relationship(
    #     "Transaction", back_populates="account"
    # )  # Opcional - para relacionar transacciones con cuentas específicas

    def __repr__(self) -> str:
        """Representación en string del modelo."""
        return (
            f"<Account(id={self.id[:8]}..., nombre={self.nombre}, "
            f"tipo={self.tipo}, saldo={self.saldo_actual} {self.moneda})>"
        )

    @property
    def saldo_crc(self) -> Decimal:
        """Retorna el saldo en colones."""
        if self.moneda == "CRC":
            return self.saldo_actual
        # Convertir USD a CRC usando exchange rate service
        tipo_cambio = exchange_rate_service.get_rate(date.today())
        return self.saldo_actual * Decimal(str(tipo_cambio))

    def calcular_interes_mensual(self) -> Decimal:
        """Calcula el interés mensual generado."""
        if not self.tasa_interes or self.tasa_interes <= 0:
            return Decimal("0")

        # Interés simple mensual = (saldo * tasa_anual / 12) / 100
        interes = (self.saldo_crc * self.tasa_interes / Decimal("12")) / Decimal("100")
        return interes.quantize(Decimal("0.01"))

    def calcular_interes_anual(self) -> Decimal:
        """Calcula el interés anual generado."""
        if not self.tasa_interes or self.tasa_interes <= 0:
            return Decimal("0")

        if self.tipo_interes == "compuesto":
            # Interés compuesto: P * ((1 + r)^t - 1)
            tasa_decimal = self.tasa_interes / Decimal("100")
            factor = (Decimal("1") + tasa_decimal) ** 1
            interes = self.saldo_crc * (factor - Decimal("1"))
        else:
            # Interés simple: P * r * t
            interes = (self.saldo_crc * self.tasa_interes) / Decimal("100")

        return interes.quantize(Decimal("0.01"))

    def proyectar_saldo(self, meses: int = 12) -> Decimal:
        """Proyecta el saldo futuro después de N meses con intereses."""
        if not self.tasa_interes or self.tasa_interes <= 0:
            return self.saldo_crc

        if self.tipo_interes == "compuesto":
            # Interés compuesto mensual
            tasa_mensual = self.tasa_interes / Decimal("1200")  # tasa anual / 12 / 100
            factor = (Decimal("1") + tasa_mensual) ** meses
            saldo_futuro = self.saldo_crc * factor
        else:
            # Interés simple
            tasa_decimal = self.tasa_interes / Decimal("100")
            años = Decimal(meses) / Decimal("12")
            interes_total = self.saldo_crc * tasa_decimal * años
            saldo_futuro = self.saldo_crc + interes_total

        return saldo_futuro.quantize(Decimal("0.01"))

    @classmethod
    def calcular_patrimonio_total(cls, session, profile_id: str) -> Decimal:
        """Calcula el patrimonio total de todas las cuentas activas del perfil."""
        cuentas = (
            session.query(cls)
            .filter(
                cls.profile_id == profile_id,
                cls.activa == True,  # noqa: E712
                cls.incluir_en_patrimonio == True,  # noqa: E712
                cls.deleted_at.is_(None),
            )
            .all()
        )

        total = sum(cuenta.saldo_crc for cuenta in cuentas)
        return total.quantize(Decimal("0.01"))

    @classmethod
    def calcular_intereses_mensuales_totales(cls, session, profile_id: str) -> Decimal:
        """Calcula los intereses mensuales totales de todas las cuentas."""
        cuentas = (
            session.query(cls)
            .filter(
                cls.profile_id == profile_id,
                cls.activa == True,  # noqa: E712
                cls.deleted_at.is_(None),
            )
            .all()
        )

        total = sum(cuenta.calcular_interes_mensual() for cuenta in cuentas)
        return total.quantize(Decimal("0.01"))

    # Validators
    @validates("nombre")
    def validate_nombre(self, key: str, value: str) -> str:
        """Valida que el nombre no esté vacío."""
        if not value or not value.strip():
            raise ValueError("El nombre de la cuenta no puede estar vacío")
        return value.strip()

    @validates("saldo_actual")
    def validate_saldo_actual(self, key: str, value: Decimal) -> Decimal:
        """Valida que el saldo actual no sea negativo."""
        if value < 0:
            raise ValueError(f"El saldo actual no puede ser negativo, recibido: ₡{value:,.2f}")
        return value

    @validates("tasa_interes")
    def validate_tasa_interes(self, key: str, value: Decimal | None) -> Decimal | None:
        """Valida que la tasa de interés esté entre 0 y 100."""
        if value is not None:
            if value < 0:
                raise ValueError(f"La tasa de interés no puede ser negativa, recibido: {value}%")
            if value > 100:
                raise ValueError(
                    f"La tasa de interés no puede ser mayor a 100%, recibido: {value}%"
                )
        return value

    @validates("plazo_meses")
    def validate_plazo_meses(self, key: str, value: int | None) -> int | None:
        """Valida que el plazo en meses sea positivo."""
        if value is not None and value <= 0:
            raise ValueError(f"El plazo debe ser mayor a 0 meses, recibido: {value}")
        return value

    @validates("fecha_vencimiento")
    def validate_fecha_vencimiento(self, key: str, value: date | None) -> date | None:
        """Valida que la fecha de vencimiento sea posterior a la fecha de apertura."""
        if value is not None and hasattr(self, "fecha_apertura") and self.fecha_apertura:
            if value < self.fecha_apertura:
                raise ValueError(
                    f"La fecha de vencimiento ({value}) no puede ser anterior "
                    f"a la fecha de apertura ({self.fecha_apertura})"
                )
        return value
