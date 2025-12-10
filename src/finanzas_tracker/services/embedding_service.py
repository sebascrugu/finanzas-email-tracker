"""
Servicio de embeddings para transacciones - RAG con pgvector.

Soporta múltiples proveedores:
- Voyage AI (recomendado por Anthropic)
- OpenAI (fallback)
- Sentence Transformers (local, offline)

El servicio genera embeddings vectoriales de las transacciones
para permitir búsqueda semántica con pgvector.
"""

__all__ = ["EmbeddingService", "EmbeddingProvider"]

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.config.settings import Settings
from finanzas_tracker.models.embedding import TransactionEmbedding


if TYPE_CHECKING:
    import openai
    from sentence_transformers import SentenceTransformer
    import voyageai

    from finanzas_tracker.models.transaction import Transaction


logger = logging.getLogger(__name__)


class EmbeddingProvider(StrEnum):
    """Proveedores de embeddings soportados."""

    VOYAGE = "voyage"
    OPENAI = "openai"
    LOCAL = "local"  # Sentence Transformers


@dataclass
class EmbeddingConfig:
    """Configuración del servicio de embeddings."""

    provider: EmbeddingProvider = EmbeddingProvider.VOYAGE
    model_name: str = "voyage-3-lite"
    embedding_dim: int = 1024
    batch_size: int = 32

    # API keys (se cargan de Settings)
    voyage_api_key: str | None = None
    openai_api_key: str | None = None


class BaseEmbeddingProvider(ABC):
    """Clase base para proveedores de embeddings."""

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Nombre del modelo usado."""
        ...

    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Dimensión de los embeddings."""
        ...

    @abstractmethod
    def get_embedding(self, text: str) -> list[float]:
        """Genera embedding para un texto."""
        ...

    @abstractmethod
    def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para múltiples textos."""
        ...


class VoyageEmbeddingProvider(BaseEmbeddingProvider):
    """
    Proveedor de embeddings usando Voyage AI.

    Voyage AI es recomendado por Anthropic para embeddings.
    Modelos disponibles:
    - voyage-3-lite: 1024 dims, más económico
    - voyage-3: 1024 dims, mejor calidad
    - voyage-finance-2: 1024 dims, especializado en finanzas
    """

    def __init__(
        self,
        api_key: str,
        model: str = "voyage-3-lite",
    ) -> None:
        """
        Inicializa el proveedor de Voyage AI.

        Args:
            api_key: API key de Voyage AI
            model: Nombre del modelo a usar
        """
        self._api_key = api_key
        self._model = model
        self._client: voyageai.Client | None = None

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def embedding_dim(self) -> int:
        # voyage-3, voyage-3-lite, voyage-finance-2 todos usan 1024
        return 1024

    def _get_client(self) -> "voyageai.Client":
        """Obtiene o crea el cliente de Voyage AI."""
        if self._client is None:
            try:
                import voyageai

                self._client = voyageai.Client(api_key=self._api_key)
            except ImportError as e:
                msg = "voyageai no está instalado. Ejecuta: poetry add voyageai"
                raise ImportError(msg) from e
        return self._client

    def get_embedding(self, text: str) -> list[float]:
        """Genera embedding para un texto."""
        client = self._get_client()
        result = client.embed(
            texts=[text],
            model=self._model,
            input_type="document",
        )
        embeddings: list[float] = result.embeddings[0]
        return embeddings

    def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para múltiples textos."""
        if not texts:
            return []

        client = self._get_client()
        result = client.embed(
            texts=texts,
            model=self._model,
            input_type="document",
        )
        embeddings: list[list[float]] = result.embeddings
        return embeddings


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """
    Proveedor de embeddings usando OpenAI.

    Modelos disponibles:
    - text-embedding-3-small: 1536 dims, económico
    - text-embedding-3-large: 3072 dims, mejor calidad
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
    ) -> None:
        """
        Inicializa el proveedor de OpenAI.

        Args:
            api_key: API key de OpenAI
            model: Nombre del modelo a usar
        """
        self._api_key = api_key
        self._model = model
        self._client: openai.OpenAI | None = None

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def embedding_dim(self) -> int:
        dims = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }
        return dims.get(self._model, 1536)

    def _get_client(self) -> "openai.OpenAI":
        """Obtiene o crea el cliente de OpenAI."""
        if self._client is None:
            try:
                import openai

                self._client = openai.OpenAI(api_key=self._api_key)
            except ImportError as e:
                msg = "openai no está instalado. Ejecuta: poetry add openai"
                raise ImportError(msg) from e
        return self._client

    def get_embedding(self, text: str) -> list[float]:
        """Genera embedding para un texto."""
        client = self._get_client()
        response = client.embeddings.create(
            input=text,
            model=self._model,
        )
        embedding: list[float] = response.data[0].embedding
        return embedding

    def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para múltiples textos."""
        if not texts:
            return []

        client = self._get_client()
        response = client.embeddings.create(
            input=texts,
            model=self._model,
        )
        return [item.embedding for item in response.data]


