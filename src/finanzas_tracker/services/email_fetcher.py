"""
Servicio para extraer correos de Outlook usando Microsoft Graph API.

Este módulo se encarga de conectar con Microsoft Graph, buscar correos
de notificaciones bancarias y extraer su información.
"""

from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import requests

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.core.retry import retry_on_network_error
from finanzas_tracker.services.auth_manager import auth_manager


logger = get_logger(__name__)


class EmailFetcher:
    """
    Servicio para extraer correos de Outlook usando Microsoft Graph API.

    Este servicio permite buscar correos de los bancos BAC Credomatic y
    Banco Popular en las cuentas de correo configuradas.
    """

    # Dominios y remitentes de los bancos (obtenidos de correos reales)
    BAC_SENDERS: ClassVar[list[str]] = [
        "notificacion@notificacionesbaccr.com",  # Notificaciones de transacciones
        "alerta@baccredomatic.com",  # Alertas de seguridad
        "servicio_al_cliente@baccredomatic.cr",  # Servicio al cliente
        "servicio-cliente@aviso.infobaccredomatic.com",  # Avisos
        "info@info.baccredomatic.net",  # Información general
    ]

    BANCO_POPULAR_SENDERS: ClassVar[list[str]] = [
        "bancopopular@bancopopularinforma.fi.cr",  # Información general
        "Mercadeo@bancopopularinforma.fi.cr",  # Marketing
        "notificaciones@bancopopular.fi.cr",  # Por si acaso (futuro)
    ]

    GRAPH_API_BASE: ClassVar[str] = "https://graph.microsoft.com/v1.0"

    def __init__(self) -> None:
        """Inicializa el EmailFetcher."""
        self.auth = auth_manager
        logger.info("EmailFetcher inicializado")

    def _is_transaction_email(self, subject: str) -> bool:
        """
        Determina si un correo es de transacción/alerta o marketing.

        Args:
            subject: Asunto del correo

        Returns:
            bool: True si es transacción/alerta, False si es marketing
        """
        subject_lower = subject.lower()

        # Palabras clave que EXCLUYEN el correo (marketing y notificaciones de configuración)
        exclude_keywords = [
            # Marketing
            "promoción",
            "promocion",
            "oferta",
            "descuento",
            "ganate",
            "gánate",
            "premio",
            "sorteo",
            "evento",
            "renueva",
            "buenas noticias",
            "marchamo",
            "pick up",
            "gamer",
            "inscripción de promoción",
            "inscripcion de promocion",
            "presente en su supermercado",
            "doble oportunidad",
            "festejamos",
            # Notificaciones de configuración (no son transacciones de dinero)
            "cambio de pin",
            "cambio de clave",
            "afiliación",
            "afiliacion",
            "desafiliación",
            "desafiliacion",
            "bac credomatic le informa",  # Suelen ser informativos
        ]

        # Si contiene palabras excluidas, rechazar
        if any(keyword in subject_lower for keyword in exclude_keywords):
            return False

        # Palabras clave que INCLUYEN el correo (solo transacciones de dinero)
        transaction_keywords = [
            "notificación de transacción",
            "notificacion de transaccion",
            "notificación de transferencia",
            "notificacion de transferencia",
            "compra",
            "pago",
            "cargo",
            "débito",
            "debito",
            "abono",
            "retiro",
            "depósito",
            "deposito",
            "consumo",
        ]

        # Si contiene palabras de transacción, incluir
        if any(keyword in subject_lower for keyword in transaction_keywords):
            return True

        # Si el remitente es de notificaciones de BAC, es probable que sea transacción
        # Esto se maneja en el filtrado posterior

        return False

    def _get_headers(self) -> dict[str, str]:
        """
        Obtiene los headers necesarios para las requests.

        Returns:
            dict: Headers con autorización

        Raises:
            RuntimeError: Si no se puede obtener el token de acceso
        """
        headers = self.auth.get_authorization_header()
        if not headers:
            raise RuntimeError("No se pudo obtener token de acceso")
        return headers

    def _build_filter_query(
        self,
        days_back: int,
        senders: list[str] | None = None,
    ) -> str:
        """
        Construye el filtro de búsqueda para correos.

        Args:
            days_back: Días hacia atrás para buscar
            senders: Lista de remitentes para filtrar (opcional)

        Returns:
            str: Query filter para Microsoft Graph API
        """
        # Fecha de inicio (días hacia atrás)
        start_date = datetime.now(UTC) - timedelta(days=days_back)
        date_filter = f"receivedDateTime ge {start_date.isoformat()}"

        # Filtro por remitentes
        if senders:
            sender_filters = " or ".join([f"from/emailAddress/address eq '{s}'" for s in senders])
            return f"{date_filter} and ({sender_filters})"

        return date_filter

    @retry_on_network_error(max_attempts=3, max_wait=10)
    def _make_graph_request(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Hace una request a Microsoft Graph API con retry logic.

        Args:
            url: URL del endpoint de Graph API
            params: Parámetros de query (opcional)

        Returns:
            dict: Respuesta JSON de la API

        Raises:
            requests.HTTPError: Si la request falla después de todos los intentos
        """
        headers = self._get_headers()
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch_emails_for_current_user(
        self,
        days_back: int | None = None,
        bank: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Obtiene correos del usuario autenticado actualmente.

        Con cuentas personales de Microsoft (outlook.com, hotmail.com),
        solo se puede acceder a los correos del usuario que inició sesión.

        Args:
            days_back: Días hacia atrás para buscar (default: desde settings)
            bank: Banco específico ('bac', 'popular') o None para ambos

        Returns:
            list: Lista de correos encontrados

        Example:
            >>> fetcher = EmailFetcher()
            >>> emails = fetcher.fetch_emails_for_current_user(days_back=7, bank="bac")
        """
        if days_back is None:
            days_back = settings.email_fetch_days_back

        # Obtener email del usuario autenticado
        user_email = self.auth.get_current_user_email()
        if not user_email:
            logger.error("No hay usuario autenticado")
            return []

        logger.info(
            f"Buscando correos para {user_email} - "
            f"Últimos {days_back} días - Banco: {bank or 'todos'}"
        )

        # Determinar remitentes según el banco
        senders: list[str] = []
        if bank == "bac":
            senders = self.BAC_SENDERS
        elif bank == "popular":
            senders = self.BANCO_POPULAR_SENDERS
        else:
            senders = self.BAC_SENDERS + self.BANCO_POPULAR_SENDERS

        # Construir query
        filter_query = self._build_filter_query(days_back, senders)

        # Endpoint de Microsoft Graph - usar "me" para usuario autenticado
        url = f"{self.GRAPH_API_BASE}/me/messages"

        # Parámetros de la request
        params = {
            "$filter": filter_query,
            "$select": "id,subject,from,receivedDateTime,body,hasAttachments",
            "$orderby": "receivedDateTime desc",
            "$top": settings.email_batch_size,
        }

        try:
            data = self._make_graph_request(url, params)
            all_emails = data.get("value", [])

            # Filtrar solo correos de transacciones y alertas (excluir marketing)
            filtered_emails = []
            marketing_count = 0

            for email in all_emails:
                subject = email.get("subject", "")
                sender = email.get("from", {}).get("emailAddress", {}).get("address", "")

                # Aceptar si es de notificacion@notificacionesbaccr.com
                # (son casi siempre transacciones)
                if sender == "notificacion@notificacionesbaccr.com":
                    if self._is_transaction_email(subject):
                        filtered_emails.append(email)
                    else:
                        marketing_count += 1
                        logger.debug(f"Marketing filtrado: {subject}")
                # Para otros remitentes, ser más estricto con el filtro
                elif self._is_transaction_email(subject):
                    filtered_emails.append(email)
                else:
                    marketing_count += 1
                    logger.debug(f"Marketing/info filtrado: {subject}")

            logger.success(
                f" {len(filtered_emails)} correos de transacciones encontrados "
                f"para {user_email}"
            )
            if marketing_count > 0:
                logger.info(f"📢 {marketing_count} correos de marketing filtrados")

            return filtered_emails

        except Exception as e:
            logger.error(f"Error al obtener correos para {user_email}: {e}")
            return []

    def fetch_all_emails(
        self,
        days_back: int | None = None,
        bank: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Obtiene correos del usuario autenticado actualmente.

        NOTA: Con cuentas personales de Microsoft, solo se puede acceder
        a los correos del usuario que inició sesión. Para ver correos de
        otra cuenta, cierra sesión y vuelve a autenticarte con esa cuenta.

        Args:
            days_back: Días hacia atrás para buscar (default: desde settings)
            bank: Banco específico ('bac', 'popular') o None para ambos

        Returns:
            list: Lista de correos encontrados

        Example:
            >>> fetcher = EmailFetcher()
            >>> emails = fetcher.fetch_all_emails(days_back=30)
            >>> print(f"Total de correos: {len(emails)}")
        """
        logger.info(" Iniciando búsqueda de correos...")

        emails = self.fetch_emails_for_current_user(days_back, bank)

        logger.success(f" Total de correos encontrados: {len(emails)}")

        return emails

    def get_email_body(self, email_id: str) -> str | None:
        """
        Obtiene el cuerpo completo de un correo específico.

        Args:
            email_id: ID del correo

        Returns:
            str | None: Cuerpo del correo en HTML o None si falla
        """
        url = f"{self.GRAPH_API_BASE}/me/messages/{email_id}"

        try:
            data = self._make_graph_request(url)
            body = data.get("body", {})
            return body.get("content", "")

        except requests.exceptions.RequestException as e:
            logger.error(f"Error al obtener cuerpo del correo {email_id}: {e}")
            return None

    def test_connection(self) -> bool:
        """
        Prueba la conexión con Microsoft Graph API.

        Returns:
            bool: True si la conexión es exitosa
        """
        logger.info("🔌 Probando conexión con Microsoft Graph API...")

        try:
            # Intentar obtener el perfil del usuario autenticado
            url = f"{self.GRAPH_API_BASE}/me"
            user_data = self._make_graph_request(url)

            display_name = user_data.get("displayName", "Unknown")
            email = user_data.get("mail") or user_data.get("userPrincipalName", "Unknown")

            logger.success(f" Conexión exitosa - Usuario: {display_name} ({email})")
            return True

        except Exception as e:
            logger.error(f" Error al probar conexión: {e}")
            return False


__all__ = ["EmailFetcher"]
