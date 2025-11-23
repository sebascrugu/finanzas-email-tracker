"""
Servicio de Predicciones y Tendencias.

Genera predicciones automáticas de:
- Gasto mensual proyectado
- Comparación vs presupuesto
- ETA de metas de ahorro
- Tendencias por categoría
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy import func

from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.savings_goal import SavingsGoal
from finanzas_tracker.models.transaction import Transaction


class PredictionService:
    """Servicio para generar predicciones y tendencias de gastos."""

    def predict_monthly_spending(self, profile_id: str) -> dict[str, Any]:
        """
        Predice el gasto total del mes actual basado en la tendencia.

        Usa dos métodos:
        1. Proyección lineal: (gasto_actual / días_transcurridos) * días_del_mes
        2. Promedio histórico: promedio de últimos 3 meses

        Args:
            profile_id: ID del perfil

        Returns:
            dict con:
                - current_spending: gasto actual del mes
                - projected_spending: proyección lineal
                - historical_average: promedio histórico
                - days_elapsed: días transcurridos del mes
                - days_remaining: días restantes del mes
                - daily_average: promedio diario actual
                - recommended_daily_spending: gasto diario recomendado para el resto del mes
        """
        with get_session() as session:
            today = date.today()
            month_start = datetime(today.year, today.month, 1, tzinfo=UTC)

            # Días del mes
            import calendar

            days_in_month = calendar.monthrange(today.year, today.month)[1]
            days_elapsed = today.day
            days_remaining = days_in_month - days_elapsed

            # Gasto actual del mes
            current_spending = (
                session.query(func.sum(Transaction.monto_crc))
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.fecha_transaccion >= month_start,
                    Transaction.deleted_at.is_(None),
                )
                .scalar()
            ) or Decimal("0")

            # Proyección lineal
            if days_elapsed > 0:
                daily_average = current_spending / Decimal(str(days_elapsed))
                projected_spending = daily_average * Decimal(str(days_in_month))
            else:
                daily_average = Decimal("0")
                projected_spending = Decimal("0")

            # Promedio histórico (últimos 3 meses, excluyendo el actual)
            three_months_ago = datetime(
                today.year if today.month > 3 else today.year - 1,
                today.month - 3 if today.month > 3 else today.month + 9,
                1,
                tzinfo=UTC,
            )

            historical_spending = (
                session.query(
                    func.strftime("%Y-%m", Transaction.fecha_transaccion).label("month"),
                    func.sum(Transaction.monto_crc).label("total"),
                )
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.fecha_transaccion >= three_months_ago,
                    Transaction.fecha_transaccion < month_start,
                    Transaction.deleted_at.is_(None),
                )
                .group_by("month")
                .all()
            )

            if historical_spending:
                historical_average = sum(month[1] for month in historical_spending) / len(
                    historical_spending
                )
            else:
                historical_average = Decimal("0")

            # Gasto diario recomendado para el resto del mes
            # (basado en promedio histórico - gasto actual) / días restantes
            if days_remaining > 0 and historical_average > current_spending:
                recommended_daily_spending = (historical_average - current_spending) / Decimal(
                    str(days_remaining)
                )
            else:
                recommended_daily_spending = daily_average

            return {
                "current_spending": current_spending,
                "projected_spending": projected_spending,
                "historical_average": historical_average,
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "days_in_month": days_in_month,
                "daily_average": daily_average,
                "recommended_daily_spending": recommended_daily_spending,
            }

    def predict_budget_status(self, profile_id: str) -> dict[str, Any] | None:
        """
        Predice si el usuario excederá su presupuesto según la tendencia actual.

        Args:
            profile_id: ID del perfil

        Returns:
            dict con predicción o None si no hay presupuesto
        """
        with get_session() as session:
            # Obtener presupuesto activo
            budget = (
                session.query(Budget)
                .filter(
                    Budget.profile_id == profile_id,
                    Budget.deleted_at.is_(None),
                )
                .order_by(Budget.created_at.desc())
                .first()
            )

            if not budget:
                return None

            # Obtener predicción de gasto
            prediction = self.predict_monthly_spending(profile_id)

            budget_total = budget.salario_mensual
            current_spending = prediction["current_spending"]
            projected_spending = prediction["projected_spending"]

            # Calcular porcentajes
            current_percentage = float((current_spending / budget_total) * 100)
            projected_percentage = float((projected_spending / budget_total) * 100)

            # Diferencia entre proyección y presupuesto
            projected_difference = projected_spending - budget_total
            will_exceed = projected_difference > 0

            # Días para alcanzar presupuesto (si sigue al ritmo actual)
            if prediction["daily_average"] > 0:
                remaining_budget = budget_total - current_spending
                days_to_budget = float(remaining_budget / prediction["daily_average"])
            else:
                days_to_budget = None

            return {
                "budget_total": budget_total,
                "current_spending": current_spending,
                "current_percentage": current_percentage,
                "projected_spending": projected_spending,
                "projected_percentage": projected_percentage,
                "projected_difference": projected_difference,
                "will_exceed": will_exceed,
                "days_to_budget": days_to_budget,
                "days_remaining": prediction["days_remaining"],
            }

    def predict_savings_goal_eta(self, goal_id: str) -> dict[str, Any] | None:
        """
        Predice cuándo alcanzará el usuario su meta de ahorro según la tendencia.

        Args:
            goal_id: ID de la meta de ahorro

        Returns:
            dict con predicción o None si no hay suficientes datos
        """
        with get_session() as session:
            goal = session.query(SavingsGoal).filter(SavingsGoal.id == goal_id).first()

            if not goal or goal.is_completed:
                return None

            # Calcular tasa de ahorro mensual histórica
            # (asumimos que current_amount se actualiza manualmente)
            # Para una predicción real, necesitaríamos historial de cambios

            # Por ahora, usamos un enfoque simple:
            # Si hay deadline, calculamos ahorro mensual requerido
            # Si no hay deadline, estimamos basado en el progreso actual

            remaining_amount = goal.amount_remaining
            current_amount = goal.current_amount

            # Método 1: Basado en deadline
            if goal.deadline:
                days_left = goal.days_remaining
                if days_left and days_left > 0:
                    months_left = max(days_left / 30, 1)
                    required_monthly = remaining_amount / Decimal(str(months_left))

                    return {
                        "goal_name": goal.name,
                        "target_amount": goal.target_amount,
                        "current_amount": current_amount,
                        "remaining_amount": remaining_amount,
                        "progress_percentage": goal.progress_percentage,
                        "deadline": goal.deadline,
                        "days_remaining": days_left,
                        "months_remaining": months_left,
                        "required_monthly_savings": required_monthly,
                        "on_track": True,  # Por definir con historial
                    }

            # Método 2: Sin deadline - estimación simple
            # Asumimos que seguirá ahorrando al mismo ritmo
            # Esto requeriría historial de transacciones o updates
            return {
                "goal_name": goal.name,
                "target_amount": goal.target_amount,
                "current_amount": current_amount,
                "remaining_amount": remaining_amount,
                "progress_percentage": goal.progress_percentage,
                "deadline": None,
                "estimated_months_to_complete": None,  # Requiere historial
            }

    def analyze_category_trends(self, profile_id: str, months: int = 3) -> list[dict[str, Any]]:
        """
        Analiza tendencias de gasto por categoría.

        Args:
            profile_id: ID del perfil
            months: Número de meses a analizar

        Returns:
            Lista de tendencias por categoría
        """
        with get_session() as session:
            today = date.today()
            current_month_start = datetime(today.year, today.month, 1, tzinfo=UTC)

            # Mes anterior
            if today.month == 1:
                prev_month_start = datetime(today.year - 1, 12, 1, tzinfo=UTC)
                prev_month_end = datetime(today.year, 1, 1, tzinfo=UTC)
            else:
                prev_month_start = datetime(today.year, today.month - 1, 1, tzinfo=UTC)
                prev_month_end = current_month_start

            # Gasto por categoría mes actual
            current_by_category = (
                session.query(
                    Transaction.subcategory_id,
                    func.sum(Transaction.monto_crc).label("total"),
                )
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.fecha_transaccion >= current_month_start,
                    Transaction.subcategory_id.isnot(None),
                    Transaction.deleted_at.is_(None),
                )
                .group_by(Transaction.subcategory_id)
                .all()
            )

            # Gasto por categoría mes anterior
            previous_by_category = {}
            prev_results = (
                session.query(
                    Transaction.subcategory_id,
                    func.sum(Transaction.monto_crc).label("total"),
                )
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.fecha_transaccion >= prev_month_start,
                    Transaction.fecha_transaccion < prev_month_end,
                    Transaction.subcategory_id.isnot(None),
                    Transaction.deleted_at.is_(None),
                )
                .group_by(Transaction.subcategory_id)
                .all()
            )

            for cat_id, total in prev_results:
                previous_by_category[cat_id] = total

            # Calcular tendencias
            trends = []
            for cat_id, current_total in current_by_category:
                prev_total = previous_by_category.get(cat_id, Decimal("0"))

                if prev_total > 0:
                    change_pct = float(((current_total - prev_total) / prev_total) * 100)
                else:
                    change_pct = 100.0 if current_total > 0 else 0.0

                # Proyectar al final del mes
                days_in_month = calendar.monthrange(today.year, today.month)[1]
                days_elapsed = today.day

                if days_elapsed > 0:
                    projected_total = current_total * Decimal(str(days_in_month / days_elapsed))
                else:
                    projected_total = current_total

                trends.append(
                    {
                        "subcategory_id": cat_id,
                        "current_spending": current_total,
                        "previous_spending": prev_total,
                        "change_percentage": change_pct,
                        "projected_spending": projected_total,
                        "trend": "up" if change_pct > 10 else "down" if change_pct < -10 else "stable",
                    }
                )

            # Ordenar por cambio porcentual (mayor primero)
            trends.sort(key=lambda x: abs(x["change_percentage"]), reverse=True)

            return trends

    def get_spending_forecast_summary(self, profile_id: str) -> dict[str, Any]:
        """
        Obtiene un resumen completo de predicciones para el perfil.

        Args:
            profile_id: ID del perfil

        Returns:
            dict con todas las predicciones
        """
        monthly_prediction = self.predict_monthly_spending(profile_id)
        budget_prediction = self.predict_budget_status(profile_id)
        category_trends = self.analyze_category_trends(profile_id)

        return {
            "monthly_spending": monthly_prediction,
            "budget_status": budget_prediction,
            "category_trends": category_trends,
        }


# Singleton para usar en toda la aplicación
prediction_service = PredictionService()
