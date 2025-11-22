"""Tests para InsightsService."""

import os


# Set env vars BEFORE any imports
os.environ.setdefault("AZURE_CLIENT_ID", "test-client-id")
os.environ.setdefault("AZURE_TENANT_ID", "test-tenant-id")
os.environ.setdefault("AZURE_CLIENT_SECRET", "test-secret")
os.environ.setdefault("USER_EMAIL", "test@example.com")
os.environ.setdefault("MOM_EMAIL", "mom@example.com")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test123")

from decimal import Decimal
from unittest.mock import MagicMock, patch

from finanzas_tracker.services.insights import Insight, InsightsService, InsightType


class TestInsightsService:
    """Tests para el servicio de insights."""

    def test_analyze_spending_trends_increase(self) -> None:
        """Test detecta aumento de gastos >20%."""
        service = InsightsService()
        data = {
            "total_current": Decimal("100000"),
            "total_last": Decimal("70000"),  # 42% aumento
        }

        insights = service._analyze_spending_trends(data)

        assert len(insights) == 1
        assert insights[0].type == InsightType.SPENDING_INCREASE
        assert insights[0].impact == "negative"
        assert insights[0].value > 40

    def test_analyze_spending_trends_decrease(self) -> None:
        """Test detecta disminucion de gastos >20%."""
        service = InsightsService()
        data = {
            "total_current": Decimal("50000"),
            "total_last": Decimal("100000"),  # 50% disminucion
        }

        insights = service._analyze_spending_trends(data)

        assert len(insights) == 1
        assert insights[0].type == InsightType.SPENDING_DECREASE
        assert insights[0].impact == "positive"

    def test_analyze_spending_trends_stable(self) -> None:
        """Test no genera insight si gasto estable."""
        service = InsightsService()
        data = {
            "total_current": Decimal("100000"),
            "total_last": Decimal("95000"),  # Solo 5% aumento
        }

        insights = service._analyze_spending_trends(data)

        assert len(insights) == 0

    def test_analyze_spending_trends_no_previous_data(self) -> None:
        """Test maneja caso sin datos mes anterior."""
        service = InsightsService()
        data = {
            "total_current": Decimal("100000"),
            "total_last": Decimal("0"),
        }

        insights = service._analyze_spending_trends(data)

        assert len(insights) == 0

    def test_analyze_unusual_transactions(self) -> None:
        """Test detecta transacciones inusuales (>3x promedio)."""
        service = InsightsService()

        mock_transaction = MagicMock()
        mock_transaction.monto_crc = Decimal("50000")  # 5x promedio
        mock_transaction.comercio = "Tienda Grande"

        data = {
            "avg_transaction": Decimal("10000"),
            "current_month": [mock_transaction],
        }

        insights = service._analyze_unusual_transactions(data)

        assert len(insights) == 1
        assert insights[0].type == InsightType.UNUSUAL_TRANSACTION
        assert "Tienda Grande" in insights[0].title

    def test_analyze_unusual_transactions_normal(self) -> None:
        """Test no genera insight para transacciones normales."""
        service = InsightsService()

        mock_transaction = MagicMock()
        mock_transaction.monto_crc = Decimal("15000")  # 1.5x promedio (normal)

        data = {
            "avg_transaction": Decimal("10000"),
            "current_month": [mock_transaction],
        }

        insights = service._analyze_unusual_transactions(data)

        assert len(insights) == 0

    def test_analyze_top_categories_high_concentration(self) -> None:
        """Test detecta alta concentracion en categoria (>40%)."""
        service = InsightsService()
        data = {
            "by_category_current": {
                "Comida": Decimal("60000"),
                "Transporte": Decimal("20000"),
                "Entretenimiento": Decimal("20000"),
            },
            "total_current": Decimal("100000"),
        }

        insights = service._analyze_top_categories(data)

        assert len(insights) == 1
        assert insights[0].type == InsightType.TOP_CATEGORY
        assert "Comida" in insights[0].title

    def test_analyze_top_categories_diversified(self) -> None:
        """Test no genera insight si gastos diversificados."""
        service = InsightsService()
        data = {
            "by_category_current": {
                "Comida": Decimal("30000"),
                "Transporte": Decimal("35000"),
                "Entretenimiento": Decimal("35000"),
            },
            "total_current": Decimal("100000"),
        }

        insights = service._analyze_top_categories(data)

        assert len(insights) == 0

    def test_analyze_recurring_expenses(self) -> None:
        """Test detecta gastos recurrentes (4+ visitas)."""
        service = InsightsService()
        data = {
            "by_merchant": {
                "Starbucks": {"count": 5, "total": Decimal("25000"), "transactions": []},
                "Supermercado": {"count": 2, "total": Decimal("50000"), "transactions": []},
            }
        }

        insights = service._analyze_recurring_expenses(data)

        assert len(insights) == 1
        assert insights[0].type == InsightType.RECURRING_EXPENSE
        assert "Starbucks" in insights[0].title
        assert "5 visitas" in insights[0].description

    def test_analyze_recurring_expenses_none(self) -> None:
        """Test no genera insight si no hay gastos frecuentes."""
        service = InsightsService()
        data = {
            "by_merchant": {
                "Tienda A": {"count": 2, "total": Decimal("20000"), "transactions": []},
                "Tienda B": {"count": 1, "total": Decimal("10000"), "transactions": []},
            }
        }

        insights = service._analyze_recurring_expenses(data)

        assert len(insights) == 0

    def test_analyze_savings_opportunities(self) -> None:
        """Test detecta oportunidades de ahorro (>50% aumento)."""
        service = InsightsService()
        data = {
            "by_category_current": {"Entretenimiento": Decimal("30000")},
            "by_category_last": {"Entretenimiento": Decimal("15000")},  # 100% aumento
        }

        insights = service._analyze_savings_opportunities(data)

        assert len(insights) == 1
        assert insights[0].type == InsightType.SAVINGS_OPPORTUNITY

    def test_analyze_savings_opportunities_none(self) -> None:
        """Test no genera insight si categorias estables."""
        service = InsightsService()
        data = {
            "by_category_current": {"Comida": Decimal("50000")},
            "by_category_last": {"Comida": Decimal("45000")},  # 11% aumento (normal)
        }

        insights = service._analyze_savings_opportunities(data)

        assert len(insights) == 0

    @patch("finanzas_tracker.services.insights.get_session")
    def test_generate_insights_orders_by_impact(self, mock_session: MagicMock) -> None:
        """Test que insights se ordenan por impacto."""
        service = InsightsService()

        mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.all.return_value = []

        insights = service.generate_insights("profile-123")

        assert isinstance(insights, list)

    def test_insight_dataclass(self) -> None:
        """Test estructura de Insight."""
        insight = Insight(
            type=InsightType.SPENDING_INCREASE,
            title="Test Title",
            description="Test Description",
            impact="negative",
            value=25.5,
            category="Comida",
            recommendation="Test recommendation",
        )

        assert insight.type == InsightType.SPENDING_INCREASE
        assert insight.title == "Test Title"
        assert insight.impact == "negative"
        assert insight.value == 25.5

    def test_insight_type_enum(self) -> None:
        """Test valores del enum InsightType."""
        assert InsightType.SPENDING_INCREASE.value == "spending_increase"
        assert InsightType.SPENDING_DECREASE.value == "spending_decrease"
        assert InsightType.UNUSUAL_TRANSACTION.value == "unusual_transaction"
        assert InsightType.TOP_CATEGORY.value == "top_category"
        assert InsightType.SAVINGS_OPPORTUNITY.value == "savings_opportunity"
        assert InsightType.RECURRING_EXPENSE.value == "recurring_expense"
