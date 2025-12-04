"""
Router para endpoints de AI - RAG, Chat, Embeddings.

Proporciona:
- /ai/chat - Chat con contexto de transacciones (RAG)
- /ai/search - Búsqueda semántica de transacciones
- /ai/embeddings - Gestión de embeddings
- /ai/analyze - Análisis de gastos con AI
- /ai/health - Estado del sistema de AI
"""

import logging
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from finanzas_tracker.api.dependencies import get_active_profile, get_db
from finanzas_tracker.api.schemas.ai import (
    AnalyzeSpendingRequest,
    ChatRequest,
    ChatResponse,
    EmbeddingStatsResponse,
    GenerateEmbeddingsRequest,
    GenerateEmbeddingsResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResult,
    TransactionContext,
)
from finanzas_tracker.models.embedding import TransactionEmbedding
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.services.embedding_service import EmbeddingService
from finanzas_tracker.services.rag_service import RAGService


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI & RAG"])


# =============================================================================
# Health Check
# =============================================================================

@router.get("/health")
def ai_health_check(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Verifica el estado del sistema de AI.

    Retorna información sobre:
    - Disponibilidad de pgvector
    - Estado del modelo de embeddings
    - Disponibilidad de Claude API
    - Estadísticas generales
    """
    health: dict[str, Any] = {
        "status": "healthy",
        "components": {},
        "metrics": {},
    }

    # Check pgvector
    try:
        result = db.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        pgvector_available = result.fetchone() is not None
        health["components"]["pgvector"] = {
            "status": "available" if pgvector_available else "not_installed",
            "ok": pgvector_available,
        }
    except Exception as e:
        health["components"]["pgvector"] = {
            "status": "error",
            "ok": False,
            "error": str(e),
        }

    # Check embedding model
    try:
        start = time.time()
        embedding_service = EmbeddingService(db)
        model_load_time = time.time() - start
        health["components"]["embedding_model"] = {
            "status": "loaded",
            "ok": True,
            "model": embedding_service.model_name,
            "dimensions": embedding_service.embedding_dim,
            "load_time_ms": round(model_load_time * 1000, 2),
        }
    except Exception as e:
        health["components"]["embedding_model"] = {
            "status": "error",
            "ok": False,
            "error": str(e),
        }

    # Check Claude API
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    has_api_key = bool(api_key) and api_key.startswith("sk-ant-")
    health["components"]["claude_api"] = {
        "status": "configured" if has_api_key else "not_configured",
        "ok": has_api_key,
    }

    # Metrics
    try:
        total_embeddings = db.execute(
            select(func.count(TransactionEmbedding.id))
        ).scalar() or 0
        total_transactions = db.execute(
            select(func.count(Transaction.id)).where(
                Transaction.deleted_at.is_(None)
            )
        ).scalar() or 0
        health["metrics"] = {
            "total_embeddings": total_embeddings,
            "total_transactions": total_transactions,
            "coverage_percent": round(
                (total_embeddings / total_transactions * 100) if total_transactions > 0 else 0, 1
            ),
        }
    except Exception:
        pass

    # Overall status
    all_ok = all(
        c.get("ok", False)
        for c in health["components"].values()
    )
    health["status"] = "healthy" if all_ok else "degraded"

    return health


@router.post("/chat", response_model=ChatResponse)
def chat_with_context(
    request: ChatRequest,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_active_profile),
) -> ChatResponse:
    """
    Chat con contexto de transacciones usando RAG.

    Usa búsqueda semántica para encontrar transacciones relevantes
    y Claude AI para generar respuestas informadas.

    Ejemplos de preguntas:
    - "Cuánto gasté en comida este mes?"
    - "Mis compras más grandes de la semana"
    - "Analiza mis gastos en Uber"

    Nota: Requiere API key de Anthropic válida con créditos disponibles.
    """
    try:
        rag = RAGService(db)
        response = rag.chat(
            query=request.query,
            profile_id=profile.id,
            include_stats=request.include_stats,
            max_context_items=request.max_context,
        )

        # Convertir contextos a schema
        sources = [
            TransactionContext(
                transaction_id=ctx.transaction_id,
                comercio=ctx.comercio,
                monto_crc=ctx.monto_crc,
                fecha=ctx.fecha,
                categoria=ctx.categoria,
                similarity=ctx.similarity,
            )
            for ctx in response.sources
        ]

        return ChatResponse(
            answer=response.answer,
            sources=sources,
            model=response.model,
            usage=response.usage,
            query=response.query,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail={"error": str(e), "code": "AI_CONFIG_ERROR"},
        )
    except Exception as e:
        error_msg = str(e).lower()

        # Detectar errores específicos de Claude API
        if "credit balance is too low" in error_msg or "insufficient" in error_msg:
            logger.warning(f"Claude API sin créditos: {e}")
            raise HTTPException(
                status_code=402,  # Payment Required
                detail={
                    "error": "Créditos de Claude API insuficientes. El chat requiere créditos activos en Anthropic.",
                    "code": "INSUFFICIENT_CREDITS",
                    "suggestion": "Usa /api/v1/ai/search para búsqueda semántica gratuita.",
                },
            )
        if "api key" in error_msg or "authentication" in error_msg:
            logger.error(f"Claude API key inválida: {e}")
            raise HTTPException(
                status_code=401,
                detail={
                    "error": "API key de Claude inválida o no configurada.",
                    "code": "INVALID_API_KEY",
                },
            )
        if "rate limit" in error_msg:
            logger.warning(f"Claude API rate limit: {e}")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Límite de requests alcanzado. Intenta en unos minutos.",
                    "code": "RATE_LIMIT",
                },
            )
        logger.error(f"Error en chat RAG: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Error procesando chat", "code": "AI_CHAT_ERROR"},
        )


@router.post("/search", response_model=SemanticSearchResponse)
def semantic_search(
    request: SemanticSearchRequest,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_active_profile),
) -> SemanticSearchResponse:
    """
    Búsqueda semántica de transacciones.

    Encuentra transacciones similares a un texto usando
    embeddings vectoriales y pgvector.

    Útil para buscar por conceptos como:
    - "comida rápida" (encuentra McDonald's, Subway, etc.)
    - "suscripciones" (encuentra Netflix, Spotify, etc.)
    - "transporte" (encuentra Uber, gasolina, etc.)

    Si no hay embeddings, usa búsqueda por texto como fallback.
    """
    start_time = time.time()

    try:
        embedding_service = EmbeddingService(db)

        results = embedding_service.search_similar(
            query=request.query,
            profile_id=profile.id,
            limit=request.limit,
            min_similarity=request.min_similarity,
        )

        # Convertir a schema
        search_results = []
        for txn, similarity in results:
            categoria = None
            if txn.subcategory:
                categoria = f"{txn.subcategory.category.nombre} > {txn.subcategory.nombre}"

            text_content = ""
            if txn.embedding:
                text_content = txn.embedding.text_content

            search_results.append(
                SemanticSearchResult(
                    transaction_id=txn.id,
                    comercio=txn.comercio,
                    monto_crc=txn.monto_crc,
                    fecha=txn.fecha_transaccion,
                    categoria=categoria,
                    similarity=similarity,
                    text_content=text_content,
                )
            )

        elapsed = time.time() - start_time
        logger.debug(f"Búsqueda semántica completada en {elapsed:.3f}s, {len(search_results)} resultados")

        return SemanticSearchResponse(
            results=search_results,
            total=len(search_results),
            query=request.query,
            model=embedding_service.model_name,
        )

    except Exception as e:
        logger.warning(f"Búsqueda semántica falló, usando fallback: {e}")

        # Fallback: búsqueda simple por texto
        try:
            return _fallback_text_search(
                db=db,
                query=request.query,
                profile_id=profile.id,
                limit=request.limit,
            )
        except Exception as fallback_error:
            logger.error(f"Fallback también falló: {fallback_error}")
            raise HTTPException(
                status_code=500,
                detail={"error": "Error en búsqueda", "code": "SEARCH_ERROR"},
            )


def _fallback_text_search(
    db: Session,
    query: str,
    profile_id: str,
    limit: int,
) -> SemanticSearchResponse:
    """
    Búsqueda simple por texto cuando los embeddings no están disponibles.

    Busca coincidencias en comercio, categoría sugerida y notas.
    """
    logger.info(f"Usando fallback de búsqueda por texto para: {query}")

    # Búsqueda simple por ILIKE
    search_term = f"%{query}%"
    stmt = (
        select(Transaction)
        .where(
            Transaction.profile_id == profile_id,
            Transaction.deleted_at.is_(None),
            (
                Transaction.comercio.ilike(search_term) |
                Transaction.categoria_sugerida_por_ia.ilike(search_term) |
                Transaction.notas.ilike(search_term)
            ),
        )
        .order_by(Transaction.fecha_transaccion.desc())
        .limit(limit)
    )

    results = db.execute(stmt).scalars().all()

    search_results = [
        SemanticSearchResult(
            transaction_id=txn.id,
            comercio=txn.comercio,
            monto_crc=txn.monto_crc,
            fecha=txn.fecha_transaccion,
            categoria=txn.categoria_sugerida_por_ia,
            similarity=0.5,  # Fallback no tiene similarity real
            text_content=f"(Búsqueda por texto) {txn.comercio}",
        )
        for txn in results
    ]

    return SemanticSearchResponse(
        results=search_results,
        total=len(search_results),
        query=query,
        model="text-search-fallback",
    )


@router.get("/embeddings/stats", response_model=EmbeddingStatsResponse)
def get_embedding_stats(
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_active_profile),
) -> EmbeddingStatsResponse:
    """
    Obtiene estadísticas de embeddings para el perfil.

    Muestra cuántas transacciones tienen embedding generado
    y cuántas están pendientes.
    """
    # Total embeddings del perfil
    stmt = (
        select(func.count(TransactionEmbedding.id))
        .join(Transaction, Transaction.id == TransactionEmbedding.transaction_id)
        .where(Transaction.profile_id == profile.id)
    )
    total_embeddings = db.execute(stmt).scalar() or 0

    # Total transacciones del perfil
    stmt = (
        select(func.count(Transaction.id))
        .where(
            Transaction.profile_id == profile.id,
            Transaction.deleted_at.is_(None),
        )
    )
    total_transactions = db.execute(stmt).scalar() or 0

    # Embedding service para metadata
    embedding_service = EmbeddingService(db)

    return EmbeddingStatsResponse(
        total_embeddings=total_embeddings,
        total_transactions=total_transactions,
        pending_transactions=total_transactions - total_embeddings,
        model=embedding_service.model_name,
        embedding_dim=embedding_service.embedding_dim,
    )


@router.post("/embeddings/generate", response_model=GenerateEmbeddingsResponse)
def generate_embeddings(
    request: GenerateEmbeddingsRequest,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_active_profile),
) -> GenerateEmbeddingsResponse:
    """
    Genera embeddings para transacciones pendientes.

    Procesa todas las transacciones del perfil que no tienen
    embedding generado. Útil después de importar muchas
    transacciones nuevas.
    """
    try:
        embedding_service = EmbeddingService(db)

        count = embedding_service.embed_pending_transactions(
            profile_id=profile.id,
            batch_size=request.batch_size,
        )

        message = (
            f"Se generaron {count} embeddings" if count > 0
            else "Todas las transacciones ya tienen embedding"
        )

        return GenerateEmbeddingsResponse(
            generated=count,
            model=embedding_service.model_name,
            message=message,
        )

    except Exception as e:
        logger.error(f"Error generando embeddings: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Error generando embeddings", "code": "EMBEDDING_ERROR"},
        )


@router.post("/analyze/spending", response_model=ChatResponse)
def analyze_spending(
    request: AnalyzeSpendingRequest,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_active_profile),
) -> ChatResponse:
    """
    Analiza patrones de gasto con AI.

    Genera un análisis detallado de los gastos del usuario
    para un período específico, opcionalmente filtrado por categoría.
    """
    try:
        rag = RAGService(db)
        response = rag.analyze_spending(
            profile_id=profile.id,
            category=request.category,
            year=request.year,
            month=request.month,
        )

        sources = [
            TransactionContext(
                transaction_id=ctx.transaction_id,
                comercio=ctx.comercio,
                monto_crc=ctx.monto_crc,
                fecha=ctx.fecha,
                categoria=ctx.categoria,
                similarity=ctx.similarity,
            )
            for ctx in response.sources
        ]

        return ChatResponse(
            answer=response.answer,
            sources=sources,
            model=response.model,
            usage=response.usage,
            query=response.query,
        )

    except Exception as e:
        logger.error(f"Error en análisis de gastos: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Error en análisis", "code": "ANALYZE_ERROR"},
        )


@router.get("/analyze/savings", response_model=ChatResponse)
def suggest_savings(
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_active_profile),
) -> ChatResponse:
    """
    Sugiere áreas donde ahorrar dinero.

    Analiza las transacciones recientes y sugiere
    oportunidades de ahorro basadas en patrones de gasto.
    """
    try:
        rag = RAGService(db)
        response = rag.suggest_savings(profile_id=profile.id)

        sources = [
            TransactionContext(
                transaction_id=ctx.transaction_id,
                comercio=ctx.comercio,
                monto_crc=ctx.monto_crc,
                fecha=ctx.fecha,
                categoria=ctx.categoria,
                similarity=ctx.similarity,
            )
            for ctx in response.sources
        ]

        return ChatResponse(
            answer=response.answer,
            sources=sources,
            model=response.model,
            usage=response.usage,
            query=response.query,
        )

    except Exception as e:
        logger.error(f"Error en sugerencias de ahorro: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Error en sugerencias", "code": "SAVINGS_ERROR"},
        )


@router.get("/analyze/anomalies", response_model=ChatResponse)
def detect_anomalies(
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_active_profile),
) -> ChatResponse:
    """
    Detecta transacciones inusuales o anómalas.

    Revisa las transacciones recientes e identifica
    patrones inusuales o gastos fuera de lo normal.
    """
    try:
        rag = RAGService(db)
        response = rag.detect_anomalies(profile_id=profile.id)

        sources = [
            TransactionContext(
                transaction_id=ctx.transaction_id,
                comercio=ctx.comercio,
                monto_crc=ctx.monto_crc,
                fecha=ctx.fecha,
                categoria=ctx.categoria,
                similarity=ctx.similarity,
            )
            for ctx in response.sources
        ]

        return ChatResponse(
            answer=response.answer,
            sources=sources,
            model=response.model,
            usage=response.usage,
            query=response.query,
        )

    except Exception as e:
        logger.error(f"Error detectando anomalías: {e}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Error en detección", "code": "ANOMALY_ERROR"},
        )
