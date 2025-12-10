"""Router de Notificaciones - Alertas de tarjetas y pagos.

Endpoints para:
- Obtener notificaciones pendientes
- Marcar notificaciones como leídas
- Configurar preferencias de notificación
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from finanzas_tracker.core.database import get_db
from finanzas_tracker.services.notification_service import (
    CardNotificationService,
    NotificationType,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/notifications", tags=["Notifications"])


# ============================================================================
# Schemas
# ============================================================================


class NotificationResponse(BaseModel):
    """Notificación para el usuario."""

    model_config = ConfigDict(from_attributes=True)

    type: str
    card_id: int
    card_name: str
    title: str
    message: str
    amount: float | None = None
    due_date: str | None = None
    days_until_due: int | None = None
    priority: str
    action_url: str | None = None
    created_at: str


class NotificationsListResponse(BaseModel):
    """Lista de notificaciones."""

    total: int
    urgent: int
    notifications: list[NotificationResponse]


class NotificationPreferences(BaseModel):
    """Preferencias de notificación del usuario."""

    payment_reminder_7_days: bool = True
    payment_reminder_3_days: bool = True
    payment_reminder_1_day: bool = True
    payment_due_today: bool = True
    statement_received: bool = True
    high_utilization: bool = True
    email_notifications: bool = False  # Por ahora solo in-app
    push_notifications: bool = False  # Futuro


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "",
    response_model=NotificationsListResponse,
)
async def get_notifications(
    profile_id: str = Query(..., description="ID del perfil"),
    include_low_priority: bool = Query(
        True, description="Incluir notificaciones de baja prioridad"
    ),
    db: Session = Depends(get_db),
) -> NotificationsListResponse:
    """Obtiene todas las notificaciones pendientes.

    Revisa todas las tarjetas del perfil y genera notificaciones
    relevantes según fechas de corte, vencimiento y pagos.

    Args:
        profile_id: ID del perfil del usuario.
        include_low_priority: Si incluir notificaciones de baja prioridad.
        db: Sesión de base de datos.

    Returns:
        Lista de notificaciones ordenadas por prioridad.
    """
    service = CardNotificationService(db)
    notifications = service.get_all_pending_notifications(profile_id)

    # Filtrar por prioridad si es necesario
    if not include_low_priority:
        notifications = [n for n in notifications if n.priority != "low"]

    # Contar urgentes
    urgent_count = sum(1 for n in notifications if n.priority == "urgent")

    return NotificationsListResponse(
        total=len(notifications),
        urgent=urgent_count,
        notifications=[
            NotificationResponse(
                type=n.type.value,
                card_id=n.card_id,
                card_name=n.card_name,
                title=n.title,
                message=n.message,
                amount=float(n.amount) if n.amount else None,
                due_date=n.due_date.isoformat() if n.due_date else None,
                days_until_due=n.days_until_due,
                priority=n.priority,
                action_url=n.action_url,
                created_at=n.created_at.isoformat() if n.created_at else None,
            )
            for n in notifications
        ],
    )


@router.get(
    "/payment-reminders",
    response_model=list[NotificationResponse],
)
async def get_payment_reminders(
    profile_id: str = Query(..., description="ID del perfil"),
    db: Session = Depends(get_db),
) -> list[NotificationResponse]:
    """Obtiene solo recordatorios de pago de tarjetas.

    Útil para mostrar en un widget o sección específica.
    """
    service = CardNotificationService(db)
    notifications = service.check_payment_reminders(profile_id)

    return [
        NotificationResponse(
            type=n.type.value,
            card_id=n.card_id,
            card_name=n.card_name,
            title=n.title,
            message=n.message,
            amount=float(n.amount) if n.amount else None,
            due_date=n.due_date.isoformat() if n.due_date else None,
            days_until_due=n.days_until_due,
            priority=n.priority,
            action_url=n.action_url,
            created_at=n.created_at.isoformat() if n.created_at else None,
        )
        for n in notifications
    ]


@router.get(
    "/upcoming-payments",
    response_model=list[dict[str, Any]],
)
async def get_upcoming_payments(
    profile_id: str = Query(..., description="ID del perfil"),
    days_ahead: int = Query(30, description="Días hacia adelante a revisar"),
    db: Session = Depends(get_db),
) -> list[dict[str, Any]]:
    """Obtiene pagos próximos de tarjetas.

    Retorna una lista de tarjetas con sus fechas de pago próximas.
    """
    from datetime import date, timedelta

    from sqlalchemy import select

    from finanzas_tracker.models import BillingCycle, Card
    from finanzas_tracker.models.enums import BillingCycleStatus

    today = date.today()
    future_date = today + timedelta(days=days_ahead)

    # Buscar ciclos con fecha de pago próxima
    stmt = (
        select(BillingCycle, Card)
        .join(Card, BillingCycle.card_id == Card.id)
        .where(
            Card.profile_id == profile_id,
            BillingCycle.fecha_pago >= today,
            BillingCycle.fecha_pago <= future_date,
            BillingCycle.status.in_(
                [
                    BillingCycleStatus.OPEN,
                    BillingCycleStatus.CLOSED,
                    BillingCycleStatus.PARTIAL,
                ]
            ),
            BillingCycle.deleted_at.is_(None),
        )
        .order_by(BillingCycle.fecha_pago)
    )

    results = db.execute(stmt).all()

    return [
        {
            "card_id": card.id,
            "card_name": f"{card.banco.value if card.banco else ''} ***{card.ultimos_4_digitos or ''}".strip(),
            "due_date": cycle.fecha_pago.isoformat(),
            "days_until": (cycle.fecha_pago - today).days,
            "total": float(cycle.total_a_pagar),
            "paid": float(cycle.monto_pagado),
            "pending": float(cycle.total_a_pagar - cycle.monto_pagado),
            "minimum": float(cycle.pago_minimo) if cycle.pago_minimo else None,
            "status": cycle.status.value,
        }
        for cycle, card in results
    ]


@router.get(
    "/types",
    response_model=list[dict[str, str]],
)
async def get_notification_types() -> list[dict[str, str]]:
    """Obtiene los tipos de notificación disponibles."""
    return [
        {
            "value": NotificationType.STATEMENT_RECEIVED.value,
            "label": "Estado de cuenta recibido",
            "icon": "📄",
        },
        {
            "value": NotificationType.PAYMENT_REMINDER_7_DAYS.value,
            "label": "Recordatorio 7 días",
            "icon": "📅",
        },
        {
            "value": NotificationType.PAYMENT_REMINDER_3_DAYS.value,
            "label": "Recordatorio 3 días",
            "icon": "⏰",
        },
        {
            "value": NotificationType.PAYMENT_REMINDER_1_DAY.value,
            "label": "Recordatorio 1 día",
            "icon": "⚠️",
        },
        {
            "value": NotificationType.PAYMENT_DUE_TODAY.value,
            "label": "Vence hoy",
            "icon": "🚨",
        },
        {
            "value": NotificationType.PAYMENT_RECEIVED.value,
            "label": "Pago recibido",
            "icon": "✅",
        },
        {
            "value": NotificationType.PAYMENT_NOT_DETECTED.value,
            "label": "Pago no detectado",
            "icon": "❓",
        },
        {
            "value": NotificationType.PAYMENT_OVERDUE.value,
            "label": "Pago vencido",
            "icon": "🔴",
        },
        {
            "value": NotificationType.HIGH_UTILIZATION.value,
            "label": "Uso alto del límite",
            "icon": "🟡",
        },
        {
            "value": NotificationType.APPROACHING_LIMIT.value,
            "label": "Cerca del límite",
            "icon": "🔴",
        },
    ]
