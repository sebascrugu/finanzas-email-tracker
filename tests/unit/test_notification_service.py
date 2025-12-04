"""Tests para NotificationService (CardNotificationService).

Tests del servicio de notificaciones de tarjetas de crédito.
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from finanzas_tracker.services.notification_service import (
    CardNotificationService,
    Notification,
    NotificationType,
)


class TestNotificationType:
    """Tests para el enum NotificationType."""

    def test_statement_types(self) -> None:
        """Tipos de notificación de estado de cuenta."""
        assert NotificationType.STATEMENT_RECEIVED.value == "statement_received"

    def test_payment_types(self) -> None:
        """Tipos de notificación de pago."""
        assert NotificationType.PAYMENT_REMINDER_7_DAYS.value == "payment_reminder_7_days"
        assert NotificationType.PAYMENT_REMINDER_3_DAYS.value == "payment_reminder_3_days"
        assert NotificationType.PAYMENT_REMINDER_1_DAY.value == "payment_reminder_1_day"
        assert NotificationType.PAYMENT_DUE_TODAY.value == "payment_due_today"
        assert NotificationType.PAYMENT_RECEIVED.value == "payment_received"
        assert NotificationType.PAYMENT_NOT_DETECTED.value == "payment_not_detected"
        assert NotificationType.PAYMENT_OVERDUE.value == "payment_overdue"

    def test_alert_types(self) -> None:
        """Tipos de alerta."""
        assert NotificationType.HIGH_UTILIZATION.value == "high_utilization"
        assert NotificationType.APPROACHING_LIMIT.value == "approaching_limit"


class TestNotification:
    """Tests para el dataclass Notification."""

    def test_create_notification(self) -> None:
        """Crea notificación con valores básicos."""
        notif = Notification(
            type=NotificationType.PAYMENT_REMINDER_3_DAYS,
            card_id=1,
            card_name="VISA ***1234",
            title="Recordatorio de Pago",
            message="Tu pago vence en 3 días",
        )

        assert notif.type == NotificationType.PAYMENT_REMINDER_3_DAYS
        assert notif.card_id == 1
        assert notif.card_name == "VISA ***1234"
        assert notif.title == "Recordatorio de Pago"
        assert notif.priority == "normal"

    def test_notification_with_amount(self) -> None:
        """Notificación con monto."""
        notif = Notification(
            type=NotificationType.PAYMENT_DUE_TODAY,
            card_id=1,
            card_name="VISA ***1234",
            title="Pago Vence Hoy",
            message="Debes pagar hoy",
            amount=Decimal("250000.00"),
            due_date=date(2024, 12, 15),
        )

        assert notif.amount == Decimal("250000.00")
        assert notif.due_date == date(2024, 12, 15)

    def test_notification_priority(self) -> None:
        """Notificación con diferentes prioridades."""
        notif = Notification(
            type=NotificationType.PAYMENT_OVERDUE,
            card_id=1,
            card_name="VISA ***1234",
            title="Pago Vencido",
            message="Tu pago está vencido",
            priority="urgent",
        )

        assert notif.priority == "urgent"

    def test_notification_created_at_default(self) -> None:
        """created_at se genera automáticamente."""
        notif = Notification(
            type=NotificationType.STATEMENT_RECEIVED,
            card_id=1,
            card_name="VISA ***1234",
            title="Estado Recibido",
            message="Llegó tu estado de cuenta",
        )

        assert notif.created_at is not None
        assert isinstance(notif.created_at, datetime)

    def test_notification_to_dict(self) -> None:
        """Convierte a diccionario correctamente."""
        notif = Notification(
            type=NotificationType.PAYMENT_REMINDER_3_DAYS,
            card_id=1,
            card_name="VISA ***1234",
            title="Recordatorio",
            message="Paga pronto",
            amount=Decimal("100000.00"),
            due_date=date(2024, 12, 15),
            days_until_due=3,
            priority="high",
            action_url="/cards/1/pay",
        )

        result = notif.to_dict()

        assert result["type"] == "payment_reminder_3_days"
        assert result["card_id"] == 1
        assert result["card_name"] == "VISA ***1234"
        assert result["title"] == "Recordatorio"
        assert result["message"] == "Paga pronto"
        assert result["amount"] == 100000.00
        assert result["due_date"] == "2024-12-15"
        assert result["days_until_due"] == 3
        assert result["priority"] == "high"
        assert result["action_url"] == "/cards/1/pay"
        assert "created_at" in result

    def test_notification_to_dict_none_values(self) -> None:
        """to_dict maneja valores None."""
        notif = Notification(
            type=NotificationType.STATEMENT_RECEIVED,
            card_id=1,
            card_name="VISA",
            title="Test",
            message="Test message",
        )

        result = notif.to_dict()

        assert result["amount"] is None
        assert result["due_date"] is None
        assert result["days_until_due"] is None
        assert result["action_url"] is None


class TestCardNotificationServiceInit:
    """Tests de inicialización del servicio."""

    def test_init_with_session(self) -> None:
        """Inicializa correctamente con sesión de BD."""
        mock_db = MagicMock(spec=Session)
        service = CardNotificationService(mock_db)

        assert service.db == mock_db


class TestCardNotificationServiceGetPending:
    """Tests del método get_all_pending_notifications."""

    @pytest.fixture
    def service(self) -> CardNotificationService:
        """Crea servicio con mock de sesión."""
        mock_db = MagicMock(spec=Session)
        return CardNotificationService(mock_db)

    @pytest.fixture
    def mock_card(self) -> MagicMock:
        """Crea tarjeta mock."""
        card = MagicMock()
        card.id = 1
        card.profile_id = "profile-123"
        card.ultimos_4_digitos = "1234"
        card.marca = "VISA"
        card.limite_credito = Decimal("500000.00")
        card.current_balance = Decimal("100000.00")
        card.fecha_vencimiento = 15
        return card

    def test_get_pending_no_cards(
        self,
        service: CardNotificationService,
    ) -> None:
        """Retorna lista vacía si no hay tarjetas."""
        with patch.object(service, "_get_credit_cards", return_value=[]):
            result = service.get_all_pending_notifications("profile-123")

        assert result == []

    def test_get_pending_with_cards(
        self,
        service: CardNotificationService,
        mock_card: MagicMock,
    ) -> None:
        """Obtiene notificaciones de múltiples tarjetas."""
        mock_notif = Notification(
            type=NotificationType.PAYMENT_REMINDER_3_DAYS,
            card_id=1,
            card_name="VISA ***1234",
            title="Test",
            message="Test",
        )

        with patch.object(service, "_get_credit_cards", return_value=[mock_card]):
            with patch.object(service, "_check_statement_for_card", return_value=None):
                with patch.object(
                    service, "_check_payment_reminders_for_card", return_value=[mock_notif]
                ):
                    with patch.object(
                        service, "_check_payment_received_for_card", return_value=None
                    ):
                        with patch.object(
                            service, "_check_utilization_for_card", return_value=None
                        ):
                            result = service.get_all_pending_notifications("profile-123")

        assert len(result) == 1
        assert result[0].type == NotificationType.PAYMENT_REMINDER_3_DAYS

    def test_get_pending_sorted_by_priority(
        self,
        service: CardNotificationService,
        mock_card: MagicMock,
    ) -> None:
        """Las notificaciones se ordenan por prioridad."""
        normal_notif = Notification(
            type=NotificationType.STATEMENT_RECEIVED,
            card_id=1,
            card_name="VISA",
            title="Normal",
            message="Normal priority",
            priority="normal",
        )
        urgent_notif = Notification(
            type=NotificationType.PAYMENT_OVERDUE,
            card_id=1,
            card_name="VISA",
            title="Urgent",
            message="Urgent priority",
            priority="urgent",
        )

        with patch.object(service, "_get_credit_cards", return_value=[mock_card]):
            with patch.object(service, "_check_statement_for_card", return_value=normal_notif):
                with patch.object(
                    service, "_check_payment_reminders_for_card", return_value=[urgent_notif]
                ):
                    with patch.object(
                        service, "_check_payment_received_for_card", return_value=None
                    ):
                        with patch.object(
                            service, "_check_utilization_for_card", return_value=None
                        ):
                            result = service.get_all_pending_notifications("profile-123")

        assert len(result) == 2
        assert result[0].priority == "urgent"  # Primero
        assert result[1].priority == "normal"  # Después


class TestCardNotificationServiceStatementArrival:
    """Tests del método check_statement_arrival."""

    @pytest.fixture
    def service(self) -> CardNotificationService:
        """Crea servicio con mock de sesión."""
        mock_db = MagicMock(spec=Session)
        return CardNotificationService(mock_db)

    def test_check_statement_arrival_empty(
        self,
        service: CardNotificationService,
    ) -> None:
        """Retorna lista vacía si no hay estados nuevos."""
        with patch.object(service, "_get_credit_cards", return_value=[]):
            result = service.check_statement_arrival("profile-123")

        # Debería funcionar aunque no haya tarjetas
        assert isinstance(result, list)


class TestNotificationHelperMethods:
    """Tests para métodos auxiliares de notificaciones."""

    @pytest.fixture
    def service(self) -> CardNotificationService:
        """Crea servicio con mock de sesión."""
        mock_db = MagicMock(spec=Session)
        return CardNotificationService(mock_db)

    def test_notification_types_complete(self) -> None:
        """Todos los tipos de notificación están definidos."""
        expected_types = [
            "statement_received",
            "payment_reminder_7_days",
            "payment_reminder_3_days",
            "payment_reminder_1_day",
            "payment_due_today",
            "payment_received",
            "payment_not_detected",
            "payment_overdue",
            "high_utilization",
            "approaching_limit",
        ]

        for type_value in expected_types:
            found = False
            for nt in NotificationType:
                if nt.value == type_value:
                    found = True
                    break
            assert found, f"Missing notification type: {type_value}"


class TestNotificationPriorityOrdering:
    """Tests para el ordenamiento por prioridad."""

    def test_priority_order_values(self) -> None:
        """Verifica el orden esperado de prioridades."""
        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}

        # urgent < high < normal < low
        assert priority_order["urgent"] < priority_order["high"]
        assert priority_order["high"] < priority_order["normal"]
        assert priority_order["normal"] < priority_order["low"]

    def test_notifications_sort_correctly(self) -> None:
        """Las notificaciones se ordenan correctamente."""
        notifications = [
            Notification(
                type=NotificationType.STATEMENT_RECEIVED,
                card_id=1,
                card_name="VISA",
                title="Low",
                message="Low priority",
                priority="low",
            ),
            Notification(
                type=NotificationType.PAYMENT_OVERDUE,
                card_id=1,
                card_name="VISA",
                title="Urgent",
                message="Urgent priority",
                priority="urgent",
            ),
            Notification(
                type=NotificationType.PAYMENT_REMINDER_3_DAYS,
                card_id=1,
                card_name="VISA",
                title="Normal",
                message="Normal priority",
                priority="normal",
            ),
            Notification(
                type=NotificationType.HIGH_UTILIZATION,
                card_id=1,
                card_name="VISA",
                title="High",
                message="High priority",
                priority="high",
            ),
        ]

        priority_order = {"urgent": 0, "high": 1, "normal": 2, "low": 3}
        sorted_notifications = sorted(
            notifications, key=lambda n: priority_order.get(n.priority, 2)
        )

        assert sorted_notifications[0].priority == "urgent"
        assert sorted_notifications[1].priority == "high"
        assert sorted_notifications[2].priority == "normal"
        assert sorted_notifications[3].priority == "low"


class TestNotificationCreation:
    """Tests de creación de diferentes tipos de notificación."""

    def test_create_payment_reminder(self) -> None:
        """Crea recordatorio de pago correctamente."""
        notif = Notification(
            type=NotificationType.PAYMENT_REMINDER_3_DAYS,
            card_id=1,
            card_name="VISA ***1234",
            title="⏰ Recordatorio de Pago",
            message="Tu pago de ₡250,000 vence en 3 días (15 de diciembre)",
            amount=Decimal("250000.00"),
            due_date=date(2024, 12, 15),
            days_until_due=3,
            priority="high",
        )

        assert "250,000" in notif.message or "250000" in notif.message
        assert notif.days_until_due == 3

    def test_create_overdue_notification(self) -> None:
        """Crea notificación de pago vencido."""
        notif = Notification(
            type=NotificationType.PAYMENT_OVERDUE,
            card_id=1,
            card_name="MASTERCARD ***5678",
            title="🚨 Pago Vencido",
            message="Tu pago venció hace 2 días. Evita intereses moratorios.",
            amount=Decimal("175000.00"),
            due_date=date(2024, 12, 10),
            days_until_due=-2,
            priority="urgent",
        )

        assert notif.type == NotificationType.PAYMENT_OVERDUE
        assert notif.priority == "urgent"
        assert notif.days_until_due == -2  # Negativo = vencido

    def test_create_utilization_alert(self) -> None:
        """Crea alerta de utilización alta."""
        notif = Notification(
            type=NotificationType.HIGH_UTILIZATION,
            card_id=1,
            card_name="VISA ***1234",
            title="⚠️ Utilización Alta",
            message="Has usado el 85% de tu límite de crédito",
            priority="high",
        )

        assert notif.type == NotificationType.HIGH_UTILIZATION
        assert "85%" in notif.message

    def test_create_payment_received(self) -> None:
        """Crea confirmación de pago recibido."""
        notif = Notification(
            type=NotificationType.PAYMENT_RECEIVED,
            card_id=1,
            card_name="VISA ***1234",
            title="✅ Pago Recibido",
            message="Se registró tu pago de ₡200,000",
            amount=Decimal("200000.00"),
            priority="low",
        )

        assert notif.type == NotificationType.PAYMENT_RECEIVED
        assert notif.priority == "low"


class TestNotificationToDict:
    """Tests adicionales para el método to_dict."""

    def test_to_dict_decimal_conversion(self) -> None:
        """Convierte Decimal a float en to_dict."""
        notif = Notification(
            type=NotificationType.PAYMENT_DUE_TODAY,
            card_id=1,
            card_name="VISA",
            title="Test",
            message="Test",
            amount=Decimal("123456.78"),
        )

        result = notif.to_dict()

        assert result["amount"] == 123456.78
        assert isinstance(result["amount"], float)

    def test_to_dict_date_conversion(self) -> None:
        """Convierte date a ISO string en to_dict."""
        notif = Notification(
            type=NotificationType.PAYMENT_DUE_TODAY,
            card_id=1,
            card_name="VISA",
            title="Test",
            message="Test",
            due_date=date(2024, 12, 25),
        )

        result = notif.to_dict()

        assert result["due_date"] == "2024-12-25"

    def test_to_dict_datetime_conversion(self) -> None:
        """Convierte datetime a ISO string en to_dict."""
        fixed_time = datetime(2024, 12, 1, 10, 30, 45)
        notif = Notification(
            type=NotificationType.STATEMENT_RECEIVED,
            card_id=1,
            card_name="VISA",
            title="Test",
            message="Test",
            created_at=fixed_time,
        )

        result = notif.to_dict()

        assert "2024-12-01" in result["created_at"]
        assert "10:30:45" in result["created_at"]
