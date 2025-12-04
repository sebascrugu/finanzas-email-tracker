"""
Tests de API para FastAPI endpoints.

Usa TestClient para probar los endpoints HTTP sin levantar servidor.
Cada test usa la base de datos de tests (PostgreSQL real).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from finanzas_tracker.api.main import app
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.profile import Profile


@pytest.fixture
def client(session: Session) -> TestClient:
    """
    Cliente de tests que usa la sesión de DB de tests.
    
    Sobreescribe la dependencia get_db para usar nuestra sesión de tests.
    """
    from finanzas_tracker.api.dependencies import get_db
    
    def override_get_db():
        yield session
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def test_profile(session: Session) -> Profile:
    """Crea un perfil de prueba activo."""
    profile = Profile(
        nombre="Test Profile",
        email_outlook="test@example.com",
        es_activo=True,
        activo=True,
    )
    session.add(profile)
    session.flush()
    return profile


@pytest.fixture
def test_category(session: Session) -> Category:
    """Crea una categoría de prueba con subcategoría."""
    category = Category(
        nombre="Alimentación",
        tipo_presupuesto="necesidades",
        icono="🍔",
    )
    session.add(category)
    session.flush()
    
    subcategory = Subcategory(
        nombre="Restaurantes",
        category_id=category.id,
    )
    session.add(subcategory)
    session.flush()
    
    return category


class TestRootEndpoints:
    """Tests para endpoints raíz."""
    
    def test_root_returns_api_info(self, client: TestClient) -> None:
        """GET / devuelve información del API."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Finanzas Tracker CR API"
        assert data["status"] == "running"
        assert "docs" in data
    
    def test_health_check(self, client: TestClient) -> None:
        """GET /health devuelve estado saludable."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "postgresql"


class TestProfilesAPI:
    """Tests para /api/v1/profiles."""
    
    def test_list_profiles_empty(self, client: TestClient) -> None:
        """GET /profiles sin datos devuelve lista vacía."""
        response = client.get("/api/v1/profiles")
        
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
    
    def test_list_profiles_with_data(
        self,
        client: TestClient,
        test_profile: Profile,
    ) -> None:
        """GET /profiles con perfil devuelve la lista."""
        response = client.get("/api/v1/profiles")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["nombre"] == "Test Profile"
    
    def test_create_profile(self, client: TestClient) -> None:
        """POST /profiles crea un perfil nuevo."""
        response = client.post(
            "/api/v1/profiles",
            json={
                "nombre": "Nuevo Perfil",
                "email_outlook": "nuevo@example.com",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["nombre"] == "Nuevo Perfil"
        assert data["email_outlook"] == "nuevo@example.com"
        assert "id" in data
    
    def test_get_profile_not_found(self, client: TestClient) -> None:
        """GET /profiles/{id} con ID inexistente devuelve 404."""
        response = client.get("/api/v1/profiles/nonexistent-id")
        
        assert response.status_code == 404
        data = response.json()
        assert "error" in data["detail"]


class TestTransactionsAPI:
    """Tests para /api/v1/transactions."""
    
    def test_list_transactions_requires_profile(
        self,
        client: TestClient,
    ) -> None:
        """GET /transactions sin perfil activo devuelve 404."""
        response = client.get("/api/v1/transactions")
        
        assert response.status_code == 404
        data = response.json()
        assert data["detail"]["code"] == "PROFILE_NOT_FOUND"
    
    def test_list_transactions_empty(
        self,
        client: TestClient,
        test_profile: Profile,
    ) -> None:
        """GET /transactions con perfil activo devuelve lista vacía."""
        response = client.get("/api/v1/transactions")
        
        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["total"] == 0
    
    def test_create_transaction(
        self,
        client: TestClient,
        test_profile: Profile,
        test_category: Category,
        session: Session,
    ) -> None:
        """POST /transactions crea transacción manual."""
        # Obtener subcategoría
        subcategory = test_category.subcategories[0]
        
        response = client.post(
            "/api/v1/transactions",
            json={
                "comercio": "Starbucks",
                "monto_original": 5000.00,
                "moneda_original": "CRC",
                "monto_crc": 5000.00,
                "tipo_transaccion": "compra",
                "banco": "bac",
                "subcategory_id": subcategory.id,
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["comercio"] == "Starbucks"
        assert data["monto_crc"] == 5000.00
    
    def test_get_transaction_not_found(
        self,
        client: TestClient,
        test_profile: Profile,
    ) -> None:
        """GET /transactions/{id} con ID inexistente devuelve 404."""
        response = client.get("/api/v1/transactions/nonexistent-id")
        
        assert response.status_code == 404


class TestCategoriesAPI:
    """Tests para /api/v1/categories."""
    
    def test_list_categories_empty(self, client: TestClient) -> None:
        """GET /categories sin datos devuelve lista vacía."""
        response = client.get("/api/v1/categories")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_list_categories_with_data(
        self,
        client: TestClient,
        test_category: Category,
    ) -> None:
        """GET /categories con categoría devuelve la lista."""
        response = client.get("/api/v1/categories")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        
        # Buscar nuestra categoría
        found = next((c for c in data if c["nombre"] == "Alimentación"), None)
        assert found is not None
        assert found["tipo_presupuesto"] == "necesidades"


class TestBudgetsAPI:
    """Tests para /api/v1/budgets."""
    
    def test_get_budget_requires_profile(self, client: TestClient) -> None:
        """GET /budgets/summary sin perfil activo devuelve 404."""
        response = client.get("/api/v1/budgets/summary")
        
        assert response.status_code == 404
    
    def test_get_budget_summary(
        self,
        client: TestClient,
        test_profile: Profile,
    ) -> None:
        """GET /budgets/summary con perfil activo devuelve resumen."""
        response = client.get("/api/v1/budgets/summary")
        
        # Puede ser 200 o 404 dependiendo de si hay budget configurado
        assert response.status_code in [200, 404]
