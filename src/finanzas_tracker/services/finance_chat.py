"""Servicio de chat con finanzas usando Claude AI."""

__all__ = ["FinanceChatService", "finance_chat_service"]

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import anthropic
from sqlalchemy.orm import joinedload

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.core.retry import retry_on_anthropic_error
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.transaction import Transaction


logger = get_logger(__name__)


class FinanceChatService:
    """
    Servicio para chatear sobre finanzas personales usando Claude AI.

    Permite hacer preguntas en lenguaje natural como:
    - "Cuanto gaste en comida este mes?"
    - "Cual es mi gasto mas alto?"
    - "Como se distribuyen mis gastos?"
    """

    def __init__(self) -> None:
        """Inicializa el servicio de chat."""
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.model = settings.claude_model
        logger.info("FinanceChatService inicializado")

    @retry_on_anthropic_error(max_attempts=3, max_wait=16)
    def _call_claude_api(self, prompt: str) -> str:
        """
        Llama a Claude API con retry logic.

        Args:
            prompt: Prompt para Claude

        Returns:
            str: Respuesta de Claude

        Raises:
            anthropic.APIError: Si la llamada falla después de todos los intentos
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def chat(self, question: str, profile_id: str) -> str:
        """
        Responde una pregunta sobre finanzas.

        Args:
            question: Pregunta del usuario en lenguaje natural
            profile_id: ID del perfil del usuario

        Returns:
            Respuesta en lenguaje natural
        """
        try:
            # 1. Obtener contexto financiero
            context = self._get_financial_context(profile_id)

            # 2. Construir prompt
            prompt = self._build_prompt(question, context)

            # 3. Llamar a Claude con retry logic
            answer = self._call_claude_api(prompt)
            logger.info(f"Chat respondido: {question[:50]}...")
            return answer

        except anthropic.APIConnectionError as e:
            logger.error(f"Error de conexion con Claude: {e}")
            return "Lo siento, no puedo conectarme al servicio de IA en este momento."
        except anthropic.RateLimitError:
            logger.warning("Rate limit alcanzado en Claude API")
            return "El servicio esta saturado. Intenta de nuevo en unos minutos."
        except Exception as e:
            logger.error(f"Error en chat: {type(e).__name__}: {e}")
            return f"Ocurrio un error procesando tu pregunta: {e}"

    def _get_financial_context(self, profile_id: str) -> dict[str, Any]:
        """Obtiene el contexto financiero del usuario."""
        with get_session() as session:
            today = date.today()
            first_day_month = today.replace(day=1)
            last_month_start = (first_day_month - timedelta(days=1)).replace(day=1)

            # Transacciones del mes actual (eager load subcategory->category)
            transactions_this_month = (
                session.query(Transaction)
                .options(joinedload(Transaction.subcategory).joinedload(Subcategory.category))
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.fecha_transaccion >= first_day_month,
                    Transaction.deleted_at.is_(None),
                )
                .all()
            )

            # Transacciones del mes pasado
            transactions_last_month = (
                session.query(Transaction)
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.fecha_transaccion >= last_month_start,
                    Transaction.fecha_transaccion < first_day_month,
                    Transaction.deleted_at.is_(None),
                )
                .all()
            )

            # Ingresos del mes
            incomes_this_month = (
                session.query(Income)
                .filter(
                    Income.profile_id == profile_id,
                    Income.fecha >= first_day_month,
                    Income.deleted_at.is_(None),
                )
                .all()
            )

            # Categorias
            categories = session.query(Category).all()
            session.query(Subcategory).all()

            # Calcular metricas
            total_gastos_mes = sum(t.monto_crc for t in transactions_this_month)
            total_gastos_mes_pasado = sum(t.monto_crc for t in transactions_last_month)
            total_ingresos_mes = sum(i.monto_crc for i in incomes_this_month)

            # Gastos por categoria
            gastos_por_categoria = {}
            for t in transactions_this_month:
                if t.subcategory:
                    cat_name = t.subcategory.category.nombre
                    if cat_name not in gastos_por_categoria:
                        gastos_por_categoria[cat_name] = Decimal("0")
                    gastos_por_categoria[cat_name] += t.monto_crc

            # Top 5 gastos
            top_gastos = sorted(
                transactions_this_month,
                key=lambda x: x.monto_crc,
                reverse=True,
            )[:5]

            # Top comercios
            comercios = {}
            for t in transactions_this_month:
                if t.comercio not in comercios:
                    comercios[t.comercio] = {"count": 0, "total": Decimal("0")}
                comercios[t.comercio]["count"] += 1
                comercios[t.comercio]["total"] += t.monto_crc

            top_comercios = sorted(
                comercios.items(),
                key=lambda x: x[1]["total"],
                reverse=True,
            )[:5]

            return {
                "fecha_actual": today.strftime("%d/%m/%Y"),
                "mes_actual": today.strftime("%B %Y"),
                "total_transacciones_mes": len(transactions_this_month),
                "total_gastos_mes": float(total_gastos_mes),
                "total_gastos_mes_pasado": float(total_gastos_mes_pasado),
                "total_ingresos_mes": float(total_ingresos_mes),
                "balance_mes": float(total_ingresos_mes - total_gastos_mes),
                "gastos_por_categoria": {k: float(v) for k, v in gastos_por_categoria.items()},
                "top_5_gastos": [
                    {
                        "comercio": t.comercio,
                        "monto": float(t.monto_crc),
                        "fecha": t.fecha_transaccion.strftime("%d/%m"),
                        "categoria": t.subcategory.nombre if t.subcategory else "Sin categorizar",
                    }
                    for t in top_gastos
                ],
                "top_comercios": [
                    {"nombre": nombre, "visitas": data["count"], "total": float(data["total"])}
                    for nombre, data in top_comercios
                ],
                "categorias_disponibles": [c.nombre for c in categories],
            }

    def _build_prompt(self, question: str, context: dict[str, Any]) -> str:
        """Construye el prompt para Claude."""
        return f"""Eres un asistente financiero personal amigable. Responde preguntas sobre finanzas de manera clara y concisa.

