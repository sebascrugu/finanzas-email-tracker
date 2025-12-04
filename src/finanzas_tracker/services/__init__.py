"""Servicios de lógica de negocio - Finanzas Tracker CR."""

from finanzas_tracker.services.ambiguous_merchant_service import (
    AmbiguousMerchantService,
    listar_comercios_ambiguos,
)
from finanzas_tracker.services.auth_manager import AuthManager, auth_manager
from finanzas_tracker.services.card_service import CardService
from finanzas_tracker.services.categorizer import TransactionCategorizer
from finanzas_tracker.services.duplicate_detector import (
    DuplicateDetectorService,
    duplicate_detector_service,
)
from finanzas_tracker.services.email_fetcher import EmailFetcher
from finanzas_tracker.services.exchange_rate import ExchangeRateService, exchange_rate_service
from finanzas_tracker.services.finance_chat import FinanceChatService
from finanzas_tracker.services.insights import InsightsService
from finanzas_tracker.services.internal_transfer_detector import InternalTransferDetector
from finanzas_tracker.services.merchant_service import MerchantNormalizationService
from finanzas_tracker.services.notification_service import CardNotificationService
from finanzas_tracker.services.onboarding_service import OnboardingService
from finanzas_tracker.services.patrimony_service import PatrimonyService
from finanzas_tracker.services.reconciliation_service import ReconciliationService
from finanzas_tracker.services.statement_email_service import (
    StatementEmailService,
    statement_email_service,
)
from finanzas_tracker.services.sync_scheduler import (
    scheduler,
    start_background_tasks,
    stop_background_tasks,
)
from finanzas_tracker.services.transaction_processor import TransactionProcessor
from finanzas_tracker.services.transaction_service import TransactionService


__all__ = [
    "AmbiguousMerchantService",
    "AuthManager",
    "auth_manager",
    "CardNotificationService",
    "CardService",
    "DuplicateDetectorService",
    "duplicate_detector_service",
    "EmailFetcher",
    "ExchangeRateService",
    "exchange_rate_service",
    "FinanceChatService",
    "InsightsService",
    "InternalTransferDetector",
    "listar_comercios_ambiguos",
    "MerchantNormalizationService",
    "OnboardingService",
    "PatrimonyService",
    "ReconciliationService",
    "scheduler",
    "start_background_tasks",
    "StatementEmailService",
    "statement_email_service",
    "stop_background_tasks",
    "TransactionCategorizer",
    "TransactionProcessor",
    "TransactionService",
]
