"""
Gestor de autenticación con Microsoft Graph API usando MSAL.

Este módulo maneja toda la autenticación OAuth 2.0 con Microsoft Graph,
incluyendo la obtención y renovación de tokens de acceso.
Soporta cuentas personales de Microsoft (outlook.com, hotmail.com).
"""

from pathlib import Path

import msal

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)

# Archivo para cache de tokens (para no tener que autenticarse cada vez)
TOKEN_CACHE_FILE = Path("data/.token_cache.bin")


class AuthManager:
    """
    Gestor de autenticación para Microsoft Graph API.

    Maneja el flujo de autenticación OAuth 2.0 usando MSAL.
    Soporta cuentas personales de Microsoft (outlook.com, hotmail.com)
    usando autenticación interactiva.
    """

    def __init__(self) -> None:
        """Inicializa el gestor de autenticación."""
        self.client_id = settings.azure_client_id
        self.scopes = [
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/User.Read",
        ]

        # Para cuentas personales, usamos "consumers" en vez de un tenant específico
        self.authority = "https://login.microsoftonline.com/consumers"

        # Cargar cache de tokens si existe
        self.cache = msal.SerializableTokenCache()
        if TOKEN_CACHE_FILE.exists():
            self.cache.deserialize(TOKEN_CACHE_FILE.read_text())

        # Crear aplicación pública de MSAL (para autenticación interactiva)
        self.app = msal.PublicClientApplication(
            client_id=self.client_id,
            authority=self.authority,
            token_cache=self.cache,
        )

        logger.info("AuthManager inicializado (modo interactivo para cuentas personales)")

    def _save_cache(self) -> None:
        """Guarda el cache de tokens en disco."""
        if self.cache.has_state_changed:
            TOKEN_CACHE_FILE.parent.mkdir(exist_ok=True)
            TOKEN_CACHE_FILE.write_text(self.cache.serialize())

    def get_access_token(self, interactive: bool = True) -> str | None:
        """
        Obtiene un token de acceso para Microsoft Graph API.

        Intenta obtener un token del cache primero. Si no hay token en cache
        o ha expirado, solicita autenticación interactiva al usuario.

        Args:
            interactive: Si True, permite autenticación interactiva (navegador)

        Returns:
            str | None: Token de acceso o None si falla la autenticación

        Example:
            >>> auth = AuthManager()
            >>> token = auth.get_access_token()
            >>> if token:
            ...     print("Autenticación exitosa")
        """
        logger.info("Obteniendo token de acceso...")

        # Intentar obtener token del cache
        accounts = self.app.get_accounts()
        if accounts:
            logger.debug(f"Encontradas {len(accounts)} cuentas en cache")
            result = self.app.acquire_token_silent(self.scopes, account=accounts[0])
            if result and "access_token" in result:
                logger.info("Token obtenido del cache")
                return result["access_token"]

        # Si no hay token en cache, usar autenticación interactiva
        if not interactive:
            logger.warning("No hay token en cache y modo interactivo deshabilitado")
            return None

        logger.info("🌐 Se abrirá el navegador para autenticación...")
        logger.info("Por favor, inicia sesión con tu cuenta de Outlook")

        try:
            # Autenticación interactiva (abre el navegador)
            result = self.app.acquire_token_interactive(
                scopes=self.scopes,
                prompt="select_account",  # Permite elegir cuenta
            )

            if "access_token" in result:
                logger.success("✅ Autenticación exitosa!")
                self._save_cache()
                return result["access_token"]

            # Error al obtener token
            error = result.get("error", "Unknown error")
            error_description = result.get("error_description", "No description")
            logger.error(f"Error al autenticar: {error} - {error_description}")
            return None

        except Exception as e:
            logger.error(f"Error durante autenticación interactiva: {e}")
            return None

    def get_authorization_header(self) -> dict[str, str] | None:
        """
        Obtiene el header de autorización para requests HTTP.

        Returns:
            dict | None: Header de autorización o None si falla

        Example:
            >>> auth = AuthManager()
            >>> headers = auth.get_authorization_header()
            >>> if headers:
            ...     response = requests.get(url, headers=headers)
        """
        token = self.get_access_token()
        if not token:
            return None

        return {"Authorization": f"Bearer {token}"}

    def get_current_user_email(self) -> str | None:
        """
        Obtiene el email del usuario autenticado actualmente.

        Returns:
            str | None: Email del usuario o None si no hay usuario autenticado
        """
        accounts = self.app.get_accounts()
        if accounts:
            return accounts[0].get("username")
        return None

    def logout(self) -> None:
        """
        Cierra sesión eliminando las cuentas del cache.

        Útil si se quiere cambiar de cuenta.
        """
        accounts = self.app.get_accounts()
        for account in accounts:
            self.app.remove_account(account)

        if TOKEN_CACHE_FILE.exists():
            TOKEN_CACHE_FILE.unlink()

        logger.info("Sesión cerrada, cache eliminado")

    def test_connection(self) -> bool:
        """
        Prueba la conexión con Microsoft Graph API.

        Intenta obtener un token de acceso para verificar que las
        credenciales sean válidas y la conexión funcione.

        Returns:
            bool: True si la conexión es exitosa, False en caso contrario

        Example:
            >>> auth = AuthManager()
            >>> if auth.test_connection():
            ...     print("Conexión exitosa con Microsoft Graph")
        """
        logger.info("Probando conexión con Microsoft Graph API...")

        token = self.get_access_token()
        if token:
            user_email = self.get_current_user_email()
            if user_email:
                logger.success(f"✅ Autenticado como: {user_email}")
            logger.success("✅ Conexión exitosa con Microsoft Graph API")
            return True

        logger.error("❌ No se pudo conectar con Microsoft Graph API")
        return False


# Instancia singleton para uso en toda la aplicación
auth_manager = AuthManager()


__all__ = ["AuthManager", "auth_manager"]

