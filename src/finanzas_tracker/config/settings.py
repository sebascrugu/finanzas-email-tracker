"""
Configuración centralizada del proyecto usando Pydantic Settings.

Este módulo maneja todas las variables de entorno necesarias para el funcionamiento
de la aplicación de manera segura y con validación automática.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import EmailStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración principal de la aplicación."""

    # === Configuración de Azure AD / Microsoft Graph API ===
    azure_client_id: str = Field(
        ...,
        description="Client ID de la aplicación registrada en Azure AD",
    )
    azure_tenant_id: str = Field(
        ...,
        description="Tenant ID de Azure AD",
    )
    azure_client_secret: str = Field(
        ...,
        description="Client Secret de la aplicación en Azure AD",
    )
    redirect_uri: str = Field(
        default="http://localhost:8501",
        description="URI de redirección para OAuth2",
    )

    # === Cuentas de correo ===
    user_email: EmailStr = Field(
        ...,
        description="Correo electrónico del usuario principal",
    )
    mom_email: EmailStr = Field(
        ...,
        description="Correo electrónico de un segundo usuario (opcional para multi-usuario)",
    )

    # === Anthropic Claude API ===
    anthropic_api_key: str = Field(
        ...,
        description="API Key de Anthropic para Claude",
    )

    # === Base de datos ===
    database_path: Path = Field(
        default=Path("data/finanzas.db"),
        description="Ruta al archivo de base de datos SQLite",
    )

    # === Configuración de la aplicación ===
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Nivel de logging",
    )
    environment: Literal["development", "production", "testing"] = Field(
        default="development",
        description="Entorno de ejecución",
    )

    # === Microsoft Graph API ===
    graph_api_scopes: list[str] = Field(
        default=["https://graph.microsoft.com/.default"],
        description="Scopes de permisos para Microsoft Graph API",
    )

    # === Configuración de logging ===
    log_rotation: str = Field(
        default="10 MB",
        description="Tamaño máximo de los archivos de log antes de rotar",
    )
    log_retention: str = Field(
        default="1 month",
        description="Tiempo de retención de logs antiguos",
    )
    logs_directory: Path = Field(
        default=Path("logs"),
        description="Directorio donde se guardan los logs",
    )

    # === Configuración de procesamiento de correos ===
    email_fetch_days_back: int = Field(
        default=30,
        description="Cantidad de días hacia atrás para buscar correos",
        ge=1,
        le=365,
    )
    email_batch_size: int = Field(
        default=50,
        description="Cantidad de correos a procesar por lote",
        ge=1,
        le=100,
    )

    # === Configuración de Conversión de Moneda ===
    usd_to_crc_rate: float = Field(
        default=520.0,
        description="Tipo de cambio de dólares a colones costarricenses (actualizar manualmente)",
        ge=1.0,
    )

    # === Configuración de Claude ===
    claude_model: str = Field(
        default="claude-3-5-haiku-20241022",
        description="Modelo de Claude a utilizar (Haiku 4.5 - más rápido y económico)",
    )
    claude_max_tokens: int = Field(
        default=1024,
        description="Máximo de tokens en respuestas de Claude",
        ge=100,
        le=4096,
    )
    claude_temperature: float = Field(
        default=0.3,
        description="Temperatura para las respuestas de Claude",
        ge=0.0,
        le=1.0,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("database_path", "logs_directory", mode="after")
    @classmethod
    def create_directories(cls, path: Path) -> Path:
        """Crea los directorios necesarios si no existen."""
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        return path

    @field_validator("azure_client_secret", "anthropic_api_key")
    @classmethod
    def validate_secrets(cls, value: str) -> str:
        """Valida que los secretos no estén vacíos."""
        if not value or value.strip() == "":
            raise ValueError("Los secretos no pueden estar vacíos")
        return value

    def get_database_url(self) -> str:
        """
        Obtiene la URL de conexión a la base de datos.

        Returns:
            str: URL de conexión SQLite
        """
        return f"sqlite:///{self.database_path}"

    def is_development(self) -> bool:
        """
        Verifica si el entorno es de desarrollo.

        Returns:
            bool: True si es desarrollo
        """
        return self.environment == "development"

    def is_production(self) -> bool:
        """
        Verifica si el entorno es de producción.

        Returns:
            bool: True si es producción
        """
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """
    Obtiene una instancia singleton de Settings.

    Esta función está decorada con lru_cache para asegurar que solo
    se cree una instancia de Settings durante la vida de la aplicación.

    Returns:
        Settings: Instancia singleton de configuración
    """
    return Settings()  # type: ignore[call-arg]


# Instancia global de configuración
settings = get_settings()
