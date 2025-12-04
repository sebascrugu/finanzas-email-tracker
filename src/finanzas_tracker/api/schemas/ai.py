"""Schemas para endpoints de AI (RAG, chat, embeddings)."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """Request para chat con contexto RAG."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Pregunta del usuario",
        examples=["Cuánto gasté en comida este mes?"],
    )
    include_stats: bool = Field(
        default=True,
        description="Incluir estadísticas mensuales en el contexto",
    )
    max_context: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Máximo de transacciones como contexto",
    )


class TransactionContext(BaseModel):
    """Contexto de transacción usada en la respuesta."""

    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    comercio: str
    monto_crc: Decimal
    fecha: datetime
    categoria: str | None = None
    similarity: float = Field(
        ge=0,
        le=1,
        description="Similitud coseno con la query (0-1)",
    )


class ChatResponse(BaseModel):
    """Response del chat RAG."""

    answer: str = Field(
        description="Respuesta generada por Claude",
    )
    sources: list[TransactionContext] = Field(
        default_factory=list,
        description="Transacciones usadas como contexto",
    )
    model: str = Field(
        description="Modelo de Claude usado",
    )
    usage: dict = Field(
        default_factory=dict,
        description="Tokens usados (input/output)",
    )
    query: str = Field(
        description="Query original",
    )


class SemanticSearchRequest(BaseModel):
    """Request para búsqueda semántica."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Texto de búsqueda",
        examples=["comida rápida", "uber", "suscripciones"],
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Número máximo de resultados",
    )
    min_similarity: float = Field(
        default=0.3,
        ge=0,
        le=1,
        description="Similitud mínima (0-1)",
    )


class SemanticSearchResult(BaseModel):
    """Resultado individual de búsqueda semántica."""

    model_config = ConfigDict(from_attributes=True)

    transaction_id: str
    comercio: str
    monto_crc: Decimal
    fecha: datetime
    categoria: str | None = None
    similarity: float
    text_content: str = Field(
        description="Texto usado para el embedding",
    )


class SemanticSearchResponse(BaseModel):
    """Response de búsqueda semántica."""

    results: list[SemanticSearchResult]
    total: int
    query: str
    model: str = Field(
        description="Modelo de embeddings usado",
    )


class EmbeddingStatsResponse(BaseModel):
    """Estadísticas de embeddings."""

    total_embeddings: int
    total_transactions: int
    pending_transactions: int = Field(
        description="Transacciones sin embedding",
    )
    model: str
    embedding_dim: int


class GenerateEmbeddingsRequest(BaseModel):
    """Request para generar embeddings pendientes."""

    batch_size: int = Field(
        default=32,
        ge=1,
        le=100,
        description="Tamaño del batch para procesamiento",
    )


class GenerateEmbeddingsResponse(BaseModel):
    """Response de generación de embeddings."""

    generated: int = Field(
        description="Número de embeddings generados",
    )
    model: str
    message: str


class AnalyzeSpendingRequest(BaseModel):
    """Request para análisis de gastos."""

    category: str | None = Field(
        default=None,
        description="Categoría específica a analizar",
    )
    year: int | None = Field(
        default=None,
        ge=2020,
        le=2100,
        description="Año a analizar",
    )
    month: int | None = Field(
        default=None,
        ge=1,
        le=12,
        description="Mes a analizar",
    )