CONTEXTO FINANCIERO DEL USUARIO:
- Fecha actual: {context['fecha_actual']}
- Mes: {context['mes_actual']}

RESUMEN DEL MES:
- Total de transacciones: {context['total_transacciones_mes']}
- Total gastado: ₡{context['total_gastos_mes']:,.0f}
- Total ingresos: ₡{context['total_ingresos_mes']:,.0f}
- Balance: ₡{context['balance_mes']:,.0f}
- Gasto mes pasado: ₡{context['total_gastos_mes_pasado']:,.0f}

GASTOS POR CATEGORIA:
{self._format_gastos_categoria(context['gastos_por_categoria'])}

TOP 5 GASTOS MAS ALTOS:
{self._format_top_gastos(context['top_5_gastos'])}

COMERCIOS MAS FRECUENTES:
{self._format_top_comercios(context['top_comercios'])}

PREGUNTA DEL USUARIO: {question}

Responde de manera amigable, usa emojis ocasionalmente, y da consejos practicos si es relevante.
Si no tienes datos suficientes para responder, indícalo claramente.
Responde en español y usa colones (₡) para montos."""

    def _format_gastos_categoria(self, gastos: dict[str, float]) -> str:
        """Formatea gastos por categoria."""
        if not gastos:
            return "- Sin datos de categorias"
        return "\n".join(f"- {cat}: ₡{monto:,.0f}" for cat, monto in gastos.items())

    def _format_top_gastos(self, gastos: list[dict]) -> str:
        """Formatea top gastos."""
        if not gastos:
            return "- Sin transacciones registradas"
        return "\n".join(
            f"- {g['comercio']}: ₡{g['monto']:,.0f} ({g['fecha']}) - {g['categoria']}"
            for g in gastos
        )

    def _format_top_comercios(self, comercios: list[dict]) -> str:
        """Formatea top comercios."""
        if not comercios:
            return "- Sin datos de comercios"
        return "\n".join(
            f"- {c['nombre']}: {c['visitas']} visitas, ₡{c['total']:,.0f} total" for c in comercios
        )


# Singleton
finance_chat_service = FinanceChatService()
