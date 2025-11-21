"""Servicio de insights financieros automaticos."""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.category import Category
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
        logger.info("InsightsService inicializado")

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
        two_months_ago = (last_month_start - timedelta(days=1)).replace(day=1)

        # Transacciones por periodo
        current_month = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion >= first_day_month,
                Transaction.deleted_at.is_(None),
            )
            .all()
        )

        last_month = (
            session.query(Transaction)
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


# Singleton
insights_service = InsightsService()
