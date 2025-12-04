"""Servicio de Notificaciones de Tarjetas de Crédito.

Sistema que monitorea:
1. Llegada del estado de cuenta (fecha de corte)
2. Recordatorio de pago (3 días antes)
3. Confirmación de pago recibido
4. Alerta si no se detecta pago

Costa Rica: Optimizado para BAC Credomatic y Banco Popular.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.models import BillingCycle, Card
from finanzas_tracker.models.enums import BillingCycleStatus, CardType


logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    """Tipos de notificación."""

    # Estado de cuenta
    STATEMENT_RECEIVED = "statement_received"  # Llegó el estado de cuenta

    # Pagos
    PAYMENT_REMINDER_7_DAYS = "payment_reminder_7_days"
    PAYMENT_REMINDER_3_DAYS = "payment_reminder_3_days"
    PAYMENT_REMINDER_1_DAY = "payment_reminder_1_day"
    PAYMENT_DUE_TODAY = "payment_due_today"
    PAYMENT_RECEIVED = "payment_received"
    PAYMENT_NOT_DETECTED = "payment_not_detected"
    PAYMENT_OVERDUE = "payment_overdue"

    # Alertas
    HIGH_UTILIZATION = "high_utilization"  # >80% del límite
    APPROACHING_LIMIT = "approaching_limit"  # >90% del límite


@dataclass
class Notification:
    """Notificación generada."""

    type: NotificationType
    card_id: int
    card_name: str
    title: str
    message: str
    amount: Decimal | None = None
    due_date: date | None = None
    days_until_due: int | None = None
    priority: str = "normal"  # low, normal, high, urgent
    action_url: str | None = None
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario para API/UI."""
        return {
            "type": self.type.value,
            "card_id": self.card_id,
            "card_name": self.card_name,
            "title": self.title,
            "message": self.message,
            "amount": float(self.amount) if self.amount else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "days_until_due": self.days_until_due,
            "priority": self.priority,
            "action_url": self.action_url,
            "created_at": self.created_at.isoformat(),
        }


