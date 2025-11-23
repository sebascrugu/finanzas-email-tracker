"""Servicio de Resúmenes Mensuales con IA."""

import json
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any

import anthropic
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.core.retry import retry_on_anthropic_error
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.savings_goal import SavingsGoal
from finanzas_tracker.models.transaction import Transaction

logger = get_logger(__name__)


class MonthlyReportService:
    """
    Servicio de Resúmenes Mensuales Narrativos.

    Genera reportes ejecutivos mensuales usando Claude AI con:
    - Análisis de tendencias vs mes anterior
    - Insights de patrones de gasto
    - Detección de cambios significativos
    - Recomendaciones accionables
    - Proyecciones para el próximo mes
    - Tono conversacional y motivador

    Ideal para revisiones mensuales y planificación financiera.
    """

    def __init__(self) -> None:
        """Inicializa el servicio de reportes."""
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        logger.info("MonthlyReportService inicializado")

    # ========================================================================
    # RECOLECCIÓN DE DATOS
    # ========================================================================

    def _get_month_dates(self, year: int, month: int) -> tuple[date, date]:
        """Obtiene fechas de inicio y fin del mes."""
        start_date = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end_date = date(year, month, last_day)
        return start_date, end_date

    def _get_transactions_summary(
        self, session: Session, profile_id: str, start_date: date, end_date: date
    ) -> dict[str, Any]:
        """Obtiene resumen de transacciones del mes."""
        stmt = (
            select(Transaction)
            .where(
                and_(
                    Transaction.profile_id == profile_id,
                    Transaction.fecha >= start_date,
                    Transaction.fecha <= end_date,
                    Transaction.deleted_at.is_(None),
                )
            )
            .order_by(desc(Transaction.fecha))
        )

        transactions = session.execute(stmt).scalars().all()

        # Calcular totales
        total_spent = sum(t.monto_crc for t in transactions)
        transaction_count = len(transactions)

        # Por categoría
        by_category = {}
        for t in transactions:
            if t.subcategory_id:
                subcat = session.get(Subcategory, t.subcategory_id)
                if subcat:
                    cat_name = subcat.nombre
                    if cat_name not in by_category:
                        by_category[cat_name] = {"count": 0, "amount": Decimal("0")}
                    by_category[cat_name]["count"] += 1
                    by_category[cat_name]["amount"] += t.monto_crc

        # Top categorías
        top_categories = sorted(
            by_category.items(), key=lambda x: x[1]["amount"], reverse=True
        )[:5]

        # Top comercios
        by_merchant = {}
        for t in transactions:
            merchant = t.comercio
            if merchant not in by_merchant:
                by_merchant[merchant] = {"count": 0, "amount": Decimal("0")}
            by_merchant[merchant]["count"] += 1
            by_merchant[merchant]["amount"] += t.monto_crc

        top_merchants = sorted(
            by_merchant.items(), key=lambda x: x[1]["amount"], reverse=True
        )[:5]

        # Transacción más grande
        largest_transaction = max(transactions, key=lambda t: t.monto_crc) if transactions else None

        return {
            "total_spent": total_spent,
            "transaction_count": transaction_count,
            "top_categories": top_categories,
            "top_merchants": top_merchants,
            "largest_transaction": largest_transaction,
            "average_transaction": (
                total_spent / transaction_count if transaction_count > 0 else 0
            ),
        }

    def _get_income_summary(
        self, session: Session, profile_id: str, year: int, month: int
    ) -> dict[str, Any]:
        """Obtiene resumen de ingresos del mes."""
        stmt = select(Income).where(
            and_(
                Income.profile_id == profile_id,
                Income.activo == True,  # noqa: E712
            )
        )

        incomes = session.execute(stmt).scalars().all()

        total_income = sum(
            self._calculate_monthly_income(income, year, month) for income in incomes
        )

        return {
            "total_income": total_income,
            "income_count": len(incomes),
            "incomes": [
                {"nombre": i.nombre, "monto": self._calculate_monthly_income(i, year, month)}
                for i in incomes
            ],
        }

    def _calculate_monthly_income(self, income: Income, year: int, month: int) -> Decimal:
        """Calcula el ingreso mensual considerando frecuencia."""
        if not income.es_recurrente:
            # Verificar si el ingreso one-time cayó en este mes
            if income.fecha_inicio and income.fecha_inicio.year == year and income.fecha_inicio.month == month:
                return income.monto_crc
            return Decimal("0")

        # Ingresos recurrentes
        from finanzas_tracker.models.enums import RecurrenceFrequency

        if income.frecuencia == RecurrenceFrequency.MONTHLY:
            return income.monto_crc
        elif income.frecuencia == RecurrenceFrequency.BIWEEKLY:
            return income.monto_crc * Decimal("2")
        elif income.frecuencia == RecurrenceFrequency.WEEKLY:
            return income.monto_crc * Decimal("4")
        else:
            return income.monto_crc

    def _get_savings_summary(self, session: Session, profile_id: str) -> dict[str, Any]:
        """Obtiene resumen de metas de ahorro."""
        stmt = (
            select(SavingsGoal)
            .where(
                and_(
                    SavingsGoal.profile_id == profile_id,
                    SavingsGoal.is_active == True,  # noqa: E712
                    SavingsGoal.deleted_at.is_(None),
                )
            )
        )

        goals = session.execute(stmt).scalars().all()

        total_target = sum(g.target_amount for g in goals)
        total_saved = sum(g.current_amount for g in goals)
        avg_progress = (
            sum(g.progress_percentage for g in goals) / len(goals) if goals else 0
        )

        # Metas completadas este mes
        completed_this_month = sum(
            1
            for g in goals
            if g.is_completed
            and g.completed_at
            and g.completed_at.month == datetime.now().month
        )

        return {
            "total_goals": len(goals),
            "total_target": total_target,
            "total_saved": total_saved,
            "avg_progress": avg_progress,
            "completed_this_month": completed_this_month,
            "at_risk": sum(1 for g in goals if g.is_at_risk),
        }

    def _compare_with_previous_month(
        self, session: Session, profile_id: str, current_month: dict, year: int, month: int
    ) -> dict[str, Any]:
        """Compara con el mes anterior."""
        # Calcular mes anterior
        if month == 1:
            prev_year, prev_month = year - 1, 12
        else:
            prev_year, prev_month = year, month - 1

        prev_start, prev_end = self._get_month_dates(prev_year, prev_month)

        prev_summary = self._get_transactions_summary(
            session, profile_id, prev_start, prev_end
        )

        # Calcular cambios
        spending_change = (
            float(current_month["total_spent"] - prev_summary["total_spent"])
            if prev_summary["total_spent"] > 0
            else 0
        )

        spending_change_pct = (
            (spending_change / float(prev_summary["total_spent"])) * 100
            if prev_summary["total_spent"] > 0
            else 0
        )

        transaction_count_change = (
            current_month["transaction_count"] - prev_summary["transaction_count"]
        )

        return {
            "previous_month_spending": prev_summary["total_spent"],
            "spending_change": spending_change,
            "spending_change_pct": spending_change_pct,
            "transaction_count_change": transaction_count_change,
            "trend": "up" if spending_change > 0 else "down" if spending_change < 0 else "stable",
        }

    # ========================================================================
    # GENERACIÓN DE REPORTE CON CLAUDE AI
    # ========================================================================

    @retry_on_anthropic_error(max_retries=2)
    def generate_monthly_report(
        self, profile_id: str, year: int, month: int
    ) -> dict[str, Any]:
        """
        Genera un reporte mensual narrativo completo.

        Args:
            profile_id: ID del perfil
            year: Año del reporte
            month: Mes del reporte (1-12)

        Returns:
            Dict con:
            - summary: Resumen ejecutivo narrativo (Claude)
            - data: Datos numéricos del mes
            - insights: Lista de insights específicos
            - recommendations: Recomendaciones accionables
            - next_month_projection: Proyección para próximo mes
        """
        logger.info(f"📊 Generando reporte mensual para {year}-{month:02d}")

        with get_session() as session:
            # Recolectar datos
            start_date, end_date = self._get_month_dates(year, month)

            transactions_data = self._get_transactions_summary(
                session, profile_id, start_date, end_date
            )

            income_data = self._get_income_summary(session, profile_id, year, month)

            savings_data = self._get_savings_summary(session, profile_id)

            comparison_data = self._compare_with_previous_month(
                session, profile_id, transactions_data, year, month
            )

            # Calcular balance
            balance = float(income_data["total_income"]) - float(transactions_data["total_spent"])
            balance_pct = (
                (balance / float(income_data["total_income"])) * 100
                if income_data["total_income"] > 0
                else 0
            )

            # Construir contexto para Claude
            context = self._build_context_for_claude(
                year,
                month,
                transactions_data,
                income_data,
                savings_data,
                comparison_data,
                balance,
                balance_pct,
            )

            # Generar reporte narrativo con Claude
            narrative = self._generate_narrative_with_claude(context)

            # Compilar reporte completo
            report = {
                "profile_id": profile_id,
                "year": year,
                "month": month,
                "month_name": date(year, month, 1).strftime("%B %Y"),
                "generated_at": datetime.now(UTC).isoformat(),
                # Narrativa AI
                "executive_summary": narrative["executive_summary"],
                "detailed_analysis": narrative["detailed_analysis"],
                "insights": narrative["insights"],
                "recommendations": narrative["recommendations"],
                "next_month_projection": narrative["next_month_projection"],
                # Datos numéricos
                "data": {
                    "income": {
                        "total": float(income_data["total_income"]),
                        "sources": income_data["incomes"],
                    },
                    "expenses": {
                        "total": float(transactions_data["total_spent"]),
                        "count": transactions_data["transaction_count"],
                        "average": float(transactions_data["average_transaction"]),
                        "top_categories": [
                            {
                                "name": cat,
                                "amount": float(data["amount"]),
                                "count": data["count"],
                            }
                            for cat, data in transactions_data["top_categories"]
                        ],
                        "top_merchants": [
                            {
                                "name": merchant,
                                "amount": float(data["amount"]),
                                "count": data["count"],
                            }
                            for merchant, data in transactions_data["top_merchants"]
                        ],
                    },
                    "balance": {
                        "amount": balance,
                        "percentage": balance_pct,
                        "status": "positive" if balance > 0 else "negative",
                    },
                    "comparison": {
                        "previous_month_spending": float(
                            comparison_data["previous_month_spending"]
                        ),
                        "change_amount": comparison_data["spending_change"],
                        "change_percentage": comparison_data["spending_change_pct"],
                        "trend": comparison_data["trend"],
                    },
                    "savings": {
                        "total_goals": savings_data["total_goals"],
                        "avg_progress": savings_data["avg_progress"],
                        "completed_this_month": savings_data["completed_this_month"],
                        "at_risk": savings_data["at_risk"],
                    },
                },
            }

            logger.info(f"✅ Reporte mensual generado: {report['month_name']}")
            return report

    def _build_context_for_claude(
        self,
        year: int,
        month: int,
        transactions: dict,
        income: dict,
        savings: dict,
        comparison: dict,
        balance: float,
        balance_pct: float,
    ) -> str:
        """Construye el contexto para enviar a Claude."""
        month_name = date(year, month, 1).strftime("%B %Y")

        context = f"""# Reporte Financiero Mensual - {month_name}

## Resumen General
- **Ingresos totales**: ₡{income['total_income']:,.0f}
- **Gastos totales**: ₡{transactions['total_spent']:,.0f}
- **Balance**: ₡{balance:,.0f} ({balance_pct:+.1f}%)
- **Número de transacciones**: {transactions['transaction_count']}

## Comparación con Mes Anterior
- **Cambio en gastos**: ₡{comparison['spending_change']:,.0f} ({comparison['spending_change_pct']:+.1f}%)
- **Tendencia**: {comparison['trend']}

## Top 5 Categorías de Gasto
"""

        for i, (cat, data) in enumerate(transactions["top_categories"], 1):
            context += f"{i}. **{cat}**: ₡{data['amount']:,.0f} ({data['count']} transacciones)\n"

        context += "\n## Top 5 Comercios\n"

        for i, (merchant, data) in enumerate(transactions["top_merchants"], 1):
            context += f"{i}. **{merchant}**: ₡{data['amount']:,.0f} ({data['count']} compras)\n"

        context += f"""
## Metas de Ahorro
- **Total de metas**: {savings['total_goals']}
- **Progreso promedio**: {savings['avg_progress']:.1f}%
- **Metas completadas este mes**: {savings['completed_this_month']}
- **Metas en riesgo**: {savings['at_risk']}

## Datos Adicionales
- **Transacción promedio**: ₡{transactions['average_transaction']:,.0f}
"""

        if transactions.get("largest_transaction"):
            largest = transactions["largest_transaction"]
            context += f"- **Gasto más grande**: ₡{largest.monto_crc:,.0f} en {largest.comercio}\n"

        return context

    def _generate_narrative_with_claude(self, context: str) -> dict[str, Any]:
        """Genera narrativa usando Claude AI."""
        prompt = f"""Eres un asesor financiero experto y motivador. Analiza el siguiente reporte mensual y proporciona un análisis completo en español.

{context}

Genera un reporte estructurado con las siguientes secciones:

1. **RESUMEN EJECUTIVO** (2-3 párrafos)
   - Visión general del mes en tono conversacional
   - Destacar el aspecto más importante (positivo o negativo)
   - Mensaje motivador

2. **ANÁLISIS DETALLADO** (3-4 párrafos)
   - Análisis de tendencias de gasto
   - Comparación con mes anterior y qué significa
   - Patrones identificados en categorías principales
   - Observaciones sobre comercios frecuentes

3. **INSIGHTS CLAVE** (Lista de 4-6 puntos)
   - Hallazgos específicos y accionables
   - Cada insight debe ser concreto y relevante
   - Usa emojis apropiados

4. **RECOMENDACIONES** (Lista de 3-5 acciones)
   - Consejos específicos para el próximo mes
   - Accionables y realistas
   - Priorizadas por impacto

5. **PROYECCIÓN PRÓXIMO MES** (1-2 párrafos)
   - Predicción basada en tendencias actuales
   - Áreas de oportunidad
   - Meta sugerida para próximo mes

IMPORTANTE:
- Usa un tono amigable, motivador pero profesional
- Sé específico con los números
- Destaca tanto logros como áreas de mejora
- Usa emojis de manera apropiada pero no excesiva
- Formato en Markdown para mejor legibilidad

Responde ÚNICAMENTE con un JSON válido con esta estructura:
{
  "executive_summary": "texto del resumen...",
  "detailed_analysis": "texto del análisis...",
  "insights": ["insight 1", "insight 2", ...],
  "recommendations": ["recomendación 1", "recomendación 2", ...],
  "next_month_projection": "texto de la proyección..."
}
"""

        message = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",  # Usar Sonnet para mejor calidad
            max_tokens=2000,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parsear respuesta JSON
        response_text = message.content[0].text  # type: ignore[union-attr]

        try:
            # Intentar parsear como JSON
            narrative = json.loads(response_text)
        except json.JSONDecodeError:
            # Si Claude no retorna JSON puro, intentar extraerlo
            import re

            json_match = re.search(r"\{.*\}", response_text, re.DOTALL)
            if json_match:
                narrative = json.loads(json_match.group())
            else:
                # Fallback: estructura básica
                narrative = {
                    "executive_summary": response_text[:500],
                    "detailed_analysis": response_text,
                    "insights": [],
                    "recommendations": [],
                    "next_month_projection": "",
                }

        return narrative


# Singleton instance
monthly_report_service = MonthlyReportService()
