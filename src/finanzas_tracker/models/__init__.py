"""Modelos de base de datos - Finanzas Tracker CR."""

from finanzas_tracker.models.base import (
    BaseModelMixin,
    SoftDeleteMixin,
    TenantMixin,
    TimestampMixin,
)
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.embedding import TransactionEmbedding
from finanzas_tracker.models.enums import (
    BankName,
    CardType,
    CategoryType,
    Currency,
    IncomeType,
    RecurrenceFrequency,
    TransactionType,
)
from finanzas_tracker.models.exchange_rate_cache import ExchangeRateCache
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.merchant import Merchant, MerchantVariant
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction


__all__ = [
    # Mixins
    "BaseModelMixin",
    "SoftDeleteMixin",
    "TenantMixin",
    "TimestampMixin",
    # Core Models
    "Budget",
    "Card",
    "Category",
    "ExchangeRateCache",
    "Income",
    "Merchant",
    "MerchantVariant",
    "Profile",
    "Subcategory",
    "Transaction",
    "TransactionEmbedding",
    # Enums
    "BankName",
    "CardType",
    "CategoryType",
    "Currency",
    "IncomeType",
    "RecurrenceFrequency",
    "TransactionType",
]
