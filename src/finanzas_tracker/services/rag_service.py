"""
Servicio RAG (Retrieval-Augmented Generation) para chat financiero.

Combina búsqueda semántica con pgvector + Claude AI para
responder preguntas sobre finanzas personales con contexto
de las transacciones del usuario.

Ejemplo de uso:
```python
rag = RAGService(db_session)

# Chat con contexto
response = rag.chat(
    query="Cuánto gasté en comida este mes?", profile_id="abc123"
)
print(response.answer)  # "Este mes gastaste ₡45,000 en comida..."
print(response.sources)  # Transacciones usadas como contexto
```
"""

__all__ = ["RAGService", "RAGResponse", "RAGContext"]

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
import logging
from typing import TYPE_CHECKING, cast

from anthropic import Anthropic
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finanzas_tracker.config.settings import Settings
from finanzas_tracker.core.claude_credits import can_use_claude, handle_claude_error
from finanzas_tracker.services.embedding_service import EmbeddingService


if TYPE_CHECKING:
    from finanzas_tracker.models.transaction import Transaction


logger = logging.getLogger(__name__)


@dataclass
class RAGContext:
    """Contexto de una transacción para RAG."""

    transaction_id: str
    comercio: str
    monto_crc: Decimal
    fecha: datetime
    categoria: str | None
    similarity: float
    text_content: str

    def to_prompt_text(self) -> str:
        """Convierte a texto para incluir en el prompt."""
        fecha_str = self.fecha.strftime("%Y-%m-%d")
        cat_str = f" ({self.categoria})" if self.categoria else ""
        return f"- {self.comercio}{cat_str}: ₡{self.monto_crc:,.0f} el {fecha_str}"


@dataclass
class RAGResponse:
    """Respuesta del servicio RAG."""

    answer: str
    sources: list[RAGContext] = field(default_factory=list)
    model: str = ""
    usage: dict = field(default_factory=dict)
    query: str = ""


SYSTEM_PROMPT = """Eres un asistente financiero personal para Costa Rica. Tu usuario es Sebastián.

Tu rol es ayudar a analizar gastos, dar insights sobre patrones de consumo,
y responder preguntas sobre transacciones financieras.

Contexto importante:
- CRC = Colones costarricenses (moneda local de Costa Rica)
- ₡ es el símbolo del colón
- Los montos grandes son comunes (₡10,000 ≈ $20 USD aproximadamente)
- SINPE Móvil es el sistema de pagos instantáneos más usado en Costa Rica

Reglas:
1. Responde siempre en español
2. Usa el símbolo ₡ para colones
3. Formatea montos con separador de miles: ₡15,000
4. Sé conciso pero informativo
5. Si no tienes información suficiente, dilo claramente
6. Basa tus respuestas en las transacciones proporcionadas como contexto
7. Menciona la fuente de tus datos cuando sea relevante

Si te preguntan algo que no puedes responder con los datos disponibles,
sugiere qué información adicional necesitarías."""


