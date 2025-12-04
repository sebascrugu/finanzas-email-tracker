"""
Tests de API para endpoints de transacciones.

Prueba completa del CRUD de /api/v1/transactions.
"""

from datetime import datetime
from decimal import Decimal

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import Session

from finanzas_tracker.api.main import app
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction


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
        nombre="Test User",
        email_outlook="testuser@example.com",
        es_activo=True,
        activo=True,
    )
    session.add(profile)
    session.flush()
    return profile


@pytest.fixture
def category_with_subcategory(session: Session) -> tuple[Category, Subcategory]:
    """Categoría con subcategoría para tests."""
    category = Category(
        nombre="Transporte",
        tipo="necesidades",  # CategoryType enum
        icono="🚗",
    )
    session.add(category)
    session.flush()

    subcategory = Subcategory(
        nombre="Gasolina",
        category_id=category.id,
    )
    session.add(subcategory)
    session.flush()

    return category, subcategory


@pytest.fixture
def sample_transaction(
    session: Session,
    active_profile: Profile,
    category_with_subcategory: tuple[Category, Subcategory],
) -> Transaction:
    """Transacción de ejemplo para tests."""
    _, subcategory = category_with_subcategory

    transaction = Transaction(
        profile_id=active_profile.id,
        email_id="test-email-001",
        comercio="GASOLINERA TOTAL",
        monto_original=Decimal("25000.00"),
        moneda_original="CRC",
        monto_crc=Decimal("25000.00"),
        tipo_transaccion="compra",
        banco="bac",
        subcategory_id=subcategory.id,
        fecha_transaccion=datetime(2025, 11, 15, 10, 30),
    )
    session.add(transaction)
    session.flush()
    return transaction


class TestListTransactions:
    """Tests para GET /api/v1/transactions."""

    def test_returns_empty_list_when_no_transactions(
        self,
        client: TestClient,
        active_profile: Profile,
    ) -> None:
        """Lista vacía cuando no hay transacciones."""
        response = client.get("/api/v1/transactions")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
        # Decimal se serializa como string en JSON
        assert data["total_crc"] == "0"

    def test_returns_transactions_for_active_profile(
        self,
        client: TestClient,
        sample_transaction: Transaction,
    ) -> None:
        """Lista transacciones del perfil activo."""
        response = client.get("/api/v1/transactions")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["comercio"] == "GASOLINERA TOTAL"
        # Decimal se serializa como string en JSON
        assert data["items"][0]["monto_crc"] == "25000.00"

    def test_pagination_works(
        self,
        client: TestClient,
        active_profile: Profile,
        category_with_subcategory: tuple[Category, Subcategory],
        session: Session,
    ) -> None:
        """Paginación funciona correctamente."""
        _, subcategory = category_with_subcategory

        # Crear 5 transacciones
        for i in range(5):
            txn = Transaction(
                profile_id=active_profile.id,
                email_id=f"pagination-test-{i}",
                comercio=f"COMERCIO {i}",
                monto_original=Decimal(f"{(i + 1) * 1000}"),
                moneda_original="CRC",
                monto_crc=Decimal(f"{(i + 1) * 1000}"),
                tipo_transaccion="compra",
                banco="bac",
                subcategory_id=subcategory.id,
                fecha_transaccion=datetime(2025, 11, i + 1, 10, 0),
            )
            session.add(txn)
        session.flush()

        # Pedir página 1 con límite 2
        response = client.get("/api/v1/transactions?skip=0&limit=2")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2
        assert data["skip"] == 0
        assert data["limit"] == 2

    def test_filter_by_banco(
        self,
        client: TestClient,
        sample_transaction: Transaction,
    ) -> None:
        """Filtro por banco funciona."""
        response = client.get("/api/v1/transactions?banco=bac")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1

        response = client.get("/api/v1/transactions?banco=popular")
        data = response.json()
        assert data["total"] == 0


