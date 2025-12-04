"""Servicio de insights financieros automaticos."""

__all__ = ["InsightsService", "Insight", "InsightType", "insights_service"]

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
import json
from typing import Any

import anthropic
from sqlalchemy.orm import joinedload

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.core.retry import retry_on_anthropic_error
from finanzas_tracker.models.category import Subcategory
from finanzas_tracker.models.transaction import Transaction


logger = get_logger(__name__)


class InsightType(Enum):
    """Tipos de insights."""

    SPENDING_INCREASE = "spending_increase"
    SPENDING_DECREASE = "spending_decrease"
    UNUSUAL_TRANSACTION = "unusual_transaction"
    TOP_CATEGORY = "top_category"
    SAVINGS_OPPORTUNITY = "savings_opportunity"
    RECURRING_EXPENSE = "recurring_expense"
    # Nuevos tipos AI-powered
    BEHAVIORAL_PATTERN = "behavioral_pattern"
    WEEKLY_PATTERN = "weekly_pattern"
    TIME_OF_DAY_PATTERN = "time_of_day_pattern"
    AI_RECOMMENDATION = "ai_recommendation"


@dataclass
class Insight:
    """Representa un insight financiero."""

    type: InsightType
    title: str
    description: str
    impact: str  # "positive", "negative", "neutral"
    value: float | None = None
    category: str | None = None
    recommendation: str | None = None


