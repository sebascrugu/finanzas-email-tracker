"""
Configuración centralizada de logging usando Loguru.

Este módulo configura el sistema de logging para toda la aplicación,
incluyendo rotación de archivos, niveles de log, y formato JSON en producción.
"""

import json
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any

from loguru import logger


if TYPE_CHECKING:
    from loguru import Logger

from finanzas_tracker.config.settings import settings


# Nombre del servicio para observability
SERVICE_NAME = "finanzas-tracker-api"


def json_serializer(record: dict[str, Any]) -> str:
    """
    Serializa un record de log a JSON para producción.

    Formato FAANG-style estructurado para parsing por ELK/Datadog/CloudWatch.
    """
    subset = {
        "ts": record["time"].strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "level": record["level"].name,
        "service": SERVICE_NAME,
        "msg": record["message"],
        "module": record["name"],
        "function": record["function"],
        "line": record["line"],
    }

    # Agregar extra fields (correlation_id, trace_id, etc.)
    if record.get("extra"):
        # Renombrar correlation_id a trace_id para estándar
        extra = record["extra"].copy()
        if "correlation_id" in extra:
            extra["trace_id"] = extra.pop("correlation_id")
        subset.update(extra)

    # Agregar exception si existe
    if record["exception"]:
        subset["error"] = {
            "type": record["exception"].type.__name__ if record["exception"].type else None,
            "message": str(record["exception"].value) if record["exception"].value else None,
        }

    return json.dumps(subset, default=str)


def json_sink(message: Any) -> None:
    """Sink que escribe JSON a stdout."""
    record = message.record
    print(json_serializer(record), flush=True)  # noqa: T201


def setup_logging() -> None:
    """
    Configura el sistema de logging de la aplicación.

    - Development: Formato colorizado legible
    - Production: JSON estructurado para observability
    - Archivos con rotación para auditoría
    """
    # Remover el handler por defecto
    logger.remove()

    # Crear directorio de logs si no existe
    logs_dir = Path(settings.logs_directory)
    logs_dir.mkdir(parents=True, exist_ok=True)

    # === LOGGING A CONSOLA ===
    if settings.is_development():
        # Formato colorizado para development
        console_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )
        logger.add(
            sys.stdout,
            format=console_format,
            level=settings.log_level,
            colorize=True,
            backtrace=True,
            diagnose=True,
        )
    else:
        # JSON estructurado para producción (ELK, Datadog, CloudWatch)
        logger.add(
            json_sink,
            level=settings.log_level,
            backtrace=False,
            diagnose=False,
        )

    # === LOGGING A ARCHIVO - LOGS GENERALES ===
    logger.add(
        logs_dir / "finanzas_tracker_{time:YYYY-MM-DD}.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{process} | "
            "{name}:{function}:{line} | "
            "{message}"
        ),
        level=settings.log_level,
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    # === LOGGING A ARCHIVO - SOLO ERRORES ===
    logger.add(
        logs_dir / "errors_{time:YYYY-MM-DD}.log",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{process} | "
            "{name}:{function}:{line} | "
            "{message}\n"
            "{exception}"
        ),
        level="ERROR",
        rotation=settings.log_rotation,
        retention=settings.log_retention,
        compression="zip",
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )

    # === LOGGING A ARCHIVO - TRANSACCIONES (para auditoría) ===
    logger.add(
        logs_dir / "transactions_{time:YYYY-MM-DD}.log",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {message}",
        level="INFO",
        rotation=settings.log_rotation,
        retention="6 months",  # Mantener logs de transacciones por más tiempo
        compression="zip",
        encoding="utf-8",
        filter=lambda record: "transaction" in record["extra"],
    )

    logger.info(
        f"Sistema de logging configurado - Nivel: {settings.log_level} - "
        f"Entorno: {settings.environment}"
    )


def get_logger(name: str) -> "Logger":
    """
    Obtiene un logger con el nombre especificado.

    Args:
        name: Nombre del logger (normalmente __name__ del módulo)

    Returns:
        Logger de loguru configurado

    Example:
        >>> from finanzas_tracker.core.logging import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Mensaje de log")
    """
    return logger.bind(name=name)


def log_transaction(
    transaction_type: str,
    amount: float,
    currency: str,
    user: str,
    details: str = "",
) -> None:
    """
    Registra una transacción en el log específico de transacciones.

    Args:
        transaction_type: Tipo de transacción (COMPRA, RETIRO, etc.)
        amount: Monto de la transacción
        currency: Moneda (CRC, USD, etc.)
        user: Usuario que realizó la transacción
        details: Detalles adicionales de la transacción

    Example:
        >>> log_transaction(
        ...     transaction_type="COMPRA",
        ...     amount=1290.00,
        ...     currency="CRC",
        ...     user="sebastian@example.com",
        ...     details="DUNKIN TRES RIOS",
        ... )
    """
    logger.bind(transaction=True).info(
        f"[{transaction_type}] {user} - {currency} {amount:,.2f} - {details}"
    )


# Configurar logging al importar el módulo
setup_logging()

# Exportar logger para uso directo
__all__ = ["logger", "get_logger", "log_transaction", "setup_logging"]
