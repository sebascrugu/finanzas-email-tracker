"""Servicios de lógica de negocio."""

from finanzas_tracker.services.auth_manager import AuthManager, auth_manager
from finanzas_tracker.services.card_detection_service import (
    CardDetectionService,
    card_detection_service,
)
from finanzas_tracker.services.duplicate_detector import (
    DuplicateDetectorService,
    duplicate_detector_service,
)
from finanzas_tracker.services.email_fetcher import EmailFetcher
from finanzas_tracker.services.goal_service import GoalService, goal_service
from finanzas_tracker.services.monthly_report_service import (
    MonthlyReportService,
    monthly_report_service,
)
from finanzas_tracker.services.onboarding_service import OnboardingService, onboarding_service


__all__ = [
    "AuthManager",
    "auth_manager",
    "CardDetectionService",
    "card_detection_service",
    "DuplicateDetectorService",
    "duplicate_detector_service",
    "EmailFetcher",
    "GoalService",
    "goal_service",
    "MonthlyReportService",
    "monthly_report_service",
    "OnboardingService",
    "onboarding_service",
]