class RAGService:
    """
    Servicio RAG para chat financiero con contexto.

    Combina:
    1. Búsqueda semántica (pgvector) para encontrar transacciones relevantes
    2. Claude AI para generar respuestas informadas

    El flujo es:
    1. Usuario hace pregunta: "Cuánto gasté en comida?"
    2. Se buscan transacciones similares a "comida"
    3. Se construye prompt con el contexto encontrado
    4. Claude genera respuesta basada en datos reales
    """

    def __init__(
        self,
        db: Session,
        settings: Settings | None = None,
    ) -> None:
        """
        Inicializa el servicio RAG.

        Args:
            db: Sesión de SQLAlchemy
            settings: Configuración (opcional)
        """
        self.db = db
        self.settings = settings or Settings()
        self.embedding_service = EmbeddingService(db, settings)
        self._anthropic: Anthropic | None = None

    def _get_anthropic_client(self) -> Anthropic:
        """Obtiene o crea el cliente de Anthropic."""
        if self._anthropic is None:
            api_key = self.settings.anthropic_api_key
            if not api_key:
                msg = "ANTHROPIC_API_KEY no está configurado"
                raise ValueError(msg)
            self._anthropic = Anthropic(api_key=api_key)
        return self._anthropic

    def _search_relevant_transactions(
        self,
        query: str,
        profile_id: str,
        limit: int = 10,
    ) -> list[tuple["Transaction", float]]:
        """
        Busca transacciones relevantes para la query.

        Args:
            query: Pregunta del usuario
            profile_id: ID del perfil
            limit: Número máximo de resultados

        Returns:
            Lista de (Transaction, similitud)
        """
        return self.embedding_service.search_similar(
            query=query,
            profile_id=profile_id,
            limit=limit,
            min_similarity=0.3,  # Threshold bajo para incluir más contexto
        )

    def _build_context(
        self,
        transactions: list[tuple["Transaction", float]],
    ) -> list[RAGContext]:
        """
        Construye contexto RAG desde transacciones.

        Args:
            transactions: Lista de (Transaction, similitud)

        Returns:
            Lista de RAGContext
        """
        contexts = []
        for txn, similarity in transactions:
            # Obtener nombre de categoría si existe
            categoria = None
            if txn.subcategory:
                categoria = f"{txn.subcategory.category.nombre} > {txn.subcategory.nombre}"

            # Obtener texto del embedding si existe
            text_content = ""
            if txn.embedding:
                text_content = txn.embedding.text_content

            ctx = RAGContext(
                transaction_id=txn.id,
                comercio=txn.comercio,
                monto_crc=txn.monto_crc,
                fecha=txn.fecha_transaccion,
                categoria=categoria,
                similarity=similarity,
                text_content=text_content,
            )
            contexts.append(ctx)

        return contexts

    def _build_prompt_with_context(
        self,
        query: str,
        contexts: list[RAGContext],
        additional_stats: dict | None = None,
    ) -> str:
        """
        Construye el prompt con contexto de transacciones.

        Args:
            query: Pregunta del usuario
            contexts: Contextos de transacciones relevantes
            additional_stats: Estadísticas adicionales

        Returns:
            Prompt completo para Claude
        """
        parts = []

        # Transacciones relevantes
        if contexts:
            parts.append("## Transacciones relevantes encontradas:")
            for ctx in contexts:
                parts.append(ctx.to_prompt_text())
            parts.append("")

        # Estadísticas adicionales
        if additional_stats:
            parts.append("## Estadísticas adicionales:")
            for key, value in additional_stats.items():
                parts.append(f"- {key}: {value}")
            parts.append("")

        # Pregunta
        parts.append("## Pregunta del usuario:")
        parts.append(query)

        return "\n".join(parts)

    def _get_monthly_stats(
        self,
        profile_id: str,
        year: int | None = None,
        month: int | None = None,
    ) -> dict:
        """
        Obtiene estadísticas mensuales para contexto adicional.

        Args:
            profile_id: ID del perfil
            year: Año (default: actual)
            month: Mes (default: actual)

        Returns:
            Diccionario con estadísticas
        """
        from finanzas_tracker.models.transaction import Transaction

        now = datetime.now()
        year = year or now.year
        month = month or now.month

        # Total gastado este mes
        sum_stmt = select(func.sum(Transaction.monto_crc)).where(
            Transaction.profile_id == profile_id,
            Transaction.deleted_at.is_(None),
            func.extract("year", Transaction.fecha_transaccion) == year,
            func.extract("month", Transaction.fecha_transaccion) == month,
        )
        total_mes = self.db.execute(sum_stmt).scalar() or Decimal("0")

        # Número de transacciones
        count_stmt = select(func.count(Transaction.id)).where(
            Transaction.profile_id == profile_id,
            Transaction.deleted_at.is_(None),
            func.extract("year", Transaction.fecha_transaccion) == year,
            func.extract("month", Transaction.fecha_transaccion) == month,
        )
        num_txns = self.db.execute(count_stmt).scalar() or 0

        return {
            f"Total gastado ({month}/{year})": f"₡{total_mes:,.0f}",
            "Número de transacciones": num_txns,
        }

    def chat(
        self,
        query: str,
        profile_id: str,
        include_stats: bool = True,
        max_context_items: int = 10,
        model: str | None = None,
    ) -> RAGResponse:
        """
        Responde una pregunta con contexto de transacciones.

        Args:
            query: Pregunta del usuario
            profile_id: ID del perfil
            include_stats: Incluir estadísticas mensuales
            max_context_items: Máximo de transacciones como contexto
            model: Modelo de Claude a usar

        Returns:
            RAGResponse con la respuesta y fuentes
        """
        default_model = "claude-haiku-4-5-20251001"
        model_to_use: str = model or cast(
            str, getattr(self.settings, "claude_model", default_model)
        ) or default_model

        # 0. Verificar si podemos usar Claude (sin llamar a la API)
        can_use, reason = can_use_claude()
        if not can_use:
            logger.info(f"⏭️ RAG no disponible: {reason}")
            return RAGResponse(
                answer="🤖 El asistente de IA no está disponible en este momento.",
                sources=[],
                model=model_to_use,
                usage={"input_tokens": 0, "output_tokens": 0},
                query=query,
            )

        # 1. Buscar transacciones relevantes
        relevant_txns = self._search_relevant_transactions(
            query=query,
            profile_id=profile_id,
            limit=max_context_items,
        )

        # 2. Construir contexto
        contexts = self._build_context(relevant_txns)

        # 3. Obtener estadísticas adicionales
        additional_stats = None
        if include_stats:
            additional_stats = self._get_monthly_stats(profile_id)

        # 4. Construir prompt
        user_prompt = self._build_prompt_with_context(
            query=query,
            contexts=contexts,
            additional_stats=additional_stats,
        )

        # 5. Llamar a Claude
        client = self._get_anthropic_client()

        logger.info(f"RAG query: {query[:50]}... con {len(contexts)} transacciones de contexto")

        response = client.messages.create(
            model=model_to_use,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # 6. Construir respuesta
        first_block = response.content[0] if response.content else None
        answer = first_block.text if first_block and hasattr(first_block, "text") else ""

        return RAGResponse(
            answer=answer,
            sources=contexts,
            model=model_to_use,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            query=query,
        )

    def analyze_spending(
        self,
        profile_id: str,
        category: str | None = None,
        year: int | None = None,
        month: int | None = None,
    ) -> RAGResponse:
        """
        Analiza patrones de gasto con AI.

        Args:
            profile_id: ID del perfil
            category: Categoría específica a analizar
            year: Año a analizar
            month: Mes a analizar

        Returns:
            RAGResponse con análisis
        """
        now = datetime.now()
        year = year or now.year
        month = month or now.month

        if category:
            query = f"Analiza mis gastos en {category} durante {month}/{year}"
        else:
            query = f"Dame un análisis de mis gastos de {month}/{year}"

        return self.chat(
            query=query,
            profile_id=profile_id,
            include_stats=True,
            max_context_items=20,  # Más contexto para análisis
        )

    def suggest_savings(
        self,
        profile_id: str,
    ) -> RAGResponse:
        """
        Sugiere áreas donde el usuario puede ahorrar.

        Args:
            profile_id: ID del perfil

        Returns:
            RAGResponse con sugerencias
        """
        query = (
            "Analiza mis transacciones recientes y sugiere "
            "áreas donde podría ahorrar dinero. Identifica patrones "
            "de gasto repetitivo o gastos que podrían reducirse."
        )

        return self.chat(
            query=query,
            profile_id=profile_id,
            include_stats=True,
            max_context_items=30,
        )

    def detect_anomalies(
        self,
        profile_id: str,
    ) -> RAGResponse:
        """
        Detecta transacciones inusuales o anómalas.

        Args:
            profile_id: ID del perfil

        Returns:
            RAGResponse con análisis de anomalías
        """
        query = (
            "Revisa mis transacciones recientes e identifica "
            "cualquier gasto inusual, anómalo o que parezca fuera "
            "de mis patrones normales de consumo."
        )

        return self.chat(
            query=query,
            profile_id=profile_id,
            include_stats=True,
            max_context_items=30,
        )
