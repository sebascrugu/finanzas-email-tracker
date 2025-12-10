"""
Gestor de autenticación con Gmail API usando Google OAuth 2.0.

Este módulo maneja toda la autenticación OAuth 2.0 con Gmail API,
incluyendo la obtención y renovación de tokens de acceso.

SEGURIDAD: Los tokens se almacenan de forma segura usando el keyring del sistema
operativo (Keychain en macOS, Credential Locker en Windows, Secret Service en Linux).
"""

import json

import keyring
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)

# Configuración para almacenamiento seguro en keyring del SO
KEYRING_SERVICE_NAME = "finanzas-email-tracker"
KEYRING_GMAIL_USERNAME = "gmail-token-cache"

# Scopes necesarios para leer emails de Gmail
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]


class GmailAuthManager:
    """
    Gestor de autenticación para Gmail API.

    Maneja el flujo de autenticación OAuth 2.0 usando las librerías de Google.
    Soporta cuentas personales de Gmail usando autenticación interactiva.
    """

    def __init__(self) -> None:
        """Inicializa el gestor de autenticación de Gmail."""
        self.client_id = settings.google_client_id
        self.client_secret = settings.google_client_secret
        self.scopes = GMAIL_SCOPES
        self.creds: Credentials | None = None

        if not self.client_id or not self.client_secret:
            logger.warning("Credenciales de Google no configuradas en .env")
            return

        # Intentar cargar credenciales desde keyring
        self._load_cached_credentials()

        logger.info("GmailAuthManager inicializado")

    def _load_cached_credentials(self) -> None:
        """Carga credenciales desde el keyring del sistema."""
        try:
            cached_data = keyring.get_password(KEYRING_SERVICE_NAME, KEYRING_GMAIL_USERNAME)
            if cached_data:
                creds_dict = json.loads(cached_data)
                self.creds = Credentials.from_authorized_user_info(creds_dict, self.scopes)
                logger.debug("Credenciales de Gmail cargadas desde keyring")
        except Exception as e:
            logger.debug(f"No se pudieron cargar credenciales de Gmail: {e}")
            self.creds = None

    def _save_credentials(self) -> None:
        """Guarda credenciales de forma segura en el keyring del sistema."""
        if self.creds:
            try:
                creds_json = self.creds.to_json()
                keyring.set_password(KEYRING_SERVICE_NAME, KEYRING_GMAIL_USERNAME, creds_json)
                logger.debug("Credenciales de Gmail guardadas en keyring")
            except Exception as e:
                logger.error(f"Error guardando credenciales de Gmail: {e}")

    def get_credentials(self, interactive: bool = True) -> Credentials | None:
        """
        Obtiene credenciales válidas para Gmail API.

        Intenta usar credenciales del cache primero. Si no hay o están
        expiradas, solicita autenticación interactiva al usuario.

        Args:
            interactive: Si True, permite autenticación interactiva (navegador)

        Returns:
            Credentials | None: Credenciales o None si falla la autenticación
        """
        if not self.client_id or not self.client_secret:
            logger.error("Credenciales de Google no configuradas")
            return None

        # Verificar si las credenciales existentes son válidas
        if self.creds and self.creds.valid:
            logger.info("Usando credenciales de Gmail del cache")
            return self.creds

        # Intentar refrescar si están expiradas
        if self.creds and self.creds.expired and self.creds.refresh_token:
            try:
                logger.info("Refrescando token de Gmail...")
                self.creds.refresh(Request())
                self._save_credentials()
                logger.info("Token de Gmail refrescado exitosamente")
                return self.creds
            except Exception as e:
                logger.warning(f"Error refrescando token: {e}")
                self.creds = None

        # Si no hay credenciales válidas, hacer auth interactivo
        if not interactive:
            logger.warning("No hay credenciales válidas y modo interactivo deshabilitado")
            return None

        return self._authenticate_interactive()

    def _authenticate_interactive(self) -> Credentials | None:
        """
        Realiza autenticación interactiva abriendo el navegador.

        Returns:
            Credentials | None: Credenciales o None si falla
        """
        logger.info("🌐 Se abrirá el navegador para autenticación con Google...")

        try:
            # Crear configuración de cliente OAuth
            client_config = {
                "installed": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": ["http://localhost"],
                }
            }

            flow = InstalledAppFlow.from_client_config(client_config, self.scopes)

            # Ejecutar autenticación local (abre navegador)
            self.creds = flow.run_local_server(
                port=0,  # Puerto aleatorio disponible
                prompt="consent",  # Siempre pedir consentimiento
                success_message="✅ ¡Autenticación exitosa! Puedes cerrar esta ventana.",
            )

            if self.creds:
                self._save_credentials()
                logger.success("✅ Autenticación con Gmail exitosa!")
                return self.creds

        except Exception as e:
            logger.error(f"Error durante autenticación con Gmail: {e}")
            return None

        return None

    def get_current_user_email(self) -> str | None:
        """
        Obtiene el email del usuario autenticado actualmente.

        Returns:
            str | None: Email del usuario o None si no hay usuario autenticado
        """
        if not self.creds or not self.creds.valid:
            return None

        try:
            from googleapiclient.discovery import build

            service = build("oauth2", "v2", credentials=self.creds)
            user_info = service.userinfo().get().execute()
            return user_info.get("email")
        except Exception as e:
            logger.error(f"Error obteniendo email del usuario: {e}")
            return None

    def logout(self) -> None:
        """
        Cierra sesión eliminando las credenciales del cache.
        """
        self.creds = None

        try:
            keyring.delete_password(KEYRING_SERVICE_NAME, KEYRING_GMAIL_USERNAME)
            logger.info("Sesión de Gmail cerrada, cache eliminado")
        except Exception:
            logger.debug("No había cache de Gmail almacenado")

    def test_connection(self) -> bool:
        """
        Prueba la conexión con Gmail API.

        Returns:
            bool: True si la conexión es exitosa, False en caso contrario
        """
        logger.info("Probando conexión con Gmail API...")

        creds = self.get_credentials()
        if creds:
            user_email = self.get_current_user_email()
            if user_email:
                logger.success(f"✅ Autenticado como: {user_email}")
            logger.success("✅ Conexión exitosa con Gmail API")
            return True

        logger.error("❌ No se pudo conectar con Gmail API")
        return False

    def is_configured(self) -> bool:
        """Verifica si las credenciales de Google están configuradas."""
        return bool(self.client_id and self.client_secret)


# Instancia singleton para uso en toda la aplicación
gmail_auth_manager = GmailAuthManager()

__all__ = ["GmailAuthManager", "gmail_auth_manager"]
