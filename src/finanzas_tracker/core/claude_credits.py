"""
Sistema de verificación de créditos de Claude API - Enfoque Reactivo.

Este módulo proporciona utilidades para:
- Detectar errores de créditos agotados cuando ocurren (NO proactivamente)
- Cachear el estado de "sin créditos" para evitar llamadas innecesarias
- Proporcionar fallbacks graceful cuando no hay créditos

IMPORTANTE: Este sistema NO hace llamadas proactivas a la API para verificar
créditos (eso también costaría dinero). En su lugar:
1. Asume que hay créditos hasta que falle una llamada
2. Cuando detecta error de créditos, cachea el estado
3. Futuras llamadas verifican el cache antes de intentar

Autor: Sebastian Cruz
Versión: 2.0.0
"""

import time
from dataclasses import dataclass
from enum import StrEnum
from functools import wraps
from typing import Any, Callable, TypeVar

import anthropic

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)

# Type var para preservar tipos en decorador
F = TypeVar("F", bound=Callable[..., Any])


class CreditStatus(StrEnum):
    """Estado de los créditos de Claude API."""

    AVAILABLE = "available"  # Créditos disponibles (o no verificado aún)
    EXHAUSTED = "exhausted"  # Créditos agotados confirmado
    ERROR = "error"  # Error de configuración (API key inválida, etc.)


@dataclass
class CreditState:
    """Estado actual de los créditos de Claude API."""

    status: CreditStatus
    message: str
    error_at: float = 0.0  # Timestamp cuando se detectó el error

    def __post_init__(self) -> None:
        """Establecer timestamp si no se proporcionó."""
        if self.error_at == 0.0 and self.status != CreditStatus.AVAILABLE:
            self.error_at = time.time()

    @property
    def is_available(self) -> bool:
        """Retorna True si se puede intentar usar Claude."""
        return self.status == CreditStatus.AVAILABLE

    @property
    def should_retry(self) -> bool:
        """Retorna True si ha pasado suficiente tiempo para reintentar."""
        if self.status == CreditStatus.AVAILABLE:
            return True
        # Reintentar después de 1 hora si los créditos estaban agotados
        # (el usuario puede haber agregado más)
        elapsed = time.time() - self.error_at
        return elapsed > 3600  # 1 hora


# Alias para compatibilidad
CreditCheckResult = CreditState


# Estado global - empieza asumiendo que hay créditos
_credit_state: CreditState = CreditState(
    status=CreditStatus.AVAILABLE,
    message="No verificado - asumiendo disponible",
)


def get_credit_state() -> CreditState:
    """
    Obtiene el estado actual de los créditos.

    NO hace llamadas a la API. Solo retorna el estado conocido.

    Returns:
        CreditState actual
    """
    global _credit_state
    return _credit_state


def mark_credits_exhausted(error_message: str) -> None:
    """
    Marca los créditos como agotados.

    Llamar esta función cuando se detecta un error de créditos
    durante una llamada a la API.

    Args:
        error_message: Mensaje de error para logging
    """
    global _credit_state
    _credit_state = CreditState(
        status=CreditStatus.EXHAUSTED,
        message=error_message,
        error_at=time.time(),
    )
    logger.warning(f"⚠️ Claude API: Créditos marcados como agotados - {error_message}")


def mark_credits_error(error_message: str) -> None:
    """
    Marca un error de configuración (API key inválida, etc.).

    Args:
        error_message: Mensaje de error
    """
    global _credit_state
    _credit_state = CreditState(
        status=CreditStatus.ERROR,
        message=error_message,
        error_at=time.time(),
    )
    logger.error(f"❌ Claude API: Error de configuración - {error_message}")


def reset_credit_state() -> None:
    """
    Resetea el estado de créditos a "disponible".

    Útil cuando el usuario indica que agregó más créditos
    o después de un tiempo prudencial.
    """
    global _credit_state
    _credit_state = CreditState(
        status=CreditStatus.AVAILABLE,
        message="Reseteado manualmente",
    )
    logger.info("✅ Estado de créditos reseteado a disponible")


def can_use_claude() -> tuple[bool, str]:
    """
    Verifica si se puede intentar usar Claude.

    NO hace llamadas a la API. Verifica:
    1. Si hay API key configurada
    2. Si el estado cached indica que hay créditos o si debemos reintentar

    Returns:
        Tuple de (puede_usar, mensaje_si_no)
    """
    # Verificar API key
    if not settings.anthropic_api_key:
        return False, "API key de Claude no configurada"

    # Verificar estado cached
    state = get_credit_state()

    if state.is_available:
        return True, ""

    if state.should_retry:
        # Ha pasado suficiente tiempo, reintentar
        reset_credit_state()
        return True, ""

    return False, state.message


def check_claude_credits(force_refresh: bool = False) -> CreditState:
    """
    Verifica el estado de créditos de Claude.

    NOTA: Esta versión NO hace llamadas a la API (enfoque reactivo).
    Solo retorna el estado conocido del cache.

    Args:
        force_refresh: Si True, resetea el estado (permite reintentar)

    Returns:
        CreditState con el estado actual
    """
    if force_refresh:
        reset_credit_state()

    can_use, reason = can_use_claude()

    if can_use:
        return CreditState(
            status=CreditStatus.AVAILABLE,
            message="Disponible para usar",
        )
    else:
        return get_credit_state()


