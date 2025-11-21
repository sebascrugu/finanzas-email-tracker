"""Tests para FinanceChatService."""

import os

# Set env vars BEFORE any imports
os.environ.setdefault("AZURE_CLIENT_ID", "test-client-id")
os.environ.setdefault("AZURE_TENANT_ID", "test-tenant-id")
os.environ.setdefault("AZURE_CLIENT_SECRET", "test-secret")
os.environ.setdefault("USER_EMAIL", "test@example.com")
os.environ.setdefault("MOM_EMAIL", "mom@example.com")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test123")

from unittest.mock import MagicMock, patch

import anthropic
import pytest


class TestFinanceChatService:
    """Tests para el servicio de chat financiero."""

    @patch("finanzas_tracker.services.finance_chat.get_session")
    @patch("finanzas_tracker.services.finance_chat.anthropic.Anthropic")
    def test_chat_returns_response(
        self, mock_anthropic_class: MagicMock, mock_session: MagicMock
    ) -> None:
        """Test que chat retorna respuesta de Claude."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Gastaste 50,000 en comida")]
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_class.return_value = mock_client

        mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.all.return_value = []

        from finanzas_tracker.services.finance_chat import FinanceChatService

        service = FinanceChatService()
        result = service.chat("Cuanto gaste en comida?", "profile-123")

        assert "50,000" in result
        mock_client.messages.create.assert_called_once()

    @patch("finanzas_tracker.services.finance_chat.get_session")
    @patch("finanzas_tracker.services.finance_chat.anthropic.Anthropic")
    def test_chat_handles_connection_error(
        self, mock_anthropic_class: MagicMock, mock_session: MagicMock
    ) -> None:
        """Test manejo de error de conexion."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.APIConnectionError(
            request=MagicMock()
        )
        mock_anthropic_class.return_value = mock_client
        mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.all.return_value = []

        from finanzas_tracker.services.finance_chat import FinanceChatService

        service = FinanceChatService()
        result = service.chat("Test", "profile-123")

        assert "no puedo conectarme" in result

    @patch("finanzas_tracker.services.finance_chat.get_session")
    @patch("finanzas_tracker.services.finance_chat.anthropic.Anthropic")
    def test_chat_handles_rate_limit(
        self, mock_anthropic_class: MagicMock, mock_session: MagicMock
    ) -> None:
        """Test manejo de rate limit."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            message="Rate limited",
            response=MagicMock(status_code=429),
            body={}
        )
        mock_anthropic_class.return_value = mock_client
        mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.all.return_value = []

        from finanzas_tracker.services.finance_chat import FinanceChatService

        service = FinanceChatService()
        result = service.chat("Test", "profile-123")

        assert "saturado" in result

    @patch("finanzas_tracker.services.finance_chat.anthropic.Anthropic")
    def test_format_gastos_categoria_empty(self, mock_anthropic: MagicMock) -> None:
        """Test formateo de categorias vacias."""
        from finanzas_tracker.services.finance_chat import FinanceChatService

        service = FinanceChatService()
        result = service._format_gastos_categoria({})

        assert "Sin datos" in result

    @patch("finanzas_tracker.services.finance_chat.anthropic.Anthropic")
    def test_format_gastos_categoria_with_data(self, mock_anthropic: MagicMock) -> None:
        """Test formateo de categorias con datos."""
        from finanzas_tracker.services.finance_chat import FinanceChatService

        service = FinanceChatService()
        result = service._format_gastos_categoria({"Comida": 50000.0, "Transporte": 20000.0})

        assert "Comida" in result
        assert "50,000" in result

    @patch("finanzas_tracker.services.finance_chat.anthropic.Anthropic")
    def test_format_top_gastos_empty(self, mock_anthropic: MagicMock) -> None:
        """Test formateo de top gastos vacio."""
        from finanzas_tracker.services.finance_chat import FinanceChatService

        service = FinanceChatService()
        result = service._format_top_gastos([])

        assert "Sin transacciones" in result

    @patch("finanzas_tracker.services.finance_chat.anthropic.Anthropic")
    def test_format_top_comercios_empty(self, mock_anthropic: MagicMock) -> None:
        """Test formateo de top comercios vacio."""
        from finanzas_tracker.services.finance_chat import FinanceChatService

        service = FinanceChatService()
        result = service._format_top_comercios([])

        assert "Sin datos" in result

    @patch("finanzas_tracker.services.finance_chat.anthropic.Anthropic")
    def test_build_prompt_includes_context(self, mock_anthropic: MagicMock) -> None:
        """Test que el prompt incluye contexto financiero."""
        from finanzas_tracker.services.finance_chat import FinanceChatService

        service = FinanceChatService()
        context = {
            "fecha_actual": "21/11/2025",
            "mes_actual": "November 2025",
            "total_transacciones_mes": 10,
            "total_gastos_mes": 100000.0,
            "total_ingresos_mes": 500000.0,
            "balance_mes": 400000.0,
            "total_gastos_mes_pasado": 80000.0,
            "gastos_por_categoria": {"Comida": 50000.0},
            "top_5_gastos": [],
            "top_comercios": [],
        }

        prompt = service._build_prompt("Cuanto gaste?", context)

        assert "100,000" in prompt
        assert "Cuanto gaste?" in prompt
        assert "asistente financiero" in prompt
