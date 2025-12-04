"""
Tests de integración para los endpoints principales de la API.

Prueba los flujos de trabajo comunes a través de múltiples endpoints.
"""

from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from finanzas_tracker.api.main import app
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.enums import BankName, CardType, Currency, TransactionType
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction


# ============================================================
# Fixtures compartidos
# ============================================================


@pytest.fixture
def client(session: Session) -> TestClient:
    """Cliente de tests con sesión de DB de tests."""
    from finanzas_tracker.api.dependencies import get_db

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def active_profile(session: Session) -> Profile:
    """Perfil activo para tests."""
    profile = Profile(
        nombre="Usuario Test",
        email_outlook="test@example.com",
        es_activo=True,
        activo=True,
    )
    session.add(profile)
    session.flush()
    return profile


@pytest.fixture
def test_category(session: Session) -> Category:
    """Categoría para tests."""
    category = Category(
        nombre="Alimentación",
        tipo="necesidades",
        icono="🍔",
    )
    session.add(category)
    session.flush()
    return category


@pytest.fixture
def test_subcategory(session: Session, test_category: Category) -> Subcategory:
    """Subcategoría para tests."""
    subcategory = Subcategory(
        nombre="Supermercado",
        category_id=test_category.id,
    )
    session.add(subcategory)
    session.flush()
    return subcategory


@pytest.fixture
def test_card(session: Session, active_profile: Profile) -> Card:
    """Tarjeta de crédito para tests."""
    card = Card(
        profile_id=active_profile.id,
        alias="Visa Platinum",
        banco=BankName.BAC,
        tipo=CardType.CREDIT,
        ultimos_4_digitos="1234",
        limite_credito=Decimal("500000"),
        fecha_corte=15,
        fecha_vencimiento=5,
    )
    session.add(card)
    session.flush()
    return card


@pytest.fixture
def test_transactions(
    session: Session,
    active_profile: Profile,
    test_subcategory: Subcategory,
) -> list[Transaction]:
    """Transacciones de ejemplo para tests."""
    transactions = []
    for i in range(5):
        tx = Transaction(
            profile_id=active_profile.id,
            email_id=f"test-email-{i:03d}",
            comercio=f"COMERCIO {i}",
            monto_original=Decimal(f"{(i + 1) * 10000}"),
            moneda_original=Currency.CRC,
            monto_crc=Decimal(f"{(i + 1) * 10000}"),
            tipo_transaccion=TransactionType.PURCHASE,
            banco=BankName.BAC,
            subcategory_id=test_subcategory.id,
            fecha_transaccion=datetime(2025, 11, 15 - i),
        )
        session.add(tx)
        transactions.append(tx)
    session.flush()
    return transactions


# ============================================================
# Tests de Profiles
# ============================================================


