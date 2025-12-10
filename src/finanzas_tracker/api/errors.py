"""
Manejo centralizado de errores para FastAPI.

Define excepciones personalizadas y handlers para formatear
respuestas de error de manera consistente.
"""

from typing import Any, cast

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.types import ExceptionHandler

from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)


# =============================================================================
# Excepciones Personalizadas
# =============================================================================


class AppException(Exception):
    """
    Excepción base de la aplicación.

    Todas las excepciones personalizadas heredan de esta clase.
    """

    def __init__(
        self,
        message: str,
        code: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppException):
    """Recurso no encontrado."""

    def __init__(
        self,
        resource: str,
        resource_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        message = f"{resource} no encontrado"
        if resource_id:
            message = f"{resource} con ID '{resource_id}' no encontrado"

        super().__init__(
            message=message,
            code=f"{resource.upper().replace(' ', '_')}_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ValidationError(AppException):
    """Error de validación de datos."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        code = "VALIDATION_ERROR"
        if field:
            code = f"INVALID_{field.upper()}"

        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class ConflictError(AppException):
    """Conflicto de datos (duplicado, etc)."""

    def __init__(
        self,
        message: str,
        code: str = "CONFLICT",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class UnauthorizedError(AppException):
    """No autorizado."""

    def __init__(
        self,
        message: str = "No autorizado",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class ForbiddenError(AppException):
    """Acceso prohibido."""

    def __init__(
        self,
        message: str = "Acceso prohibido",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class ExternalServiceError(AppException):
    """Error de servicio externo (AI, email, etc)."""

    def __init__(
        self,
        service: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=f"Error en servicio {service}: {message}",
            code=f"{service.upper()}_ERROR",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details=details,
        )


# =============================================================================
# Modelo de Respuesta de Error
# =============================================================================


class ErrorResponse(BaseModel):
    """Respuesta de error estandarizada."""

    error: str
    code: str
    details: dict[str, Any] = {}
    path: str | None = None
    timestamp: str | None = None


# =============================================================================
# Exception Handlers
# =============================================================================


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handler para excepciones de la aplicación."""
    from datetime import UTC, datetime

    logger.warning(
        f"AppException: {exc.code} - {exc.message}",
        extra={"path": request.url.path, "code": exc.code},
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=exc.message,
            code=exc.code,
            details=exc.details,
            path=request.url.path,
            timestamp=datetime.now(UTC).isoformat(),
        ).model_dump(),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handler para HTTPException estándar de FastAPI."""
    from datetime import UTC, datetime

    # Si detail es dict, extraer info
    if isinstance(exc.detail, dict):
        error = exc.detail.get("error", str(exc.detail))
        code = exc.detail.get("code", f"HTTP_{exc.status_code}")
        details: dict[str, str] = {
            k: str(v) for k, v in exc.detail.items() if k not in ("error", "code")
        }
    else:
        error = str(exc.detail)
        code = f"HTTP_{exc.status_code}"
        details = {}

    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            error=error,
            code=code,
            details=details,
            path=request.url.path,
            timestamp=datetime.now(UTC).isoformat(),
        ).model_dump(),
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handler para errores de validación de Pydantic."""
    from datetime import UTC, datetime

    errors = exc.errors()
    formatted_errors = []

    for error in errors:
        loc = ".".join(str(x) for x in error["loc"])
        formatted_errors.append(
            {
                "field": loc,
                "message": error["msg"],
                "type": error["type"],
            }
        )

    logger.warning(
        f"Validation error: {len(errors)} errors",
        extra={"path": request.url.path, "errors": formatted_errors},
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            error="Error de validación en los datos enviados",
            code="VALIDATION_ERROR",
            details={"errors": formatted_errors},
            path=request.url.path,
            timestamp=datetime.now(UTC).isoformat(),
        ).model_dump(),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Handler para excepciones no manejadas.

    En producción: NO expone detalles internos (seguridad).
    En desarrollo: Incluye tipo de error para debugging.
    """
    from datetime import UTC, datetime

    from finanzas_tracker.config.settings import settings

    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc}",
        extra={"path": request.url.path},
        exc_info=True,
    )

    # En producción NO exponemos detalles internos
    if settings.is_production():
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorResponse(
                error="Error interno del servidor",
                code="INTERNAL_ERROR",
                details={},  # Sin detalles en prod
                path=request.url.path,
                timestamp=datetime.now(UTC).isoformat(),
            ).model_dump(),
        )

    # En desarrollo incluimos más info para debugging
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error="Error interno del servidor",
            code="INTERNAL_ERROR",
            details={
                "type": type(exc).__name__,
                "message": str(exc),  # Solo en dev
            },
            path=request.url.path,
            timestamp=datetime.now(UTC).isoformat(),
        ).model_dump(),
    )


# =============================================================================
# Registrar Handlers
# =============================================================================


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Registra todos los exception handlers en la app FastAPI.

    Llamar en el startup de la aplicación.
    """
    # Cast necesario porque los handlers tienen tipos específicos de excepción
    # pero add_exception_handler espera Callable[[Request, Exception], ...]
    app.add_exception_handler(AppException, cast(ExceptionHandler, app_exception_handler))
    app.add_exception_handler(HTTPException, cast(ExceptionHandler, http_exception_handler))
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, validation_exception_handler)
    )
    app.add_exception_handler(Exception, cast(ExceptionHandler, unhandled_exception_handler))
