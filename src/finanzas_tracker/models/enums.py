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


class AlertType(str, Enum):
    """Tipos de alertas del sistema."""

    # Fase 1 - MVP (Top 10 Critical Alerts)
    STATEMENT_UPLOAD_REMINDER = "statement_upload_reminder"  # #1: Recordatorio PDF mensual
    CREDIT_CARD_PAYMENT_DUE = "credit_card_payment_due"  # #2: Fecha pago tarjeta
    SPENDING_EXCEEDS_INCOME = "spending_exceeds_income"  # #3: Gastas más de lo que ganás
    BUDGET_80_PERCENT = "budget_80_percent"  # #4: 80% de presupuesto alcanzado
    BUDGET_100_PERCENT = "budget_100_percent"  # #5: 100% de presupuesto alcanzado
    SUBSCRIPTION_RENEWAL = "subscription_renewal"  # #6: Renovación suscripción
    DUPLICATE_TRANSACTION = "duplicate_transaction"  # #7: Transacción duplicada
    HIGH_INTEREST_PROJECTION = "high_interest_projection"  # #8: Intereses proyectados
    CARD_EXPIRATION = "card_expiration"  # #9: Vencimiento tarjeta física
    UNCATEGORIZED_TRANSACTIONS = "uncategorized_transactions"  # #10: Transacciones sin categorizar

    # Fase 2 - Smart Alerts (Negative/Preventive)
    OVERDRAFT_PROJECTION = "overdraft_projection"  # Sobregiro proyectado
    LOW_SAVINGS_WARNING = "low_savings_warning"  # Ahorro mínimo crítico
    UNKNOWN_MERCHANT_HIGH = "unknown_merchant_high"  # Cargo desconocido alto
    CREDIT_UTILIZATION_HIGH = "credit_utilization_high"  # Utilización crédito alta
    SPENDING_VELOCITY_HIGH = "spending_velocity_high"  # Velocidad de gasto anormal
    SEASONAL_SPENDING_WARNING = "seasonal_spending_warning"  # Patrón estacional
    GOAL_BEHIND_SCHEDULE = "goal_behind_schedule"  # Meta atrasada

    # Fase 2 - Positive Alerts (Gamification/Motivation) 🎉
    SPENDING_REDUCTION = "spending_reduction"  # Reducción significativa en categoría
    SAVINGS_MILESTONE = "savings_milestone"  # Milestone de ahorro alcanzado
    BUDGET_UNDER_TARGET = "budget_under_target"  # Gastó menos del presupuesto
    DEBT_PAYMENT_PROGRESS = "debt_payment_progress"  # Progreso pagando deudas
    STREAK_ACHIEVEMENT = "streak_achievement"  # X meses bajo presupuesto
    CATEGORY_IMPROVEMENT = "category_improvement"  # Mejora sostenida en categoría
    ZERO_EATING_OUT = "zero_eating_out"  # Periodo sin gastar en comer afuera
    EMERGENCY_FUND_MILESTONE = "emergency_fund_milestone"  # Fondo emergencia creciendo

    def __str__(self) -> str:
        """Retorna el valor del enum como string."""
        return self.value


class AlertPriority(str, Enum):
    """Prioridad de las alertas."""

    CRITICAL = "critical"  # 🔴 Requiere acción inmediata
    HIGH = "high"  # 🟠 Importante, actuar pronto
    MEDIUM = "medium"  # 🟡 Revisar cuando puedas
    LOW = "low"  # 🟢 Informativo

    def __str__(self) -> str:
        """Retorna el valor del enum como string."""
        return self.value


class AlertStatus(str, Enum):
    """Estados de una alerta."""

    PENDING = "pending"  # Pendiente de revisar
    READ = "read"  # Leída pero no resuelta
    RESOLVED = "resolved"  # Resuelta/Atendida
    DISMISSED = "dismissed"  # Descartada

    def __str__(self) -> str:
        """Retorna el valor del enum como string."""
        return self.value