class InsightsService:
    """
    Servicio para generar insights financieros automaticos.

    Analiza transacciones y genera observaciones utiles como:
    - Comparacion con meses anteriores
    - Deteccion de gastos inusuales
    - Oportunidades de ahorro
    """

    def __init__(self) -> None:
        """Inicializa el servicio de insights."""
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        logger.info("InsightsService inicializado con Claude AI")

    def generate_insights(self, profile_id: str) -> list[Insight]:
        """
        Genera insights para un perfil.

        Args:
            profile_id: ID del perfil

        Returns:
            Lista de insights ordenados por relevancia
        """
        insights = []

        try:
            with get_session() as session:
                # Obtener datos
                data = self._get_analysis_data(session, profile_id)

                # Generar diferentes tipos de insights
                insights.extend(self._analyze_spending_trends(data))
                insights.extend(self._analyze_unusual_transactions(data))
                insights.extend(self._analyze_top_categories(data))
                insights.extend(self._analyze_recurring_expenses(data))
                insights.extend(self._analyze_savings_opportunities(data))

                # Nuevos análisis AI-powered
                insights.extend(self._analyze_behavioral_patterns(data))
                insights.extend(self._analyze_time_patterns(data))
                insights.extend(self._generate_ai_insights(data, profile_id))

        except Exception as e:
            logger.error(f"Error generando insights: {e}")

        # Ordenar por impacto (negativos primero)
        priority = {"negative": 0, "neutral": 1, "positive": 2}
        insights.sort(key=lambda x: priority.get(x.impact, 1))

        return insights[:10]  # Maximo 10 insights

    def _get_analysis_data(self, session, profile_id: str) -> dict[str, Any]:
        """Obtiene datos para analisis."""
        today = date.today()
        first_day_month = today.replace(day=1)
        last_month_start = (first_day_month - timedelta(days=1)).replace(day=1)
        (last_month_start - timedelta(days=1)).replace(day=1)

        # Transacciones por periodo (eager load para evitar N+1)
        current_month = (
            session.query(Transaction)
            .options(joinedload(Transaction.subcategory).joinedload(Subcategory.category))
            .filter(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion >= first_day_month,
                Transaction.deleted_at.is_(None),
            )
            .all()
        )

        last_month = (
            session.query(Transaction)
            .options(joinedload(Transaction.subcategory).joinedload(Subcategory.category))
            .filter(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion >= last_month_start,
                Transaction.fecha_transaccion < first_day_month,
                Transaction.deleted_at.is_(None),
            )
            .all()
        )

        # Calcular promedios
        avg_transaction_current = (
            sum(t.monto_crc for t in current_month) / len(current_month)
            if current_month
            else Decimal("0")
        )

        # Gastos por categoria
        by_category_current = {}
        by_category_last = {}

        for t in current_month:
            cat = t.subcategory.category.nombre if t.subcategory else "Sin categorizar"
            by_category_current[cat] = by_category_current.get(cat, Decimal("0")) + t.monto_crc

        for t in last_month:
            cat = t.subcategory.category.nombre if t.subcategory else "Sin categorizar"
            by_category_last[cat] = by_category_last.get(cat, Decimal("0")) + t.monto_crc

        # Gastos por comercio
        by_merchant = {}
        for t in current_month:
            if t.comercio not in by_merchant:
                by_merchant[t.comercio] = {"count": 0, "total": Decimal("0"), "transactions": []}
            by_merchant[t.comercio]["count"] += 1
            by_merchant[t.comercio]["total"] += t.monto_crc
            by_merchant[t.comercio]["transactions"].append(t)

        return {
            "current_month": current_month,
            "last_month": last_month,
            "total_current": sum(t.monto_crc for t in current_month),
            "total_last": sum(t.monto_crc for t in last_month),
            "avg_transaction": avg_transaction_current,
            "by_category_current": by_category_current,
            "by_category_last": by_category_last,
            "by_merchant": by_merchant,
        }

    def _analyze_spending_trends(self, data: dict) -> list[Insight]:
        """Analiza tendencias de gasto."""
        insights = []
        total_current = float(data["total_current"])
        total_last = float(data["total_last"])

        if total_last > 0:
            change_pct = ((total_current - total_last) / total_last) * 100

            if change_pct > 20:
                insights.append(
                    Insight(
                        type=InsightType.SPENDING_INCREASE,
                        title="Gasto aumentado significativamente",
                        description=f"Has gastado {change_pct:.0f}% mas que el mes pasado",
                        impact="negative",
                        value=change_pct,
                        recommendation="Revisa tus gastos y busca areas donde puedas reducir",
                    )
                )
            elif change_pct < -20:
                insights.append(
                    Insight(
                        type=InsightType.SPENDING_DECREASE,
                        title="Excelente control de gastos",
                        description=f"Has reducido tus gastos en {abs(change_pct):.0f}% respecto al mes pasado",
                        impact="positive",
                        value=abs(change_pct),
                        recommendation="Sigue asi! Considera mover el ahorro a una cuenta de inversion",
                    )
                )

        return insights

    def _analyze_unusual_transactions(self, data: dict) -> list[Insight]:
        """Detecta transacciones inusuales."""
        insights = []
        avg = float(data["avg_transaction"])

        if avg > 0:
            threshold = avg * 3  # 3x el promedio

            for t in data["current_month"]:
                if float(t.monto_crc) > threshold:
                    insights.append(
                        Insight(
                            type=InsightType.UNUSUAL_TRANSACTION,
                            title=f"Gasto inusual en {t.comercio}",
                            description=f"₡{float(t.monto_crc):,.0f} es {float(t.monto_crc) / avg:.1f}x tu promedio",
                            impact="neutral",
                            value=float(t.monto_crc),
                            recommendation="Verifica que esta transaccion sea correcta",
                        )
                    )

        return insights[:3]  # Max 3 inusuales

    def _analyze_top_categories(self, data: dict) -> list[Insight]:
        """Analiza categorias principales."""
        insights = []
        by_cat = data["by_category_current"]
        total = float(data["total_current"])

        if by_cat and total > 0:
            top_cat = max(by_cat.items(), key=lambda x: x[1])
            pct = (float(top_cat[1]) / total) * 100

            if pct > 40:
                insights.append(
                    Insight(
                        type=InsightType.TOP_CATEGORY,
                        title=f"Alta concentracion en {top_cat[0]}",
                        description=f"El {pct:.0f}% de tus gastos estan en esta categoria",
                        impact="neutral",
                        value=pct,
                        category=top_cat[0],
                        recommendation="Considera diversificar o revisar si estos gastos son necesarios",
                    )
                )

        return insights

    def _analyze_recurring_expenses(self, data: dict) -> list[Insight]:
        """Detecta gastos recurrentes."""
        insights = []

        for merchant, info in data["by_merchant"].items():
            if info["count"] >= 4:  # 4+ visitas al mes
                insights.append(
                    Insight(
                        type=InsightType.RECURRING_EXPENSE,
                        title=f"Gasto frecuente en {merchant}",
                        description=f"{info['count']} visitas, ₡{float(info['total']):,.0f} total",
                        impact="neutral",
                        value=float(info["total"]),
                        recommendation="Evalua si puedes reducir frecuencia o buscar alternativas",
                    )
                )

        return insights[:2]

    def _analyze_savings_opportunities(self, data: dict) -> list[Insight]:
        """Identifica oportunidades de ahorro."""
        insights = []
        current = data["by_category_current"]
        last = data["by_category_last"]

        # Categorias que aumentaron mucho
        for cat, amount in current.items():
            last_amount = last.get(cat, Decimal("0"))
            if last_amount > 0:
                increase = ((amount - last_amount) / last_amount) * 100
                if increase > 50 and float(amount) > 10000:
                    insights.append(
                        Insight(
                            type=InsightType.SAVINGS_OPPORTUNITY,
                            title=f"Oportunidad de ahorro en {cat}",
                            description=f"Aumento del {increase:.0f}% respecto al mes pasado",
                            impact="negative",
                            value=float(amount - last_amount),
                            category=cat,
                            recommendation=f"Podrias ahorrar ₡{float(amount - last_amount):,.0f} volviendo al nivel anterior",
                        )
                    )

        return insights[:2]

    def _analyze_behavioral_patterns(self, data: dict) -> list[Insight]:
        """Analiza patrones de comportamiento de gasto."""
        insights = []

        try:
            # Detectar si gasta más en fin de semana
            weekend_spending = Decimal("0")
            weekday_spending = Decimal("0")
            weekend_count = 0
            weekday_count = 0

            for t in data["current_month"]:
                is_weekend = t.fecha_transaccion.weekday() >= 5  # Sábado=5, Domingo=6
                if is_weekend:
                    weekend_spending += t.monto_crc
                    weekend_count += 1
                else:
                    weekday_spending += t.monto_crc
                    weekday_count += 1

            # Calcular promedio por día
            avg_weekend = (
                (weekend_spending / (weekend_count / 7)) if weekend_count > 0 else Decimal("0")
            )
            avg_weekday = (
                (weekday_spending / (weekday_count / 7)) if weekday_count > 0 else Decimal("0")
            )

            if avg_weekend > 0 and avg_weekday > 0:
                if avg_weekend > avg_weekday * Decimal("1.5"):
                    diff_pct = ((avg_weekend - avg_weekday) / avg_weekday) * 100
                    insights.append(
                        Insight(
                            type=InsightType.BEHAVIORAL_PATTERN,
                            title="Gastas más en fines de semana",
                            description=f"Promedio fin de semana: ₡{float(avg_weekend):,.0f} vs "
                            f"entre semana: ₡{float(avg_weekday):,.0f} ({diff_pct:.0f}% más)",
                            impact="neutral",
                            value=float(avg_weekend - avg_weekday),
                            recommendation="Considera planificar actividades de fin de semana "
                            "más económicas o establecer un presupuesto específico",
                        )
                    )

            # Detectar concentración de gastos pequeños
            small_transactions = [
                t for t in data["current_month"] if float(t.monto_crc) < 5000
            ]
            if len(small_transactions) > 20:
                total_small = sum(float(t.monto_crc) for t in small_transactions)
                pct_of_total = (total_small / float(data["total_current"])) * 100

                if pct_of_total > 30:
                    insights.append(
                        Insight(
                            type=InsightType.BEHAVIORAL_PATTERN,
                            title="Muchos gastos pequeños",
                            description=f"{len(small_transactions)} transacciones menores a ₡5,000 "
                            f"suman ₡{total_small:,.0f} ({pct_of_total:.0f}% del total)",
                            impact="neutral",
                            value=total_small,
                            recommendation="Los gastos pequeños se acumulan. Considera usar efectivo "
                            "o una app de presupuesto diario para estos gastos",
                        )
                    )

        except Exception as e:
            logger.error(f"Error analizando patrones de comportamiento: {e}")

        return insights

    def _analyze_time_patterns(self, data: dict) -> list[Insight]:
        """Analiza patrones temporales de gasto."""
        insights = []

        try:
            # Agrupar por hora del día
            by_hour = {}
            for t in data["current_month"]:
                hour = t.fecha_transaccion.hour
                time_slot = self._get_time_slot(hour)
                if time_slot not in by_hour:
                    by_hour[time_slot] = {"count": 0, "total": Decimal("0")}
                by_hour[time_slot]["count"] += 1
                by_hour[time_slot]["total"] += t.monto_crc

            # Detectar slot con más gasto
            if by_hour:
                max_slot = max(by_hour.items(), key=lambda x: x[1]["total"])
                slot_name, slot_data = max_slot
                total = float(data["total_current"])
                pct = (float(slot_data["total"]) / total) * 100 if total > 0 else 0

                if pct > 40:
                    insights.append(
                        Insight(
                            type=InsightType.TIME_OF_DAY_PATTERN,
                            title=f"Gastas más en {slot_name}",
                            description=f"{slot_data['count']} transacciones, "
                            f"₡{float(slot_data['total']):,.0f} ({pct:.0f}% del total)",
                            impact="neutral",
                            value=float(slot_data["total"]),
                            recommendation=f"Tus gastos se concentran en {slot_name}. "
                            "Esto puede ser normal según tu rutina, pero vale la pena revisarlo",
                        )
                    )

            # Detectar gastos nocturnos (posible entretenimiento/impulso)
            night_transactions = [
                t
                for t in data["current_month"]
                if t.fecha_transaccion.hour >= 22 or t.fecha_transaccion.hour <= 2
            ]

            if len(night_transactions) >= 5:
                total_night = sum(float(t.monto_crc) for t in night_transactions)
                insights.append(
                    Insight(
                        type=InsightType.TIME_OF_DAY_PATTERN,
                        title="Gastos nocturnos frecuentes",
                        description=f"{len(night_transactions)} transacciones entre 10pm-2am "
                        f"totalizan ₡{total_night:,.0f}",
                        impact="neutral",
                        value=total_night,
                        recommendation="Los gastos nocturnos suelen ser por entretenimiento o "
                        "compras impulsivas. Considera establecer un límite para estas ocasiones",
                    )
                )

        except Exception as e:
            logger.error(f"Error analizando patrones temporales: {e}")

        return insights

    def _get_time_slot(self, hour: int) -> str:
        """Convierte hora en slot de tiempo."""
        if 6 <= hour < 12:
            return "mañanas (6am-12pm)"
        if 12 <= hour < 18:
            return "tardes (12pm-6pm)"
        if 18 <= hour < 22:
            return "noches (6pm-10pm)"
        return "madrugadas (10pm-6am)"

    @retry_on_anthropic_error(max_attempts=2, max_wait=8)
    def _generate_ai_insights(self, data: dict, profile_id: str) -> list[Insight]:
        """Genera insights usando Claude AI para análisis profundo."""
        insights = []

        try:
            # Preparar contexto para Claude
            context = self._prepare_ai_context(data)

            # Solo generar si hay suficientes datos
            if len(data["current_month"]) < 5:
                return insights

            prompt = f"""Eres un asesor financiero experto analizando el comportamiento de gastos de un usuario.

DATOS DEL MES ACTUAL:
{json.dumps(context, indent=2, ensure_ascii=False)}

TAREA:
Analiza estos datos y genera 1-2 insights ACCIONABLES y ESPECÍFICOS que no sean obvios.
NO repitas información básica (como "gastaste más este mes").
Busca patrones sutiles, tendencias preocupantes, o oportunidades reales.

Responde ÚNICAMENTE con un JSON válido:
{{
  "insights": [
    {{
      "title": "Título corto y específico",
      "description": "Descripción clara del hallazgo (1-2 oraciones)",
      "recommendation": "Acción concreta que puede tomar",
      "impact": "positive/negative/neutral"
    }}
  ]
}}"""

            # Llamar a Claude Haiku para análisis
            response = self.client.messages.create(
                model=settings.claude_model,
                max_tokens=600,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )

            response_text = response.content[0].text.strip()

            # Parsear respuesta
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()

            result = json.loads(response_text)

            # Convertir a objetos Insight
            for ai_insight in result.get("insights", [])[:2]:  # Max 2 AI insights
                insights.append(
                    Insight(
                        type=InsightType.AI_RECOMMENDATION,
                        title=f"💡 {ai_insight['title']}",
                        description=ai_insight["description"],
                        impact=ai_insight.get("impact", "neutral"),
                        recommendation=ai_insight["recommendation"],
                    )
                )

            logger.info(f"✨ Generados {len(insights)} insights con Claude AI")

        except Exception as e:
            logger.error(f"Error generando insights con AI: {e}")

        return insights

    def _prepare_ai_context(self, data: dict) -> dict[str, Any]:
        """Prepara contexto resumido para Claude."""
        # Top 5 categorías
        top_categories = sorted(
            data["by_category_current"].items(), key=lambda x: x[1], reverse=True
        )[:5]

        # Top 5 comercios
        top_merchants = sorted(
            data["by_merchant"].items(), key=lambda x: x[1]["total"], reverse=True
        )[:5]

        # Estadísticas básicas
        current_transactions = data["current_month"]
        avg_transaction = float(data["avg_transaction"])

        return {
            "total_gastado": float(data["total_current"]),
            "numero_transacciones": len(current_transactions),
            "promedio_por_transaccion": avg_transaction,
            "cambio_vs_mes_anterior": (
                float(
                    ((data["total_current"] - data["total_last"]) / data["total_last"]) * 100
                )
                if data["total_last"] > 0
                else 0
            ),
            "top_categorias": [
                {"nombre": cat, "monto": float(amt)} for cat, amt in top_categories
            ],
            "top_comercios": [
                {
                    "nombre": merchant,
                    "visitas": info["count"],
                    "total": float(info["total"]),
                }
                for merchant, info in top_merchants
            ],
        }


# Singleton
insights_service = InsightsService()
