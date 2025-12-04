"""Modelos de base de datos - Finanzas Tracker CR."""

from finanzas_tracker.models.account import Account
from finanzas_tracker.models.base import (
    BaseModelMixin,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
)
from finanzas_tracker.models.billing_cycle import BillingCycle
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.card_payment import CardPayment
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.embedding import TransactionEmbedding
from finanzas_tracker.models.enums import (
    AccountType,
    BankName,
    BillingCycleStatus,
    CardPaymentType,
    CardType,
    CategoryType,
    Currency,
    GoalPriority,
    GoalStatus,
    IncomeType,
    InvestmentStatus,
    InvestmentType,
    RecurrenceFrequency,
    TransactionStatus,
    TransactionType,
)
from finanzas_tracker.models.exchange_rate_cache import ExchangeRateCache
from finanzas_tracker.models.goal import Goal
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.investment import Investment
from finanzas_tracker.models.merchant import Merchant, MerchantVariant
from finanzas_tracker.models.patrimonio_snapshot import PatrimonioSnapshot
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.reconciliation_report import ReconciliationReport
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.models.user import User


__all__ = [
    # Mixins
    "BaseModelMixin",
    "SoftDeleteMixin",
    "TenantMixin",
    "TimestampMixin",
    # Core Models
    "Account",
    "BillingCycle",
    "Budget",
    "Card",
    "CardPayment",
    "Category",
    "ExchangeRateCache",
    "Goal",
    "Income",
    "Investment",
    "Merchant",
    "MerchantVariant",
    "PatrimonioSnapshot",
    "Profile",
    "ReconciliationReport",
    "Subcategory",
    "Transaction",
    "TransactionEmbedding",
    "User",
    # Enums
    "AccountType",
    "BankName",
    "BillingCycleStatus",
    "CardPaymentType",
    "CardType",
    "CategoryType",
    "Currency",
    "GoalPriority",
    "GoalStatus",
    "IncomeType",
    "InvestmentStatus",
    "InvestmentType",
    "RecurrenceFrequency",
    "TransactionStatus",
    "TransactionType",
]
