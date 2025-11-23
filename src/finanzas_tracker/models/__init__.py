"""Modelos de base de datos."""

from finanzas_tracker.models.account import Account, AccountType
from finanzas_tracker.models.alert import Alert, AlertConfig, AlertSeverity, AlertStatus, AlertType
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.credit_card import CreditCard
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
from finanzas_tracker.models.goal_milestone import GoalMilestone
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.income_split import IncomeSplit
from finanzas_tracker.models.merchant import Merchant, MerchantVariant
from finanzas_tracker.models.onboarding_progress import OnboardingProgress
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.savings_goal import SavingsGoal
from finanzas_tracker.models.subscription import Subscription
from finanzas_tracker.models.transaction import Transaction


__all__ = [
    # Models
    "Account",
    "Alert",
    "AlertConfig",
    "Budget",
    "Card",
    "Category",
    "CreditCard",
    "ExchangeRateCache",
    "GoalMilestone",
    "Income",
    "IncomeSplit",
    "Merchant",
    "MerchantVariant",
    "OnboardingProgress",
    "Profile",
    "SavingsGoal",
    "Subcategory",
    "Subscription",
    "Transaction",
    # Enums
    "AccountType",
    "AlertSeverity",
    "AlertStatus",
    "AlertType",
    "BankName",
    "CardType",
    "CategoryType",
    "Currency",
    "IncomeType",
    "RecurrenceFrequency",
    "TransactionType",
]