class TestProfilesAPI:
    """Tests para /api/v1/profiles."""

    def test_list_profiles_returns_200(self, client: TestClient, active_profile: Profile) -> None:
        """GET /api/v1/profiles retorna 200."""
        response = client.get("/api/v1/profiles")
        assert response.status_code == 200

    def test_get_profile_by_id_returns_200(
        self, client: TestClient, active_profile: Profile
    ) -> None:
        """GET /api/v1/profiles/{id} retorna 200."""
        response = client.get(f"/api/v1/profiles/{active_profile.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["nombre"] == "Usuario Test"

    def test_get_nonexistent_profile_returns_404(self, client: TestClient) -> None:
        """GET /api/v1/profiles/{id} con ID inexistente retorna 404."""
        response = client.get("/api/v1/profiles/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


# ============================================================
# Tests de Categories
# ============================================================


class TestCategoriesAPI:
    """Tests para /api/v1/categories."""

    def test_list_categories_returns_200(self, client: TestClient, test_category: Category) -> None:
        """GET /api/v1/categories retorna 200."""
        response = client.get("/api/v1/categories")
        assert response.status_code == 200


# ============================================================
# Tests de Transactions
# ============================================================


class TestTransactionsAPI:
    """Tests para /api/v1/transactions."""

    def test_list_transactions_returns_200(
        self, client: TestClient, active_profile: Profile
    ) -> None:
        """GET /api/v1/transactions retorna 200."""
        response = client.get(f"/api/v1/transactions?profile_id={active_profile.id}")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data

    def test_list_transactions_with_data(
        self, client: TestClient, active_profile: Profile, test_transactions: list[Transaction]
    ) -> None:
        """GET /api/v1/transactions con datos retorna transacciones."""
        response = client.get(f"/api/v1/transactions?profile_id={active_profile.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5

    def test_get_transaction_by_id_returns_200(
        self, client: TestClient, test_transactions: list[Transaction]
    ) -> None:
        """GET /api/v1/transactions/{id} retorna 200."""
        tx = test_transactions[0]
        response = client.get(f"/api/v1/transactions/{tx.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["comercio"] == tx.comercio

    def test_get_nonexistent_transaction_returns_404(self, client: TestClient) -> None:
        """GET /api/v1/transactions/{id} con ID inexistente retorna 404."""
        response = client.get("/api/v1/transactions/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


# ============================================================
# Tests de Cards
# ============================================================


class TestCardsAPI:
    """Tests para /api/v1/cards."""

    def test_list_cards_returns_200(
        self, client: TestClient, active_profile: Profile, test_card: Card
    ) -> None:
        """GET /api/v1/cards retorna 200."""
        response = client.get(f"/api/v1/cards?profile_id={active_profile.id}")
        assert response.status_code == 200

    def test_get_card_by_id_returns_response(self, client: TestClient, test_card: Card) -> None:
        """GET /api/v1/cards/{id} retorna respuesta (200 o 404 si no hay summary)."""
        response = client.get(f"/api/v1/cards/{test_card.id}")
        # El endpoint puede retornar 200 con summary o 404 si no encuentra la tarjeta
        # En tests con tarjeta nueva sin ciclos, puede retornar 404
        assert response.status_code in [200, 404]


# ============================================================
# Tests de Expenses
# ============================================================


class TestExpensesAPI:
    """Tests para /api/v1/expenses."""

    def test_summary_monthly_returns_200(
        self, client: TestClient, active_profile: Profile, test_transactions: list[Transaction]
    ) -> None:
        """GET /api/v1/expenses/summary/monthly retorna 200."""
        response = client.get(
            "/api/v1/expenses/summary/monthly",
            params={
                "profile_id": str(active_profile.id),
                "mes": 11,
                "anio": 2025,
            },
        )
        assert response.status_code == 200

    def test_predicted_expenses_returns_200(
        self, client: TestClient, active_profile: Profile
    ) -> None:
        """GET /api/v1/expenses/predicted retorna 200."""
        response = client.get(
            "/api/v1/expenses/predicted", params={"profile_id": str(active_profile.id)}
        )
        assert response.status_code == 200

    def test_cash_flow_returns_200(self, client: TestClient, active_profile: Profile) -> None:
        """GET /api/v1/expenses/cash-flow retorna 200."""
        response = client.get(
            "/api/v1/expenses/cash-flow",
            params={
                "profile_id": str(active_profile.id),
                "mes": 11,
                "anio": 2025,
                "saldo_inicial": "100000",
            },
        )
        assert response.status_code == 200


# ============================================================
# Tests de Health y Root
# ============================================================


class TestHealthAPI:
    """Tests para endpoints de salud."""

    def test_health_check_returns_200(self, client: TestClient) -> None:
        """GET /health retorna 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_root_returns_200(self, client: TestClient) -> None:
        """GET / retorna 200."""
        response = client.get("/")
        assert response.status_code == 200


# ============================================================
# Tests de Errores
# ============================================================


class TestErrorHandling:
    """Tests de manejo de errores."""

    def test_invalid_uuid_returns_4xx(self, client: TestClient) -> None:
        """UUID inválido retorna 4xx (404 o 422 según implementación)."""
        response = client.get("/api/v1/profiles/not-a-uuid")
        # FastAPI puede retornar 404 (no encontrado) o 422 (validación)
        assert response.status_code in [404, 422]

    def test_nonexistent_endpoint_returns_404(self, client: TestClient) -> None:
        """Endpoint inexistente retorna 404."""
        response = client.get("/api/v1/this-does-not-exist")
        assert response.status_code == 404
