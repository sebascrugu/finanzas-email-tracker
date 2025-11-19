"""
Tests unitarios para el servicio EmailFetcher.

Estos tests verifican la funcionalidad del servicio de extracción de correos
usando mocks para no hacer requests reales a Microsoft Graph API.
"""

from unittest.mock import MagicMock, patch

import pytest

from finanzas_tracker.services.email_fetcher import EmailFetcher


@pytest.fixture
def mock_auth_manager() -> MagicMock:
    """Mock del AuthManager para tests."""
    mock = MagicMock()
    mock.get_authorization_header.return_value = {"Authorization": "Bearer test_token"}
    return mock


@pytest.fixture
def email_fetcher(mock_auth_manager: MagicMock) -> EmailFetcher:
    """Fixture que retorna una instancia de EmailFetcher con auth mockeado."""
    with patch("finanzas_tracker.services.email_fetcher.auth_manager", mock_auth_manager):
        return EmailFetcher()


def test_email_fetcher_initialization(email_fetcher: EmailFetcher) -> None:
    """Test que verifica que EmailFetcher se inicializa correctamente."""
    assert email_fetcher is not None
    assert hasattr(email_fetcher, "BAC_SENDERS")
    assert hasattr(email_fetcher, "BANCO_POPULAR_SENDERS")


def test_build_filter_query_basic(email_fetcher: EmailFetcher) -> None:
    """Test que verifica la construcción básica del query filter."""
    # Sin filtro de remitentes
    query = email_fetcher._build_filter_query(days_back=30, senders=None)

    assert "receivedDateTime ge" in query
    assert len(query) > 0


def test_build_filter_query_with_senders(email_fetcher: EmailFetcher) -> None:
    """Test que verifica el query filter con remitentes específicos."""
    senders = ["test1@example.com", "test2@example.com"]
    query = email_fetcher._build_filter_query(days_back=30, senders=senders)

    assert "receivedDateTime ge" in query
    assert "from/emailAddress/address eq" in query
    assert "test1@example.com" in query
    assert "test2@example.com" in query


@patch("finanzas_tracker.services.email_fetcher.requests.get")
def test_fetch_emails_for_user_success(
    mock_get: MagicMock,
    email_fetcher: EmailFetcher,
) -> None:
    """Test que verifica la extracción exitosa de correos para un usuario."""
    # Mock de la respuesta de la API
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "value": [
            {
                "id": "email1",
                "subject": "Notificación de transacción",
                "from": {"emailAddress": {"address": "notificaciones@baccredomatic.com"}},
                "receivedDateTime": "2025-11-09T10:00:00Z",
            },
            {
                "id": "email2",
                "subject": "Alerta de compra",
                "from": {"emailAddress": {"address": "alertas@bp.fi.cr"}},
                "receivedDateTime": "2025-11-08T15:00:00Z",
            },
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    # Ejecutar
    emails = email_fetcher.fetch_emails_for_current_user(days_back=7)

    # Verificar
    assert len(emails) == 2
    assert emails[0]["id"] == "email1"
    assert emails[1]["subject"] == "Alerta de compra"


@patch("finanzas_tracker.services.email_fetcher.requests.get")
def test_fetch_emails_for_user_empty(
    mock_get: MagicMock,
    email_fetcher: EmailFetcher,
) -> None:
    """Test que verifica el caso donde no se encuentran correos."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"value": []}
    mock_response.raise_for_status = MagicMock()
    mock_get.return_value = mock_response

    emails = email_fetcher.fetch_emails_for_current_user()

    assert len(emails) == 0


@patch("finanzas_tracker.services.email_fetcher.requests.get")
def test_fetch_emails_for_user_error(
    mock_get: MagicMock,
    email_fetcher: EmailFetcher,
) -> None:
    """Test que verifica el manejo de errores en la extracción."""
    mock_get.side_effect = Exception("API Error")

    emails = email_fetcher.fetch_emails_for_current_user()

    assert len(emails) == 0  # Debe retornar lista vacía en caso de error


def test_bac_senders_defined(email_fetcher: EmailFetcher) -> None:
    """Test que verifica que los remitentes del BAC estén definidos."""
    assert len(email_fetcher.BAC_SENDERS) > 0
    assert any("baccredomatic" in sender for sender in email_fetcher.BAC_SENDERS)


def test_banco_popular_senders_defined(email_fetcher: EmailFetcher) -> None:
    """Test que verifica que los remitentes del Banco Popular estén definidos."""
    assert len(email_fetcher.BANCO_POPULAR_SENDERS) > 0
    assert any(
        "bp.fi.cr" in sender or "bancopopular" in sender
        for sender in email_fetcher.BANCO_POPULAR_SENDERS
    )