class LocalEmbeddingProvider(BaseEmbeddingProvider):
    """
    Proveedor de embeddings local usando Sentence Transformers.

    No requiere API key, útil para desarrollo offline.
    Modelos recomendados:
    - all-MiniLM-L6-v2: 384 dims, muy rápido
    - all-mpnet-base-v2: 768 dims, mejor calidad
    - paraphrase-multilingual-MiniLM-L12-v2: 384 dims, español
    """

    def __init__(
        self,
        model: str = "all-MiniLM-L6-v2",
    ) -> None:
        """
        Inicializa el proveedor local.

        Args:
            model: Nombre del modelo de Sentence Transformers
        """
        self._model_name = model
        self._model: SentenceTransformer | None = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def embedding_dim(self) -> int:
        dims = {
            "all-MiniLM-L6-v2": 384,
            "all-mpnet-base-v2": 768,
            "paraphrase-multilingual-MiniLM-L12-v2": 384,
        }
        return dims.get(self._model_name, 384)

    def _get_model(self) -> "SentenceTransformer":
        """Obtiene o crea el modelo."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self._model_name)
            except ImportError as e:
                msg = "sentence-transformers no está instalado. Ejecuta: poetry add sentence-transformers"
                raise ImportError(msg) from e
        return self._model

    def get_embedding(self, text: str) -> list[float]:
        """Genera embedding para un texto."""
        model = self._get_model()
        embedding = model.encode(text)
        result: list[float] = embedding.tolist()
        return result

    def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Genera embeddings para múltiples textos."""
        if not texts:
            return []

        model = self._get_model()
        embeddings = model.encode(texts)
        return [e.tolist() for e in embeddings]


