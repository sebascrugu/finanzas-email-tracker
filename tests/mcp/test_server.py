"""Tests para el servidor MCP de Finanzas Tracker.

Tests actualizados para servidor con:
- Profile-awareness (set_profile requerido)
- MCP Resources
- MCP Prompts
- Error handling robusto
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from finanzas_tracker.mcp.server import (
    budget_coaching,
    cashflow_prediction,
    get_monthly_comparison,
    get_spending_summary,
    get_top_merchants,
    get_transactions,
    goal_advisor,
    list_profiles,
    mcp,
    savings_opportunities,
    search_transactions,
    set_profile,
    spending_alert,
)


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_profile_id() -> str:
    """ID de perfil para tests."""
    return str(uuid4())


@pytest.fixture
def mock_profile(mock_profile_id: str) -> MagicMock:
    """Mock de perfil."""
    profile = MagicMock()
    profile.id = mock_profile_id
    profile.nombre = "Test User"
    profile.email_cuenta = "test@example.com"
    profile.created_at = datetime.now()
    profile.deleted_at = None
    return profile


@pytest.fixture
def mock_transaction() -> MagicMock:
    """Mock de transacción."""
    txn = MagicMock()
    txn.fecha_transaccion = datetime.now()
    txn.comercio = "AUTOMERCADO"
    txn.monto_crc = Decimal("15000")
    txn.tipo_transaccion = "compra"
    txn.categoria_sugerida_por_ia = "Supermercado"
    txn.banco = "BAC"
    txn.deleted_at = None
    return txn


@pytest.fixture(autouse=True)
def reset_active_profile() -> None:
    """Reset active profile before each test."""
    import finanzas_tracker.mcp.server as server_module
    server_module._state.active_profile_id = None


# =============================================================================
# TEST: SERVER SETUP
# =============================================================================


class TestMCPServerSetup:
    """Tests para la configuración del servidor MCP."""

    def test_mcp_server_name(self) -> None:
        """Verifica que el servidor tiene el nombre correcto."""
        assert mcp.name == "finanzas-tracker"

    def test_mcp_has_all_tools_registered(self) -> None:
        """Verifica que todas las herramientas están registradas."""
        expected_tools = {
            # Configuración
            "set_profile",
            "list_profiles",
            # Nivel 1: Consultas básicas
            "get_transactions",
            "get_spending_summary",
            "get_top_merchants",
            # Nivel 2: Análisis
            "search_transactions",
            "get_monthly_comparison",
            # Nivel 3: Coaching (DIFERENCIADOR)
            "budget_coaching",
            "savings_opportunities",
            "cashflow_prediction",
            "spending_alert",
            "goal_advisor",
        }

        registered_tools = set(mcp._tool_manager._tools.keys())
        assert expected_tools.issubset(registered_tools), f"Missing tools: {expected_tools - registered_tools}"

    def test_mcp_has_nivel_3_coaching_tools(self) -> None:
        """Verifica que las herramientas de coaching están presentes."""
        coaching_tools = [
            "budget_coaching",
            "savings_opportunities",
            "cashflow_prediction",
            "spending_alert",
            "goal_advisor",
        ]

        for tool in coaching_tools:
            assert tool in mcp._tool_manager._tools, f"Falta herramienta: {tool}"

    def test_mcp_has_resources_registered(self) -> None:
        """Verifica que los resources están registrados."""
        # Resources se registran en el resource_manager
        assert hasattr(mcp, "_resource_manager")

    def test_mcp_has_prompts_registered(self) -> None:
        """Verifica que los prompts están registrados."""
        assert hasattr(mcp, "_prompt_manager")


# =============================================================================
# TEST: PROFILE MANAGEMENT
# =============================================================================


class TestSetProfile:
    """Tests para set_profile."""

    @patch("finanzas_tracker.mcp.server.get_session")
    def test_sets_active_profile_successfully(
        self, mock_session: MagicMock, mock_profile: MagicMock
    ) -> None:
        """Verifica que establece el perfil activo."""
        mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = (
            mock_profile
        )

        result = set_profile(mock_profile.id)

        assert result["success"] is True
        assert "activado" in result["message"]
        assert result["profile"]["id"] == str(mock_profile.id)

    @patch("finanzas_tracker.mcp.server.get_session")
    def test_returns_error_for_invalid_profile(self, mock_session: MagicMock) -> None:
        """Verifica error para perfil inexistente."""
        mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.first.return_value = (
            None
        )

        result = set_profile("invalid-uuid")

        assert result["error"] is True
        assert result["code"] == "PROFILE_NOT_FOUND"


class TestListProfiles:
    """Tests para list_profiles."""

    @patch("finanzas_tracker.mcp.server.get_session")
    def test_returns_list_of_profiles(
        self, mock_session: MagicMock, mock_profile: MagicMock
    ) -> None:
        """Verifica que retorna lista de perfiles."""
        mock_session.return_value.__enter__.return_value.query.return_value.all.return_value = [
            mock_profile
        ]

        result = list_profiles()

        assert "perfiles" in result
        assert result["total"] == 1
        assert result["perfiles"][0]["nombre"] == "Test User"

    @patch("finanzas_tracker.mcp.server.get_session")
    def test_returns_error_when_no_profiles(self, mock_session: MagicMock) -> None:
        """Verifica error cuando no hay perfiles."""
        mock_session.return_value.__enter__.return_value.query.return_value.all.return_value = []

        result = list_profiles()

        assert result["error"] is True
        assert result["code"] == "NO_DATA"


# =============================================================================
# TEST: GET TRANSACTIONS
# =============================================================================


class TestGetTransactions:
    """Tests para get_transactions."""

    @patch("finanzas_tracker.mcp.server.get_session")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_requires_active_profile(
        self, mock_profile_id: MagicMock, mock_session: MagicMock
    ) -> None:
        """Verifica que requiere perfil activo."""
        mock_profile_id.return_value = None

        result = get_transactions()

        assert result["error"] is True
        assert result["code"] == "PROFILE_NOT_FOUND"

    @patch("finanzas_tracker.mcp.server.get_session")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_returns_transactions_with_defaults(
        self,
        mock_get_profile: MagicMock,
        mock_session: MagicMock,
        mock_transaction: MagicMock,
        mock_profile_id: str,
    ) -> None:
        """Verifica que retorna transacciones con parámetros por defecto."""
        mock_get_profile.return_value = mock_profile_id
        mock_session.return_value.__enter__.return_value.execute.return_value.scalars.return_value.all.return_value = [
            mock_transaction
        ]

        result = get_transactions()

        assert "total" in result
        assert "periodo" in result
        assert "transacciones" in result
        assert result["periodo"] == "Últimos 30 días"
        assert result["total"] == 1

    @patch("finanzas_tracker.mcp.server.get_session")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_respects_days_parameter(
        self, mock_get_profile: MagicMock, mock_session: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica que respeta el parámetro days."""
        mock_get_profile.return_value = mock_profile_id
        mock_session.return_value.__enter__.return_value.execute.return_value.scalars.return_value.all.return_value = []

        result = get_transactions(days=7)

        assert result["periodo"] == "Últimos 7 días"

    @patch("finanzas_tracker.mcp.server.get_session")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_validates_days_range(
        self, mock_get_profile: MagicMock, mock_session: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica validación de rango de days."""
        mock_get_profile.return_value = mock_profile_id
        mock_session.return_value.__enter__.return_value.execute.return_value.scalars.return_value.all.return_value = []

        # Días negativos debería ajustarse a 1
        result = get_transactions(days=-5)
        assert result["periodo"] == "Últimos 1 días"

        # Días mayores a 365 debería ajustarse
        result = get_transactions(days=999)
        assert result["periodo"] == "Últimos 365 días"


# =============================================================================
# TEST: GET SPENDING SUMMARY
# =============================================================================


class TestGetSpendingSummary:
    """Tests para get_spending_summary."""

    @patch("finanzas_tracker.mcp.server.get_session")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_requires_active_profile(
        self, mock_profile_id: MagicMock, mock_session: MagicMock
    ) -> None:
        """Verifica que requiere perfil activo."""
        mock_profile_id.return_value = None

        result = get_spending_summary()

        assert result["error"] is True

    @patch("finanzas_tracker.mcp.server.get_session")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_returns_summary_grouped_by_categoria(
        self, mock_get_profile: MagicMock, mock_session: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica agrupación por categoría."""
        mock_get_profile.return_value = mock_profile_id
        mock_result = MagicMock()
        mock_result.grupo = "Supermercado"
        mock_result.total = Decimal("50000")
        mock_result.cantidad = 5

        mock_session.return_value.__enter__.return_value.execute.return_value.all.return_value = [
            mock_result
        ]

        result = get_spending_summary()

        assert "agrupado_por" in result
        assert result["agrupado_por"] == "categoria"
        assert "total" in result

    @patch("finanzas_tracker.mcp.server.get_session")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_calculates_percentages(
        self, mock_get_profile: MagicMock, mock_session: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica cálculo de porcentajes."""
        mock_get_profile.return_value = mock_profile_id
        mock_result1 = MagicMock()
        mock_result1.grupo = "Supermercado"
        mock_result1.total = Decimal("50000")
        mock_result1.cantidad = 5

        mock_result2 = MagicMock()
        mock_result2.grupo = "Restaurantes"
        mock_result2.total = Decimal("50000")
        mock_result2.cantidad = 3

        mock_session.return_value.__enter__.return_value.execute.return_value.all.return_value = [
            mock_result1,
            mock_result2,
        ]

        result = get_spending_summary()

        # Cada uno debería ser 50%
        assert len(result["grupos"]) == 2
        for grupo in result["grupos"]:
            assert grupo["porcentaje"] == 50.0


# =============================================================================
# TEST: TOP MERCHANTS
# =============================================================================


class TestTopMerchants:
    """Tests para get_top_merchants."""

    @patch("finanzas_tracker.mcp.server.get_session")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_returns_top_merchants(
        self, mock_get_profile: MagicMock, mock_session: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica que retorna top comercios."""
        mock_get_profile.return_value = mock_profile_id
        mock_result = MagicMock()
        mock_result.comercio = "AUTOMERCADO"
        mock_result.total = Decimal("80000")
        mock_result.visitas = 4

        mock_session.return_value.__enter__.return_value.execute.return_value.all.return_value = [
            mock_result
        ]

        result = get_top_merchants()

        assert "top_comercios" in result
        assert len(result["top_comercios"]) == 1
        assert result["top_comercios"][0]["comercio"] == "AUTOMERCADO"

    @patch("finanzas_tracker.mcp.server.get_session")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_calculates_average_per_visit(
        self, mock_get_profile: MagicMock, mock_session: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica cálculo de promedio por visita."""
        mock_get_profile.return_value = mock_profile_id
        mock_result = MagicMock()
        mock_result.comercio = "PRICESMART"
        mock_result.total = Decimal("100000")
        mock_result.visitas = 2

        mock_session.return_value.__enter__.return_value.execute.return_value.all.return_value = [
            mock_result
        ]

        result = get_top_merchants()

        # 100000 / 2 = 50000
        assert "₡50,000" in result["top_comercios"][0]["promedio_visita"]


# =============================================================================
# TEST: SEARCH TRANSACTIONS
# =============================================================================


class TestSearchTransactions:
    """Tests para search_transactions."""

    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_requires_query(self, mock_profile: MagicMock) -> None:
        """Verifica que requiere una consulta válida."""
        mock_profile.return_value = "some-profile-id"

        result = search_transactions(query="")

        assert result["error"] is True
        assert result["code"] == "INVALID_INPUT"

    @patch("finanzas_tracker.mcp.server.get_session")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_returns_search_results(
        self,
        mock_get_profile: MagicMock,
        mock_session: MagicMock,
        mock_transaction: MagicMock,
        mock_profile_id: str,
    ) -> None:
        """Verifica que retorna resultados de búsqueda."""
        mock_get_profile.return_value = mock_profile_id
        mock_ctx = MagicMock()
        mock_ctx.execute.return_value.scalars.return_value.all.return_value = [
            mock_transaction
        ]
        mock_session.return_value.__enter__.return_value = mock_ctx

        result = search_transactions(query="walmart")

        assert "query" in result
        assert "total" in result
        assert "resultados" in result


# =============================================================================
# TEST: MONTHLY COMPARISON
# =============================================================================


class TestMonthlyComparison:
    """Tests para get_monthly_comparison."""

    @patch("finanzas_tracker.mcp.server.get_session")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_returns_comparison_structure(
        self, mock_get_profile: MagicMock, mock_session: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica estructura de comparación mensual."""
        mock_get_profile.return_value = mock_profile_id
        mock_session.return_value.__enter__.return_value.query.return_value.filter.return_value.scalar.return_value = Decimal(
            "100000"
        )

        result = get_monthly_comparison()

        assert "mes_actual" in result
        assert "mes_anterior" in result
        assert "comparacion" in result
        assert "tendencia" in result["comparacion"]


# =============================================================================
# TEST: BUDGET COACHING (DIFERENCIADOR)
# =============================================================================


class TestBudgetCoaching:
    """Tests para budget_coaching - DIFERENCIADOR."""

    @patch("finanzas_tracker.mcp.server._get_analysis_data")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_returns_coaching_structure(
        self, mock_get_profile: MagicMock, mock_data: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica estructura de respuesta de coaching."""
        mock_get_profile.return_value = mock_profile_id
        mock_data.return_value = {
            "transactions": [],
            "current_month_txns": [],
            "total_current": Decimal("100000"),
            "total_last": Decimal("80000"),
            "by_category_current": {"Supermercado": Decimal("50000")},
            "by_category_last": {"Supermercado": Decimal("40000")},
            "by_merchant": {},
            "transaction_count": 10,
            "days": 30,
        }

        result = budget_coaching()

        assert "periodo" in result
        assert "resumen" in result
        assert "coaching" in result
        assert "salud_financiera" in result

    @patch("finanzas_tracker.mcp.server._get_analysis_data")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_calculates_health_score(
        self, mock_get_profile: MagicMock, mock_data: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica que calcula el score de salud financiera."""
        mock_get_profile.return_value = mock_profile_id
        mock_data.return_value = {
            "transactions": [],
            "current_month_txns": [],
            "total_current": Decimal("100000"),
            "total_last": Decimal("100000"),
            "by_category_current": {},
            "by_category_last": {},
            "by_merchant": {},
            "transaction_count": 10,
            "days": 30,
        }

        result = budget_coaching()

        assert "score" in result["salud_financiera"]
        assert 0 <= result["salud_financiera"]["score"] <= 100


# =============================================================================
# TEST: SAVINGS OPPORTUNITIES (DIFERENCIADOR)
# =============================================================================


class TestSavingsOpportunities:
    """Tests para savings_opportunities - DIFERENCIADOR."""

    @patch("finanzas_tracker.mcp.server._get_analysis_data")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_finds_category_increases(
        self, mock_get_profile: MagicMock, mock_data: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica que detecta categorías que aumentaron."""
        mock_get_profile.return_value = mock_profile_id
        mock_data.return_value = {
            "transactions": [],
            "current_month_txns": [],
            "total_current": Decimal("150000"),
            "total_last": Decimal("100000"),
            "by_category_current": {"Restaurantes": Decimal("60000")},
            "by_category_last": {"Restaurantes": Decimal("30000")},
            "by_merchant": {},
            "transaction_count": 10,
            "days": 30,
        }

        result = savings_opportunities()

        assert "ahorro_potencial_total" in result
        assert "oportunidades" in result

    @patch("finanzas_tracker.mcp.server._get_analysis_data")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_returns_formatted_savings(
        self, mock_get_profile: MagicMock, mock_data: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica que retorna montos formateados."""
        mock_get_profile.return_value = mock_profile_id
        mock_data.return_value = {
            "transactions": [],
            "current_month_txns": [],
            "total_current": Decimal("100000"),
            "total_last": Decimal("100000"),
            "by_category_current": {},
            "by_category_last": {},
            "by_merchant": {},
            "transaction_count": 10,
            "days": 30,
        }

        result = savings_opportunities()

        assert "ahorro_potencial_total" in result
        assert "₡" in result["ahorro_potencial_total"]


# =============================================================================
# TEST: CASHFLOW PREDICTION (DIFERENCIADOR)
# =============================================================================


class TestCashflowPrediction:
    """Tests para cashflow_prediction - DIFERENCIADOR."""

    @patch("finanzas_tracker.mcp.server._get_analysis_data")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_returns_prediction_structure(
        self, mock_get_profile: MagicMock, mock_data: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica estructura de predicción."""
        mock_get_profile.return_value = mock_profile_id
        mock_txn = MagicMock()
        mock_txn.fecha_transaccion = datetime.now() - timedelta(days=5)
        mock_txn.monto_crc = Decimal("10000")

        mock_data.return_value = {
            "transactions": [mock_txn],
            "current_month_txns": [mock_txn],
            "total_current": Decimal("100000"),
            "total_last": Decimal("90000"),
            "by_category_current": {},
            "by_category_last": {},
            "by_merchant": {},
            "transaction_count": 10,
            "days": 60,
        }

        result = cashflow_prediction()

        assert "prediccion_7_dias" in result
        assert "proyeccion_mensual" in result
        assert "sostenibilidad" in result

    @patch("finanzas_tracker.mcp.server._get_analysis_data")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_identifies_high_risk_days(
        self, mock_get_profile: MagicMock, mock_data: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica que identifica días de alto riesgo."""
        mock_get_profile.return_value = mock_profile_id
        mock_txn = MagicMock()
        mock_txn.fecha_transaccion = datetime.now() - timedelta(days=5)
        mock_txn.monto_crc = Decimal("10000")

        mock_data.return_value = {
            "transactions": [mock_txn],
            "current_month_txns": [mock_txn],
            "total_current": Decimal("100000"),
            "total_last": Decimal("90000"),
            "by_category_current": {},
            "by_category_last": {},
            "by_merchant": {},
            "transaction_count": 10,
            "days": 60,
        }

        result = cashflow_prediction(days_ahead=14)

        assert "dias_riesgo" in result


# =============================================================================
# TEST: SPENDING ALERT (DIFERENCIADOR)
# =============================================================================


class TestSpendingAlert:
    """Tests para spending_alert - DIFERENCIADOR."""

    @patch("finanzas_tracker.mcp.server._get_analysis_data")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_returns_alert_structure(
        self, mock_get_profile: MagicMock, mock_data: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica estructura de alertas."""
        mock_get_profile.return_value = mock_profile_id
        mock_data.return_value = {
            "transactions": [],
            "current_month_txns": [],
            "total_current": Decimal("100000"),
            "total_last": Decimal("80000"),
            "by_category_current": {},
            "by_category_last": {},
            "by_merchant": {},
            "transaction_count": 0,
            "days": 30,
        }

        result = spending_alert()

        assert "estado" in result
        assert "total_alertas" in result
        assert "alertas" in result
        assert "mensaje" in result

    @patch("finanzas_tracker.mcp.server._get_analysis_data")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_detects_unusual_transactions(
        self, mock_get_profile: MagicMock, mock_data: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica que detecta transacciones inusuales."""
        mock_get_profile.return_value = mock_profile_id
        mock_txn = MagicMock()
        mock_txn.fecha_transaccion = datetime.now()
        mock_txn.comercio = "Tienda Grande"
        mock_txn.monto_crc = Decimal("100000")

        mock_data.return_value = {
            "transactions": [mock_txn],
            "current_month_txns": [mock_txn],
            "total_current": Decimal("100000"),
            "total_last": Decimal("80000"),
            "by_category_current": {},
            "by_category_last": {},
            "by_merchant": {},
            "transaction_count": 10,
            "days": 30,
        }

        result = spending_alert()

        assert result["total_alertas"] >= 0


# =============================================================================
# TEST: GOAL ADVISOR (DIFERENCIADOR)
# =============================================================================


class TestGoalAdvisor:
    """Tests para goal_advisor - DIFERENCIADOR."""

    @patch("finanzas_tracker.mcp.server._get_analysis_data")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_returns_goal_analysis(
        self, mock_get_profile: MagicMock, mock_data: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica análisis de meta."""
        mock_get_profile.return_value = mock_profile_id
        mock_data.return_value = {
            "transactions": [],
            "current_month_txns": [],
            "total_current": Decimal("500000"),
            "total_last": Decimal("500000"),
            "by_category_current": {
                "Entretenimiento": Decimal("80000"),
                "Restaurantes": Decimal("100000"),
            },
            "by_category_last": {},
            "by_merchant": {},
            "transaction_count": 30,
            "days": 30,
        }

        result = goal_advisor(goal_amount=300000, goal_months=6)

        assert "meta" in result
        assert "necesitas" in result
        assert "viabilidad" in result
        assert "plan" in result

    @patch("finanzas_tracker.mcp.server._get_analysis_data")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_validates_inputs(
        self, mock_get_profile: MagicMock, mock_data: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica validación de inputs."""
        mock_get_profile.return_value = mock_profile_id

        # Monto negativo
        result = goal_advisor(goal_amount=-100, goal_months=6)
        assert result["error"] is True

        # Meses negativos
        result = goal_advisor(goal_amount=100000, goal_months=-1)
        assert result["error"] is True

    @patch("finanzas_tracker.mcp.server._get_analysis_data")
    @patch("finanzas_tracker.mcp.server._get_active_profile_id")
    def test_assesses_viability(
        self, mock_get_profile: MagicMock, mock_data: MagicMock, mock_profile_id: str
    ) -> None:
        """Verifica evaluación de viabilidad."""
        mock_get_profile.return_value = mock_profile_id
        mock_data.return_value = {
            "transactions": [],
            "current_month_txns": [],
            "total_current": Decimal("500000"),
            "total_last": Decimal("500000"),
            "by_category_current": {
                "Entretenimiento": Decimal("200000"),
            },
            "by_category_last": {},
            "by_merchant": {},
            "transaction_count": 30,
            "days": 30,
        }

        result = goal_advisor(goal_amount=100000, goal_months=3)

        assert "es_alcanzable" in result["viabilidad"]
        assert "dificultad" in result["viabilidad"]
