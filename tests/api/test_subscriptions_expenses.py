"""Tests para API endpoints de suscripciones y gastos proyectados.

Tests de integración para los nuevos routers.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from finanzas_tracker.api.main import app
from finanzas_tracker.services.recurring_expense_predictor import (
    AlertLevel,
    ExpenseType,
    PredictedExpense,
)
from finanzas_tracker.services.subscription_detector import (
    DetectedSubscription,
    SubscriptionFrequency,
)


client = TestClient(app)


def create_mock_subscription(
    comercio: str = "Netflix",
    monto: float = 10.99,
    frecuencia: SubscriptionFrequency = SubscriptionFrequency.MONTHLY,
    confianza: int = 85,
) -> DetectedSubscription:
    """Crea una suscripción mock."""
    return DetectedSubscription(
        comercio=comercio,
        comercio_normalizado=comercio.upper(),
        monto_promedio=Decimal(str(monto)),
        monto_min=Decimal(str(monto)),
        monto_max=Decimal(str(monto)),
        frecuencia=frecuencia,
        dias_promedio_entre_cobros=30.0,
        ultimo_cobro=date.today() - timedelta(days=5),
        primer_cobro=date.today() - timedelta(days=95),
        cantidad_cobros=4,
        confianza=confianza,
    )


def create_mock_expense(
    comercio: str = "Netflix",
    monto: float = 10.99,
    dias_restantes: int = 5,
    nivel: AlertLevel = AlertLevel.INFO,
) -> PredictedExpense:
    """Crea un gasto predecido mock."""
    return PredictedExpense(
        comercio=comercio,
        monto_estimado=Decimal(str(monto)),
        monto_min=Decimal(str(monto)),
        monto_max=Decimal(str(monto)),
        fecha_estimada=date.today() + timedelta(days=dias_restantes),
        tipo=ExpenseType.SUBSCRIPTION,
        confianza=80,
        dias_restantes=dias_restantes,
        nivel_alerta=nivel,
    )


class TestSubscriptionsRouter:
    """Tests para el router de suscripciones."""

    @patch("finanzas_tracker.api.routers.subscriptions.SubscriptionDetector")
    def test_list_subscriptions(self, MockDetector):
        """Test GET /subscriptions."""
        mock_detector = MagicMock()
        mock_detector.detectar_suscripciones.return_value = [
            create_mock_subscription("Netflix", 10.99),
            create_mock_subscription("Spotify", 5.99),
        ]
        mock_detector.get_gasto_mensual_suscripciones.return_value = Decimal("16.98")
        mock_detector.get_proximo_cobro.return_value = date.today() + timedelta(days=25)
        MockDetector.return_value = mock_detector

        response = client.get(
            "/api/v1/subscriptions",
            params={"profile_id": str(uuid4())},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert data["gasto_mensual_estimado"] == 16.98
        assert len(data["suscripciones"]) == 2

    @patch("finanzas_tracker.api.routers.subscriptions.SubscriptionDetector")
    def test_detect_subscriptions(self, MockDetector):
        """Test POST /subscriptions/detect."""
        mock_detector = MagicMock()
        mock_detector.detectar_suscripciones.return_value = [
            create_mock_subscription("AWS", 25.50, confianza=90),
        ]
        mock_detector.get_gasto_mensual_suscripciones.return_value = Decimal("25.50")
        mock_detector.get_proximo_cobro.return_value = date.today() + timedelta(days=20)
        MockDetector.return_value = mock_detector

        response = client.post(
            "/api/v1/subscriptions/detect",
            params={"profile_id": str(uuid4())},
            json={
                "meses_atras": 6,
                "min_ocurrencias": 2,
                "confianza_minima": 60,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["suscripciones"][0]["comercio"] == "AWS"

    @patch("finanzas_tracker.api.routers.subscriptions.SubscriptionDetector")
    def test_list_known_subscriptions(self, MockDetector):
        """Test GET /subscriptions/known."""
        mock_detector = MagicMock()
        mock_detector.detectar_conocidas.return_value = [
            create_mock_subscription("Netflix", 10.99, confianza=95),
        ]
        mock_detector.get_gasto_mensual_suscripciones.return_value = Decimal("10.99")
        mock_detector.get_proximo_cobro.return_value = date.today() + timedelta(days=25)
        MockDetector.return_value = mock_detector

        response = client.get(
            "/api/v1/subscriptions/known",
            params={"profile_id": str(uuid4())},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

    @patch("finanzas_tracker.api.routers.subscriptions.SubscriptionDetector")
    def test_monthly_total(self, MockDetector):
        """Test GET /subscriptions/monthly-total."""
        mock_detector = MagicMock()
        mock_detector.detectar_suscripciones.return_value = [
            create_mock_subscription("Netflix", 10.99),
            create_mock_subscription("Spotify", 5.99),
        ]
        mock_detector.get_gasto_mensual_suscripciones.return_value = Decimal("16.98")
        MockDetector.return_value = mock_detector

        response = client.get(
            "/api/v1/subscriptions/monthly-total",
            params={"profile_id": str(uuid4())},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["gasto_mensual_estimado"] == 16.98
        assert data["cantidad_suscripciones"] == 2


class TestExpensesRouter:
    """Tests para el router de gastos proyectados."""

    @patch("finanzas_tracker.api.routers.expenses.RecurringExpensePredictor")
    def test_get_predicted_expenses(self, MockPredictor):
        """Test GET /expenses/predicted."""
        mock_predictor = MagicMock()
        mock_predictor.predecir_gastos.return_value = [
            create_mock_expense("Netflix", 10.99, 5, AlertLevel.INFO),
            create_mock_expense("ICE", 35000, 2, AlertLevel.URGENT),
        ]
        MockPredictor.return_value = mock_predictor

        response = client.get(
            "/api/v1/expenses/predicted",
            params={"profile_id": str(uuid4()), "dias": 30},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cantidad"] == 2
        assert data["alertas_urgentes"] == 1
        assert data["total_estimado"] > 0

    @patch("finanzas_tracker.api.routers.expenses.RecurringExpensePredictor")
    def test_get_expense_alerts(self, MockPredictor):
        """Test GET /expenses/alerts."""
        mock_predictor = MagicMock()
        mock_predictor.get_alertas_vencimiento.return_value = [
            create_mock_expense("Cuota Préstamo", 150000, 1, AlertLevel.URGENT),
        ]
        MockPredictor.return_value = mock_predictor

        response = client.get(
            "/api/v1/expenses/alerts",
            params={"profile_id": str(uuid4())},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["alertas_urgentes"] == 1
        assert data["gastos"][0]["nivel_alerta"] == "urgent"

    @patch("finanzas_tracker.api.routers.expenses.RecurringExpensePredictor")
    def test_get_monthly_summary(self, MockPredictor):
        """Test GET /expenses/summary/monthly."""
        from finanzas_tracker.services.recurring_expense_predictor import ExpenseSummary

        mock_predictor = MagicMock()
        mock_predictor.generar_resumen_mensual.return_value = ExpenseSummary(
            periodo_inicio=date(2025, 12, 1),
            periodo_fin=date(2025, 12, 31),
            total_estimado=Decimal("50000"),
            gastos=[create_mock_expense("Netflix", 10.99, 5)],
            por_tipo={ExpenseType.SUBSCRIPTION: Decimal("10.99")},
            alertas_urgentes=0,
        )
        MockPredictor.return_value = mock_predictor

        response = client.get(
            "/api/v1/expenses/summary/monthly",
            params={"profile_id": str(uuid4())},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_estimado"] == 50000
        assert "subscription" in data["por_tipo"]

    @patch("finanzas_tracker.api.routers.expenses.RecurringExpensePredictor")
    def test_get_cash_flow(self, MockPredictor):
        """Test GET /expenses/cash-flow."""
        mock_predictor = MagicMock()

        # Simular flujo de caja
        hoy = date.today()
        flujo = {
            hoy: Decimal("500000"),
            hoy + timedelta(days=5): Decimal("490000"),
            hoy + timedelta(days=30): Decimal("450000"),
        }
        mock_predictor.estimar_flujo_caja.return_value = flujo
        MockPredictor.return_value = mock_predictor

        response = client.get(
            "/api/v1/expenses/cash-flow",
            params={
                "profile_id": str(uuid4()),
                "saldo_inicial": 500000,
                "dias": 30,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["saldo_inicial"] == 500000
        assert data["saldo_final"] == 450000
        assert len(data["flujo_diario"]) == 3

    @patch("finanzas_tracker.api.routers.expenses.generar_reporte_gastos_proximos")
    def test_get_expense_report(self, mock_report):
        """Test GET /expenses/report."""
        mock_report.return_value = {
            "generado_en": date.today().isoformat(),
            "dias_proyectados": 30,
            "total_gastos": 5,
            "total_estimado": 75000,
            "alertas_urgentes": 1,
            "alertas_warning": 2,
            "gastos": [],
            "alertas": [],
        }

        response = client.get(
            "/api/v1/expenses/report",
            params={"profile_id": str(uuid4())},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_gastos"] == 5
        assert data["total_estimado"] == 75000


class TestPatrimonyHistoryEndpoint:
    """Tests para el endpoint de historial de patrimonio."""

    def test_get_patrimony_history_empty(self):
        """Test GET /patrimony/history con historial vacío."""
        # Este endpoint usa el service real, así que verificamos
        # que responda correctamente aunque no haya datos
        response = client.get(
            "/api/v1/patrimony/history",
            params={"profile_id": str(uuid4()), "meses": 6},
        )

        assert response.status_code == 200
        data = response.json()
        # Puede estar vacío o tener datos según el estado de la DB
        assert isinstance(data, list)
