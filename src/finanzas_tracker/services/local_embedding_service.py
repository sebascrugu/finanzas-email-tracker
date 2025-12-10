"""
Servicio de embeddings locales usando SentenceTransformers.

Este servicio genera embeddings 100% GRATIS usando modelos locales.
NO requiere API key, NO tiene costos, funciona offline.

Modelo: all-MiniLM-L6-v2
- Dimensiones: 384
- Tamaño: ~80MB
- Velocidad: ~14,000 oraciones/segundo en CPU
- Idiomas: Multilingüe (incluye español)
"""

__all__ = ["LocalEmbeddingService", "local_embedding_service"]

import logging
from functools import lru_cache
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.embedding import TransactionEmbedding


logger = logging.getLogger(__name__)


class LocalEmbeddingService:
    """
    Servicio de embeddings usando SentenceTransformers (100% gratis).
    
    Modelo: all-MiniLM-L6-v2
    - Tamaño: 80MB
    - Dimensiones: 384
    - Idiomas: Multilingüe (incluye español)
    - Velocidad: ~14,000 sentencias/segundo en CPU
    
    Uso:
        >>> from finanzas_tracker.services.local_embedding_service import local_embedding_service
        >>> vector = local_embedding_service.embed_text("AUTOMERCADO ESCAZU")
        >>> print(len(vector))  # 384
    """
    
    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384
    
    _instance: "LocalEmbeddingService | None" = None
    _model: SentenceTransformer | None = None
    
    def __new__(cls) -> "LocalEmbeddingService":
        """Singleton para no cargar el modelo múltiples veces."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        """Inicializa el servicio (carga el modelo la primera vez)."""
        if LocalEmbeddingService._model is None:
            logger.info(f"🧠 Cargando modelo de embeddings: {self.MODEL_NAME}")
            LocalEmbeddingService._model = SentenceTransformer(self.MODEL_NAME)
            logger.info("✅ Modelo cargado exitosamente")
    
    @property
    def model(self) -> SentenceTransformer:
        """Retorna el modelo cargado."""
        if LocalEmbeddingService._model is None:
            raise RuntimeError("Modelo no inicializado")
        return LocalEmbeddingService._model
    
    @property
    def embedding_dimension(self) -> int:
        """Retorna la dimensión de los embeddings."""
        return self.EMBEDDING_DIM
    
    def embed_text(self, text: str) -> list[float]:
        """
        Genera embedding para un texto.
        
        Args:
            text: Descripción de transacción (ej: "AUTOMERCADO ESCAZU CRC 45000")
            
        Returns:
            Vector de 384 dimensiones
        """
        if not text or not text.strip():
            # Retornar vector de ceros para texto vacío
            return [0.0] * self.EMBEDDING_DIM
        
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Genera embeddings para múltiples textos (más eficiente).
        
        Args:
            texts: Lista de descripciones
            
        Returns:
            Lista de vectores de 384 dimensiones
        """
        if not texts:
            return []
        
        # Filtrar textos vacíos
        clean_texts = [t if t and t.strip() else " " for t in texts]
        
        embeddings = self.model.encode(clean_texts, convert_to_numpy=True, batch_size=32)
        return embeddings.tolist()
    
    def similarity(self, text1: str, text2: str) -> float:
        """
        Calcula similitud coseno entre dos textos.
        
        Args:
            text1: Primer texto
            text2: Segundo texto
            
        Returns:
            Valor entre 0 y 1 (1 = idénticos)
        """
        embeddings = self.model.encode([text1, text2], convert_to_numpy=True)
        
        # Similitud coseno
        dot_product = np.dot(embeddings[0], embeddings[1])
        norm1 = np.linalg.norm(embeddings[0])
        norm2 = np.linalg.norm(embeddings[1])
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        similarity = dot_product / (norm1 * norm2)
        return float(similarity)
    
    def save_embedding(
        self,
        session: Session,
        transaction_id: str,
        text: str,
        tenant_id: str | None = None,
    ) -> TransactionEmbedding:
        """
        Genera y guarda el embedding de una transacción.
        
        Args:
            session: Sesión de SQLAlchemy
            transaction_id: ID de la transacción
            text: Texto para generar embedding (comercio + monto)
            tenant_id: ID del tenant (opcional)
            
        Returns:
            TransactionEmbedding creado o actualizado
        """
        # Verificar si ya existe
        existing = session.execute(
            select(TransactionEmbedding).where(
                TransactionEmbedding.transaction_id == transaction_id
            )
        ).scalar_one_or_none()
        
        # Generar embedding
        vector = self.embed_text(text)
        
        if existing:
            # Actualizar
            existing.embedding = vector
            existing.text_content = text
            existing.model_version = self.MODEL_NAME.split("/")[-1]
            existing.embedding_dim = self.EMBEDDING_DIM
            logger.debug(f"Embedding actualizado para transacción {transaction_id[:8]}...")
            return existing
        
        # Crear nuevo
        embedding = TransactionEmbedding(
            transaction_id=transaction_id,
            tenant_id=tenant_id,
            embedding=vector,
            text_content=text,
            model_version=self.MODEL_NAME.split("/")[-1],
            embedding_dim=self.EMBEDDING_DIM,
        )
        session.add(embedding)
        logger.debug(f"Embedding creado para transacción {transaction_id[:8]}...")
        return embedding
    
    def find_similar(
        self,
        session: Session,
        text: str,
        limit: int = 5,
        min_similarity: float = 0.7,
    ) -> list[dict[str, Any]]:
        """
        Encuentra transacciones similares usando pgvector.
        
        Args:
            session: Sesión de SQLAlchemy
            text: Texto de búsqueda
            limit: Número máximo de resultados
            min_similarity: Similitud mínima (0-1)
            
        Returns:
            Lista de dicts con transaction_id, similarity, text_content
        """
        from sqlalchemy import text as sql_text
        
        # Generar embedding de búsqueda
        query_embedding = self.embed_text(text)
        
        # Buscar usando operador de distancia coseno de pgvector
        # La distancia coseno en pgvector es 1 - similarity, entonces:
        # similarity = 1 - distance
        # Para min_similarity=0.7, max_distance = 0.3
        max_distance = 1 - min_similarity
        
        # Query usando pgvector
        result = session.execute(
            sql_text("""
                SELECT 
                    transaction_id,
                    text_content,
                    1 - (embedding <=> :query_embedding::vector) as similarity
                FROM transaction_embeddings
                WHERE 1 - (embedding <=> :query_embedding::vector) >= :min_similarity
                ORDER BY embedding <=> :query_embedding::vector
                LIMIT :limit
            """),
            {
                "query_embedding": str(query_embedding),
                "min_similarity": min_similarity,
                "limit": limit,
            }
        )
        
        return [
            {
                "transaction_id": row.transaction_id,
                "text_content": row.text_content,
                "similarity": float(row.similarity),
            }
            for row in result
        ]
    
    def generate_embeddings_for_all(
        self,
        profile_id: str | None = None,
        batch_size: int = 100,
    ) -> dict[str, int]:
        """
        Genera embeddings para todas las transacciones sin embedding.
        
        Args:
            profile_id: Filtrar por perfil (opcional)
            batch_size: Tamaño del batch
            
        Returns:
            Dict con estadísticas: created, skipped, failed
        """
        from finanzas_tracker.models.transaction import Transaction
        
        stats = {"created": 0, "skipped": 0, "failed": 0}
        
        with get_session() as session:
            # Query base
            query = (
                select(Transaction)
                .outerjoin(TransactionEmbedding)
                .where(TransactionEmbedding.id.is_(None))  # Sin embedding
                .where(Transaction.deleted_at.is_(None))
            )
            
            if profile_id:
                query = query.where(Transaction.profile_id == profile_id)
            
            transactions = session.execute(query).scalars().all()
            
            logger.info(f"📊 Generando embeddings para {len(transactions)} transacciones...")
            
            # Procesar en batches
            for i in range(0, len(transactions), batch_size):
                batch = transactions[i:i + batch_size]
                
                # Preparar textos
                texts = []
                for tx in batch:
                    # Combinar comercio + monto para contexto
                    text = f"{tx.comercio} {tx.monto_crc or tx.monto_original}"
                    texts.append(text)
                
                try:
                    # Generar embeddings en batch
                    embeddings = self.embed_batch(texts)
                    
                    # Guardar
                    for tx, vector, text in zip(batch, embeddings, texts):
                        try:
                            emb = TransactionEmbedding(
                                transaction_id=tx.id,
                                tenant_id=tx.tenant_id,
                                embedding=vector,
                                text_content=text,
                                model_version=self.MODEL_NAME.split("/")[-1],
                                embedding_dim=self.EMBEDDING_DIM,
                            )
                            session.add(emb)
                            stats["created"] += 1
                        except Exception as e:
                            logger.error(f"Error guardando embedding: {e}")
                            stats["failed"] += 1
                    
                    session.commit()
                    logger.info(f"  Procesados {i + len(batch)}/{len(transactions)}")
                    
                except Exception as e:
                    logger.error(f"Error en batch: {e}")
                    session.rollback()
                    stats["failed"] += len(batch)
        
        logger.info(
            f"✅ Embeddings generados: {stats['created']} creados, "
            f"{stats['failed']} fallidos"
        )
        return stats


# Singleton global
local_embedding_service = LocalEmbeddingService()
