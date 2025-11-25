"""
Alert Engine - Sistema de Alertas Inteligentes.

Este servicio evalúa condiciones y genera alertas automáticas para
notificar al usuario sobre eventos importantes.

Fase 1 implementa las 10 alertas críticas más importantes:
1. Statement Upload Reminder
2. Credit Card Payment Due
3. Spending Exceeds Income
4. Budget 80% Reached
5. Budget 100% Reached
6. Subscription Renewal
7. Duplicate Transaction
8. High Interest Projection
9. Card Expiration
10. Uncategorized Transactions
"""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.alert import Alert
from finanzas_tracker.models.bank_statement import BankStatement
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.enums import AlertPriority, AlertStatus, AlertType, CardType
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.savings_goal import SavingsGoal
from finanzas_tracker.models.subscription import Subscription
from finanzas_tracker.models.transaction import Transaction

logger = get_logger(__name__)


class AlertEngine:
    """
    Motor de Alertas Inteligentes.

    Evalúa reglas y genera alertas automáticas para el usuario.
    """

    def __init__(self, session: Session):
        """
        Inicializa el Alert Engine.

        Args:
            session: Sesión de SQLAlchemy
        """
        self.session = session
        logger.info("AlertEngine inicializado")

    # ========================================================================
    # MÉTODO PRINCIPAL
    # ========================================================================

    def evaluate_all_alerts(self, profile_id: str) -> list[Alert]:
        """
        Evalúa todas las reglas de alertas para un perfil.

        Args:
            profile_id: ID del perfil

        Returns:
            Lista de alertas generadas
        """
        alerts_generated: list[Alert] = []

        # Fase 1 - Top 10 Critical Alerts
        alerts_generated.extend(self._check_statement_upload_reminder(profile_id))
        alerts_generated.extend(self._check_credit_card_payment_due(profile_id))
        alerts_generated.extend(self._check_spending_exceeds_income(profile_id))
        alerts_generated.extend(self._check_budget_thresholds(profile_id))
        alerts_generated.extend(self._check_subscription_renewals(profile_id))
        alerts_generated.extend(self._check_duplicate_transactions(profile_id))
        alerts_generated.extend(self._check_high_interest_projection(profile_id))
        alerts_generated.extend(self._check_card_expiration(profile_id))
        alerts_generated.extend(self._check_uncategorized_transactions(profile_id))

        # Fase 2 - Negative/Preventive Alerts
        alerts_generated.extend(self._check_overdraft_projection(profile_id))
        alerts_generated.extend(self._check_low_savings_warning(profile_id))
        alerts_generated.extend(self._check_unknown_merchant_high(profile_id))
        alerts_generated.extend(self._check_credit_utilization_high(profile_id))
        alerts_generated.extend(self._check_spending_velocity_high(profile_id))
        alerts_generated.extend(self._check_seasonal_spending_warning(profile_id))
        alerts_generated.extend(self._check_goal_behind_schedule(profile_id))

        # Fase 2 - Positive Alerts (Gamification/Motivation)
        alerts_generated.extend(self._check_spending_reduction(profile_id))
        alerts_generated.extend(self._check_savings_milestone(profile_id))
        alerts_generated.extend(self._check_budget_under_target(profile_id))
        alerts_generated.extend(self._check_debt_payment_progress(profile_id))
        alerts_generated.extend(self._check_streak_achievement(profile_id))
        alerts_generated.extend(self._check_category_improvement(profile_id))
        alerts_generated.extend(self._check_zero_eating_out(profile_id))
        alerts_generated.extend(self._check_emergency_fund_milestone(profile_id))

        logger.info(
            f"Evaluación completa: {len(alerts_generated)} alertas generadas",
            extra={"profile_id": profile_id},
        )

        return alerts_generated

    # ========================================================================
    # ALERTA #1: Statement Upload Reminder
    # ========================================================================

    def _check_statement_upload_reminder(self, profile_id: str) -> list[Alert]:
        """
        Alerta #1: Recordatorio de subir estado de cuenta mensual.

        Genera alerta si:
        - Es día 5+ del mes
        - No hay statement del mes actual
        """
        alerts: list[Alert] = []
        today = date.today()

        # Solo recordar después del día 5 (BAC es el 4)
        if today.day < 5:
            return alerts

        # Buscar statement del mes actual
        stmt = select(BankStatement).where(
            BankStatement.profile_id == profile_id,
            func.extract("year", BankStatement.fecha_corte) == today.year,
            func.extract("month", BankStatement.fecha_corte) == today.month,
        )
        current_month_statement = self.session.execute(stmt).scalar_one_or_none()

        if current_month_statement:
            return alerts  # Ya subió el statement

        # Verificar si ya existe alerta pendiente
        if self._alert_already_exists(
            profile_id, AlertType.STATEMENT_UPLOAD_REMINDER
        ):
            return alerts

        # Generar alerta
        alert = Alert(
            id=str(uuid4()),
            profile_id=profile_id,
            alert_type=AlertType.STATEMENT_UPLOAD_REMINDER,
            priority=AlertPriority.MEDIUM,
            status=AlertStatus.PENDING,
            title="📄 Recordatorio: Subir Estado de Cuenta",
            message=(
                f"Es {today.strftime('%d de %B')}. "
                f"¿Ya subiste tu estado de cuenta de BAC del mes? "
                f"Mantener tus estados al día te asegura datos 100% completos."
            ),
            action_url="/Reconciliacion",  # Dashboard de reconciliación
        )

        alerts.append(alert)
        logger.info(
            "Alerta generada: Statement Upload Reminder",
            extra={"profile_id": profile_id},
        )

        return alerts

    # ========================================================================
    # ALERTA #2: Credit Card Payment Due
    # ========================================================================

    def _check_credit_card_payment_due(self, profile_id: str) -> list[Alert]:
        """
        Alerta #2: Fecha de pago de tarjeta de crédito próxima.

        Genera alerta si:
        - Faltan 7 días o menos para la fecha de pago
        """
        alerts: list[Alert] = []
        today = date.today()
        threshold_date = today + timedelta(days=7)

        # Buscar tarjetas de crédito con fecha de pago próxima
        # (Esto asume que tienes un campo payment_due_date en Card o CreditCard)
        # Por ahora lo simulo con fecha de corte + 20 días
        stmt = select(Card).where(
            Card.profile_id == profile_id,
            Card.activa == True,  # noqa: E712
        )
        cards = self.session.execute(stmt).scalars().all()

        for card in cards:
            # Calcular fecha de pago estimada (corte + 20 días)
            # BAC: corte 4 del mes → pago 24 del mes
            payment_date = date(today.year, today.month, 24)

            # Ajustar si ya pasó este mes
            if payment_date < today:
                if today.month == 12:
                    payment_date = date(today.year + 1, 1, 24)
                else:
                    payment_date = date(today.year, today.month + 1, 24)

            days_until_payment = (payment_date - today).days

            if 0 < days_until_payment <= 7:
                # Verificar si ya existe alerta pendiente
                if self._alert_already_exists(
                    profile_id, AlertType.CREDIT_CARD_PAYMENT_DUE, related_id=card.id
                ):
                    continue

                # Determinar prioridad según días restantes
                if days_until_payment <= 2:
                    priority = AlertPriority.CRITICAL
                elif days_until_payment <= 5:
                    priority = AlertPriority.HIGH
                else:
                    priority = AlertPriority.MEDIUM

                alert = Alert(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    alert_type=AlertType.CREDIT_CARD_PAYMENT_DUE,
                    priority=priority,
                    status=AlertStatus.PENDING,
                    title=f"💳 Pago de Tarjeta {card.banco.value.upper()} Próximo",
                    message=(
                        f"Tu tarjeta {card.banco.value.upper()} ••••{card.ultimos_digitos} "
                        f"vence en {days_until_payment} día(s) ({payment_date.strftime('%d/%m/%Y')}). "
                        f"No olvides realizar el pago para evitar intereses."
                    ),
                    action_url="/Tarjetas",
                    card_id=card.id,
                )

                alerts.append(alert)
                logger.info(
                    f"Alerta generada: Credit Card Payment Due - {card.banco.value}",
                    extra={"profile_id": profile_id, "days": days_until_payment},
                )

        return alerts

    # ========================================================================
    # ALERTA #3: Spending Exceeds Income (CRÍTICA)
    # ========================================================================

    def _check_spending_exceeds_income(self, profile_id: str) -> list[Alert]:
        """
        Alerta #3: Gastos proyectados exceden ingresos.

        Genera alerta si:
        - Gastos del mes actual > Ingreso mensual
        - O proyección indica que excederá ingreso
        """
        alerts: list[Alert] = []
        today = date.today()
        month_start = date(today.year, today.month, 1)

        # Obtener ingreso mensual total
        stmt_income = select(func.sum(Income.monto_crc)).where(
            Income.profile_id == profile_id
        )
        total_income = self.session.execute(stmt_income).scalar_one_or_none() or Decimal(
            0
        )

        if total_income == 0:
            return alerts  # No hay ingreso configurado

        # Calcular gastos del mes actual
        stmt_spending = select(func.sum(Transaction.monto_crc)).where(
            Transaction.profile_id == profile_id,
            Transaction.fecha_transaccion >= month_start,
            Transaction.monto_crc < 0,  # Solo gastos (negativos)
        )
        total_spending = abs(
            self.session.execute(stmt_spending).scalar_one_or_none() or Decimal(0)
        )

        # Proyectar gasto total del mes
        days_elapsed = today.day
        days_in_month = 30  # Simplificado
        projected_spending = (total_spending / days_elapsed) * days_in_month

        # Generar alerta si excede o proyecta exceder
        if total_spending > total_income or projected_spending > total_income:
            # Verificar si ya existe alerta pendiente
            if self._alert_already_exists(
                profile_id, AlertType.SPENDING_EXCEEDS_INCOME
            ):
                return alerts

            difference = projected_spending - total_income
            alert = Alert(
                id=str(uuid4()),
                profile_id=profile_id,
                alert_type=AlertType.SPENDING_EXCEEDS_INCOME,
                priority=AlertPriority.CRITICAL,
                status=AlertStatus.PENDING,
                title="🚨 ¡Alerta! Gastos Exceden Ingresos",
                message=(
                    f"Tus gastos este mes están proyectados en ₡{projected_spending:,.0f}, "
                    f"pero tu ingreso es ₡{total_income:,.0f}. "
                    f"Exceso: ₡{difference:,.0f}. "
                    f"Considera reducir gastos o usar ahorros."
                ),
                action_url="/Transacciones",
            )

            alerts.append(alert)
            logger.warning(
                "Alerta CRÍTICA: Spending Exceeds Income",
                extra={
                    "profile_id": profile_id,
                    "income": float(total_income),
                    "projected_spending": float(projected_spending),
                },
            )

        return alerts

    # ========================================================================
    # ALERTA #4 y #5: Budget Thresholds (80% y 100%)
    # ========================================================================

    def _check_budget_thresholds(self, profile_id: str) -> list[Alert]:
        """
        Alerta #4 y #5: Umbrales de presupuesto.

        Genera alerta si:
        - Alcanzó 80% del presupuesto (warning)
        - Alcanzó o excedió 100% del presupuesto (critical)
        """
        alerts: list[Alert] = []
        today = date.today()
        month_start = date(today.year, today.month, 1)

        # Obtener todos los presupuestos activos
        stmt = select(Budget).where(
            Budget.profile_id == profile_id
        )
        budgets = self.session.execute(stmt).scalars().all()

        for budget in budgets:
            # Calcular gasto en esta categoría este mes
            stmt_spending = select(func.sum(Transaction.monto_crc)).where(
                Transaction.profile_id == profile_id,
                Transaction.subcategory_id == budget.category_id,
                Transaction.fecha_transaccion >= month_start,
                Transaction.monto_crc < 0,
            )
            spent = abs(
                self.session.execute(stmt_spending).scalar_one_or_none() or Decimal(0)
            )

            percentage = (spent / budget.amount_crc) * 100 if budget.amount_crc > 0 else 0

            # 100% o más → CRÍTICO
            if percentage >= 100:
                if not self._alert_already_exists(
                    profile_id, AlertType.BUDGET_100_PERCENT, related_id=budget.id
                ):
                    # Obtener nombre de categoría
                    category = self.session.get(Category, budget.category_id)
                    category_name = category.nombre if category else "Categoría"

                    alert = Alert(
                        id=str(uuid4()),
                        profile_id=profile_id,
                        budget_id=budget.id,
                        alert_type=AlertType.BUDGET_100_PERCENT,
                        priority=AlertPriority.CRITICAL,
                        status=AlertStatus.PENDING,
                        title=f"🔴 Presupuesto Excedido: {category_name}",
                        message=(
                            f"Has excedido tu presupuesto de '{category_name}'. "
                            f"Gastaste: ₡{spent:,.0f} de ₡{budget.amount_crc:,.0f} "
                            f"({percentage:.0f}%). Considera reducir gastos."
                        ),
                        action_url=f"/Presupuestos?category={budget.category_id}",
                    )
                    alerts.append(alert)
                    logger.warning(
                        f"Alerta CRÍTICA: Budget 100% - {category_name}",
                        extra={"profile_id": profile_id, "percentage": float(percentage)},
                    )

            # 80-99% → WARNING
            elif percentage >= 80:
                if not self._alert_already_exists(
                    profile_id, AlertType.BUDGET_80_PERCENT, related_id=budget.id
                ):
                    category = self.session.get(Category, budget.category_id)
                    category_name = category.nombre if category else "Categoría"

                    alert = Alert(
                        id=str(uuid4()),
                        profile_id=profile_id,
                        budget_id=budget.id,
                        alert_type=AlertType.BUDGET_80_PERCENT,
                        priority=AlertPriority.HIGH,
                        status=AlertStatus.PENDING,
                        title=f"⚠️ Acercándote al Límite: {category_name}",
                        message=(
                            f"Has usado {percentage:.0f}% de tu presupuesto de '{category_name}'. "
                            f"Gastaste: ₡{spent:,.0f} de ₡{budget.amount_crc:,.0f}. "
                            f"Te quedan ₡{budget.amount_crc - spent:,.0f}."
                        ),
                        action_url=f"/Presupuestos?category={budget.category_id}",
                    )
                    alerts.append(alert)
                    logger.info(
                        f"Alerta generada: Budget 80% - {category_name}",
                        extra={"profile_id": profile_id, "percentage": float(percentage)},
                    )

        return alerts

    # ========================================================================
    # UTILIDADES
    # ========================================================================

    def _alert_already_exists(
        self, profile_id: str, alert_type: AlertType, related_id: str | None = None
    ) -> bool:
        """
        Verifica si ya existe una alerta pendiente del mismo tipo.

        Args:
            profile_id: ID del perfil
            alert_type: Tipo de alerta
            related_id: ID de entidad relacionada (opcional)

        Returns:
            True si ya existe, False otherwise
        """
        stmt = select(Alert).where(
            Alert.profile_id == profile_id,
            Alert.alert_type == alert_type,
            Alert.status.in_([AlertStatus.PENDING, AlertStatus.READ]),
        )

        # Si hay related_id, verificar también
        if related_id:
            stmt = stmt.where(
                (Alert.transaction_id == related_id)
                | (Alert.subscription_id == related_id)
                | (Alert.budget_id == related_id)
            )

        existing = self.session.execute(stmt).scalar_one_or_none()
        return existing is not None

    def create_alert(self, alert: Alert) -> Alert:
        """
        Crea y persiste una alerta en la base de datos.

        Args:
            alert: Alerta a crear

        Returns:
            Alerta creada
        """
        self.session.add(alert)
        self.session.commit()
        self.session.refresh(alert)

        logger.info(
            f"Alerta creada: {alert.alert_type}",
            extra={"alert_id": alert.id, "profile_id": alert.profile_id},
        )

        return alert


    # ========================================================================
    # ALERTA #6: Subscription Renewal
    # ========================================================================

    def _check_subscription_renewals(self, profile_id: str) -> list[Alert]:
        """
        Alerta #6: Renovación de suscripción próxima.

        Genera alerta si:
        - Fal

tan 7 días o menos para renovación
        """
        alerts: list[Alert] = []
        today = date.today()
        threshold_date = today + timedelta(days=7)

        # Buscar suscripciones activas con renovación próxima
        stmt = select(Subscription).where(
            Subscription.profile_id == profile_id,
            Subscription.is_active == True,  # noqa: E712
            Subscription.proxima_fecha_estimada <= threshold_date,
            Subscription.proxima_fecha_estimada >= today,
        )
        subscriptions = self.session.execute(stmt).scalars().all()

        for subscription in subscriptions:
            days_until = (subscription.proxima_fecha_estimada - today).days

            # Verificar si ya existe alerta pendiente
            if self._alert_already_exists(
                profile_id, AlertType.SUBSCRIPTION_RENEWAL, related_id=subscription.id
            ):
                continue

            # Prioridad según días restantes
            if days_until <= 2:
                priority = AlertPriority.HIGH
            else:
                priority = AlertPriority.MEDIUM

            alert = Alert(
                id=str(uuid4()),
                profile_id=profile_id,
                subscription_id=subscription.id,
                alert_type=AlertType.SUBSCRIPTION_RENEWAL,
                priority=priority,
                status=AlertStatus.PENDING,
                title=f"📅 Renovación: {subscription.comercio}",
                message=(
                    f"Tu suscripción '{subscription.comercio}' se renueva en {days_until} día(s) "
                    f"({subscription.proxima_fecha_estimada.strftime('%d/%m/%Y')}). "
                    f"Monto: ₡{subscription.monto_promedio:,.0f}."
                ),
                action_url="/Suscripciones",
            )

            alerts.append(alert)
            logger.info(
                f"Alerta generada: Subscription Renewal - {subscription.comercio}",
                extra={"profile_id": profile_id, "days": days_until},
            )

        return alerts

    # ========================================================================
    # ALERTA #7: Duplicate Transaction
    # ========================================================================

    def _check_duplicate_transactions(self, profile_id: str) -> list[Alert]:
        """
        Alerta #7: Transacción duplicada detectada.

        Genera alerta si:
        - 2+ transacciones con mismo comercio, monto y fecha (dentro de 48h)
        """
        alerts: list[Alert] = []
        today = date.today()
        lookback_date = today - timedelta(days=2)

        # Buscar transacciones recientes
        stmt = select(Transaction).where(
            Transaction.profile_id == profile_id,
            Transaction.fecha_transaccion >= lookback_date,
        )
        recent_transactions = self.session.execute(stmt).scalars().all()

        # Agrupar por comercio + monto
        groups: dict[tuple[str, Decimal], list[Transaction]] = {}
        for tx in recent_transactions:
            key = (tx.comercio, tx.monto_crc)
            if key not in groups:
                groups[key] = []
            groups[key].append(tx)

        # Detectar duplicados
        for (comercio, monto), transactions in groups.items():
            if len(transactions) >= 2:
                # Verificar si ya existe alerta para este grupo
                tx_ids = [tx.id for tx in transactions]
                found_alert = False
                for tx_id in tx_ids:
                    if self._alert_already_exists(
                        profile_id, AlertType.DUPLICATE_TRANSACTION, related_id=tx_id
                    ):
                        found_alert = True
                        break

                if found_alert:
                    continue

                # Generar alerta
                alert = Alert(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    transaction_id=transactions[0].id,  # Referenciar la primera
                    alert_type=AlertType.DUPLICATE_TRANSACTION,
                    priority=AlertPriority.HIGH,
                    status=AlertStatus.PENDING,
                    title="⚠️ Posible Transacción Duplicada",
                    message=(
                        f"Detectamos {len(transactions)} transacciones idénticas en '{comercio}' "
                        f"por ₡{monto:,.2f} en las últimas 48 horas. "
                        f"Verifica que no sea un cargo duplicado."
                    ),
                    action_url="/Transacciones",
                )

                alerts.append(alert)
                logger.warning(
                    f"Alerta generada: Duplicate Transaction - {comercio}",
                    extra={"profile_id": profile_id, "count": len(transactions)},
                )

        return alerts

    # ========================================================================
    # ALERTA #8: High Interest Projection
    # ========================================================================

    def _check_high_interest_projection(self, profile_id: str) -> list[Alert]:
        """
        Alerta #8: Proyección de intereses altos.

        Genera alerta si:
        - Hay saldo pendiente en tarjeta de crédito
        - Pagar solo el mínimo genera > ₡20,000 en intereses mensuales
        """
        alerts: list[Alert] = []

        # Buscar tarjetas de crédito con saldo, tasa de interés y pago mínimo configurados
        from finanzas_tracker.models.card import Card

        stmt = select(Card).where(
            Card.profile_id == profile_id,
            Card.tipo == CardType.CREDIT,
            Card.activa == True,  # noqa: E712
            Card.current_balance.is_not(None),
            Card.interest_rate_annual.is_not(None),
            Card.minimum_payment_percentage.is_not(None),
        )
        credit_cards = self.session.execute(stmt).scalars().all()

        for card in credit_cards:
            if not card.current_balance or card.current_balance <= 0:
                continue

            # Calcular interés mensual
            # Fórmula: (Saldo * Tasa Anual / 12)
            monthly_interest_rate = card.interest_rate_annual / Decimal("12")
            monthly_interest = card.current_balance * (monthly_interest_rate / Decimal("100"))

            # Threshold: ₡20,000 de interés mensual
            interest_threshold = Decimal("20000")

            if monthly_interest >= interest_threshold:
                # Verificar si ya existe alerta pendiente
                if self._alert_already_exists(
                    profile_id, AlertType.HIGH_INTEREST_PROJECTION, related_id=card.id
                ):
                    continue

                # Calcular pago mínimo
                minimum_payment = card.current_balance * (
                    card.minimum_payment_percentage / Decimal("100")
                )

                # Prioridad según magnitud del interés
                if monthly_interest >= Decimal("50000"):
                    priority = AlertPriority.CRITICAL
                elif monthly_interest >= Decimal("30000"):
                    priority = AlertPriority.HIGH
                else:
                    priority = AlertPriority.MEDIUM

                alert = Alert(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    alert_type=AlertType.HIGH_INTEREST_PROJECTION,
                    priority=priority,
                    status=AlertStatus.PENDING,
                    title=f"💰 ¡Cuidado con los Intereses! - {card.nombre_display}",
                    message=(
                        f"Tu tarjeta {card.nombre_display} tiene un saldo de ₡{card.current_balance:,.0f}. "
                        f"Si solo pagas el mínimo (₡{minimum_payment:,.0f}), pagarás ~₡{monthly_interest:,.0f} "
                        f"en intereses este mes ({monthly_interest_rate:.2f}% mensual). "
                        f"Considera pagar más del mínimo para ahorrar en intereses."
                    ),
                    action_url="/Tarjetas",
                    card_id=card.id,
                )

                alerts.append(alert)
                logger.warning(
                    f"Alerta generada: High Interest Projection - {card.nombre_display}",
                    extra={
                        "profile_id": profile_id,
                        "card_id": card.id,
                        "balance": float(card.current_balance),
                        "monthly_interest": float(monthly_interest),
                    },
                )

        return alerts

    # ========================================================================
    # ALERTA #9: Card Expiration
    # ========================================================================

    def _check_card_expiration(self, profile_id: str) -> list[Alert]:
        """
        Alerta #9: Vencimiento de tarjeta física.

        Genera alerta si:
        - Faltan 60 días o menos para que expire la tarjeta física
        """
        alerts: list[Alert] = []
        today = date.today()
        threshold_date = today + timedelta(days=60)

        # Buscar tarjetas con fecha de vencimiento configurada
        from finanzas_tracker.models.card import Card

        stmt = select(Card).where(
            Card.profile_id == profile_id,
            Card.activa == True,  # noqa: E712
            Card.card_expiration_date.is_not(None),
            Card.card_expiration_date <= threshold_date,
            Card.card_expiration_date >= today,  # No alertar sobre tarjetas ya vencidas
        )
        expiring_cards = self.session.execute(stmt).scalars().all()

        for card in expiring_cards:
            days_until = (card.card_expiration_date - today).days

            # Verificar si ya existe alerta pendiente
            if self._alert_already_exists(
                profile_id, AlertType.CARD_EXPIRATION, related_id=card.id
            ):
                continue

            # Prioridad según días restantes
            if days_until <= 15:
                priority = AlertPriority.CRITICAL
            elif days_until <= 30:
                priority = AlertPriority.HIGH
            else:
                priority = AlertPriority.MEDIUM

            alert = Alert(
                id=str(uuid4()),
                profile_id=profile_id,
                alert_type=AlertType.CARD_EXPIRATION,
                priority=priority,
                status=AlertStatus.PENDING,
                title=f"💳 Tarjeta por Vencer - {card.nombre_display}",
                message=(
                    f"Tu tarjeta {card.nombre_display} vence en {days_until} día(s) "
                    f"({card.card_expiration_date.strftime('%m/%Y')}). "
                    f"Contactá a tu banco para solicitar una nueva tarjeta si aún no te llegó."
                ),
                action_url="/Tarjetas",
                card_id=card.id,
            )

            alerts.append(alert)
            logger.info(
                f"Alerta generada: Card Expiration - {card.nombre_display}",
                extra={
                    "profile_id": profile_id,
                    "card_id": card.id,
                    "days_until": days_until,
                    "expiration_date": card.card_expiration_date.isoformat(),
                },
            )

        return alerts

    # ========================================================================
    # ALERTA #10: Uncategorized Transactions
    # ========================================================================

    def _check_uncategorized_transactions(self, profile_id: str) -> list[Alert]:
        """
        Alerta #10: Transacciones sin categorizar.

        Genera alerta si:
        - Hay 10+ transacciones sin categoría
        """
        alerts: list[Alert] = []

        # Contar transacciones sin categoría
        stmt = select(func.count(Transaction.id)).where(
            Transaction.profile_id == profile_id,
            Transaction.subcategory_id.is_(None),
        )
        uncategorized_count = self.session.execute(stmt).scalar_one()

        if uncategorized_count >= 10:
            # Verificar si ya existe alerta pendiente
            if self._alert_already_exists(
                profile_id, AlertType.UNCATEGORIZED_TRANSACTIONS
            ):
                return alerts

            alert = Alert(
                id=str(uuid4()),
                profile_id=profile_id,
                alert_type=AlertType.UNCATEGORIZED_TRANSACTIONS,
                priority=AlertPriority.MEDIUM,
                status=AlertStatus.PENDING,
                title="📊 Transacciones Sin Categorizar",
                message=(
                    f"Tienes {uncategorized_count} transacciones sin categoría. "
                    f"Categorizarlas mejora tus análisis y presupuestos. "
                    f"¿Las revisamos?"
                ),
                action_url="/Transacciones?filter=uncategorized",
            )

            alerts.append(alert)
            logger.info(
                "Alerta generada: Uncategorized Transactions",
                extra={"profile_id": profile_id, "count": uncategorized_count},
            )

        return alerts

    # ========================================================================
    # FASE 2 - NEGATIVE/PREVENTIVE ALERTS
    # ========================================================================

    def _check_overdraft_projection(self, profile_id: str) -> list[Alert]:
        """
        Alerta Fase 2: Proyección de sobregiro.

        Genera alerta si proyecta quedarse sin fondos antes de fin de mes.
        """
        alerts: list[Alert] = []
        today = date.today()

        # Obtener ingresos del mes actual
        stmt = select(func.sum(Income.monto_crc)).where(
            Income.profile_id == profile_id,
            func.extract("year", Income.fecha) == today.year,
            func.extract("month", Income.fecha) == today.month,
        )
        total_income = self.session.execute(stmt).scalar_one() or Decimal("0")

        # Obtener gastos del mes actual
        stmt = select(func.sum(Transaction.monto_crc)).where(
            Transaction.profile_id == profile_id,
            Transaction.debe_contar_en_presupuesto == True,  # noqa: E712
            func.extract("year", Transaction.fecha_transaccion) == today.year,
            func.extract("month", Transaction.fecha_transaccion) == today.month,
        )
        total_spending = self.session.execute(stmt).scalar_one() or Decimal("0")

        # Proyectar gastos al final del mes
        days_elapsed = today.day
        if days_elapsed == 0:
            return alerts

        projected_spending = (total_spending / days_elapsed) * 30
        deficit_projected = projected_spending - total_income
        available_funds = total_income - total_spending

        # Alerta si proyecta deficit
        if deficit_projected > Decimal("0") and available_funds < deficit_projected:
            if self._alert_already_exists(profile_id, AlertType.OVERDRAFT_PROJECTION):
                return alerts

            alert = Alert(
                id=str(uuid4()),
                profile_id=profile_id,
                alert_type=AlertType.OVERDRAFT_PROJECTION,
                priority=AlertPriority.CRITICAL,
                status=AlertStatus.PENDING,
                title="⛔ ¡Alerta de Sobregiro Proyectado!",
                message=(
                    f"Según tu ritmo de gasto actual, proyectamos un déficit de ₡{deficit_projected:,.0f} "
                    f"para fin de mes. Tus ingresos son ₡{total_income:,.0f} pero proyectamos gastos de "
                    f"₡{projected_spending:,.0f}. Considerá reducir gastos opcionales."
                ),
                action_url="/Dashboard",
            )

            alerts.append(alert)
            logger.warning("Alerta generada: Overdraft Projection", extra={"profile_id": profile_id})

        return alerts

    def _check_low_savings_warning(self, profile_id: str) -> list[Alert]:
        """
        Alerta Fase 2: Ahorro mínimo crítico.

        Genera alerta si ahorros < 1 mes de gastos promedio.
        """
        alerts: list[Alert] = []

        # Calcular gastos promedio mensual (últimos 3 meses)
        three_months_ago = date.today() - timedelta(days=90)
        stmt = select(func.sum(Transaction.monto_crc)).where(
            Transaction.profile_id == profile_id,
            Transaction.debe_contar_en_presupuesto == True,  # noqa: E712
            Transaction.fecha_transaccion >= three_months_ago,
        )
        total_spending_3m = self.session.execute(stmt).scalar_one() or Decimal("0")
        avg_monthly_spending = total_spending_3m / Decimal("3")

        # Obtener ahorros actuales (aproximado con ingresos de inversión)
        stmt = select(func.sum(Income.monto_crc)).where(
            Income.profile_id == profile_id, Income.tipo == "inversion"
        )
        total_savings = self.session.execute(stmt).scalar_one() or Decimal("0")

        # Umbral: < 1 mes de gastos
        if avg_monthly_spending > 0 and total_savings < avg_monthly_spending:
            if self._alert_already_exists(profile_id, AlertType.LOW_SAVINGS_WARNING):
                return alerts

            months_covered = total_savings / avg_monthly_spending if avg_monthly_spending > 0 else 0

            alert = Alert(
                id=str(uuid4()),
                profile_id=profile_id,
                alert_type=AlertType.LOW_SAVINGS_WARNING,
                priority=AlertPriority.HIGH,
                status=AlertStatus.PENDING,
                title="📉 Ahorros Bajos - Fondo de Emergencia Insuficiente",
                message=(
                    f"Tus ahorros actuales (₡{total_savings:,.0f}) cubren solo {months_covered:.1f} "
                    f"mes(es) de gastos. Lo ideal es tener al menos 3-6 meses. "
                    f"Tu gasto mensual promedio es ₡{avg_monthly_spending:,.0f}."
                ),
                action_url="/Dashboard",
            )

            alerts.append(alert)
            logger.warning("Alerta generada: Low Savings Warning", extra={"profile_id": profile_id})

        return alerts

    def _check_unknown_merchant_high(self, profile_id: str) -> list[Alert]:
        """
        Alerta Fase 2: Cargo alto en comercio desconocido.

        Detecta posibles fraudes o compras no reconocidas.
        """
        alerts: list[Alert] = []
        threshold_amount = Decimal("50000")
        days_window = 7

        # Buscar transacciones recientes grandes sin merchant
        since_date = date.today() - timedelta(days=days_window)
        stmt = select(Transaction).where(
            Transaction.profile_id == profile_id,
            Transaction.monto_crc >= threshold_amount,
            Transaction.fecha_transaccion >= since_date,
            Transaction.merchant_id.is_(None),
        )
        unknown_high_txs = self.session.execute(stmt).scalars().all()

        for tx in unknown_high_txs:
            if self._alert_already_exists(
                profile_id, AlertType.UNKNOWN_MERCHANT_HIGH, related_id=tx.id
            ):
                continue

            alert = Alert(
                id=str(uuid4()),
                profile_id=profile_id,
                alert_type=AlertType.UNKNOWN_MERCHANT_HIGH,
                priority=AlertPriority.HIGH,
                status=AlertStatus.PENDING,
                title="❓ Cargo Alto en Comercio Desconocido",
                message=(
                    f"Detectamos un cargo de ₡{tx.monto_crc:,.0f} en '{tx.descripcion}' "
                    f"el {tx.fecha_transaccion.strftime('%d/%m/%Y')}. "
                    f"¿Reconocés esta transacción? Si no, podría ser fraude."
                ),
                action_url=f"/Transacciones?tx={tx.id}",
                transaction_id=tx.id,
            )

            alerts.append(alert)
            logger.warning("Alerta generada: Unknown Merchant High", extra={"profile_id": profile_id})

        return alerts

    def _check_credit_utilization_high(self, profile_id: str) -> list[Alert]:
        """
        Alerta Fase 2: Utilización de crédito alta.

        Afecta credit score si utilización > 70%.
        """
        alerts: list[Alert] = []

        # Buscar tarjetas de crédito con límite y saldo
        stmt = select(Card).where(
            Card.profile_id == profile_id,
            Card.tipo == CardType.CREDIT,
            Card.activa == True,  # noqa: E712
            Card.limite_credito.is_not(None),
            Card.current_balance.is_not(None),
        )
        credit_cards = self.session.execute(stmt).scalars().all()

        for card in credit_cards:
            if not card.limite_credito or not card.current_balance:
                continue

            utilization = (card.current_balance / card.limite_credito) * 100

            if utilization > 70:
                if self._alert_already_exists(
                    profile_id, AlertType.CREDIT_UTILIZATION_HIGH, related_id=card.id
                ):
                    continue

                # Prioridad según utilización
                if utilization >= 90:
                    priority = AlertPriority.CRITICAL
                elif utilization >= 80:
                    priority = AlertPriority.HIGH
                else:
                    priority = AlertPriority.MEDIUM

                alert = Alert(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    alert_type=AlertType.CREDIT_UTILIZATION_HIGH,
                    priority=priority,
                    status=AlertStatus.PENDING,
                    title=f"📊 Utilización de Crédito Alta - {card.nombre_display}",
                    message=(
                        f"Estás utilizando {utilization:.1f}% de tu límite de crédito "
                        f"(₡{card.current_balance:,.0f} de ₡{card.limite_credito:,.0f}). "
                        f"Mantener bajo 30% es ideal para tu score crediticio."
                    ),
                    action_url="/Tarjetas",
                    card_id=card.id,
                )

                alerts.append(alert)
                logger.warning("Alerta generada: Credit Utilization High", extra={"profile_id": profile_id})

        return alerts

    def _check_spending_velocity_high(self, profile_id: str) -> list[Alert]:
        """
        Alerta Fase 2: Velocidad de gasto anormal.

        Gasto diario últimos 3 días > 2x promedio histórico.
        """
        alerts: list[Alert] = []
        today = date.today()

        # Gasto últimos 3 días
        three_days_ago = today - timedelta(days=3)
        stmt = select(func.sum(Transaction.monto_crc)).where(
            Transaction.profile_id == profile_id,
            Transaction.debe_contar_en_presupuesto == True,  # noqa: E712
            Transaction.fecha_transaccion >= three_days_ago,
        )
        recent_spending = self.session.execute(stmt).scalar_one() or Decimal("0")
        daily_recent = recent_spending / Decimal("3")

        # Gasto promedio histórico (últimos 90 días, excluyendo últimos 3)
        ninety_days_ago = today - timedelta(days=90)
        stmt = select(func.sum(Transaction.monto_crc)).where(
            Transaction.profile_id == profile_id,
            Transaction.debe_contar_en_presupuesto == True,  # noqa: E712
            Transaction.fecha_transaccion >= ninety_days_ago,
            Transaction.fecha_transaccion < three_days_ago,
        )
        historical_spending = self.session.execute(stmt).scalar_one() or Decimal("0")
        daily_historical = historical_spending / Decimal("87")

        # Umbral: > 2x promedio
        if daily_historical > 0 and daily_recent > (daily_historical * 2):
            if self._alert_already_exists(profile_id, AlertType.SPENDING_VELOCITY_HIGH):
                return alerts

            increase_pct = ((daily_recent / daily_historical) - 1) * 100

            alert = Alert(
                id=str(uuid4()),
                profile_id=profile_id,
                alert_type=AlertType.SPENDING_VELOCITY_HIGH,
                priority=AlertPriority.HIGH,
                status=AlertStatus.PENDING,
                title="⚡ Velocidad de Gasto Inusual",
                message=(
                    f"Tu gasto diario de los últimos 3 días (₡{daily_recent:,.0f}/día) "
                    f"es {increase_pct:.0f}% mayor que tu promedio histórico (₡{daily_historical:,.0f}/día). "
                    f"¿Hay algún gasto extraordinario o podés reducir?"
                ),
                action_url="/Transacciones",
            )

            alerts.append(alert)
            logger.warning("Alerta generada: Spending Velocity High", extra={"profile_id": profile_id})

        return alerts

    def _check_seasonal_spending_warning(self, profile_id: str) -> list[Alert]:
        """
        Alerta Fase 2: Patrón estacional de gasto.

        Detecta épocas de alto gasto (Navidad, etc).
        """
        alerts: list[Alert] = []
        today = date.today()

        # Definir épocas de alto gasto
        is_high_spending_season = False
        season_name = ""

        if today.month == 12:
            is_high_spending_season, season_name = True, "Navidad"
        elif today.month in [1, 2]:
            is_high_spending_season, season_name = True, "Inicio de Año"
        elif today.month == 7:
            is_high_spending_season, season_name = True, "Vacaciones"

        if not is_high_spending_season:
            return alerts

        # Comparar gasto del mes vs promedio
        stmt = select(func.sum(Transaction.monto_crc)).where(
            Transaction.profile_id == profile_id,
            Transaction.debe_contar_en_presupuesto == True,  # noqa: E712
            func.extract("year", Transaction.fecha_transaccion) == today.year,
            func.extract("month", Transaction.fecha_transaccion) == today.month,
        )
        current_month_spending = self.session.execute(stmt).scalar_one() or Decimal("0")

        # Promedio meses normales (últimos 6 meses, excluyendo diciembre)
        six_months_ago = today - timedelta(days=180)
        stmt = select(func.avg(Transaction.monto_crc)).where(
            Transaction.profile_id == profile_id,
            Transaction.debe_contar_en_presupuesto == True,  # noqa: E712
            Transaction.fecha_transaccion >= six_months_ago,
            func.extract("month", Transaction.fecha_transaccion) != 12,
        )
        avg_normal_spending = self.session.execute(stmt).scalar_one() or Decimal("0")

        # Si gasto actual > 150% del promedio
        if avg_normal_spending > 0 and current_month_spending > (avg_normal_spending * Decimal("1.5")):
            if self._alert_already_exists(profile_id, AlertType.SEASONAL_SPENDING_WARNING):
                return alerts

            alert = Alert(
                id=str(uuid4()),
                profile_id=profile_id,
                alert_type=AlertType.SEASONAL_SPENDING_WARNING,
                priority=AlertPriority.MEDIUM,
                status=AlertStatus.PENDING,
                title=f"🎄 Gasto Elevado en Época de {season_name}",
                message=(
                    f"Estamos en época de {season_name} y tu gasto este mes (₡{current_month_spending:,.0f}) "
                    f"es mayor que tu promedio (₡{avg_normal_spending:,.0f}). "
                    f"Es normal gastar más en esta época, pero vigilá no excederte demasiado."
                ),
                action_url="/Dashboard",
            )

            alerts.append(alert)
            logger.info("Alerta generada: Seasonal Spending Warning", extra={"profile_id": profile_id})

        return alerts

    def _check_goal_behind_schedule(self, profile_id: str) -> list[Alert]:
        """
        Alerta Fase 2: Meta financiera atrasada.

        Genera alerta si meta está en riesgo de no cumplirse a tiempo.
        """
        alerts: list[Alert] = []

        # Buscar metas activas que estén en riesgo
        stmt = select(SavingsGoal).where(
            SavingsGoal.profile_id == profile_id,
            SavingsGoal.is_active == True,  # noqa: E712
            SavingsGoal.is_completed == False,  # noqa: E712
            SavingsGoal.deadline.is_not(None),
        )
        goals = self.session.execute(stmt).scalars().all()

        for goal in goals:
            # Usar el property is_at_risk del modelo
            if goal.is_at_risk:
                if self._alert_already_exists(
                    profile_id, AlertType.GOAL_BEHIND_SCHEDULE, related_id=goal.id
                ):
                    continue

                # Calcular días restantes y ahorro mensual requerido
                days_left = goal.days_remaining or 0
                required_monthly = goal.required_monthly_savings or Decimal("0")
                progress_pct = goal.progress_percentage

                # Prioridad según urgencia
                if days_left <= 30:
                    priority = AlertPriority.CRITICAL
                elif days_left <= 90:
                    priority = AlertPriority.HIGH
                else:
                    priority = AlertPriority.MEDIUM

                alert = Alert(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    alert_type=AlertType.GOAL_BEHIND_SCHEDULE,
                    priority=priority,
                    status=AlertStatus.PENDING,
                    title=f"⏰ Meta Atrasada: {goal.name}",
                    message=(
                        f"Tu meta '{goal.name}' está en riesgo. Llevas {progress_pct:.0f}% de progreso "
                        f"(₡{goal.current_amount:,.0f} de ₡{goal.target_amount:,.0f}) y quedan {days_left} días. "
                        f"Necesitás ahorrar ₡{required_monthly:,.0f}/mes para lograrlo a tiempo."
                    ),
                    action_url="/Metas",
                    savings_goal_id=goal.id,
                )

                alerts.append(alert)
                logger.warning("Alerta generada: Goal Behind Schedule", extra={"profile_id": profile_id})

        return alerts

    # ========================================================================
    # FASE 2 - POSITIVE ALERTS (GAMIFICATION/MOTIVATION)
    # ========================================================================

    def _check_spending_reduction(self, profile_id: str) -> list[Alert]:
        """
        Alerta Positiva: Reducción significativa en categoría.

        Celebra cuando reduce >30% gasto en una categoría vs mes anterior.
        """
        alerts: list[Alert] = []
        today = date.today()
        current_month = today.month
        current_year = today.year

        # Mes anterior
        if current_month == 1:
            prev_month, prev_year = 12, current_year - 1
        else:
            prev_month, prev_year = current_month - 1, current_year

        # Obtener subcategorías usadas por el usuario
        stmt = select(Subcategory).join(Transaction).where(
            Transaction.profile_id == profile_id,
            Transaction.subcategory_id.is_not(None)
        ).distinct()
        subcategories = self.session.execute(stmt).scalars().all()

        for category in subcategories:
            # Gasto mes actual
            stmt = select(func.sum(Transaction.monto_crc)).where(
                Transaction.profile_id == profile_id,
                Transaction.subcategory_id == category.id,
                func.extract("year", Transaction.fecha_transaccion) == current_year,
                func.extract("month", Transaction.fecha_transaccion) == current_month,
            )
            current_spending = self.session.execute(stmt).scalar_one() or Decimal("0")

            # Gasto mes anterior
            stmt = select(func.sum(Transaction.monto_crc)).where(
                Transaction.profile_id == profile_id,
                Transaction.subcategory_id == category.id,
                func.extract("year", Transaction.fecha_transaccion) == prev_year,
                func.extract("month", Transaction.fecha_transaccion) == prev_month,
            )
            prev_spending = self.session.execute(stmt).scalar_one() or Decimal("0")

            if prev_spending == 0:
                continue

            # Calcular reducción
            reduction_pct = ((prev_spending - current_spending) / prev_spending) * 100

            if reduction_pct >= 30:
                if self._alert_already_exists(
                    profile_id, AlertType.SPENDING_REDUCTION, related_id=category.id
                ):
                    continue

                alert = Alert(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    alert_type=AlertType.SPENDING_REDUCTION,
                    priority=AlertPriority.LOW,
                    status=AlertStatus.PENDING,
                    title=f"🎯 ¡Excelente! Reduciste {reduction_pct:.0f}% en {category.nombre}",
                    message=(
                        f"¡Felicitaciones! Este mes gastaste ₡{current_spending:,.0f} en {category.nombre}, "
                        f"una reducción del {reduction_pct:.0f}% comparado con el mes pasado "
                        f"(₡{prev_spending:,.0f}). ¡Seguí así!"
                    ),
                    action_url="/Dashboard",
                )

                alerts.append(alert)
                logger.info("Alerta generada: Spending Reduction", extra={"profile_id": profile_id})

        return alerts

    def _check_savings_milestone(self, profile_id: str) -> list[Alert]:
        """
        Alerta Positiva: Milestone de ahorro alcanzado.

        Celebra cuando alcanza hitos de ahorro (₡100k, ₡500k, ₡1M, etc).
        """
        alerts: list[Alert] = []

        # Obtener ahorros totales
        stmt = select(func.sum(Income.monto_crc)).where(
            Income.profile_id == profile_id, Income.tipo == "inversion"
        )
        total_savings = self.session.execute(stmt).scalar_one() or Decimal("0")

        # Milestones: 100k, 500k, 1M, 2M, 5M, 10M
        milestones = [
            (Decimal("100000"), "₡100 mil"),
            (Decimal("500000"), "₡500 mil"),
            (Decimal("1000000"), "₡1 millón"),
            (Decimal("2000000"), "₡2 millones"),
            (Decimal("5000000"), "₡5 millones"),
            (Decimal("10000000"), "₡10 millones"),
        ]

        for milestone_amount, milestone_name in milestones:
            if total_savings >= milestone_amount:
                # Verificar si ya celebramos este milestone
                if self._alert_already_exists(profile_id, AlertType.SAVINGS_MILESTONE):
                    continue

                alert = Alert(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    alert_type=AlertType.SAVINGS_MILESTONE,
                    priority=AlertPriority.LOW,
                    status=AlertStatus.PENDING,
                    title=f"🏆 ¡Milestone Alcanzado! {milestone_name} en Ahorros",
                    message=(
                        f"¡Increíble! Alcanzaste {milestone_name} en ahorros totales. "
                        f"Tu saldo actual es ₡{total_savings:,.0f}. ¡Seguí construyendo tu futuro financiero!"
                    ),
                    action_url="/Dashboard",
                )

                alerts.append(alert)
                logger.info("Alerta generada: Savings Milestone", extra={"profile_id": profile_id})
                break  # Solo un milestone a la vez

        return alerts

    def _check_budget_under_target(self, profile_id: str) -> list[Alert]:
        """
        Alerta Positiva: Gastó menos del presupuesto.

        Celebra cuando gasta <90% del presupuesto mensual.
        """
        alerts: list[Alert] = []
        today = date.today()

        # Obtener presupuestos activos del mes
        stmt = select(Budget).where(
            Budget.profile_id == profile_id,
            func.extract("year", Budget.mes) == today.year,
            func.extract("month", Budget.mes) == today.month,
        )
        budgets = self.session.execute(stmt).scalars().all()

        for budget in budgets:
            if budget.monto_limite == 0:
                continue

            # Calcular gasto actual de la categoría
            stmt = select(func.sum(Transaction.monto_crc)).where(
                Transaction.profile_id == profile_id,
                Transaction.subcategory_id == budget.category_id,
                func.extract("year", Transaction.fecha_transaccion) == today.year,
                func.extract("month", Transaction.fecha_transaccion) == today.month,
            )
            current_spending = self.session.execute(stmt).scalar_one() or Decimal("0")

            utilization_pct = (current_spending / budget.monto_limite) * 100

            # Celebrar si está bajo 90% y estamos cerca del fin del mes (día 25+)
            if utilization_pct < 90 and today.day >= 25:
                if self._alert_already_exists(
                    profile_id, AlertType.BUDGET_UNDER_TARGET, related_id=budget.id
                ):
                    continue

                category_name = budget.category.nombre if budget.category else "esta categoría"

                alert = Alert(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    alert_type=AlertType.BUDGET_UNDER_TARGET,
                    priority=AlertPriority.LOW,
                    status=AlertStatus.PENDING,
                    title=f"✨ ¡Bien Hecho! Bajo Presupuesto en {category_name}",
                    message=(
                        f"¡Excelente! Solo usaste {utilization_pct:.0f}% de tu presupuesto en {category_name}. "
                        f"Gastaste ₡{current_spending:,.0f} de ₡{budget.monto_limite:,.0f} permitidos. "
                        f"¡Seguí con este control!"
                    ),
                    action_url="/Presupuestos",
                    budget_id=budget.id,
                )

                alerts.append(alert)
                logger.info("Alerta generada: Budget Under Target", extra={"profile_id": profile_id})

        return alerts

    def _check_debt_payment_progress(self, profile_id: str) -> list[Alert]:
        """
        Alerta Positiva: Progreso pagando deudas.

        Celebra cuando el saldo de la tarjeta es significativamente menor
        que las compras del mes (indica pago extra).
        """
        alerts: list[Alert] = []
        today = date.today()

        # Buscar tarjetas de crédito con saldo
        stmt = select(Card).where(
            Card.profile_id == profile_id,
            Card.tipo == CardType.CREDIT,
            Card.activa == True,  # noqa: E712
            Card.current_balance.is_not(None),
        )
        credit_cards = self.session.execute(stmt).scalars().all()

        for card in credit_cards:
            if not card.current_balance or card.current_balance == 0:
                continue

            # Calcular compras del mes actual con esta tarjeta
            stmt = select(func.sum(Transaction.monto_crc)).where(
                Transaction.profile_id == profile_id,
                Transaction.card_id == card.id,
                func.extract("year", Transaction.fecha_transaccion) == today.year,
                func.extract("month", Transaction.fecha_transaccion) == today.month,
            )
            monthly_charges = self.session.execute(stmt).scalar_one() or Decimal("0")

            # Si el saldo actual es mucho menor que las compras del mes,
            # significa que pagó saldo anterior + parte del actual
            if monthly_charges > 0:
                # Calcular "saldo anterior" aproximado
                previous_balance = card.current_balance + monthly_charges

                # Si pagó >30% del saldo anterior, celebrar
                if previous_balance > 0:
                    payment_ratio = (previous_balance - card.current_balance) / previous_balance
                    reduction_pct = payment_ratio * 100

                    if reduction_pct >= 30:
                        if self._alert_already_exists(
                            profile_id, AlertType.DEBT_PAYMENT_PROGRESS, related_id=card.id
                        ):
                            continue

                        paid_amount = previous_balance - card.current_balance

                        alert = Alert(
                            id=str(uuid4()),
                            profile_id=profile_id,
                            alert_type=AlertType.DEBT_PAYMENT_PROGRESS,
                            priority=AlertPriority.LOW,
                            status=AlertStatus.PENDING,
                            title=f"💪 ¡Gran Progreso! Reduciendo Deuda - {card.nombre_display}",
                            message=(
                                f"¡Excelente! Pagaste ₡{paid_amount:,.0f} en {card.nombre_display} este mes, "
                                f"reduciendo {reduction_pct:.0f}% del saldo. "
                                f"Saldo actual: ₡{card.current_balance:,.0f}. ¡Seguí así para estar libre de deudas!"
                            ),
                            action_url="/Tarjetas",
                            card_id=card.id,
                        )

                        alerts.append(alert)
                        logger.info("Alerta generada: Debt Payment Progress", extra={"profile_id": profile_id})

        return alerts

    def _check_streak_achievement(self, profile_id: str) -> list[Alert]:
        """
        Alerta Positiva: X meses seguidos bajo presupuesto.

        Celebra rachas de 3, 6, 12 meses cumpliendo presupuestos.
        """
        alerts: list[Alert] = []
        today = date.today()

        # Verificar últimos N meses (hasta 12)
        consecutive_months = 0
        max_months_to_check = 12

        for months_ago in range(max_months_to_check):
            # Calcular fecha del mes a revisar
            target_date = today - timedelta(days=30 * months_ago)
            target_year = target_date.year
            target_month = target_date.month

            # Obtener presupuestos de ese mes
            stmt = select(Budget).where(
                Budget.profile_id == profile_id,
                func.extract("year", Budget.mes) == target_year,
                func.extract("month", Budget.mes) == target_month,
            )
            budgets = self.session.execute(stmt).scalars().all()

            if not budgets:
                break  # No hay presupuestos configurados en este mes, romper racha

            # Verificar si cumplió TODOS los presupuestos de ese mes
            all_budgets_met = True
            for budget in budgets:
                # Calcular gasto real de la categoría en ese mes
                stmt = select(func.sum(Transaction.monto_crc)).where(
                    Transaction.profile_id == profile_id,
                    Transaction.subcategory_id == budget.category_id,
                    func.extract("year", Transaction.fecha_transaccion) == target_year,
                    func.extract("month", Transaction.fecha_transaccion) == target_month,
                )
                actual_spending = self.session.execute(stmt).scalar_one() or Decimal("0")

                # Si excedió el límite, no cumplió
                if actual_spending > budget.monto_limite:
                    all_budgets_met = False
                    break

            if all_budgets_met:
                consecutive_months += 1
            else:
                break  # Rompe la racha

        # Milestones para celebrar: 3, 6, 12 meses
        milestones = [(3, "3 meses"), (6, "6 meses"), (12, "1 año")]

        for milestone_months, milestone_name in milestones:
            if consecutive_months >= milestone_months:
                if self._alert_already_exists(profile_id, AlertType.STREAK_ACHIEVEMENT):
                    continue

                alert = Alert(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    alert_type=AlertType.STREAK_ACHIEVEMENT,
                    priority=AlertPriority.LOW,
                    status=AlertStatus.PENDING,
                    title=f"🔥 ¡Racha Increíble! {milestone_name} Bajo Presupuesto",
                    message=(
                        f"¡Impresionante disciplina! Llevas {consecutive_months} meses consecutivos "
                        f"cumpliendo todos tus presupuestos. ¡Esta racha demuestra un control financiero excepcional!"
                    ),
                    action_url="/Presupuestos",
                )

                alerts.append(alert)
                logger.info("Alerta generada: Streak Achievement", extra={"profile_id": profile_id})
                break  # Solo celebrar el milestone más alto alcanzado

        return alerts

    def _check_category_improvement(self, profile_id: str) -> list[Alert]:
        """
        Alerta Positiva: Mejora sostenida en categoría.

        Celebra cuando reduce gastos en categoría durante 3 meses consecutivos.
        """
        alerts: list[Alert] = []
        today = date.today()

        # Obtener categorías
        stmt = select(Category).where(Category.profile_id == profile_id)
        categories = self.session.execute(stmt).scalars().all()

        for category in categories:
            # Calcular gasto últimos 3 meses
            spending_by_month = []
            for month_offset in range(3):
                target_date = today - timedelta(days=30 * month_offset)
                stmt = select(func.sum(Transaction.monto_crc)).where(
                    Transaction.profile_id == profile_id,
                    Transaction.subcategory_id == category.id,
                    func.extract("year", Transaction.fecha_transaccion) == target_date.year,
                    func.extract("month", Transaction.fecha_transaccion) == target_date.month,
                )
                spending = self.session.execute(stmt).scalar_one() or Decimal("0")
                spending_by_month.append(spending)

            # Verificar tendencia decreciente (cada mes < anterior)
            if len(spending_by_month) == 3:
                if spending_by_month[0] < spending_by_month[1] < spending_by_month[2]:
                    if self._alert_already_exists(
                        profile_id, AlertType.CATEGORY_IMPROVEMENT, related_id=category.id
                    ):
                        continue

                    total_reduction = spending_by_month[2] - spending_by_month[0]
                    reduction_pct = (total_reduction / spending_by_month[2]) * 100 if spending_by_month[2] > 0 else 0

                    alert = Alert(
                        id=str(uuid4()),
                        profile_id=profile_id,
                        alert_type=AlertType.CATEGORY_IMPROVEMENT,
                        priority=AlertPriority.LOW,
                        status=AlertStatus.PENDING,
                        title=f"📈 ¡Mejora Sostenida! 3 Meses Reduciendo {category.nombre}",
                        message=(
                            f"¡Impresionante! Llevas 3 meses consecutivos reduciendo gastos en {category.nombre}. "
                            f"Reducción total: ₡{total_reduction:,.0f} ({reduction_pct:.0f}%). ¡No pares!"
                        ),
                        action_url="/Dashboard",
                    )

                    alerts.append(alert)
                    logger.info("Alerta generada: Category Improvement", extra={"profile_id": profile_id})

        return alerts

    def _check_zero_eating_out(self, profile_id: str) -> list[Alert]:
        """
        Alerta Positiva: Periodo sin gastar en comer afuera.

        Celebra cuando completa 7+ días sin gastos en Comer Afuera.
        """
        alerts: list[Alert] = []

        # Buscar categoría "Comer Afuera"
        stmt = select(Category).where(
            Category.profile_id == profile_id,
            Category.nombre.ilike("%comer%afuera%"),
        )
        eating_out_category = self.session.execute(stmt).scalar_one_or_none()

        if not eating_out_category:
            return alerts

        # Verificar últimos 7 días
        seven_days_ago = date.today() - timedelta(days=7)
        stmt = select(func.count(Transaction.id)).where(
            Transaction.profile_id == profile_id,
            Transaction.subcategory_id == eating_out_category.id,
            Transaction.fecha_transaccion >= seven_days_ago,
        )
        count = self.session.execute(stmt).scalar_one()

        if count == 0:
            if self._alert_already_exists(profile_id, AlertType.ZERO_EATING_OUT):
                return alerts

            alert = Alert(
                id=str(uuid4()),
                profile_id=profile_id,
                alert_type=AlertType.ZERO_EATING_OUT,
                priority=AlertPriority.LOW,
                status=AlertStatus.PENDING,
                title="🥗 ¡Semana Completa Sin Comer Afuera!",
                message=(
                    "¡Felicitaciones! Llevas 7 días sin gastar en comer afuera. "
                    "Estás ahorrando dinero y probablemente comiendo más saludable. ¡Seguí así!"
                ),
                action_url="/Dashboard",
            )

            alerts.append(alert)
            logger.info("Alerta generada: Zero Eating Out", extra={"profile_id": profile_id})

        return alerts

    def _check_emergency_fund_milestone(self, profile_id: str) -> list[Alert]:
        """
        Alerta Positiva: Fondo de emergencia creciendo.

        Celebra cuando fondo de emergencia cubre 3, 6, 12 meses de gastos.
        """
        alerts: list[Alert] = []

        # Calcular gastos promedio mensual
        three_months_ago = date.today() - timedelta(days=90)
        stmt = select(func.sum(Transaction.monto_crc)).where(
            Transaction.profile_id == profile_id,
            Transaction.debe_contar_en_presupuesto == True,  # noqa: E712
            Transaction.fecha_transaccion >= three_months_ago,
        )
        total_spending_3m = self.session.execute(stmt).scalar_one() or Decimal("0")
        avg_monthly_spending = total_spending_3m / Decimal("3")

        # Obtener ahorros actuales
        stmt = select(func.sum(Income.monto_crc)).where(
            Income.profile_id == profile_id, Income.tipo == "inversion"
        )
        total_savings = self.session.execute(stmt).scalar_one() or Decimal("0")

        if avg_monthly_spending == 0:
            return alerts

        months_covered = total_savings / avg_monthly_spending

        # Milestones: 3, 6, 12 meses
        milestones = [(3, "3 meses"), (6, "6 meses"), (12, "1 año")]

        for milestone_months, milestone_name in milestones:
            if months_covered >= milestone_months:
                if self._alert_already_exists(profile_id, AlertType.EMERGENCY_FUND_MILESTONE):
                    continue

                alert = Alert(
                    id=str(uuid4()),
                    profile_id=profile_id,
                    alert_type=AlertType.EMERGENCY_FUND_MILESTONE,
                    priority=AlertPriority.LOW,
                    status=AlertStatus.PENDING,
                    title=f"🛡️ ¡Fondo de Emergencia Sólido! {milestone_name} Cubiertos",
                    message=(
                        f"¡Excelente gestión financiera! Tu fondo de emergencia (₡{total_savings:,.0f}) "
                        f"ya cubre {milestone_name} de gastos. Tu promedio mensual es ₡{avg_monthly_spending:,.0f}. "
                        f"¡Estás muy bien preparado para imprevistos!"
                    ),
                    action_url="/Dashboard",
                )

                alerts.append(alert)
                logger.info("Alerta generada: Emergency Fund Milestone", extra={"profile_id": profile_id})
                break  # Solo un milestone a la vez

        return alerts

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _alert_already_exists(
        self,
        profile_id: str,
        alert_type: AlertType,
        related_id: str | None = None,
    ) -> bool:
        """
        Verifica si ya existe una alerta pendiente/activa del mismo tipo.

        Args:
            profile_id: ID del perfil
            alert_type: Tipo de alerta
            related_id: ID relacionado opcional (transaction_id, budget_id, etc.)

        Returns:
            True si ya existe, False si no
        """
        stmt = select(func.count(Alert.id)).where(
            Alert.profile_id == profile_id,
            Alert.alert_type == alert_type,
            Alert.status.in_([AlertStatus.PENDING, AlertStatus.READ]),
        )

        # Si hay related_id, verificar contra los campos de relación
        if related_id:
            stmt = stmt.where(
                (Alert.transaction_id == related_id)
                | (Alert.subscription_id == related_id)
                | (Alert.budget_id == related_id)
                | (Alert.card_id == related_id)
                | (Alert.savings_goal_id == related_id)
            )

        count = self.session.execute(stmt).scalar_one()
        return count > 0

    def create_alert(self, alert: Alert) -> Alert:
        """
        Persiste una alerta en la base de datos.

        Args:
            alert: Instancia de Alert

        Returns:
            Alert persistido
        """
        self.session.add(alert)
        self.session.commit()
        self.session.refresh(alert)
        return alert