class TestGetTransaction:
    """Tests para GET /api/v1/transactions/{id}."""

    def test_returns_transaction_by_id(
        self,
        client: TestClient,
        sample_transaction: Transaction,
    ) -> None:
        """Obtiene transacción por ID."""
        response = client.get(f"/api/v1/transactions/{sample_transaction.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_transaction.id
        assert data["comercio"] == "GASOLINERA TOTAL"

    def test_returns_404_for_nonexistent_id(
        self,
        client: TestClient,
        active_profile: Profile,
    ) -> None:
        """404 para ID inexistente."""
        response = client.get("/api/v1/transactions/nonexistent-uuid")

        assert response.status_code == 404
        data = response.json()
        assert data["code"] == "TRANSACCIÓN_NOT_FOUND"


class TestCreateTransaction:
    """Tests para POST /api/v1/transactions."""

    def test_creates_transaction_successfully(
        self,
        client: TestClient,
        active_profile: Profile,
        category_with_subcategory: tuple[Category, Subcategory],
    ) -> None:
        """Crea transacción correctamente."""
        _, subcategory = category_with_subcategory

        response = client.post(
            "/api/v1/transactions",
            json={
                "comercio": "WALMART",
                "monto_original": 15000.00,
                "moneda_original": "CRC",
                "monto_crc": 15000.00,
                "tipo_transaccion": "compra",
                "banco": "popular",
                "subcategory_id": subcategory.id,
                "fecha_transaccion": "2025-11-20T14:30:00",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["comercio"] == "WALMART"
        # Decimal se serializa como string en JSON
        assert data["monto_crc"] == "15000.00"
        assert data["banco"] == "popular"
        assert "id" in data

    def test_validates_required_fields(
        self,
        client: TestClient,
        active_profile: Profile,
    ) -> None:
        """Valida campos requeridos."""
        response = client.post(
            "/api/v1/transactions",
            json={
                "comercio": "TEST",
                # Faltan campos requeridos
            },
        )

        assert response.status_code == 422  # Validation error


class TestUpdateTransaction:
    """Tests para PATCH /api/v1/transactions/{id}."""

    def test_updates_transaction_partially(
        self,
        client: TestClient,
        sample_transaction: Transaction,
    ) -> None:
        """Actualiza transacción parcialmente."""
        response = client.patch(
            f"/api/v1/transactions/{sample_transaction.id}",
            json={
                "comercio": "GASOLINERA TOTAL UPDATED",
                "notas": "Llenado de tanque",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["comercio"] == "GASOLINERA TOTAL UPDATED"
        assert data["notas"] == "Llenado de tanque"
        # Campos no actualizados permanecen igual (Decimal como string)
        assert data["monto_crc"] == "25000.00"

    def test_returns_404_for_nonexistent_transaction(
        self,
        client: TestClient,
        active_profile: Profile,
    ) -> None:
        """404 para transacción inexistente."""
        response = client.patch(
            "/api/v1/transactions/nonexistent-uuid",
            json={"comercio": "TEST"},
        )

        assert response.status_code == 404


class TestDeleteTransaction:
    """Tests para DELETE /api/v1/transactions/{id}."""

    def test_soft_deletes_transaction(
        self,
        client: TestClient,
        sample_transaction: Transaction,
        session: Session,
    ) -> None:
        """Soft delete de transacción."""
        response = client.delete(f"/api/v1/transactions/{sample_transaction.id}")

        assert response.status_code == 204

        # Verificar que no aparece en lista
        response = client.get("/api/v1/transactions")
        data = response.json()
        assert data["total"] == 0

        # Pero sigue en DB con deleted_at
        session.refresh(sample_transaction)
        assert sample_transaction.deleted_at is not None

    def test_returns_404_for_nonexistent_transaction(
        self,
        client: TestClient,
        active_profile: Profile,
    ) -> None:
        """404 para transacción inexistente."""
        response = client.delete("/api/v1/transactions/nonexistent-uuid")

        assert response.status_code == 404
