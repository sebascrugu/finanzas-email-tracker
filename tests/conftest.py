"""
Configuración de fixtures para pytest.

Este archivo contiene fixtures compartidos que pueden ser usados
en todos los tests del proyecto.
"""

import os
import sys
from unittest.mock import MagicMock


# Setup de variables de entorno ANTES de cualquier import
# Esto es necesario porque Pydantic Settings se carga al importar módulos
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("GMAIL_CREDENTIALS_FILE", "credentials.json")
os.environ.setdefault("GMAIL_TOKEN_FILE", "token.json")
os.environ.setdefault("AZURE_CLIENT_ID", "test-client-id")
os.environ.setdefault("AZURE_TENANT_ID", "test-tenant-id")
os.environ.setdefault("AZURE_CLIENT_SECRET", "test-secret")
os.environ.setdefault("USER_EMAIL", "test@example.com")
os.environ.setdefault("MOM_EMAIL", "mom@example.com")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test123")
os.environ.setdefault("ENVIRONMENT", "testing")

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from finanzas_tracker.core.database import Base


# Mock keyring ANTES de que cualquier módulo lo importe
keyring_mock = MagicMock()
keyring_mock.get_password.return_value = None
keyring_mock.set_password.return_value = None
sys.modules["keyring"] = keyring_mock


@pytest.fixture(scope="function")
def session(tmp_path, request):
    """
    Fixture de sesión de base de datos para tests.

    Crea una nueva base de datos SQLite temporal para cada test.
    """
    import uuid

    # Crear archivo temporal único para cada test
    test_id = str(uuid.uuid4())[:8]
    db_file = tmp_path / f"test_{test_id}.db"

    engine = create_engine(f"sqlite:///{db_file}")

    # Importar todos los modelos
    from finanzas_tracker.models import (  # noqa: F401
        Budget,
        Card,
        Category,
        Income,
        Profile,
        Subcategory,
        Subscription,
        Transaction,
    )

    # Crear todas las tablas
    Base.metadata.create_all(engine)

    session_local = sessionmaker(bind=engine)
    session = session_local()

    yield session

    session.close()
    engine.dispose()

    # Limpiar archivo de base de datos
    if db_file.exists():
        db_file.unlink()


@pytest.fixture
def sample_bac_email_html() -> str:
    """
    Fixture con HTML de ejemplo de un correo del BAC.

    Returns:
        str: HTML del correo de ejemplo
    """
    return """
    <html>
    <body>
        <p>Hola SEBASTIAN ERNESTO CRUZ GUZMAN</p>
        <p>A continuación le detallamos la transacción realizada:</p>
        <p>Comercio: DUNKIN TRES RIOS</p>
        <p>Ciudad y país: , Costa Rica</p>
        <p>Fecha: Nov 6, 2025, 10:32</p>
        <p>AMEX ***********6380</p>
        <p>Autorización: 937009</p>
        <p>Tipo de Transacción: COMPRA</p>
        <p>Monto: CRC 1,290.00</p>
    </body>
    </html>
    """


@pytest.fixture
def sample_banco_popular_email_text() -> str:
    """
    Fixture con texto de ejemplo de un correo del Banco Popular.

    Returns:
        str: Texto del correo de ejemplo
    """
    return """
    Estimado (a) cliente,

    El Banco Popular le informa de la transacción realizada en
    HOSPITAL METROPOLITANO PLSAN JOSE CR el 06/11/2025 a las 10:28,
    con la tarjeta VISA INTERNACIONAL A 6446, Auth # 566794,
    Ref # 531016110325, por 25,991.33 Colones
    """


@pytest.fixture
def mock_transaction_data() -> dict[str, str | float]:
    """
    Fixture con datos de ejemplo de una transacción.

    Returns:
        dict: Datos de transacción de ejemplo
    """
    return {
        "amount": 1290.00,
        "currency": "CRC",
        "merchant": "DUNKIN TRES RIOS",
        "date": "2025-11-06T10:32:00",
        "card_last_digits": "6380",
        "transaction_type": "COMPRA",
        "user_email": "test@example.com",
    }
