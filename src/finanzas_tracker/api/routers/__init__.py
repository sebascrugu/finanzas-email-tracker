"""Routers FastAPI - Finanzas Tracker CR."""

from finanzas_tracker.api.routers import (
    ai,
    auth,
    budgets,
    cards,
    categories,
    notifications,
    onboarding,
    patrimony,
    profiles,
    reconciliation,
    statements,
    transactions,
)


__all__ = [
    "ai",
    "auth",
    "budgets",
    "cards",
    "categories",
    "notifications",
    "onboarding",
    "patrimony",
    "profiles",
    "reconciliation",
    "statements",
    "transactions",
]