class EmbeddingService:
    """
    Servicio principal para generar y gestionar embeddings de transacciones.

    Ejemplo de uso:
    ```python
    service = EmbeddingService(db_session)

    # Generar embedding para una transacción
    embedding = service.embed_transaction(transaction)

    # Generar embeddings para todas las transacciones sin embedding
    count = service.embed_pending_transactions(profile_id)

    # Buscar transacciones similares a un texto
    results = service.search_similar("comida rápida", limit=10)
    ```
    """

    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
        provider: EmbeddingProvider | None = None,
    ) -> None:
        """
        Inicializa el servicio de embeddings.

        Args:
            db: Sesión de SQLAlchemy
            settings: Configuración (opcional, se carga automáticamente)
            provider: Proveedor de embeddings (opcional, se selecciona automáticamente)
        """
        self.db = db
        self.settings = settings or Settings()
        self._provider = self._create_provider(provider)

    def _create_provider(
        self,
        provider_type: EmbeddingProvider | None = None,
    ) -> BaseEmbeddingProvider:
        """Crea el proveedor de embeddings según la configuración."""
        # Intentar Voyage AI primero (recomendado)
        voyage_key = getattr(self.settings, "voyage_api_key", None)
        if voyage_key and (provider_type is None or provider_type == EmbeddingProvider.VOYAGE):
            logger.info("Usando Voyage AI para embeddings")
            return VoyageEmbeddingProvider(
                api_key=voyage_key,
                model=getattr(self.settings, "voyage_model", "voyage-3-lite"),
            )

        # Fallback a OpenAI
        openai_key = getattr(self.settings, "openai_api_key", None)
        if openai_key and (provider_type is None or provider_type == EmbeddingProvider.OPENAI):
            logger.info("Usando OpenAI para embeddings")
            return OpenAIEmbeddingProvider(
                api_key=openai_key,
                model=getattr(self.settings, "openai_embedding_model", "text-embedding-3-small"),
            )

        # Fallback a local (Sentence Transformers)
        logger.info("Usando modelo local (Sentence Transformers) para embeddings")
        return LocalEmbeddingProvider(
            model=getattr(self.settings, "local_embedding_model", "all-MiniLM-L6-v2"),
        )

    @property
    def model_name(self) -> str:
        """Nombre del modelo de embeddings usado."""
        return self._provider.model_name

    @property
    def embedding_dim(self) -> int:
        """Dimensión de los embeddings."""
        return self._provider.embedding_dim

    def _build_transaction_text(self, transaction: "Transaction") -> str:
        """
        Construye el texto representativo de una transacción para embedding.

        El texto incluye información estructurada que permite
        búsquedas semánticas como:
        - "Cuánto gasté en comida?"
        - "Mis compras en Walmart"
        - "Transacciones grandes de este mes"

        Args:
            transaction: Transacción a procesar

        Returns:
            Texto representativo para generar embedding
        """
        parts = []

        # Comercio y tipo
        parts.append(f"Comercio: {transaction.comercio}")
        parts.append(f"Tipo: {transaction.tipo_transaccion}")

        # Monto (con contexto de tamaño)
        monto = float(transaction.monto_crc)
        if monto < 5000:
            size = "pequeño"
        elif monto < 20000:
            size = "mediano"
        elif monto < 50000:
            size = "grande"
        else:
            size = "muy grande"

        moneda = transaction.moneda_original
        parts.append(f"Monto: ₡{monto:,.0f} ({size})")
        if moneda != "CRC" and transaction.monto_original:
            parts.append(f"Monto original: {moneda} {transaction.monto_original}")

        # Categoría
        if transaction.subcategory:
            parts.append(
                f"Categoría: {transaction.subcategory.category.nombre} > {transaction.subcategory.nombre}"
            )
        elif transaction.categoria_sugerida_por_ia:
            parts.append(f"Categoría sugerida: {transaction.categoria_sugerida_por_ia}")

        # Banco y tarjeta
        parts.append(f"Banco: {transaction.banco}")
        if transaction.card and transaction.card.alias:
            parts.append(f"Tarjeta: {transaction.card.alias}")

        # Fecha
        fecha = transaction.fecha_transaccion
        parts.append(f"Fecha: {fecha.strftime('%Y-%m-%d')}")

        # Ubicación
        if transaction.ciudad or transaction.pais:
            loc = ", ".join(filter(None, [transaction.ciudad, transaction.pais]))
            parts.append(f"Ubicación: {loc}")

        # Notas y contexto
        if transaction.notas:
            parts.append(f"Notas: {transaction.notas}")
        if transaction.contexto:
            parts.append(f"Contexto: {transaction.contexto}")

        # Flags especiales
        if transaction.tipo_especial:
            parts.append(f"Tipo especial: {transaction.tipo_especial}")
        if transaction.es_desconocida:
            parts.append("Estado: Desconocida")
        if transaction.is_anomaly:
            parts.append(f"Anomalía: {transaction.anomaly_reason or 'Detectada'}")

        return " | ".join(parts)

    def get_embedding(self, text: str) -> list[float]:
        """
        Genera embedding para un texto.

        Args:
            text: Texto a embedder

        Returns:
            Vector embedding
        """
        return self._provider.get_embedding(text)

    def embed_transaction(
        self,
        transaction: "Transaction",
        force_update: bool = False,
    ) -> TransactionEmbedding:
        """
        Genera y guarda embedding para una transacción.

        Args:
            transaction: Transacción a procesar
            force_update: Si es True, regenera aunque ya exista

        Returns:
            TransactionEmbedding creado o actualizado
        """
        # Verificar si ya existe
        stmt = select(TransactionEmbedding).where(
            TransactionEmbedding.transaction_id == transaction.id
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing and not force_update:
            logger.debug(f"Embedding ya existe para transacción {transaction.id}")
            return existing

        # Generar texto y embedding
        text = self._build_transaction_text(transaction)
        embedding = self.get_embedding(text)

        if existing:
            # Actualizar existente
            existing.embedding = embedding
            existing.text_content = text
            existing.model_version = self.model_name
            existing.embedding_dim = self.embedding_dim
            self.db.commit()
            logger.info(f"Embedding actualizado para transacción {transaction.id}")
            return existing

        # Crear nuevo
        new_embedding = TransactionEmbedding(
            transaction_id=transaction.id,
            tenant_id=transaction.tenant_id,
            embedding=embedding,
            text_content=text,
            model_version=self.model_name,
            embedding_dim=self.embedding_dim,
        )
        self.db.add(new_embedding)
        self.db.commit()
        logger.info(f"Embedding creado para transacción {transaction.id}")

        return new_embedding

    def embed_pending_transactions(
        self,
        profile_id: str | None = None,
        batch_size: int = 32,
    ) -> int:
        """
        Genera embeddings para transacciones sin embedding.

        Args:
            profile_id: Filtrar por perfil (opcional)
            batch_size: Tamaño del batch para procesamiento

        Returns:
            Número de embeddings generados
        """
        from finanzas_tracker.models.transaction import Transaction

        # Query de transacciones sin embedding
        subquery = select(TransactionEmbedding.transaction_id)
        stmt = select(Transaction).where(
            Transaction.deleted_at.is_(None),
            ~Transaction.id.in_(subquery),
        )

        if profile_id:
            stmt = stmt.where(Transaction.profile_id == profile_id)

        transactions = list(self.db.execute(stmt).scalars().all())

        if not transactions:
            logger.info("No hay transacciones pendientes de embedding")
            return 0

        logger.info(f"Generando embeddings para {len(transactions)} transacciones...")

        # Procesar en batches
        count = 0
        for i in range(0, len(transactions), batch_size):
            batch = transactions[i : i + batch_size]
            texts = [self._build_transaction_text(t) for t in batch]
            embeddings = self._provider.get_embeddings_batch(texts)

            for txn, text, emb in zip(batch, texts, embeddings, strict=False):
                new_embedding = TransactionEmbedding(
                    transaction_id=txn.id,
                    tenant_id=txn.tenant_id,
                    embedding=emb,
                    text_content=text,
                    model_version=self.model_name,
                    embedding_dim=self.embedding_dim,
                )
                self.db.add(new_embedding)
                count += 1

            self.db.commit()
            logger.info(f"Batch {i // batch_size + 1}: {len(batch)} embeddings generados")

        logger.info(f"Total: {count} embeddings generados")
        return count

    def search_similar(
        self,
        query: str,
        profile_id: str | None = None,
        limit: int = 10,
        min_similarity: float = 0.5,
    ) -> list[tuple["Transaction", float]]:
        """
        Busca transacciones similares a un texto usando pgvector.

        Args:
            query: Texto de búsqueda (ej: "comida rápida")
            profile_id: Filtrar por perfil (opcional)
            limit: Número máximo de resultados
            min_similarity: Similitud mínima (0-1, cosine)

        Returns:
            Lista de tuplas (Transaction, similitud)
        """
        from sqlalchemy import text

        from finanzas_tracker.models.transaction import Transaction

        # Generar embedding de la query
        query_embedding = self.get_embedding(query)

        # Usar pgvector para búsqueda por similitud coseno
        # La función <=> es distancia coseno (1 - similarity)
        # Convertimos a similitud: 1 - distancia
        embedding_array = f"ARRAY{query_embedding}::float[]"

        # Query con similitud coseno usando pgvector
        # Nota: pgvector usa <=> para distancia coseno
        stmt = text(f"""
            SELECT
                te.transaction_id,
                1 - (te.embedding <=> {embedding_array}::vector) as similarity
            FROM transaction_embeddings te
            JOIN transactions t ON t.id = te.transaction_id
            WHERE t.deleted_at IS NULL
            {"AND t.profile_id = :profile_id" if profile_id else ""}
            AND 1 - (te.embedding <=> {embedding_array}::vector) >= :min_similarity
            ORDER BY similarity DESC
            LIMIT :limit
        """)

        params: dict[str, int | float | str] = {"limit": limit, "min_similarity": min_similarity}
        if profile_id:
            params["profile_id"] = profile_id

        results = self.db.execute(stmt, params).fetchall()

        # Cargar transacciones completas
        transaction_ids = [r[0] for r in results]
        similarities: dict[Any, float] = {r[0]: r[1] for r in results}

        if not transaction_ids:
            return []

        txn_stmt = select(Transaction).where(Transaction.id.in_(transaction_ids))
        transactions = {t.id: t for t in self.db.execute(txn_stmt).scalars().all()}

        # Mantener orden por similitud
        return [
            (transactions[tid], similarities[tid]) for tid in transaction_ids if tid in transactions
        ]

    def delete_embedding(self, transaction_id: str) -> bool:
        """
        Elimina el embedding de una transacción.

        Args:
            transaction_id: ID de la transacción

        Returns:
            True si se eliminó, False si no existía
        """
        stmt = select(TransactionEmbedding).where(
            TransactionEmbedding.transaction_id == transaction_id
        )
        existing = self.db.execute(stmt).scalar_one_or_none()

        if not existing:
            return False

        self.db.delete(existing)
        self.db.commit()
        return True
