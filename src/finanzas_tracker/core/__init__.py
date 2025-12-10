"""Módulo core con funcionalidades fundamentales del proyecto."""

from finanzas_tracker.core.cache import TTLCache, cached_query, invalidate_profile_cache
from finanzas_tracker.core.claude_credits import (
    CreditStatus,
    CreditState,
    CreditCheckResult,
    ClaudeServiceUnavailable,
    # Funciones principales
    get_credit_state,
    can_use_claude,
    check_claude_credits,
    handle_claude_error,
    with_claude_fallback,
    get_credit_status_summary,
    # Funciones de control
    mark_credits_exhausted,
    reset_credit_state,
    # Aliases
    invalidate_credit_cache,
    require_claude_credits,
)
from finanzas_tracker.core.constants import (
    AUTO_CATEGORIZE_CONFIDENCE_THRESHOLD,
    HIGH_CONFIDENCE_SCORE,
    KEYWORD_MIN_LENGTH_FOR_HIGH_CONFIDENCE,
    MEDIUM_CONFIDENCE_SCORE,
)
from finanzas_tracker.core.database import Base, get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.core.retry import retry_on_anthropic_error


__all__ = [
    # Cache
    "TTLCache",
    "cached_query",
    "invalidate_profile_cache",
    # Claude Credits
    "CreditStatus",
    "CreditState",
    "CreditCheckResult",
    "ClaudeServiceUnavailable",
    "get_credit_state",
    "can_use_claude",
    "check_claude_credits",
    "handle_claude_error",
    "with_claude_fallback",
    "get_credit_status_summary",
    "mark_credits_exhausted",
    "reset_credit_state",
    "invalidate_credit_cache",
    "require_claude_credits",
    # Constants
    "AUTO_CATEGORIZE_CONFIDENCE_THRESHOLD",
    "HIGH_CONFIDENCE_SCORE",
    "KEYWORD_MIN_LENGTH_FOR_HIGH_CONFIDENCE",
    "MEDIUM_CONFIDENCE_SCORE",
    # Database
    "Base",
    "get_session",
    # Logging
    "get_logger",
    # Retry
    "retry_on_anthropic_error",
]
