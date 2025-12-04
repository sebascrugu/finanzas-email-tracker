"""
Tests para RAGService.

Verifica la integración de búsqueda semántica con Claude AI.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4


class TestRAGContext:
    """Tests para RAGContext dataclass."""

    def test_rag_context_creation(self) -> None:
        """Verifica la creación del contexto RAG."""
        from finanzas_tracker.services.rag_service import RAGContext

        context = RAGContext(
            transaction_id="abc-123",
            comercio="Walmart",
            monto_crc=Decimal("25000"),
            fecha=datetime.now(),
            categoria="Supermercado",
            similarity=0.85,
            text_content="Compra en Walmart",
        )

        assert context.comercio == "Walmart"
        assert context.similarity == 0.85

    def test_to_prompt_text(self) -> None:
        """Verifica la conversión a texto para prompt."""
        from finanzas_tracker.services.rag_service import RAGContext

        context = RAGContext(
            transaction_id="abc-123",
            comercio="Walmart",
            monto_crc=Decimal("25000"),
            fecha=datetime(2025, 11, 30),
            categoria="Supermercado",
            similarity=0.85,
            text_content="Compra en Walmart",
        )

        text = context.to_prompt_text()

        assert "Walmart" in text
        assert "25,000" in text or "25000" in text
        assert "2025-11-30" in text


class TestRAGResponse:
    """Tests para RAGResponse dataclass."""

    def test_rag_response_creation(self) -> None:
        """Verifica la creación de respuesta RAG."""
        from finanzas_tracker.services.rag_service import RAGResponse

        response = RAGResponse(
            answer="Gastaste ₡25,000 en Walmart",
            sources=[],
            model="claude-haiku-4-5-20251001",
            query="cuanto gaste en walmart",
        )

        assert "25,000" in response.answer
        assert response.model == "claude-haiku-4-5-20251001"


class TestRAGService:
    """Tests para el servicio RAG."""

    def test_system_prompt_contains_costa_rica_context(self, session) -> None:
        """Verifica que el system prompt tenga contexto de Costa Rica."""
        from finanzas_tracker.services.rag_service import SYSTEM_PROMPT

        assert "Costa Rica" in SYSTEM_PROMPT
        assert "CRC" in SYSTEM_PROMPT or "colones" in SYSTEM_PROMPT.lower()

    @patch("finanzas_tracker.services.rag_service.EmbeddingService")
    def test_rag_service_initialization(
        self,
        mock_embedding_service: MagicMock,
        session,
    ) -> None:
        """Verifica la inicialización del servicio RAG."""
        from finanzas_tracker.services.rag_service import RAGService

        service = RAGService(session)

        assert service.db is session
        mock_embedding_service.assert_called_once()


class TestEmbeddingEvents:
    """Tests para el sistema de eventos de auto-embeddings."""

    def test_queue_embedding_adds_to_queue(self) -> None:
        """Verifica que queue_embedding agrega a la cola."""
        from finanzas_tracker.services.embedding_events import (
            _embedding_queue,
            queue_embedding,
        )

        # Limpiar cola
        while not _embedding_queue.empty():
            _embedding_queue.get_nowait()

        transaction_id = str(uuid4())
        queue_embedding(transaction_id)

        assert not _embedding_queue.empty()
        queued_id = _embedding_queue.get_nowait()
        assert queued_id == transaction_id

    def test_register_and_unregister_events(self) -> None:
        """Verifica registro y desregistro de eventos."""
        from finanzas_tracker.services.embedding_events import (
            register_embedding_events,
            unregister_embedding_events,
        )

        # No debe fallar al registrar/desregistrar
        register_embedding_events()
        unregister_embedding_events()
