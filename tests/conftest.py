"""
Configuración de fixtures para pytest.

Este archivo contiene fixtures compartidos que pueden ser usados
en todos los tests del proyecto.

Estrategia de Testing:
- Todos los tests usan PostgreSQL real via Testcontainers
- Cada sesión de tests obtiene un container PostgreSQL limpio
- Las tablas se crean una vez por sesión y se limpian entre tests

Nota: Si Docker no está disponible o Testcontainers falla, se usa
el container PostgreSQL local existente (finanzas_postgres).
"""

import logging
import os
import sys
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configurar logging
logging.getLogger("testcontainers").setLevel(logging.WARNING)

# Setup de variables de entorno ANTES de cualquier import de la app
os.environ.setdefault("GMAIL_CREDENTIALS_FILE", "credentials.json")
os.environ.setdefault("GMAIL_TOKEN_FILE", "token.json")
os.environ.setdefault("AZURE_CLIENT_ID", "test-client-id")
os.environ.setdefault("AZURE_TENANT_ID", "test-tenant-id")
os.environ.setdefault("AZURE_CLIENT_SECRET", "test-secret")
os.environ.setdefault("USER_EMAIL", "test@example.com")
os.environ.setdefault("MOM_EMAIL", "mom@example.com")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test123")
os.environ.setdefault("ENVIRONMENT", "testing")

# Mock keyring ANTES de que cualquier módulo lo importe
keyring_mock = MagicMock()
keyring_mock.get_password.return_value = None
keyring_mock.set_password.return_value = None
sys.modules["keyring"] = keyring_mock


# Engine de tests compartido
_test_engine = None


def get_test_database_url() -> str:
    """
    Obtiene la URL de la base de datos para tests.
    
    Usa el container PostgreSQL local (finanzas_postgres).
    Para CI/CD, se puede configurar con TEST_DATABASE_URL.
    """
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://finanzas:finanzas_dev_2024@localhost:5432/finanzas_test"
    )


def get_test_engine():
    """Obtiene o crea el engine de tests."""
    global _test_engine
    if _test_engine is None:
        connection_url = get_test_database_url()
        _test_engine = create_engine(connection_url, echo=False)
        
        # Crear extensión pgvector si no existe
        with _test_engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
    return _test_engine


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Fixture que configura la base de datos para toda la sesión de tests.
    
    Se ejecuta automáticamente al inicio de la sesión de tests.
    Crea todas las tablas necesarias.
    """
    engine = get_test_engine()
    
    # Importar todos los modelos para registrarlos con Base.metadata
    from finanzas_tracker.core.database import Base
    from finanzas_tracker.models import (  # noqa: F401
        Budget,
        Card,
        Category,
        Income,
        Profile,
        Subcategory,
        Transaction,
    )
    from finanzas_tracker.models.embedding import TransactionEmbedding  # noqa: F401
    from finanzas_tracker.models.merchant import Merchant, MerchantVariant  # noqa: F401
    from finanzas_tracker.models.exchange_rate_cache import ExchangeRateCache  # noqa: F401
    from finanzas_tracker.models.patrimonio_snapshot import PatrimonioSnapshot  # noqa: F401
    from finanzas_tracker.models.reconciliation_report import ReconciliationReport  # noqa: F401
    from finanzas_tracker.models.account import Account  # noqa: F401
    from finanzas_tracker.models.investment import Investment  # noqa: F401
    from finanzas_tracker.models.goal import Goal  # noqa: F401
    from finanzas_tracker.models.billing_cycle import BillingCycle  # noqa: F401
    
    # Drop y crear todas las tablas (limpia cualquier estado previo)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Cleanup al final de la sesión - drop all tables
    Base.metadata.drop_all(engine)
    
    global _test_engine
    if _test_engine:
        _test_engine.dispose()
        _test_engine = None


@pytest.fixture(scope="function")
def session(setup_test_database):
    """
    Fixture de sesión de base de datos para tests.
    
    Usa PostgreSQL real.
    Cada test obtiene una sesión limpia con rollback automático.
    """
    engine = setup_test_database
    
    # Crear conexión con transacción
    connection = engine.connect()
    transaction = connection.begin()
    
    # Crear session vinculada a esta conexión
    Session = sessionmaker(bind=connection)
    db_session = Session()
    
    yield db_session
    
    # Rollback para limpiar cambios del test
    db_session.close()
    transaction.rollback()
    connection.close()


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
