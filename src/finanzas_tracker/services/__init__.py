"""Servicios de lógica de negocio - Finanzas Tracker CR."""

from finanzas_tracker.services.ambiguous_merchant_service import (
    AmbiguousMerchantService,
    listar_comercios_ambiguos,
)
from finanzas_tracker.services.auth_manager import AuthManager, auth_manager
from finanzas_tracker.services.categorizer import TransactionCategorizer
from finanzas_tracker.services.duplicate_detector import (
    DuplicateDetectorService,
    duplicate_detector_service,
)
from finanzas_tracker.services.email_fetcher import EmailFetcher
from finanzas_tracker.services.exchange_rate import ExchangeRateService, exchange_rate_service
from finanzas_tracker.services.finance_chat import FinanceChatService
from finanzas_tracker.services.insights import InsightsService
from finanzas_tracker.services.merchant_service import MerchantNormalizationService
from finanzas_tracker.services.transaction_processor import TransactionProcessor


__all__ = [
    "AmbiguousMerchantService",
    "AuthManager",
    "auth_manager",
    "DuplicateDetectorService",
    "duplicate_detector_service",
    "EmailFetcher",
    "ExchangeRateService",
    "exchange_rate_service",
    "FinanceChatService",
    "InsightsService",
    "listar_comercios_ambiguos",
    "MerchantNormalizationService",
    "TransactionCategorizer",
    "TransactionProcessor",
]