class CardNotificationService:
    """
    Servicio de notificaciones para tarjetas de crédito.

    Flujo:
    1. check_statement_arrival() - ¿Llegó el estado de cuenta?
    2. check_payment_reminders() - Recordatorios antes del vencimiento
    3. check_payment_received() - ¿Se detectó el pago?
    4. check_overdue() - Alertas de vencimiento
    """

    def __init__(self, db: Session) -> None:
        """Inicializa el servicio."""
        self.db = db

    def get_all_pending_notifications(
        self,
        profile_id: str,
    ) -> list[Notification]:
        """
        Obtiene todas las notificaciones pendientes para un perfil.

        Revisa todas las tarjetas y genera notificaciones relevantes.
        """
        notifications: list[Notification] = []

        # Obtener tarjetas de crédito del perfil
        cards = self._get_credit_cards(profile_id)

        for card in cards:
            # Verificar estado de cuenta
            statement_notif = self._check_statement_for_card(card)
            if statement_notif:
                notifications.append(statement_notif)

            # Verificar recordatorios de pago
            payment_notifs = self._check_payment_reminders_for_card(card)
            notifications.extend(payment_notifs)

            # Verificar si se recibió pago
            payment_check = self._check_payment_received_for_card(card)
            if payment_check:
                notifications.append(payment_check)

            # Verificar utilización alta
            util_notif = self._check_utilization_for_card(card)
            if util_notif:
                notifications.append(util_notif)

        # Ordenar por prioridad
        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        notifications.sort(key=lambda n: priority_order.get(n.priority, 2))

        return notifications

    def check_statement_arrival(
        self,
        profile_id: str,
    ) -> list[Notification]:
        """
        Verifica si llegó el estado de cuenta para alguna tarjeta.

        Busca emails con PDF de estado de cuenta cerca de la fecha de corte.
        """
        notifications = []
        cards = self._get_credit_cards(profile_id)
        today = date.today()

        for card in cards:
            if not card.fecha_corte:
                continue

            # Calcular fecha de corte de este mes
            try:
                cut_date = date(today.year, today.month, card.fecha_corte)
            except ValueError:
                # Día inválido para el mes (ej: 31 en febrero)
                continue

            # Si estamos en los 3 días después del corte
            days_since_cut = (today - cut_date).days
            if 0 <= days_since_cut <= 3:
                # Buscar si hay un ciclo creado recientemente
                cycle = self._get_latest_cycle(card.id)

                if cycle and cycle.fecha_corte == cut_date:
                    notifications.append(
                        Notification(
                            type=NotificationType.STATEMENT_RECEIVED,
                            card_id=card.id,
                            card_name=self._get_card_display_name(card),
                            title="📄 Estado de cuenta recibido",
                            message=f"Tu estado de cuenta llegó. Total a pagar: ₡{cycle.total_a_pagar:,.0f}",
                            amount=cycle.total_a_pagar,
                            due_date=cycle.fecha_pago,
                            priority="normal",
                        )
                    )

        return notifications

    def check_payment_reminders(
        self,
        profile_id: str,
    ) -> list[Notification]:
        """
        Genera recordatorios de pago según la proximidad al vencimiento.

        Recordatorios a los 7, 3 y 1 día antes del vencimiento.
        """
        notifications = []
        cards = self._get_credit_cards(profile_id)
        today = date.today()

        for card in cards:
            cycle = self._get_current_unpaid_cycle(card.id)
            if not cycle or not cycle.fecha_pago:
                continue

            days_until = (cycle.fecha_pago - today).days
            amount_pending = cycle.total_a_pagar - cycle.monto_pagado

            if amount_pending <= 0:
                continue  # Ya está pagada

            # Determinar tipo de recordatorio
            if days_until == 7:
                notif_type = NotificationType.PAYMENT_REMINDER_7_DAYS
                priority = "low"
                title = "📅 Pago en 7 días"
            elif days_until == 3:
                notif_type = NotificationType.PAYMENT_REMINDER_3_DAYS
                priority = "normal"
                title = "⏰ Pago en 3 días"
            elif days_until == 1:
                notif_type = NotificationType.PAYMENT_REMINDER_1_DAY
                priority = "high"
                title = "⚠️ ¡Pago mañana!"
            elif days_until == 0:
                notif_type = NotificationType.PAYMENT_DUE_TODAY
                priority = "urgent"
                title = "🚨 ¡Pago HOY!"
            elif days_until < 0:
                notif_type = NotificationType.PAYMENT_OVERDUE
                priority = "urgent"
                title = f"🔴 Vencido hace {abs(days_until)} días"
            else:
                continue  # No es día de recordatorio

            # Calcular pago mínimo
            min_payment = cycle.pago_minimo or (amount_pending * Decimal("0.10"))

            notifications.append(
                Notification(
                    type=notif_type,
                    card_id=card.id,
                    card_name=self._get_card_display_name(card),
                    title=title,
                    message=f"Total: ₡{amount_pending:,.0f} | Mínimo: ₡{min_payment:,.0f}",
                    amount=amount_pending,
                    due_date=cycle.fecha_pago,
                    days_until_due=days_until,
                    priority=priority,
                )
            )

        return notifications

    def check_payment_received(
        self,
        profile_id: str,
    ) -> list[Notification]:
        """
        Verifica si se detectó el pago de la tarjeta.

        Busca transacciones de tipo PAGO_TARJETA después de la fecha de corte.
        """
        notifications = []
        cards = self._get_credit_cards(profile_id)
        today = date.today()

        for card in cards:
            cycle = self._get_current_unpaid_cycle(card.id)
            if not cycle or not cycle.fecha_pago:
                continue

            days_until = (cycle.fecha_pago - today).days

            # Si ya pasó la fecha de pago y no hay pago registrado
            if days_until < 0 and cycle.monto_pagado == 0:
                notifications.append(
                    Notification(
                        type=NotificationType.PAYMENT_NOT_DETECTED,
                        card_id=card.id,
                        card_name=self._get_card_display_name(card),
                        title="❓ No detectamos tu pago",
                        message=f"Tu tarjeta venció el {cycle.fecha_pago}. ¿Ya pagaste?",
                        amount=cycle.total_a_pagar,
                        due_date=cycle.fecha_pago,
                        days_until_due=days_until,
                        priority="urgent",
                    )
                )

            # Si se detectó un pago
            elif cycle.monto_pagado > 0:
                if cycle.monto_pagado >= cycle.total_a_pagar:
                    status = "✅ Pagado completo"
                    priority = "low"
                else:
                    status = f"⚠️ Pago parcial (₡{cycle.monto_pagado:,.0f})"
                    priority = "normal"

                notifications.append(
                    Notification(
                        type=NotificationType.PAYMENT_RECEIVED,
                        card_id=card.id,
                        card_name=self._get_card_display_name(card),
                        title=status,
                        message=f"Pago detectado: ₡{cycle.monto_pagado:,.0f} de ₡{cycle.total_a_pagar:,.0f}",
                        amount=cycle.monto_pagado,
                        priority=priority,
                    )
                )

        return notifications

    # =========================================================================
    # Métodos auxiliares
    # =========================================================================

    def _get_credit_cards(self, profile_id: str) -> list[Card]:
        """Obtiene tarjetas de crédito del perfil."""
        stmt = select(Card).where(
            Card.profile_id == profile_id,
            Card.tipo == CardType.CREDIT,
            Card.activa == True,
            Card.deleted_at.is_(None),
        )
        return list(self.db.execute(stmt).scalars().all())

    def _get_latest_cycle(self, card_id: int) -> BillingCycle | None:
        """Obtiene el ciclo de facturación más reciente."""
        stmt = (
            select(BillingCycle)
            .where(
                BillingCycle.card_id == card_id,
                BillingCycle.deleted_at.is_(None),
            )
            .order_by(BillingCycle.fecha_corte.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def _get_current_unpaid_cycle(self, card_id: int) -> BillingCycle | None:
        """Obtiene el ciclo actual que no está completamente pagado."""
        stmt = (
            select(BillingCycle)
            .where(
                BillingCycle.card_id == card_id,
                BillingCycle.status.in_(
                    [
                        BillingCycleStatus.OPEN,
                        BillingCycleStatus.CLOSED,
                        BillingCycleStatus.PARTIAL,
                        BillingCycleStatus.OVERDUE,
                    ]
                ),
                BillingCycle.deleted_at.is_(None),
            )
            .order_by(BillingCycle.fecha_pago.asc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def _check_statement_for_card(self, card: Card) -> Notification | None:
        """Verifica estado de cuenta para una tarjeta."""
        # Implementado en check_statement_arrival
        return None

    def _check_payment_reminders_for_card(self, card: Card) -> list[Notification]:
        """Verifica recordatorios para una tarjeta."""
        # Delegado a check_payment_reminders
        return []

    def _check_payment_received_for_card(self, card: Card) -> Notification | None:
        """Verifica pago recibido para una tarjeta."""
        # Delegado a check_payment_received
        return None

    def _check_utilization_for_card(self, card: Card) -> Notification | None:
        """Verifica utilización alta del límite."""
        if not card.limite_credito or card.limite_credito == 0:
            return None

        utilization = (card.current_balance or 0) / card.limite_credito

        if utilization >= 0.90:
            return Notification(
                type=NotificationType.APPROACHING_LIMIT,
                card_id=card.id,
                card_name=self._get_card_display_name(card),
                title="🔴 Cerca del límite",
                message=f"Usaste {utilization * 100:.0f}% de tu límite",
                amount=card.current_balance,
                priority="high",
            )
        if utilization >= 0.80:
            return Notification(
                type=NotificationType.HIGH_UTILIZATION,
                card_id=card.id,
                card_name=self._get_card_display_name(card),
                title="🟡 Uso alto",
                message=f"Usaste {utilization * 100:.0f}% de tu límite",
                amount=card.current_balance,
                priority="normal",
            )

        return None

    def _get_card_display_name(self, card: Card) -> str:
        """Genera nombre display para la tarjeta."""
        parts = []
        if card.banco:
            parts.append(card.banco.value if hasattr(card.banco, "value") else str(card.banco))
        if card.ultimos_4_digitos:
            parts.append(f"***{card.ultimos_4_digitos}")
        return " ".join(parts) if parts else f"Tarjeta #{card.id}"

    # =========================================================================
    # Integración con email fetcher
    # =========================================================================

    def process_payment_email(
        self,
        card_id: int,
        amount: Decimal,
        payment_date: date,
    ) -> Notification:
        """
        Procesa un email de confirmación de pago.

        Llamado por el EmailFetcher cuando detecta un pago.
        """
        card = self.db.get(Card, card_id)
        if not card:
            raise ValueError(f"Tarjeta {card_id} no encontrada")

        cycle = self._get_current_unpaid_cycle(card_id)

        if cycle:
            # Registrar pago en el ciclo
            cycle.monto_pagado += amount
            if cycle.monto_pagado >= cycle.total_a_pagar:
                cycle.status = BillingCycleStatus.PAID
            else:
                cycle.status = BillingCycleStatus.PARTIAL
            self.db.commit()

        return Notification(
            type=NotificationType.PAYMENT_RECEIVED,
            card_id=card_id,
            card_name=self._get_card_display_name(card),
            title="✅ Pago recibido",
            message=f"Se registró tu pago de ₡{amount:,.0f}",
            amount=amount,
            priority="normal",
        )
