"""
Servicio para buscar correos bancarios en Gmail.

Este módulo utiliza Gmail API para buscar y leer correos de bancos
(BAC, Popular) incluyendo estados de cuenta en PDF.
"""

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from googleapiclient.discovery import build

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.services.gmail_auth_manager import gmail_auth_manager


logger = get_logger(__name__)


@dataclass
class GmailMessage:
    """Representa un mensaje de Gmail."""

    id: str
    subject: str
    sender: str
    received_date: datetime
    body_text: str
    body_html: str
    attachments: list[dict]


@dataclass
class GmailStatementEmail:
    """Representa un email con estado de cuenta PDF."""

    message_id: str
    subject: str
    sender: str
    received_date: datetime
    attachment_id: str
    attachment_name: str
    statement_type: str  # "BAC" o "POPULAR"


class GmailEmailFetcher:
    """
    Servicio para obtener correos bancarios de Gmail.

    Busca correos de BAC y Banco Popular, incluyendo
    estados de cuenta en PDF.
    """

    # Remitentes conocidos de bancos
    BAC_SENDERS = [
        "notificaciones@baccredomatic.com",
        "notificaciones@credomatic.com",
        "alertas@bac.net",
        "servicioalcliente@baccredomatic.com",
        "estadodecuenta@baccredomatic.com",
    ]

    POPULAR_SENDERS = [
        "notificaciones@bancopopular.fi.cr",
        "alertas@bancopopular.fi.cr",
        "servicios@bancopopular.fi.cr",
    ]

    def __init__(self) -> None:
        """Inicializa el fetcher de Gmail."""
        self.auth_manager = gmail_auth_manager
        self._service = None

    def _get_service(self):
        """Obtiene el servicio de Gmail API."""
        if self._service is None:
            creds = self.auth_manager.get_credentials()
            if creds:
                self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def fetch_bank_emails(self, days_back: int = 30) -> list[GmailMessage]:
        """
        Busca correos de bancos en Gmail.

        Args:
            days_back: Días hacia atrás para buscar

        Returns:
            Lista de mensajes de Gmail
        """
        service = self._get_service()
        if not service:
            logger.error("No se pudo obtener servicio de Gmail")
            return []

        # Construir query para buscar correos de bancos
        all_senders = self.BAC_SENDERS + self.POPULAR_SENDERS
        sender_query = " OR ".join([f"from:{s}" for s in all_senders])

        after_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
        query = f"({sender_query}) after:{after_date}"

        logger.info(f"Buscando correos bancarios en Gmail (últimos {days_back} días)...")

        messages = []
        try:
            results = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=100)
                .execute()
            )

            message_ids = results.get("messages", [])
            logger.info(f"Encontrados {len(message_ids)} correos bancarios")

            for msg_data in message_ids:
                msg = self._get_message_details(service, msg_data["id"])
                if msg:
                    messages.append(msg)

        except Exception as e:
            logger.error(f"Error buscando correos: {e}")

        return messages

    def fetch_statement_emails(self, days_back: int = 60) -> list[GmailStatementEmail]:
        """
        Busca emails con estados de cuenta PDF en Gmail.

        Args:
            days_back: Días hacia atrás para buscar

        Returns:
            Lista de emails con PDFs de estados de cuenta
        """
        service = self._get_service()
        if not service:
            logger.error("No se pudo obtener servicio de Gmail")
            return []

        # Buscar correos con PDFs de remitentes bancarios
        all_senders = self.BAC_SENDERS + self.POPULAR_SENDERS
        sender_query = " OR ".join([f"from:{s}" for s in all_senders])

        after_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
        query = f"({sender_query}) has:attachment filename:pdf after:{after_date}"

        logger.info(f"Buscando estados de cuenta PDF en Gmail (últimos {days_back} días)...")

        statements = []
        try:
            results = (
                service.users()
                .messages()
                .list(userId="me", q=query, maxResults=50)
                .execute()
            )

            message_ids = results.get("messages", [])
            logger.info(f"Encontrados {len(message_ids)} correos con PDFs")

            for msg_data in message_ids:
                stmt = self._get_statement_from_message(service, msg_data["id"])
                if stmt:
                    statements.append(stmt)

        except Exception as e:
            logger.error(f"Error buscando estados de cuenta: {e}")

        # Ordenar por fecha (más reciente primero)
        statements.sort(key=lambda x: x.received_date, reverse=True)

        return statements

    def _get_message_details(self, service, message_id: str) -> GmailMessage | None:
        """Obtiene detalles de un mensaje."""
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}

            subject = headers.get("Subject", "")
            sender = headers.get("From", "")
            date_str = headers.get("Date", "")

            # Parsear fecha
            try:
                received_date = parsedate_to_datetime(date_str)
            except Exception:
                received_date = datetime.now()

            # Extraer cuerpo
            body_text, body_html = self._extract_body(msg["payload"])

            # Extraer attachments
            attachments = self._extract_attachments(msg["payload"], message_id)

            return GmailMessage(
                id=message_id,
                subject=subject,
                sender=sender,
                received_date=received_date,
                body_text=body_text,
                body_html=body_html,
                attachments=attachments,
            )

        except Exception as e:
            logger.error(f"Error obteniendo mensaje {message_id}: {e}")
            return None

    def _get_statement_from_message(
        self, service, message_id: str
    ) -> GmailStatementEmail | None:
        """Extrae información de estado de cuenta de un mensaje."""
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=message_id, format="full")
                .execute()
            )

            headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}

            subject = headers.get("Subject", "")
            sender = headers.get("From", "").lower()
            date_str = headers.get("Date", "")

            # Parsear fecha
            try:
                received_date = parsedate_to_datetime(date_str)
            except Exception:
                received_date = datetime.now()

            # Determinar tipo de banco
            statement_type = "BAC" if any(s in sender for s in ["bac", "credomatic"]) else "POPULAR"

            # Buscar attachment PDF
            attachments = self._extract_attachments(msg["payload"], message_id)
            pdf_attachment = None

            for att in attachments:
                if att["filename"].lower().endswith(".pdf"):
                    pdf_attachment = att
                    break

            if not pdf_attachment:
                return None

            return GmailStatementEmail(
                message_id=message_id,
                subject=subject,
                sender=sender,
                received_date=received_date,
                attachment_id=pdf_attachment["id"],
                attachment_name=pdf_attachment["filename"],
                statement_type=statement_type,
            )

        except Exception as e:
            logger.error(f"Error procesando mensaje {message_id}: {e}")
            return None

    def _extract_body(self, payload: dict) -> tuple[str, str]:
        """Extrae el cuerpo del mensaje (texto y HTML)."""
        body_text = ""
        body_html = ""

        if "parts" in payload:
            for part in payload["parts"]:
                mime_type = part.get("mimeType", "")

                if mime_type == "text/plain" and "data" in part.get("body", {}):
                    body_text = base64.urlsafe_b64decode(part["body"]["data"]).decode(
                        "utf-8", errors="ignore"
                    )
                elif mime_type == "text/html" and "data" in part.get("body", {}):
                    body_html = base64.urlsafe_b64decode(part["body"]["data"]).decode(
                        "utf-8", errors="ignore"
                    )
                elif "parts" in part:
                    # Recursivo para partes anidadas
                    nested_text, nested_html = self._extract_body(part)
                    if nested_text:
                        body_text = nested_text
                    if nested_html:
                        body_html = nested_html

        elif "body" in payload and "data" in payload["body"]:
            data = base64.urlsafe_b64decode(payload["body"]["data"]).decode(
                "utf-8", errors="ignore"
            )
            if payload.get("mimeType") == "text/html":
                body_html = data
            else:
                body_text = data

        return body_text, body_html

    def _extract_attachments(self, payload: dict, message_id: str) -> list[dict]:
        """Extrae información de los attachments."""
        attachments = []

        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("filename") and part.get("body", {}).get("attachmentId"):
                    attachments.append(
                        {
                            "id": part["body"]["attachmentId"],
                            "filename": part["filename"],
                            "mimeType": part.get("mimeType", ""),
                            "size": part.get("body", {}).get("size", 0),
                        }
                    )
                elif "parts" in part:
                    # Recursivo
                    nested = self._extract_attachments(part, message_id)
                    attachments.extend(nested)

        return attachments

    def download_attachment(self, message_id: str, attachment_id: str) -> bytes | None:
        """
        Descarga un attachment.

        Args:
            message_id: ID del mensaje
            attachment_id: ID del attachment

        Returns:
            bytes del archivo o None si falla
        """
        service = self._get_service()
        if not service:
            return None

        try:
            attachment = (
                service.users()
                .messages()
                .attachments()
                .get(userId="me", messageId=message_id, id=attachment_id)
                .execute()
            )

            data = attachment.get("data", "")
            return base64.urlsafe_b64decode(data)

        except Exception as e:
            logger.error(f"Error descargando attachment: {e}")
            return None


# Instancia singleton
gmail_email_fetcher = GmailEmailFetcher()

__all__ = ["GmailEmailFetcher", "gmail_email_fetcher", "GmailMessage", "GmailStatementEmail"]
