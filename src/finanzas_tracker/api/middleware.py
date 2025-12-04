"""
Middlewares de API - Logging, Correlation IDs, Timing.

Implementación FAANG-style con:
- Correlation ID para trazabilidad
- Request/Response logging estructurado
- Timing de requests
"""

from collections.abc import Callable
from contextvars import ContextVar
import time
from typing import Any
import uuid

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


# Context variable para correlation ID (thread-safe)
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Obtiene el correlation ID del contexto actual."""
    return correlation_id_var.get()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware que genera/propaga Correlation IDs.

    - Si viene X-Correlation-ID en header, lo usa
    - Si no, genera uno nuevo
    - Lo agrega al response header
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Response:
        # Obtener o generar correlation ID
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            str(uuid.uuid4())[:8],  # Short UUID para legibilidad
        )

        # Guardar en context var
        correlation_id_var.set(correlation_id)

        # Bind al logger de loguru para este contexto
        with logger.contextualize(correlation_id=correlation_id):
            response = await call_next(request)

        # Agregar al response
        response.headers["X-Correlation-ID"] = correlation_id
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware de logging estructurado para requests HTTP.

    Loggea:
    - Request: method, path, client IP
    - Response: status code, duration
    - Excluye paths de health check
    """

    EXCLUDE_PATHS = {"/", "/health", "/ready", "/metrics", "/docs", "/openapi.json"}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Response:
        # Excluir paths que no queremos loggear
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)

        # Extraer info del request
        method = request.method
        path = request.url.path
        query = str(request.query_params) if request.query_params else ""
        client_ip = request.client.host if request.client else "unknown"
        correlation_id = get_correlation_id()

        # Timing
        start_time = time.perf_counter()

        # Log request
        logger.info(
            "Request started",
            extra={
                "event": "request_start",
                "method": method,
                "path": path,
                "query": query,
                "client_ip": client_ip,
                "correlation_id": correlation_id,
            },
        )

        # Procesar request
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log response
            log_level = "info" if response.status_code < 400 else "warning"
            getattr(logger, log_level)(
                f"{method} {path} - {response.status_code} ({duration_ms:.2f}ms)",
                extra={
                    "event": "request_complete",
                    "method": method,
                    "path": path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                    "correlation_id": correlation_id,
                },
            )

            return response

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"{method} {path} - ERROR ({duration_ms:.2f}ms): {e!s}",
                extra={
                    "event": "request_error",
                    "method": method,
                    "path": path,
                    "duration_ms": round(duration_ms, 2),
                    "error": str(e),
                    "correlation_id": correlation_id,
                },
            )
            raise


def setup_middlewares(app: Any) -> None:
    """
    Configura todos los middlewares en el orden correcto.

    El orden importa:
    1. CorrelationIdMiddleware (primero para que esté disponible)
    2. RequestLoggingMiddleware (usa el correlation ID)
    """
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(CorrelationIdMiddleware)
