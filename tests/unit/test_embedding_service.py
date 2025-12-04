"""
Tests para EmbeddingService.

Verifica la generación de embeddings locales y búsqueda semántica.
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest


# Skip si no está disponible sentence-transformers (CI sin GPU)
pytest.importorskip("sentence_transformers", reason="sentence-transformers not installed")


class TestLocalEmbeddingProvider:
    """Tests para el proveedor de embeddings local."""

    def test_get_embedding_returns_correct_dimension(self) -> None:
        """Verifica que el embedding tenga 384 dimensiones."""
        from finanzas_tracker.services.embedding_service import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()
        text = "Compra en Walmart por 25000 colones"

        embedding = provider.get_embedding(text)

        assert len(embedding) == 384
        assert all(isinstance(x, float) for x in embedding)

    def test_get_embedding_different_texts_different_vectors(self) -> None:
        """Verifica que textos diferentes generen embeddings diferentes."""
        from finanzas_tracker.services.embedding_service import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()

        emb1 = provider.get_embedding("Compra en supermercado")
        emb2 = provider.get_embedding("Pago de servicios públicos")

        # Los embeddings deben ser diferentes
        assert emb1 != emb2

    def test_get_embedding_similar_texts_similar_vectors(self) -> None:
        """Verifica que textos similares generen embeddings cercanos."""
        import numpy as np

        from finanzas_tracker.services.embedding_service import LocalEmbeddingProvider

        provider = LocalEmbeddingProvider()

        emb1 = provider.get_embedding("Compra en Walmart supermercado")
        emb2 = provider.get_embedding("Compra en Automercado supermercado")
        emb3 = provider.get_embedding("Pago de electricidad ICE")

        # Calcular similitud coseno
        def cosine_similarity(a: list[float], b: list[float]) -> float:
            a_arr = np.array(a)
            b_arr = np.array(b)
            return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))

        sim_walmart_auto = cosine_similarity(emb1, emb2)
        sim_walmart_ice = cosine_similarity(emb1, emb3)

        # Supermercados deben ser más similares entre sí que con servicios
        assert sim_walmart_auto > sim_walmart_ice


class TestEmbeddingService:
    """Tests para el servicio de embeddings."""

    def test_build_transaction_text(self, session) -> None:
        """Verifica la construcción del texto para embedding."""
        from finanzas_tracker.models.transaction import Transaction
        from finanzas_tracker.services.embedding_service import EmbeddingService

        service = EmbeddingService(session)

        transaction = Transaction(
            id=uuid4(),
            comercio="Walmart Escazú",
            tipo_transaccion="compra",
            monto_crc=Decimal("25000.00"),
            monto_original=Decimal("25000.00"),
            moneda_original="CRC",
            banco="bac",
            fecha_transaccion=datetime(2025, 11, 30, 10, 30),
            notas="Compra del super",
            email_id="test-123",
        )

        text = service._build_transaction_text(transaction)

        assert "Walmart Escazú" in text
        assert "compra" in text
        assert "bac" in text


class TestEmbeddingServiceProviderSelection:
    """Tests para la selección de proveedores de embeddings."""

    def test_defaults_to_local_provider(self, session) -> None:
        """Verifica que usa proveedor local por defecto."""
        from finanzas_tracker.services.embedding_service import (
            EmbeddingService,
            LocalEmbeddingProvider,
        )

        service = EmbeddingService(session)

        assert isinstance(service._provider, LocalEmbeddingProvider)
        assert service._provider.model_name == "all-MiniLM-L6-v2"
