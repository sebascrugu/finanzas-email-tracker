"""Servicio de gestión de metas financieras con AI y ML."""

import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import anthropic
from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.core.retry import retry_on_anthropic_error
from finanzas_tracker.models.goal_milestone import GoalMilestone
from finanzas_tracker.models.savings_goal import SavingsGoal
from finanzas_tracker.models.transaction import Transaction

logger = get_logger(__name__)


class GoalService:
    """
    Servicio de Metas Financieras con AI y ML.

    Features 🚀:
    - CRUD de metas
    - Cálculo automático de progreso y recomendaciones
    - Predicción de éxito con análisis de patrones de gasto
    - Recomendaciones personalizadas con Claude AI
    - Tracking de hitos (milestones)
    - Análisis de viabilidad
    """

    def __init__(self) -> None:
        """Inicializa el servicio de metas."""
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        logger.info("GoalService inicializado")

    # ========================================================================
    # CRUD OPERATIONS
    # ========================================================================

    def create_goal(
        self,
        profile_id: str,
        name: str,
        target_amount: Decimal,
        deadline: date | None = None,
        category: str | None = None,
        icon: str | None = None,
        priority: int = 3,
        savings_type: str = "manual",
        monthly_contribution_target: Decimal | None = None,
        current_amount: Decimal = Decimal("0"),
        description: str | None = None,
    ) -> SavingsGoal:
        """
        Crea una nueva meta financiera.

        Args:
            profile_id: ID del perfil
            name: Nombre de la meta (ej: "Mundial 2026")
            target_amount: Monto objetivo en CRC
            deadline: Fecha límite para alcanzar la meta
            category: Categoría de la meta (vacaciones, emergencia, compra, etc.)
            icon: Emoji/icono de la meta (ej: ⚽, ✈️, 🏠)
            priority: Prioridad (1=Alta, 2=Media, 3=Baja)
            savings_type: Tipo de ahorro (manual, automatic, monthly_target)
            monthly_contribution_target: Meta de contribución mensual
            current_amount: Monto inicial ahorrado
            description: Descripción opcional

        Returns:
            Meta creada
        """
        with get_session() as session:
            goal = SavingsGoal(
                id=str(uuid4()),
                profile_id=profile_id,
                name=name,
                target_amount=target_amount,
                current_amount=current_amount,
                deadline=deadline,
                category=category,
                description=description,
                icon=icon,
                priority=priority,
                savings_type=savings_type,
                monthly_contribution_target=monthly_contribution_target,
                is_active=True,
                is_completed=False,
            )

            # Calcular monto mensual sugerido si hay deadline
            if deadline and not monthly_contribution_target:
                goal.monthly_contribution_target = goal.required_monthly_savings

            session.add(goal)
            session.commit()
            session.refresh(goal)

            # Crear hito de creación
            self._create_milestone(
                session,
                goal.id,
                "achievement",
                f"Meta creada: {name}",
                f"Meta de {self._format_amount(target_amount)} creada",
                goal.current_amount,
                goal.progress_percentage,
            )

            session.commit()

            logger.info(f"✅ Meta creada: {name} - {self._format_amount(target_amount)}")
            return goal

    def get_goal(self, goal_id: str) -> SavingsGoal | None:
        """Obtiene una meta por ID."""
        with get_session() as session:
            return session.get(SavingsGoal, goal_id)

    def get_active_goals(self, profile_id: str) -> list[SavingsGoal]:
        """Obtiene todas las metas activas de un perfil."""
        with get_session() as session:
            stmt = (
                select(SavingsGoal)
                .where(
                    and_(
                        SavingsGoal.profile_id == profile_id,
                        SavingsGoal.is_active == True,  # noqa: E712
                        SavingsGoal.deleted_at.is_(None),
                    )
                )
                .order_by(SavingsGoal.priority, desc(SavingsGoal.created_at))
            )
            results = session.execute(stmt).scalars().all()
            return list(results)

    def update_goal(self, goal_id: str, **updates: Any) -> SavingsGoal:
        """
        Actualiza una meta.

        Args:
            goal_id: ID de la meta
            **updates: Campos a actualizar

        Returns:
            Meta actualizada
        """
        with get_session() as session:
            goal = session.get(SavingsGoal, goal_id)
            if not goal:
                raise ValueError(f"Meta {goal_id} no encontrada")

            for key, value in updates.items():
                if hasattr(goal, key):
                    setattr(goal, key, value)

            session.commit()
            session.refresh(goal)
            logger.info(f"Meta actualizada: {goal.name}")
            return goal

    def delete_goal(self, goal_id: str, soft: bool = True) -> None:
        """
        Elimina una meta.

        Args:
            goal_id: ID de la meta
            soft: Si es True, hace soft delete. Si es False, elimina permanentemente
        """
        with get_session() as session:
            goal = session.get(SavingsGoal, goal_id)
            if not goal:
                raise ValueError(f"Meta {goal_id} no encontrada")

            if soft:
                goal.deleted_at = datetime.now(UTC)
                goal.is_active = False
                logger.info(f"Meta desactivada (soft delete): {goal.name}")
            else:
                session.delete(goal)
                logger.info(f"Meta eliminada permanentemente: {goal.name}")

            session.commit()

    # ========================================================================
    # CONTRIBUTIONS & PROGRESS
    # ========================================================================

    def add_contribution(
        self,
        goal_id: str,
        amount: Decimal,
        note: str | None = None,
    ) -> SavingsGoal:
        """
        Agrega una contribución a la meta.

        Args:
            goal_id: ID de la meta
            amount: Monto de la contribución
            note: Nota opcional sobre la contribución

        Returns:
            Meta actualizada
        """
        with get_session() as session:
            goal = session.get(SavingsGoal, goal_id)
            if not goal:
                raise ValueError(f"Meta {goal_id} no encontrada")

            old_amount = goal.current_amount
            old_percentage = goal.progress_percentage

            goal.add_savings(amount)

            # Crear hito de contribución
            milestone_title = f"Contribución de {self._format_amount(amount)}"
            if note:
                milestone_desc = note
            else:
                milestone_desc = f"Progreso: {old_percentage:.1f}% → {goal.progress_percentage:.1f}%"

            self._create_milestone(
                session,
                goal.id,
                "contribution",
                milestone_title,
                milestone_desc,
                goal.current_amount,
                goal.progress_percentage,
                contribution_amount=amount,
            )

            # Verificar hitos de progreso (25%, 50%, 75%, 100%)
            self._check_progress_milestones(session, goal, old_percentage)

            session.commit()
            session.refresh(goal)

            logger.info(
                f"💰 Contribución agregada a {goal.name}: "
                f"{self._format_amount(amount)} ({goal.progress_percentage:.1f}%)"
            )

            return goal

    def _check_progress_milestones(
        self,
        session: Session,
        goal: SavingsGoal,
        old_percentage: float,
    ) -> None:
        """Verifica y crea hitos de progreso (25%, 50%, 75%, 100%)."""
        milestones = [25, 50, 75, 100]
        current_percentage = goal.progress_percentage

        for milestone_pct in milestones:
            # Si cruzamos este milestone
            if old_percentage < milestone_pct <= current_percentage:
                emoji = "🎯" if milestone_pct < 100 else "🎉"
                title = f"{emoji} ¡Alcanzaste {milestone_pct}% de tu meta!"
                description = (
                    f"¡Excelente progreso! Ya lograste {self._format_amount(goal.current_amount)} "
                    f"de {self._format_amount(goal.target_amount)}"
                )

                self._create_milestone(
                    session,
                    goal.id,
                    "progress" if milestone_pct < 100 else "achievement",
                    title,
                    description,
                    goal.current_amount,
                    Decimal(str(milestone_pct)),
                )

    def _create_milestone(
        self,
        session: Session,
        goal_id: str,
        milestone_type: str,
        title: str,
        description: str,
        amount_at_milestone: Decimal,
        percentage_at_milestone: float | Decimal,
        contribution_amount: Decimal | None = None,
    ) -> GoalMilestone:
        """Crea un hito de progreso."""
        milestone = GoalMilestone(
            id=str(uuid4()),
            goal_id=goal_id,
            milestone_type=milestone_type,
            title=title,
            description=description,
            amount_at_milestone=amount_at_milestone,
            percentage_at_milestone=Decimal(str(percentage_at_milestone)),
            contribution_amount=contribution_amount,
            created_at=datetime.now(UTC),
        )
        session.add(milestone)
        return milestone

    # ========================================================================
    # AI/ML FEATURES 🤖
    # ========================================================================

    def calculate_success_probability(self, goal_id: str) -> Decimal:
        """
        Calcula la probabilidad de éxito de una meta usando análisis de patrones.

        Factores considerados:
        - Progreso actual vs tiempo transcurrido
        - Tendencia de contribuciones recientes
        - Promedio mensual de ahorro del usuario
        - Gastos promedio vs ingreso
        - Consistencia de ahorro

        Returns:
            Probabilidad de éxito (0-100)
        """
        with get_session() as session:
            goal = session.get(SavingsGoal, goal_id)
            if not goal:
                raise ValueError(f"Meta {goal_id} no encontrada")

            if goal.is_completed:
                return Decimal("100.0")

            if not goal.deadline:
                # Sin deadline, basarse solo en tendencia
                return self._calculate_probability_no_deadline(session, goal)

            # Con deadline, análisis completo
            probability = self._calculate_probability_with_deadline(session, goal)

            # Actualizar en la base de datos
            goal.success_probability = probability
            goal.last_ml_prediction_at = datetime.now(UTC)
            session.commit()

            logger.info(
                f"📊 Probabilidad de éxito calculada para {goal.name}: {probability:.1f}%"
            )

            return probability

    def _calculate_probability_with_deadline(
        self, session: Session, goal: SavingsGoal
    ) -> Decimal:
        """Calcula probabilidad cuando hay deadline."""
        # Factor 1: Progreso vs tiempo (40% del peso)
        time_progress_score = self._calculate_time_progress_score(goal)

        # Factor 2: Tendencia de contribuciones (30% del peso)
        contribution_trend_score = self._calculate_contribution_trend(session, goal)

        # Factor 3: Capacidad de ahorro (30% del peso)
        saving_capacity_score = self._calculate_saving_capacity(session, goal)

        # Combinar scores con pesos
        probability = (
            time_progress_score * Decimal("0.4")
            + contribution_trend_score * Decimal("0.3")
            + saving_capacity_score * Decimal("0.3")
        )

        return min(probability, Decimal("100.0"))

    def _calculate_probability_no_deadline(
        self, session: Session, goal: SavingsGoal
    ) -> Decimal:
        """Calcula probabilidad cuando no hay deadline."""
        # Basarse solo en tendencia y capacidad
        contribution_trend = self._calculate_contribution_trend(session, goal)
        saving_capacity = self._calculate_saving_capacity(session, goal)

        return (contribution_trend + saving_capacity) / Decimal("2.0")

    def _calculate_time_progress_score(self, goal: SavingsGoal) -> Decimal:
        """Calcula score basado en progreso vs tiempo transcurrido."""
        if not goal.deadline:
            return Decimal("50.0")

        # Tiempo transcurrido desde creación
        total_days = (goal.deadline - goal.created_at.date()).days
        if total_days <= 0:
            return Decimal("0.0")  # Ya venció

        days_passed = (date.today() - goal.created_at.date()).days
        time_progress_pct = (days_passed / total_days) * 100

        # Progreso en dinero
        actual_progress_pct = float(goal.progress_percentage)

        # Score: qué tan adelantado o atrasado está
        # Si progreso >= tiempo esperado → 100%
        # Si progreso < tiempo esperado → proporcional
        if actual_progress_pct >= time_progress_pct:
            score = 100.0
        else:
            # Penalizar proporcionalmente el atraso
            score = (actual_progress_pct / time_progress_pct) * 100 if time_progress_pct > 0 else 0

        return Decimal(str(min(score, 100.0)))

    def _calculate_contribution_trend(self, session: Session, goal: SavingsGoal) -> Decimal:
        """Calcula score basado en la tendencia de contribuciones recientes."""
        # Obtener milestones de contribución de los últimos 90 días
        ninety_days_ago = datetime.now(UTC) - timedelta(days=90)

        stmt = (
            select(GoalMilestone)
            .where(
                and_(
                    GoalMilestone.goal_id == goal.id,
                    GoalMilestone.milestone_type == "contribution",
                    GoalMilestone.created_at >= ninety_days_ago,
                )
            )
            .order_by(desc(GoalMilestone.created_at))
        )

        contributions = session.execute(stmt).scalars().all()

        if not contributions:
            return Decimal("30.0")  # Score bajo sin contribuciones recientes

        # Calcular contribución promedio mensual
        total_contributed = sum(
            m.contribution_amount for m in contributions if m.contribution_amount
        )
        months_active = len(contributions) / 4  # Aproximadamente 4 contribuciones/mes

        if months_active == 0:
            avg_monthly = Decimal("0")
        else:
            avg_monthly = Decimal(str(total_contributed)) / Decimal(str(max(months_active, 1)))

        # Comparar con lo necesario
        required_monthly = goal.required_monthly_savings or Decimal("0")

        if required_monthly == 0:
            return Decimal("100.0")  # Sin requerimiento específico

        ratio = (avg_monthly / required_monthly) * 100 if required_monthly > 0 else 0
        score = min(float(ratio), 100.0)

        return Decimal(str(score))

    def _calculate_saving_capacity(self, session: Session, goal: SavingsGoal) -> Decimal:
        """Calcula score basado en la capacidad de ahorro del usuario."""
        # Analizar transacciones de los últimos 3 meses
        three_months_ago = datetime.now(UTC) - timedelta(days=90)

        stmt = (
            select(func.sum(Transaction.monto_crc))
            .where(
                and_(
                    Transaction.profile_id == goal.profile_id,
                    Transaction.fecha >= three_months_ago,
                    Transaction.deleted_at.is_(None),
                )
            )
        )

        total_spent = session.execute(stmt).scalar() or 0
        avg_monthly_spending = Decimal(str(total_spent)) / Decimal("3")

        # Si gasta menos, tiene más capacidad de ahorro
        # Asumiendo ingreso promedio de ₡800,000
        # (en una implementación real, obtener de Income table)
        assumed_income = Decimal("800000")
        potential_savings = assumed_income - avg_monthly_spending

        required_monthly = goal.required_monthly_savings or goal.monthly_contribution_target

        if not required_monthly or required_monthly == 0:
            return Decimal("75.0")

        # Ratio de capacidad
        capacity_ratio = (potential_savings / required_monthly) * 100
        score = min(float(capacity_ratio), 100.0)

        return Decimal(str(max(score, 0.0)))

    @retry_on_anthropic_error(max_retries=2)
    def generate_ai_recommendations(self, goal_id: str) -> str:
        """
        Genera recomendaciones personalizadas usando Claude AI.

        Returns:
            Recomendaciones en formato markdown
        """
        with get_session() as session:
            goal = session.get(SavingsGoal, goal_id)
            if not goal:
                raise ValueError(f"Meta {goal_id} no encontrada")

            # Recolectar contexto
            context = self._gather_goal_context(session, goal)

            # Prompt para Claude
            prompt = f"""Eres un asesor financiero experto. Analiza la siguiente meta financiera y proporciona recomendaciones personalizadas y accionables.

META:
- Nombre: {goal.name}
- Objetivo: ₡{goal.target_amount:,.2f}
- Progreso actual: ₡{goal.current_amount:,.2f} ({goal.progress_percentage:.1f}%)
- Faltante: ₡{goal.amount_remaining:,.2f}
- Fecha límite: {goal.deadline or 'Sin fecha límite'}
- Días restantes: {goal.days_remaining or 'N/A'}
- Ahorro mensual requerido: ₡{goal.required_monthly_savings or 0:,.2f}
- Probabilidad de éxito: {goal.success_probability or 'No calculada'}%
- Estado de salud: {goal.health_status}

CONTEXTO:
{context}

Proporciona:
1. **Análisis de viabilidad**: ¿Es realista alcanzar esta meta?
2. **Recomendaciones específicas**: 3-5 acciones concretas que puede tomar
3. **Áreas de recorte**: Dónde puede reducir gastos para ahorrar más
4. **Motivación**: Mensaje inspirador personalizado

Sé conciso, práctico y motivador. Usa emojis cuando sea apropiado."""

            message = self.client.messages.create(
                model=settings.claude_model,
                max_tokens=800,
                temperature=0.7,
                messages=[{"role": "user", "content": prompt}],
            )

            recommendations = message.content[0].text  # type: ignore[union-attr]

            # Guardar en base de datos
            goal.ai_recommendations = recommendations
            goal.last_ai_analysis_at = datetime.now(UTC)
            session.commit()

            logger.info(f"🤖 Recomendaciones AI generadas para: {goal.name}")

            return recommendations

    def _gather_goal_context(self, session: Session, goal: SavingsGoal) -> str:
        """Recopila contexto sobre la meta para el análisis AI."""
        # Obtener milestones recientes
        stmt = (
            select(GoalMilestone)
            .where(GoalMilestone.goal_id == goal.id)
            .order_by(desc(GoalMilestone.created_at))
            .limit(5)
        )
        milestones = session.execute(stmt).scalars().all()

        context_parts = []

        if milestones:
            context_parts.append("**Actividad reciente:**")
            for m in milestones:
                context_parts.append(f"- {m.title}")

        # Obtener gasto promedio mensual
        three_months_ago = datetime.now(UTC) - timedelta(days=90)
        stmt = (
            select(func.sum(Transaction.monto_crc))
            .where(
                and_(
                    Transaction.profile_id == goal.profile_id,
                    Transaction.fecha >= three_months_ago,
                    Transaction.deleted_at.is_(None),
                )
            )
        )
        total_spent = session.execute(stmt).scalar() or 0
        avg_monthly = Decimal(str(total_spent)) / Decimal("3")

        context_parts.append(f"**Gasto mensual promedio:** ₡{avg_monthly:,.2f}")

        # Estado de riesgo
        if goal.is_at_risk:
            context_parts.append("⚠️ **ALERTA:** Esta meta está en riesgo de no cumplirse")

        return "\n".join(context_parts)

    # ========================================================================
    # UTILITY METHODS
    # ========================================================================

    def _format_amount(self, amount: Decimal) -> str:
        """Formatea un monto en CRC."""
        return f"₡{amount:,.0f}"

    def get_goal_summary(self, goal_id: str) -> dict[str, Any]:
        """
        Obtiene un resumen completo de una meta para el dashboard.

        Returns:
            Dict con toda la información relevante para mostrar
        """
        with get_session() as session:
            goal = session.get(SavingsGoal, goal_id)
            if not goal:
                raise ValueError(f"Meta {goal_id} no encontrada")

            # Obtener milestones recientes
            stmt = (
                select(GoalMilestone)
                .where(GoalMilestone.goal_id == goal.id)
                .order_by(desc(GoalMilestone.created_at))
                .limit(10)
            )
            milestones = list(session.execute(stmt).scalars().all())

            return {
                "id": goal.id,
                "name": goal.display_name,
                "category": goal.category,
                "priority": goal.priority,
                "target_amount": float(goal.target_amount),
                "current_amount": float(goal.current_amount),
                "amount_remaining": float(goal.amount_remaining),
                "progress_percentage": goal.progress_percentage,
                "deadline": goal.deadline.isoformat() if goal.deadline else None,
                "days_remaining": goal.days_remaining,
                "is_at_risk": goal.is_at_risk,
                "is_overdue": goal.is_overdue,
                "health_status": goal.health_status,
                "required_monthly_savings": (
                    float(goal.required_monthly_savings) if goal.required_monthly_savings else None
                ),
                "monthly_contribution_target": (
                    float(goal.monthly_contribution_target)
                    if goal.monthly_contribution_target
                    else None
                ),
                "success_probability": (
                    float(goal.success_probability) if goal.success_probability else None
                ),
                "ai_recommendations": goal.ai_recommendations,
                "milestones": [
                    {
                        "type": m.milestone_type,
                        "title": m.title,
                        "description": m.description,
                        "date": m.created_at.isoformat(),
                        "amount": float(m.amount_at_milestone),
                        "percentage": float(m.percentage_at_milestone),
                    }
                    for m in milestones
                ],
                "created_at": goal.created_at.isoformat(),
            }


# Singleton instance
goal_service = GoalService()
