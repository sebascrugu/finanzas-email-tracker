"""Schemas Pydantic para API FastAPI."""

from finanzas_tracker.api.schemas.budget import (
    BudgetCreate,
    BudgetListResponse,
    BudgetResponse,
    BudgetSummaryResponse,
    BudgetUpdate,
)
from finanzas_tracker.api.schemas.category import (
    CategoryListResponse,
    CategoryResponse,
    SubcategoryResponse,
)
from finanzas_tracker.api.schemas.profile import (
    ProfileCreate,
    ProfileListResponse,
    ProfileResponse,
    ProfileUpdate,
)
from finanzas_tracker.api.schemas.reconciliation import (
    PatrimonioSnapshotCreate,
    PatrimonioSnapshotResponse,
    PatrimonioSnapshotUpdate,
    ReconciliationReportCreate,
    ReconciliationReportResponse,
    ReconciliationReportUpdate,
)
from finanzas_tracker.api.schemas.transaction import (
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)


__all__ = [
    # Transaction
    "TransactionCreate",
    "TransactionUpdate",
    "TransactionResponse",
    "TransactionListResponse",
    # Category
    "CategoryResponse",
    "CategoryListResponse",
    "SubcategoryResponse",
    # Budget
    "BudgetCreate",
    "BudgetUpdate",
    "BudgetResponse",
    "BudgetListResponse",
    "BudgetSummaryResponse",
    # Profile
    "ProfileCreate",
    "ProfileUpdate",
    "ProfileResponse",
    "ProfileListResponse",
    # Reconciliation & Patrimonio
    "ReconciliationReportCreate",
    "ReconciliationReportUpdate",
    "ReconciliationReportResponse",
    "PatrimonioSnapshotCreate",
    "PatrimonioSnapshotUpdate",
    "PatrimonioSnapshotResponse",
]
