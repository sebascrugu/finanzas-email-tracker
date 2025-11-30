"""
Enums centralizados para el sistema de finanzas.

Este módulo define todos los enums usados en los modelos para garantizar
consistencia y type-safety a nivel de base de datos y aplicación.
"""

from enum import Enum


class CardType(str, Enum):
    """Tipos de tarjetas bancarias."""

    DEBIT = "debito"
    CREDIT = "credito"

    def __str__(self) -> str:
        """Retorna el valor del enum como string."""
        return self.value


class BankName(str, Enum):
    """Bancos soportados en Costa Rica."""

    BAC = "bac"
    POPULAR = "popular"

    def __str__(self) -> str:
        """Retorna el valor del enum como string."""
        return self.value


class Currency(str, Enum):
    """Monedas soportadas."""

    CRC = "CRC"  # Colones costarricenses
    USD = "USD"  # Dólares estadounidenses

    def __str__(self) -> str:
        """Retorna el valor del enum como string."""
        return self.value


class TransactionType(str, Enum):
    """Tipos de transacciones bancarias."""

    PURCHASE = "compra"
    TRANSFER = "transferencia"
    WITHDRAWAL = "retiro"
    SERVICE_PAYMENT = "pago_servicio"
    SINPE = "sinpe"
    WITHDRAWAL_NO_CARD = "retiro_sin_tarjeta"
    COMPASS = "compass"  # BAC Compass (peajes/parking)
    INTEREST_CHARGE = "interes_cobrado"  # Intereses de tarjeta de crédito
    ADJUSTMENT = "ajuste"  # Ajustes bancarios
    INSURANCE = "seguro_tarjeta"  # Seguro de tarjeta
    MAINTENANCE_FEE = "comision_mantenimiento"  # Comisiones bancarias
    OTHER = "otro"

    def __str__(self) -> str:
        """Retorna el valor del enum como string."""
        return self.value


class IncomeType(str, Enum):
    """Tipos de ingresos."""

    SALARY = "salario"
    PENSION = "pension"
    FREELANCE = "freelance"
    BUSINESS = "negocio"
    INVESTMENT = "inversion"
    INVESTMENT_RETURN = "rendimiento_inversion"
    SALE = "venta"
    GIFT = "regalo"
    REFUND = "devolucion"
    LOAN_RECEIVED = "prestamo_recibido"
    OTHER = "otro"

    def __str__(self) -> str:
        """Retorna el valor del enum como string."""
        return self.value


class CategoryType(str, Enum):
    """Tipos de categorías principales (regla 50/30/20)."""

    NECESSITIES = "necesidades"  # 50%
    WANTS = "gustos"  # 30%
    SAVINGS = "ahorros"  # 20%

    def __str__(self) -> str:
        """Retorna el valor del enum como string."""
        return self.value


class RecurrenceFrequency(str, Enum):
    """Frecuencia de recurrencia para gastos/ingresos."""

    DAILY = "diario"
    WEEKLY = "semanal"
    BIWEEKLY = "quincenal"
    MONTHLY = "mensual"
    QUARTERLY = "trimestral"
    YEARLY = "anual"

    def __str__(self) -> str:
        """Retorna el valor del enum como string."""
        return self.value
