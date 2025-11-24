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
from finanzas_tracker.models.category import Category
from finanzas_tracker.models.enums import AlertPriority, AlertStatus, AlertType
from finanzas_tracker.models.income import Income
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
            Income.profile_id == profile_id, Income.activo == True  # noqa: E712
        )
        total_income = self.session.execute(stmt_income).scalar_one_or_none() or Decimal(
            0
        )

        if total_income == 0:
            return alerts  # No hay ingreso configurado

        # Calcular gastos del mes actual
        stmt_spending = select(func.sum(Transaction.monto_crc)).where(
            Transaction.profile_id == profile_id,
            Transaction.fecha >= month_start,
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
            Budget.profile_id == profile_id,
            Budget.is_active == True,  # noqa: E712
        )
        budgets = self.session.execute(stmt).scalars().all()

        for budget in budgets:
            # Calcular gasto en esta categoría este mes
            stmt_spending = select(func.sum(Transaction.monto_crc)).where(
                Transaction.profile_id == profile_id,
                Transaction.category_id == budget.category_id,
                Transaction.fecha >= month_start,
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
            Subscription.next_charge_date <= threshold_date,
            Subscription.next_charge_date >= today,
        )
        subscriptions = self.session.execute(stmt).scalars().all()

        for subscription in subscriptions:
            days_until = (subscription.next_charge_date - today).days

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
                title=f"📅 Renovación: {subscription.name}",
                message=(
                    f"Tu suscripción '{subscription.name}' se renueva en {days_until} día(s) "
                    f"({subscription.next_charge_date.strftime('%d/%m/%Y')}). "
                    f"Monto: ₡{subscription.amount_crc:,.0f}."
                ),
                action_url="/Suscripciones",
            )

            alerts.append(alert)
            logger.info(
                f"Alerta generada: Subscription Renewal - {subscription.name}",
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
            Transaction.fecha >= lookback_date,
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
            Transaction.category_id.is_(None),
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
