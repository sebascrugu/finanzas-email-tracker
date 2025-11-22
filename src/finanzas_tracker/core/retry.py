"""Configuración de retry logic para llamadas a APIs externas.

Este módulo proporciona decoradores y estrategias de retry para:
- Microsoft Graph API
- Claude API (Anthropic)
- Exchange Rate APIs

Usa tenacity para implementar exponential backoff con jitter.
"""

from typing import Any, Callable

import anthropic
import requests
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)


def _log_retry_attempt(retry_state: RetryCallState) -> None:
    """
    Callback para loggear intentos de retry.

    Args:
        retry_state: Estado del retry de tenacity
    """
    if retry_state.attempt_number > 1:
        exception = retry_state.outcome.exception() if retry_state.outcome else None
        logger.warning(
            f"⚠️  Reintento {retry_state.attempt_number} después de error: "
            f"{type(exception).__name__}: {exception}"
        )


def retry_on_network_error(max_attempts: int = 3, max_wait: int = 10) -> Callable[..., Any]:
    """
    Decorador para reintentar en errores de red.

    Usado para:
    - Requests a Microsoft Graph API
    - Requests a Exchange Rate APIs

    Args:
        max_attempts: Número máximo de intentos (default: 3)
        max_wait: Tiempo máximo de espera en segundos (default: 10)

    Returns:
        Decorador de tenacity configurado

    Example:
        >>> @retry_on_network_error(max_attempts=3)
        ... def fetch_data():
        ...     response = requests.get(url)
        ...     return response.json()
    """
    return retry(
        # Reintentar en errores de red transitorios
        retry=retry_if_exception_type(
            (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError,
            )
        ),
        # Máximo 3 intentos
        stop=stop_after_attempt(max_attempts),
        # Exponential backoff: 1s, 2s, 4s, 8s (con jitter)
        wait=wait_exponential(multiplier=1, min=1, max=max_wait),
        # Log de reintentos
        after=_log_retry_attempt,
        # Re-raise la excepción después del último intento
        reraise=True,
    )


def retry_on_anthropic_error(max_attempts: int = 3, max_wait: int = 16) -> Callable[..., Any]:
    """
    Decorador para reintentar en errores de Anthropic API.

    Usado para:
    - Categorización de transacciones con Claude
    - Chat financiero con Claude

    Reintenta en:
    - APIConnectionError (errores de red/conexión)
    - APITimeoutError (timeouts)
    - InternalServerError (errores 500 del servidor)
    - RateLimitError (429 - rate limiting) con backoff más largo

    NO reintenta en:
    - BadRequestError (400 - error de cliente)
    - AuthenticationError (401 - credenciales inválidas)
    - PermissionDeniedError (403 - sin permisos)
    - NotFoundError (404 - recurso no encontrado)

    Args:
        max_attempts: Número máximo de intentos (default: 3)
        max_wait: Tiempo máximo de espera en segundos (default: 16)

    Returns:
        Decorador de tenacity configurado

    Example:
        >>> @retry_on_anthropic_error(max_attempts=3)
        ... def categorize_transaction():
        ...     response = client.messages.create(...)
        ...     return response
    """
    return retry(
        # Reintentar solo en errores transitorios
        retry=retry_if_exception_type(
            (
                anthropic.APIConnectionError,
                anthropic.APITimeoutError,
                anthropic.InternalServerError,
                anthropic.RateLimitError,
            )
        ),
        # Máximo 3 intentos
        stop=stop_after_attempt(max_attempts),
        # Exponential backoff: 2s, 4s, 8s, 16s (con jitter)
        # Más largo que network errors porque rate limits necesitan más tiempo
        wait=wait_exponential(multiplier=2, min=2, max=max_wait),
        # Log de reintentos
        after=_log_retry_attempt,
        # Re-raise la excepción después del último intento
        reraise=True,
    )


__all__ = ["retry_on_network_error", "retry_on_anthropic_error"]
