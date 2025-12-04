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
    INTEREST_EARNED = "interes_ganado"  # Intereses ganados en cuenta
    DEPOSIT = "deposito"  # Depósitos (salario, reembolsos, etc.)
    ADJUSTMENT = "ajuste"  # Ajustes bancarios
    INSURANCE = "seguro_tarjeta"  # Seguro de tarjeta
    MAINTENANCE_FEE = "comision_mantenimiento"  # Comisiones bancarias
    OTHER = "otro"

    def __str__(self) -> str:
        """Retorna el valor del enum como string."""
        return self.value


class TransactionStatus(str, Enum):
    """Estado del ciclo de vida de una transacción.
    
    Flujo típico:
    - PENDING: Recién importada desde email/PDF
    - CONFIRMED: Usuario verificó que es válida
    - RECONCILED: Verificada contra estado de cuenta mensual
    - CANCELLED: Marcada como inválida/error
    - ORPHAN: No encontrada en reconciliación (discrepancia)
    """

    PENDING = "pendiente"
    CONFIRMED = "confirmada"
    RECONCILED = "reconciliada"
    CANCELLED = "cancelada"
    ORPHAN = "huerfana"

    def __str__(self) -> str:
        """Retorna el valor del enum como string."""
        return self.value


class ReconciliationStatus(str, Enum):
    """Estado de un reporte de reconciliación.
    
    - PENDIENTE: Reconciliación iniciada pero no completada
    - EN_PROCESO: Reconciliación en progreso
    - CON_DISCREPANCIAS: Encontradas discrepancias que requieren revisión
    - COMPLETADO: Reconciliación finalizada y aprobada
    """

    PENDIENTE = "pendiente"
    EN_PROCESO = "en_proceso"
    CON_DISCREPANCIAS = "con_discrepancias"
    COMPLETADO = "completado"

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


class AccountType(str, Enum):
    """Tipos de cuentas bancarias."""

    CHECKING = "corriente"
    SAVINGS = "ahorro"
    PAYROLL = "planilla"

    def __str__(self) -> str:
        return self.value


class InvestmentType(str, Enum):
    """Tipos de inversiones."""

    CDP = "cdp"  # Certificado de Depósito a Plazo
    SAVINGS_ACCOUNT = "ahorro_plazo"  # Ahorro a plazo
    FUND = "fondo_inversion"  # Fondo de inversión
    STOCKS = "acciones"  # Acciones
    BONDS = "bonos"  # Bonos
    CRYPTO = "cripto"  # Criptomonedas
    OTHER = "otro"

    def __str__(self) -> str:
        return self.value


class InvestmentStatus(str, Enum):
    """Estados de una inversión."""

    ACTIVA = "activa"
    VENCIDA = "vencida"
    LIQUIDADA = "liquidada"

    def __str__(self) -> str:
        return self.value


class GoalStatus(str, Enum):
    """Estados de una meta financiera."""

    ACTIVA = "activa"
    COMPLETADA = "completada"
    PAUSADA = "pausada"
    CANCELADA = "cancelada"

    def __str__(self) -> str:
        return self.value


class GoalPriority(str, Enum):
    """Prioridad de una meta financiera."""

    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"

    def __str__(self) -> str:
        return self.value


class BillingCycleStatus(str, Enum):
    """Estados de un ciclo de facturación de tarjeta."""

    OPEN = "abierto"  # Ciclo actual, aceptando compras
    CLOSED = "cerrado"  # Cerrado, pendiente de pago
    PAID = "pagado"  # Pagado completamente
    PARTIAL = "parcial"  # Pago parcial realizado
    OVERDUE = "vencido"  # Pasó la fecha de pago sin pagar

    def __str__(self) -> str:
        return self.value


class CardPaymentType(str, Enum):
    """Tipos de pago a tarjeta de crédito."""

    FULL = "total"  # Pago total del saldo
    MINIMUM = "minimo"  # Pago mínimo
    PARTIAL = "parcial"  # Pago parcial (entre mínimo y total)
    EXTRA = "extra"  # Abono extra fuera de ciclo

    def __str__(self) -> str:
        return self.value
