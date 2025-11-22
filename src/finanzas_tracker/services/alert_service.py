"""
Servicio de Alertas Inteligentes.

Genera alertas automáticas basadas en:
- Anomalías detectadas
- Suscripciones próximas
- Presupuestos excedidos
- Gastos inusuales
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from loguru import logger
from sqlalchemy import and_, func

from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.alert import (
    Alert,
    AlertConfig,
    AlertSeverity,
    AlertStatus,
    AlertType,
)
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.subscription import Subscription
from finanzas_tracker.models.transaction import Transaction


class AlertService:
    """
    Servicio para generar y gestionar alertas inteligentes.

    Detecta automáticamente eventos que requieren atención del usuario.
    """

    def __init__(self) -> None:
        """Inicializa el servicio de alertas."""
        logger.debug("AlertService inicializado")

    def generate_alerts_for_transaction(
        self, transaction: Transaction, profile_id: str
    ) -> list[Alert]:
        """
        Genera alertas para una transacción recién procesada.

        Args:
            transaction: Transacción a analizar
            profile_id: ID del perfil

        Returns:
            Lista de alertas generadas
        """
        alerts = []

        # Obtener configuración de alertas del usuario
        config = self._get_alert_config(profile_id)

        # 1. Alerta de anomalía detectada
        if config.enable_anomaly_alerts and transaction.is_anomaly:
            alert = self._create_anomaly_alert(transaction, profile_id)
            if alert:
                alerts.append(alert)

        # 2. Alerta de compra internacional
        if config.enable_international_alerts and transaction.es_internacional:
            alert = self._create_international_alert(transaction, profile_id)
            if alert:
                alerts.append(alert)

        # 3. Alerta de gasto alto en categoría (opcional)
        if config.enable_category_spike_alerts and transaction.subcategory_id:
            alert = self._check_category_spike(transaction, profile_id)
            if alert:
                alerts.append(alert)

        logger.info(f"Generadas {len(alerts)} alertas para transacción {transaction.id[:8]}")
        return alerts

    def generate_subscription_alerts(self, profile_id: str, days_ahead: int = 3) -> list[Alert]:
        """
        Genera alertas para suscripciones próximas a vencerse.

        Args:
            profile_id: ID del perfil
            days_ahead: Días de anticipación para alertar

        Returns:
            Lista de alertas generadas
        """
        alerts = []
        config = self._get_alert_config(profile_id)

        if not config.enable_subscription_alerts:
            return alerts

        # Obtener suscripciones próximas
        today = datetime.now(UTC).date()
        alert_date = today + timedelta(days=days_ahead)

        with get_session() as session:
            upcoming_subs = (
                session.query(Subscription)
                .filter(
                    Subscription.profile_id == profile_id,
                    Subscription.is_active == True,  # noqa: E712
                    Subscription.proxima_fecha_estimada <= alert_date,
                    Subscription.proxima_fecha_estimada >= today,
                    Subscription.deleted_at.is_(None),
                )
                .all()
            )

            for sub in upcoming_subs:
                # Verificar si ya existe alerta para esta suscripción
                existing = (
                    session.query(Alert)
                    .filter(
                        Alert.profile_id == profile_id,
                        Alert.subscription_id == sub.id,
                        Alert.alert_type == AlertType.SUBSCRIPTION_DUE,
                        Alert.status.in_([AlertStatus.PENDING, AlertStatus.READ]),
                    )
                    .first()
                )

                if not existing:
                    alert = self._create_subscription_alert(sub, profile_id)
                    if alert:
                        alerts.append(alert)
                        session.add(alert)

            session.commit()

        logger.info(f"Generadas {len(alerts)} alertas de suscripciones")
        return alerts

    def generate_budget_alerts(self, profile_id: str) -> list[Alert]:
        """
        Genera alertas si se ha excedido el presupuesto.

        Args:
            profile_id: ID del perfil

        Returns:
            Lista de alertas generadas
        """
        alerts = []
        config = self._get_alert_config(profile_id)

        if not config.enable_budget_alerts:
            return alerts

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
                return alerts

            # Calcular gasto del mes actual
            now = datetime.now(UTC)
            month_start = datetime(now.year, now.month, 1, tzinfo=UTC)

            total_spent = (
                session.query(func.sum(Transaction.monto_crc))
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.fecha_transaccion >= month_start,
                    Transaction.excluir_de_presupuesto == False,  # noqa: E712
                    Transaction.deleted_at.is_(None),
                )
                .scalar()
            ) or Decimal("0")

            # Calcular porcentaje gastado
            budget_total = budget.salario_mensual
            if budget_total > 0:
                percentage_spent = float((total_spent / budget_total) * 100)

                # Verificar si excede el umbral
                if percentage_spent >= config.budget_alert_threshold:
                    # Verificar si ya existe alerta para este mes
                    existing = (
                        session.query(Alert)
                        .filter(
                            Alert.profile_id == profile_id,
                            Alert.budget_id == budget.id,
                            Alert.alert_type == AlertType.BUDGET_EXCEEDED,
                            Alert.created_at >= month_start,
                            Alert.status.in_([AlertStatus.PENDING, AlertStatus.READ]),
                        )
                        .first()
                    )

                    if not existing:
                        alert = self._create_budget_alert(
                            budget, total_spent, percentage_spent, profile_id
                        )
                        if alert:
                            alerts.append(alert)
                            session.add(alert)

            session.commit()

        logger.info(f"Generadas {len(alerts)} alertas de presupuesto")
        return alerts

    def _get_alert_config(self, profile_id: str) -> AlertConfig:
        """
        Obtiene la configuración de alertas del perfil.

        Si no existe, crea una con valores por defecto.
        """
        with get_session() as session:
            config = (
                session.query(AlertConfig)
                .filter(AlertConfig.profile_id == profile_id)
                .first()
            )

            if not config:
                config = AlertConfig(profile_id=profile_id)
                session.add(config)
                session.commit()
                session.refresh(config)

            # Hacer merge para evitar problemas con la sesión
            config = session.merge(config)
            session.expunge(config)

            return config

    def _create_anomaly_alert(self, transaction: Transaction, profile_id: str) -> Alert | None:
        """Crea alerta de anomalía detectada."""
        if not transaction.is_anomaly:
            return None

        severity = AlertSeverity.CRITICAL if transaction.anomaly_score < -0.5 else AlertSeverity.WARNING

        # Mensaje más específico como el usuario quiere
        title = f"⚠️ Gasto inusual detectado: ₡{transaction.monto_crc:,.0f} en {transaction.comercio}"
        message = (
            f"**Transacción anómala detectada**\n\n"
            f"💰 Monto: ₡{transaction.monto_crc:,.0f}\n"
            f"🏪 Comercio: {transaction.comercio}\n"
            f"📅 Fecha: {transaction.fecha_transaccion.strftime('%d/%m/%Y %H:%M')}\n\n"
            f"**¿Por qué es inusual?**\n"
            f"{transaction.anomaly_reason or 'Patrón diferente a tus hábitos de compra'}\n\n"
            f"💡 Verifica que reconozcas esta transacción."
        )

        return Alert(
            profile_id=profile_id,
            transaction_id=transaction.id,
            alert_type=AlertType.ANOMALY_DETECTED,
            severity=severity,
            status=AlertStatus.PENDING,
            title=title,
            message=message,
        )

    def _create_international_alert(self, transaction: Transaction, profile_id: str) -> Alert | None:
        """Crea alerta de compra internacional."""
        if not transaction.es_internacional:
            return None

        title = f"🌍 Compra Internacional: {transaction.comercio}"
        message = (
            f"Se detectó una compra internacional de ₡{transaction.monto_crc:,.0f} "
            f"en {transaction.comercio}.\n\n"
            f"Fecha: {transaction.fecha_transaccion.strftime('%d/%m/%Y %H:%M')}\n\n"
            f"Verifica que reconozcas esta transacción."
        )

        return Alert(
            profile_id=profile_id,
            transaction_id=transaction.id,
            alert_type=AlertType.INTERNATIONAL_PURCHASE,
            severity=AlertSeverity.WARNING,
            status=AlertStatus.PENDING,
            title=title,
            message=message,
        )

    def _create_subscription_alert(self, subscription: Subscription, profile_id: str) -> Alert | None:
        """Crea alerta de suscripción próxima."""
        days_until = subscription.dias_hasta_proximo_cobro

        if days_until < 0:
            title = f"📅 Suscripción Vencida: {subscription.comercio}"
            severity = AlertSeverity.CRITICAL
        elif days_until == 0:
            title = f"📅 Suscripción HOY: {subscription.comercio}"
            severity = AlertSeverity.WARNING
        else:
            title = f"📅 Suscripción en {days_until} día(s): {subscription.comercio}"
            severity = AlertSeverity.INFO

        message = (
            f"Tu suscripción de {subscription.comercio} se cobrará pronto.\n\n"
            f"Monto aproximado: ₡{subscription.monto_promedio:,.0f}\n"
            f"Fecha estimada: {subscription.proxima_fecha_estimada.strftime('%d/%m/%Y')}\n"
            f"Frecuencia: {subscription.frecuencia_display}"
        )

        return Alert(
            profile_id=profile_id,
            subscription_id=subscription.id,
            alert_type=AlertType.SUBSCRIPTION_DUE,
            severity=severity,
            status=AlertStatus.PENDING,
            title=title,
            message=message,
        )

    def _create_budget_alert(
        self, budget: Budget, spent: Decimal, percentage: float, profile_id: str
    ) -> Alert | None:
        """Crea alerta de presupuesto excedido."""
        severity = AlertSeverity.CRITICAL if percentage >= 100 else AlertSeverity.WARNING

        if percentage >= 100:
            title = f"💰 Presupuesto EXCEDIDO ({percentage:.0f}%)"
        else:
            title = f"💰 Presupuesto al {percentage:.0f}%"

        message = (
            f"Has gastado ₡{spent:,.0f} de ₡{budget.salario_mensual:,.0f} "
            f"este mes ({percentage:.1f}%).\n\n"
            f"Considera revisar tus gastos para mantenerte dentro del presupuesto."
        )

        return Alert(
            profile_id=profile_id,
            budget_id=budget.id,
            alert_type=AlertType.BUDGET_EXCEEDED,
            severity=severity,
            status=AlertStatus.PENDING,
            title=title,
            message=message,
        )

    def _check_category_spike(self, transaction: Transaction, profile_id: str) -> Alert | None:
        """Verifica si hay un gasto inusual en la categoría."""
        # Calcular promedio de gastos en esta categoría en los últimos 3 meses
        with get_session() as session:
            three_months_ago = datetime.now(UTC) - timedelta(days=90)

            avg_amount = (
                session.query(func.avg(Transaction.monto_crc))
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.subcategory_id == transaction.subcategory_id,
                    Transaction.fecha_transaccion >= three_months_ago,
                    Transaction.deleted_at.is_(None),
                    Transaction.id != transaction.id,  # Excluir transacción actual
                )
                .scalar()
            )

            if not avg_amount or avg_amount == 0:
                return None  # No hay suficiente historial

            # Si la transacción es 3x el promedio, generar alerta
            if transaction.monto_crc >= (avg_amount * 3):
                multiplier = transaction.monto_crc / avg_amount
                category_name = transaction.subcategory.name if transaction.subcategory else "esta categoría"

                title = f"📈 Gasto {multiplier:.1f}x superior en {category_name}"
                message = (
                    f"**Gasto inusualmente alto detectado**\n\n"
                    f"💰 Monto: ₡{transaction.monto_crc:,.0f}\n"
                    f"🏪 Comercio: {transaction.comercio}\n"
                    f"📊 Categoría: {category_name}\n\n"
                    f"**Comparación:**\n"
                    f"Este gasto es **{multiplier:.1f}x** superior a tu promedio usual "
                    f"en esta categoría (₡{avg_amount:,.0f}).\n\n"
                    f"💡 Revisa si este gasto está dentro de tu presupuesto."
                )

                return Alert(
                    profile_id=profile_id,
                    transaction_id=transaction.id,
                    alert_type=AlertType.CATEGORY_SPIKE,
                    severity=AlertSeverity.WARNING,
                    status=AlertStatus.PENDING,
                    title=title,
                    message=message,
                )

        return None

    def get_pending_alerts(self, profile_id: str) -> list[Alert]:
        """Obtiene alertas pendientes para un perfil."""
        with get_session() as session:
            alerts = (
                session.query(Alert)
                .filter(
                    Alert.profile_id == profile_id,
                    Alert.status == AlertStatus.PENDING,
                )
                .order_by(Alert.created_at.desc())
                .all()
            )

            # Expunge para evitar problemas con la sesión
            for alert in alerts:
                session.expunge(alert)

            return alerts

    def mark_alert_as_read(self, alert_id: str) -> bool:
        """Marca una alerta como leída."""
        with get_session() as session:
            alert = session.query(Alert).filter(Alert.id == alert_id).first()

            if alert:
                alert.mark_as_read()
                session.commit()
                return True

            return False

    def dismiss_alert(self, alert_id: str) -> bool:
        """Descarta una alerta."""
        with get_session() as session:
            alert = session.query(Alert).filter(Alert.id == alert_id).first()

            if alert:
                alert.dismiss()
                session.commit()
                return True

            return False

    def generate_monthly_comparison_alerts(self, profile_id: str) -> list[Alert]:
        """
        Genera alertas comparando gastos del mes actual vs mes anterior.

        Alertas como: "Este mes gastaste 40% más en Uber Eats"

        Args:
            profile_id: ID del perfil

        Returns:
            Lista de alertas generadas
        """
        alerts = []
        config = self._get_alert_config(profile_id)

        # Por ahora usamos el flag de category_spike como indicador
        # En el futuro se puede agregar un flag específico
        if not config.enable_category_spike_alerts:
            return alerts

        with get_session() as session:
            now = datetime.now(UTC)

            # Mes actual
            current_month_start = datetime(now.year, now.month, 1, tzinfo=UTC)

            # Mes anterior
            if now.month == 1:
                prev_month_start = datetime(now.year - 1, 12, 1, tzinfo=UTC)
                prev_month_end = datetime(now.year, 1, 1, tzinfo=UTC)
            else:
                prev_month_start = datetime(now.year, now.month - 1, 1, tzinfo=UTC)
                prev_month_end = current_month_start

            # Analizar por merchant (comercios específicos como Uber Eats)
            # Obtener top merchants del mes actual
            current_spending = (
                session.query(
                    Transaction.comercio,
                    func.sum(Transaction.monto_crc).label("total"),
                    func.count(Transaction.id).label("count"),
                )
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.fecha_transaccion >= current_month_start,
                    Transaction.deleted_at.is_(None),
                )
                .group_by(Transaction.comercio)
                .having(func.sum(Transaction.monto_crc) > 10000)  # Mínimo 10k
                .all()
            )

            for comercio, current_total, current_count in current_spending:
                # Obtener gasto del mismo comercio el mes anterior
                prev_total = (
                    session.query(func.sum(Transaction.monto_crc))
                    .filter(
                        Transaction.profile_id == profile_id,
                        Transaction.comercio == comercio,
                        Transaction.fecha_transaccion >= prev_month_start,
                        Transaction.fecha_transaccion < prev_month_end,
                        Transaction.deleted_at.is_(None),
                    )
                    .scalar()
                ) or Decimal("0")

                if prev_total > 0:
                    # Calcular porcentaje de cambio
                    change_pct = float(((current_total - prev_total) / prev_total) * 100)

                    # Solo alertar si el cambio es significativo (> 30%)
                    if abs(change_pct) >= 30:
                        # Verificar si ya existe alerta para este comercio este mes
                        existing = (
                            session.query(Alert)
                            .filter(
                                Alert.profile_id == profile_id,
                                Alert.alert_type == AlertType.MONTHLY_COMPARISON,
                                Alert.created_at >= current_month_start,
                                Alert.title.like(f"%{comercio}%"),
                                Alert.status.in_([AlertStatus.PENDING, AlertStatus.READ]),
                            )
                            .first()
                        )

                        if not existing:
                            alert = self._create_monthly_comparison_alert(
                                comercio=comercio,
                                current_total=current_total,
                                prev_total=prev_total,
                                change_pct=change_pct,
                                profile_id=profile_id,
                            )
                            if alert:
                                alerts.append(alert)
                                session.add(alert)

            session.commit()

        logger.info(f"Generadas {len(alerts)} alertas de comparación mensual")
        return alerts

    def _create_monthly_comparison_alert(
        self,
        comercio: str,
        current_total: Decimal,
        prev_total: Decimal,
        change_pct: float,
        profile_id: str,
    ) -> Alert | None:
        """Crea alerta de comparación mensual."""
        # Determinar si es aumento o disminución
        if change_pct > 0:
            direction = "más"
            emoji = "📈"
            severity = AlertSeverity.WARNING if change_pct > 50 else AlertSeverity.INFO
        else:
            direction = "menos"
            emoji = "📉"
            severity = AlertSeverity.INFO

        title = f"{emoji} Este mes gastaste {abs(change_pct):.0f}% {direction} en {comercio}"
        message = (
            f"**Comparación mensual**\n\n"
            f"🏪 Comercio: {comercio}\n"
            f"💰 Mes actual: ₡{current_total:,.0f}\n"
            f"💰 Mes anterior: ₡{prev_total:,.0f}\n\n"
            f"**Cambio:** {'+' if change_pct > 0 else ''}{change_pct:.1f}%\n\n"
        )

        if change_pct > 0:
            message += "💡 Tu gasto en este comercio ha aumentado. Considera si está dentro de tu presupuesto."
        else:
            message += "✅ ¡Buen trabajo! Has reducido tu gasto en este comercio."

        return Alert(
            profile_id=profile_id,
            alert_type=AlertType.MONTHLY_COMPARISON,
            severity=severity,
            status=AlertStatus.PENDING,
            title=title,
            message=message,
        )


# Singleton para usar en toda la aplicación
alert_service = AlertService()
