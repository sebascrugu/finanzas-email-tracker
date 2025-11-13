"""
Tests unitarios para el módulo de configuración.

Estos tests verifican que la configuración se carga correctamente
y que las validaciones funcionan como se espera.
"""

from pydantic import ValidationError
import pytest

from finanzas_tracker.config.settings import Settings


def test_settings_with_valid_env_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test que verifica que Settings se carga correctamente con variables válidas."""
    # Configurar variables de entorno para el test
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("USER_EMAIL", "test@example.com")
    monkeypatch.setenv("MOM_EMAIL", "mom@example.com")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test123")

    # Crear instancia de Settings
    settings = Settings()  # type: ignore[call-arg]

    # Verificar que los valores se cargaron correctamente
    assert settings.azure_client_id == "test-client-id"
    assert settings.azure_tenant_id == "test-tenant-id"
    assert settings.user_email == "test@example.com"
    assert settings.mom_email == "mom@example.com"


def test_settings_invalid_email(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test que verifica que se rechacen emails inválidos."""
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("USER_EMAIL", "invalid-email")  # Email inválido
    monkeypatch.setenv("MOM_EMAIL", "mom@example.com")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test123")

    # Debe lanzar ValidationError
    with pytest.raises(ValidationError):
        Settings()  # type: ignore[call-arg]


def test_settings_get_database_url() -> None:
    """Test que verifica la generación de la URL de base de datos."""
    # Este test usa las variables de .env o valores por defecto
    # En un entorno de test real, usarías monkeypatch
    pass  # Placeholder - implementar cuando se tengan variables de test


def test_settings_environment_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test que verifica los métodos de verificación de entorno."""
    monkeypatch.setenv("AZURE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("AZURE_TENANT_ID", "test-tenant-id")
    monkeypatch.setenv("AZURE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("USER_EMAIL", "test@example.com")
    monkeypatch.setenv("MOM_EMAIL", "mom@example.com")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test123")
    monkeypatch.setenv("ENVIRONMENT", "development")

    settings = Settings()  # type: ignore[call-arg]

    assert settings.is_development() is True
    assert settings.is_production() is False