def handle_claude_error(error: Exception) -> bool:
    """
    Maneja un error de Claude API y actualiza el estado de créditos.

    Args:
        error: Excepción capturada de la llamada a Claude

    Returns:
        True si el error fue manejado (créditos agotados), False si debe re-raise
    """
    error_str = str(error).lower()

    # Errores de créditos/billing
    if isinstance(error, anthropic.APIStatusError):
        if error.status_code == 402 or "credit" in error_str or "billing" in error_str:
            mark_credits_exhausted(f"Error {error.status_code}: {error}")
            return True

    # Error de autenticación
    if isinstance(error, anthropic.AuthenticationError):
        mark_credits_error(f"API key inválida: {error}")
        return True

    # Error de permisos
    if isinstance(error, anthropic.PermissionDeniedError):
        # Puede ser créditos o permisos
        if "credit" in error_str or "billing" in error_str:
            mark_credits_exhausted(str(error))
        else:
            mark_credits_error(f"Sin permisos: {error}")
        return True

    # Otros errores no son de créditos
    return False


def with_claude_fallback(
    fallback_value: Any = None,
    fallback_message: str = "Servicio de IA no disponible",
) -> Callable[[F], F]:
    """
    Decorador que maneja errores de créditos y proporciona fallback.

    A diferencia del enfoque anterior, este decorador:
    1. NO verifica créditos proactivamente (no gasta dinero)
    2. Verifica el cache de estado antes de ejecutar
    3. Captura errores de créditos y actualiza el cache
    4. Retorna fallback_value si no hay créditos

    Args:
        fallback_value: Valor a retornar si Claude no está disponible
        fallback_message: Mensaje para logging

    Returns:
        Decorador configurado

    Example:
        >>> @with_claude_fallback(fallback_value=None)
        ... def categorize_with_ai(description: str) -> str | None:
        ...     client = anthropic.Anthropic()
        ...     return client.messages.create(...)
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Verificar si podemos usar Claude (sin llamar a la API)
            can_use, reason = can_use_claude()

            if not can_use:
                logger.info(
                    f"⏭️ Saltando {func.__name__}: {fallback_message} ({reason})"
                )
                return fallback_value

            try:
                return func(*args, **kwargs)

            except anthropic.APIStatusError as e:
                # Manejar error y verificar si es de créditos
                if handle_claude_error(e):
                    logger.info(
                        f"⏭️ {func.__name__} falló por créditos, usando fallback"
                    )
                    return fallback_value
                # No es error de créditos, re-raise
                raise

            except anthropic.AuthenticationError as e:
                handle_claude_error(e)
                logger.info(f"⏭️ {func.__name__} falló por auth, usando fallback")
                return fallback_value

            except anthropic.PermissionDeniedError as e:
                handle_claude_error(e)
                logger.info(f"⏭️ {func.__name__} falló por permisos, usando fallback")
                return fallback_value

            except anthropic.APIConnectionError as e:
                # Error de conexión - temporal, no actualizar estado
                logger.warning(f"⚠️ {func.__name__}: Error de conexión - {e}")
                return fallback_value

            except anthropic.RateLimitError as e:
                # Rate limit - temporal, no actualizar estado de créditos
                logger.warning(f"⚠️ {func.__name__}: Rate limit - {e}")
                return fallback_value

        return wrapper  # type: ignore

    return decorator


class ClaudeServiceUnavailable(Exception):
    """
    Excepción para cuando Claude no está disponible.

    Usada para señalar que el servicio de IA no está disponible
    pero la aplicación debe continuar funcionando.
    """

    def __init__(self, message: str = "Servicio de IA no disponible") -> None:
        self.message = message
        super().__init__(message)


def get_credit_status_summary() -> dict[str, Any]:
    """
    Obtiene un resumen del estado de créditos para mostrar en UI.

    NO hace llamadas a la API - solo retorna el estado conocido.

    Returns:
        Dict con información del estado
    """
    state = get_credit_state()
    can_use, reason = can_use_claude()

    return {
        "status": state.status.value,
        "message": state.message,
        "can_use_claude": can_use,
        "reason_if_not": reason,
        "error_at": state.error_at if state.error_at > 0 else None,
        "will_retry_at": (
            state.error_at + 3600 if state.error_at > 0 else None
        ),
    }


# Alias para compatibilidad con código existente
invalidate_credit_cache = reset_credit_state


def require_claude_credits(
    fallback_value: Any = None,
    fallback_message: str = "Servicio de IA no disponible temporalmente",
) -> Callable[[F], F]:
    """Alias para with_claude_fallback para compatibilidad."""
    return with_claude_fallback(fallback_value, fallback_message)


__all__ = [
    # Clases
    "CreditStatus",
    "CreditState",
    "CreditCheckResult",
    "ClaudeServiceUnavailable",
    # Funciones principales
    "get_credit_state",
    "can_use_claude",
    "check_claude_credits",
    "handle_claude_error",
    "with_claude_fallback",
    "get_credit_status_summary",
    # Funciones de control
    "mark_credits_exhausted",
    "mark_credits_error",
    "reset_credit_state",
    # Aliases para compatibilidad
    "invalidate_credit_cache",
    "require_claude_credits",
]
