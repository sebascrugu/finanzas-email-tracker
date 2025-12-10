"""
Configuración de SQLAlchemy y manejo de sesiones de base de datos.

Este módulo configura la conexión a PostgreSQL con pgvector
y proporciona utilidades para trabajar con la base de datos.

Requiere PostgreSQL 16+ con extensión pgvector instalada.
"""

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)

# Base para modelos SQLAlchemy
Base = declarative_base()


def _create_engine(database_url: str | None = None) -> Engine:
    """
    Crea el engine de SQLAlchemy para PostgreSQL.

    Args:
        database_url: URL de conexión opcional (para testing con Testcontainers)

    Returns:
        Engine de SQLAlchemy configurado para PostgreSQL
    """
    url = database_url or settings.get_database_url()

    logger.info("🐘 Conectando a PostgreSQL...")
    return create_engine(
        url,
        echo=settings.is_development(),
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
    )


# Engine de SQLAlchemy
engine = _create_engine()

# SessionLocal para crear sesiones de base de datos
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, Any, None]:
    """
    Generador de sesiones de base de datos.

    Yields:
        Session: Sesión de SQLAlchemy

    Example:
        >>> from finanzas_tracker.core.database import get_db
        >>> with get_db() as db:
        ...     # Usar db aquí
        ...     pass
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_session() -> Generator[Session, None, None]:
    """
    Context manager para obtener una sesión de base de datos.

    Yields:
        Session: Sesión de SQLAlchemy

    Example:
        >>> from finanzas_tracker.core.database import get_session
        >>> with get_session() as session:
        ...     transaction = Transaction(...)
        ...     session.add(transaction)
        ...     session.commit()
    """
    session = SessionLocal()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """
    Inicializa la base de datos creando todas las tablas.

    Esta función debe ser llamada al inicio de la aplicación
    o durante la configuración inicial.
    """
    logger.info("Inicializando base de datos...")

    # Importar todos los modelos aquí para que SQLAlchemy los registre

    Base.metadata.create_all(bind=engine)
    logger.success("Base de datos inicializada correctamente")


def drop_db() -> None:
    """
    Elimina todas las tablas de la base de datos.

     PRECAUCIÓN: Esta función borra TODOS los datos.
    Solo debe usarse en desarrollo o testing.
    """
    if settings.is_production():
        logger.error("No se puede ejecutar drop_db en producción")
        raise RuntimeError("No se puede eliminar la base de datos en producción")

    logger.warning("Eliminando todas las tablas de la base de datos...")
    Base.metadata.drop_all(bind=engine)
    logger.success("Base de datos eliminada")


__all__ = ["Base", "engine", "SessionLocal", "get_db", "get_session", "init_db", "drop_db"]
