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

    # === Configuración de Google OAuth (Gmail) ===
    google_client_id: str | None = Field(
        default=None,
        description="Client ID de Google Cloud para Gmail API",
    )
    google_client_secret: str | None = Field(
        default=None,
        description="Client Secret de Google Cloud para Gmail API",
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

    # === Embeddings (RAG) ===
    # Voyage AI (recomendado por Anthropic)
    voyage_api_key: str | None = Field(
        default=None,
        description="API Key de Voyage AI para embeddings (opcional)",
    )
    voyage_model: str = Field(
        default="voyage-3-lite",
        description="Modelo de Voyage AI: voyage-3-lite, voyage-3, voyage-finance-2",
    )

    # OpenAI (fallback para embeddings)
    openai_api_key: str | None = Field(
        default=None,
        description="API Key de OpenAI para embeddings (opcional, fallback)",
    )
    openai_embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Modelo de embeddings de OpenAI",
    )

    # Modelo local (último fallback)
    local_embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="Modelo de Sentence Transformers para embeddings locales",
    )

    # === Base de datos (PostgreSQL) ===
    postgres_host: str = Field(
        default="localhost",
        description="Host del servidor PostgreSQL",
    )
    postgres_port: int = Field(
        default=5432,
        description="Puerto del servidor PostgreSQL",
    )
    postgres_user: str = Field(
        default="finanzas",
        description="Usuario de PostgreSQL",
    )
    postgres_password: str = Field(
        default="finanzas_dev_2025",
        description="Contraseña de PostgreSQL",
    )
    postgres_db: str = Field(
        default="finanzas_tracker",
        description="Nombre de la base de datos PostgreSQL",
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
        default="claude-haiku-4-5-20251001",
        description="Modelo de Claude a utilizar (Haiku 4.5 - más rápido y económico, $1/M tokens)",
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

    # === JWT Authentication ===
    jwt_secret_key: str = Field(
        default="dev-secret-key-change-in-production-32chars",
        description="Clave secreta para firmar tokens JWT (CAMBIAR EN PRODUCCIÓN)",
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="Algoritmo para firmar tokens JWT",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=60 * 24,  # 24 horas
        description="Tiempo de expiración del access token en minutos",
        ge=5,
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("logs_directory", mode="after")
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
        Obtiene la URL de conexión a PostgreSQL.

        Returns:
            str: URL de conexión a PostgreSQL
        """
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    def get_async_database_url(self) -> str:
        """
        Obtiene la URL de conexión asíncrona a PostgreSQL.

        Returns:
            str: URL de conexión asíncrona (para FastAPI)
        """
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

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
    return Settings()


# Instancia global de configuración
settings = get_settings()
