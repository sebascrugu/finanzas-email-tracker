"""Servicio para procesar estados de cuenta PDF que llegan por correo.

Detecta automáticamente correos con estados de cuenta adjuntos,
descarga los PDFs y los procesa con el parser correspondiente:
- BACCreditCardParser para tarjetas de crédito
- BACPDFParser para cuentas bancarias

Flujo:
1. Buscar correos de BAC con asunto de "estado de cuenta"
2. Descargar PDFs adjuntos
3. Detectar tipo (tarjeta o cuenta) y parsear
4. Crear BillingCycle y transacciones en la BD
5. Notificar que llegó el estado de cuenta
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import tempfile
from typing import TYPE_CHECKING, Any

import requests

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.parsers import BACCreditCardParser, BACPDFParser
from finanzas_tracker.parsers.bac_credit_card_parser import CreditCardStatementResult
from finanzas_tracker.parsers.bac_pdf_parser import BACStatementResult
from finanzas_tracker.services.auth_manager import auth_manager


if TYPE_CHECKING:
    pass


logger = get_logger(__name__)


# Remitentes conocidos de estados de cuenta
STATEMENT_SENDERS = [
    # Estados de cuenta de tarjetas de crédito
    "estadodecuenta@baccredomatic.cr",
    # Estados de cuenta de cuentas bancarias
    "estadosdecuenta@baccredomatic.cr",
    # Facturas electrónicas
    "facturaelectronica@baccredomatic.cr",
    # Otros posibles
    "notificacion@notificacionesbaccr.com",
    "envio@envio.baccredomatic.com",
]

# Remitentes específicos por tipo
CREDIT_CARD_SENDERS = ["estadodecuenta@baccredomatic.cr"]
BANK_ACCOUNT_SENDERS = ["estadosdecuenta@baccredomatic.cr"]

# Palabras clave en asunto para identificar estados de cuenta
STATEMENT_SUBJECT_KEYWORDS = [
    "estado de cuenta",
    "estado cuenta",
    "resumen de cuenta",
    "tu estado de",
    "tarjeta(s) de crédito",
    "cuenta(s) bancaria",
]


@dataclass
class StatementEmailInfo:
    """Información de un correo con estado de cuenta."""

    email_id: str
    subject: str
    sender: str
    received_date: datetime
    attachment_id: str
    attachment_name: str
    attachment_size: int
    statement_type: str = "unknown"  # "credit_card" o "bank_account"


@dataclass
class ProcessedStatement:
    """Resultado del procesamiento de un estado de cuenta."""

    email_info: StatementEmailInfo
    statement_result: BACStatementResult | CreditCardStatementResult | None
    pdf_path: Path | None = None
    saved_to_db: bool = False
    transactions_created: int = 0
    transactions_skipped: int = 0
    error: str | None = None


class StatementEmailService:
    """
    Servicio para detectar y procesar estados de cuenta por correo.

    Uso:
        >>> service = StatementEmailService()
        >>> statements = service.fetch_statement_emails(days_back=30)
        >>> for stmt in statements:
        >>>     result = service.process_statement(stmt)
        >>>     print(f"Procesado: {result.statement_result.metadata.fecha_corte}")
    """

    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(self) -> None:
        """Inicializa el servicio."""
        self.auth = auth_manager
        self.pdf_parser = BACPDFParser()
        self.credit_card_parser = BACCreditCardParser()
        logger.info("StatementEmailService inicializado")

    def _get_headers(self) -> dict[str, str]:
        """Obtiene headers de autorización."""
        headers = self.auth.get_authorization_header()
        if not headers:
            raise RuntimeError("No se pudo obtener token de acceso")
        return headers

    def _is_statement_email(self, subject: str, sender: str) -> bool:
        """
        Determina si un correo es de estado de cuenta.

        Args:
            subject: Asunto del correo
            sender: Email del remitente

        Returns:
            True si es un correo de estado de cuenta
        """
        subject_lower = subject.lower()

        # Verificar palabras clave en asunto
        has_keyword = any(keyword in subject_lower for keyword in STATEMENT_SUBJECT_KEYWORDS)

        # Verificar remitente conocido
        is_known_sender = sender.lower() in [s.lower() for s in STATEMENT_SENDERS]

        return has_keyword or (is_known_sender and "pdf" in subject_lower)

    def _detect_statement_type(self, sender: str, subject: str) -> str:
        """
        Detecta el tipo de estado de cuenta.

        Args:
            sender: Email del remitente
            subject: Asunto del correo

        Returns:
            "credit_card" o "bank_account"
        """
        sender_lower = sender.lower()
        subject_lower = subject.lower()

        # Detectar por remitente específico
        if sender_lower in [s.lower() for s in CREDIT_CARD_SENDERS]:
            return "credit_card"
        if sender_lower in [s.lower() for s in BANK_ACCOUNT_SENDERS]:
            return "bank_account"

        # Detectar por palabras clave en asunto
        if "tarjeta" in subject_lower or "crédito" in subject_lower:
            return "credit_card"
        if "cuenta bancaria" in subject_lower or "ahorro" in subject_lower:
            return "bank_account"

        # Por defecto, asumir tarjeta (más común)
        return "credit_card"

    def fetch_statement_emails(
        self,
        days_back: int = 30,
    ) -> list[StatementEmailInfo]:
        """
        Busca correos con estados de cuenta adjuntos.

        Args:
            days_back: Días hacia atrás para buscar

        Returns:
            Lista de correos con estados de cuenta
        """
        logger.info(f"📧 Buscando estados de cuenta de los últimos {days_back} días...")

        # Buscar correos con attachments de los remitentes conocidos
        from datetime import timedelta

        start_date = datetime.now(UTC) - timedelta(days=days_back)

        # Filtro para correos con adjuntos de BAC
        sender_filters = " or ".join(
            [f"from/emailAddress/address eq '{s}'" for s in STATEMENT_SENDERS]
        )
        filter_query = (
            f"receivedDateTime ge {start_date.isoformat()} "
            f"and hasAttachments eq true "
            f"and ({sender_filters})"
        )

        url = f"{self.GRAPH_API_BASE}/me/messages"
        params = {
            "$filter": filter_query,
            "$select": "id,subject,from,receivedDateTime,hasAttachments",
            "$orderby": "receivedDateTime desc",
            "$top": 50,
        }

        try:
            headers = self._get_headers()
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            emails = data.get("value", [])
            logger.info(f"📬 {len(emails)} correos con adjuntos encontrados")

            # Filtrar por asunto de estado de cuenta y buscar PDFs
            statements: list[StatementEmailInfo] = []

            for email in emails:
                subject = email.get("subject", "")
                sender = email.get("from", {}).get("emailAddress", {}).get("address", "")

                if not self._is_statement_email(subject, sender):
                    continue

                # Detectar tipo de estado de cuenta por remitente
                statement_type = self._detect_statement_type(sender, subject)

                # Buscar adjuntos PDF
                attachments = self._get_email_attachments(email["id"])

                for att in attachments:
                    if att.get("name", "").lower().endswith(".pdf"):
                        stmt_info = StatementEmailInfo(
                            email_id=email["id"],
                            subject=subject,
                            sender=sender,
                            received_date=datetime.fromisoformat(
                                email["receivedDateTime"].replace("Z", "+00:00")
                            ),
                            attachment_id=att["id"],
                            attachment_name=att["name"],
                            attachment_size=att.get("size", 0),
                            statement_type=statement_type,
                        )
                        statements.append(stmt_info)
                        tipo_label = (
                            "💳 Tarjeta" if statement_type == "credit_card" else "🏦 Cuenta"
                        )
                        logger.info(f"  📄 {tipo_label}: {att['name']}")

            logger.success(f"✅ {len(statements)} estados de cuenta encontrados")
            return statements

        except Exception as e:
            logger.error(f"Error buscando estados de cuenta: {e}")
            return []

    def _get_email_attachments(self, email_id: str) -> list[dict[str, Any]]:
        """
        Obtiene lista de adjuntos de un correo.

        Args:
            email_id: ID del correo

        Returns:
            Lista de adjuntos con id, name, size, contentType
        """
        url = f"{self.GRAPH_API_BASE}/me/messages/{email_id}/attachments"
        params = {
            "$select": "id,name,size,contentType",
        }

        try:
            headers = self._get_headers()
            response = requests.get(url, headers=headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json().get("value", [])
        except Exception as e:
            logger.error(f"Error obteniendo adjuntos: {e}")
            return []

    def download_attachment(
        self,
        email_id: str,
        attachment_id: str,
        save_path: Path | None = None,
    ) -> Path | None:
        """
        Descarga un adjunto de un correo.

        Args:
            email_id: ID del correo
            attachment_id: ID del adjunto
            save_path: Ruta donde guardar (opcional, usa temp si no se especifica)

        Returns:
            Path al archivo descargado o None si falla
        """
        url = f"{self.GRAPH_API_BASE}/me/messages/{email_id}/attachments/{attachment_id}"

        try:
            headers = self._get_headers()
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()

            # El contenido viene en base64
            import base64

            content_bytes = base64.b64decode(data.get("contentBytes", ""))

            # Guardar archivo
            if save_path is None:
                # Crear archivo temporal
                fd, temp_path = tempfile.mkstemp(suffix=".pdf")
                save_path = Path(temp_path)

            save_path.write_bytes(content_bytes)
            logger.info(f"📥 PDF descargado: {save_path}")

            return save_path

        except Exception as e:
            logger.error(f"Error descargando adjunto: {e}")
            return None

    def process_statement(
        self,
        stmt_info: StatementEmailInfo,
        profile_id: str | None = None,
        save_pdf: bool = False,
        save_to_db: bool = False,
        output_dir: Path | None = None,
    ) -> ProcessedStatement:
        """
        Procesa un estado de cuenta: descarga PDF, parsea y opcionalmente guarda en BD.

        Detecta automáticamente el tipo (tarjeta o cuenta bancaria)
        y usa el parser apropiado.

        Args:
            stmt_info: Información del correo con el estado
            profile_id: ID del perfil para guardar transacciones (requerido si save_to_db=True)
            save_pdf: Si True, guarda el PDF permanentemente
            save_to_db: Si True, consolida las transacciones en la base de datos
            output_dir: Directorio donde guardar PDFs (default: data/raw/)

        Returns:
            Resultado del procesamiento
        """
        tipo_label = "💳 Tarjeta" if stmt_info.statement_type == "credit_card" else "🏦 Cuenta"
        logger.info(f"🔄 Procesando {tipo_label}: {stmt_info.attachment_name}")

        # Determinar dónde guardar
        if save_pdf:
            if output_dir is None:
                output_dir = Path("data/raw/statements")
            output_dir.mkdir(parents=True, exist_ok=True)

            # Nombre único basado en fecha y tipo
            date_str = stmt_info.received_date.strftime("%Y%m%d")
            prefix = "tarjeta" if stmt_info.statement_type == "credit_card" else "cuenta"
            pdf_path = output_dir / f"estado_{prefix}_{date_str}.pdf"
        else:
            pdf_path = None

        # Descargar PDF
        downloaded_path = self.download_attachment(
            stmt_info.email_id,
            stmt_info.attachment_id,
            pdf_path,
        )

        if not downloaded_path:
            return ProcessedStatement(
                email_info=stmt_info,
                statement_result=None,
                error="No se pudo descargar el PDF",
            )

        try:
            transactions_created = 0
            transactions_skipped = 0
            saved_to_db = False

            # Usar parser según tipo
            if stmt_info.statement_type == "credit_card":
                result = self.credit_card_parser.parse(downloaded_path)
                logger.success(
                    f"✅ Estado de tarjeta procesado: "
                    f"{result.metadata.tarjeta_marca} ***{result.metadata.tarjeta_ultimos_4} - "
                    f"{len(result.transactions)} transacciones"
                )

                # Consolidar en BD si se solicita
                if save_to_db and profile_id:
                    from finanzas_tracker.services.credit_card_statement_service import (
                        CreditCardStatementService,
                    )

                    cc_service = CreditCardStatementService()
                    consolidation = cc_service.consolidate_statement(result, profile_id)

                    if consolidation.success:
                        saved_to_db = True
                        transactions_created = consolidation.transactions_created
                        transactions_skipped = consolidation.transactions_skipped
                        logger.success(
                            f"💾 Consolidado en BD: {transactions_created} creadas, "
                            f"{transactions_skipped} omitidas"
                        )
            else:
                result = self.pdf_parser.parse(downloaded_path)
                logger.success(
                    f"✅ Estado de cuenta procesado: "
                    f"{result.metadata.fecha_corte} - "
                    f"{len(result.transactions)} transacciones"
                )

                # Consolidar cuentas bancarias en BD
                if save_to_db and profile_id:
                    from finanzas_tracker.services.bank_account_statement_service import (
                        BankAccountStatementService,
                    )

                    bank_service = BankAccountStatementService()
                    consolidation = bank_service.consolidate_statement(result, profile_id)

                    if consolidation.success:
                        saved_to_db = True
                        transactions_created = consolidation.transactions_created
                        transactions_skipped = consolidation.transactions_skipped
                        logger.success(
                            f"💾 Consolidado en BD: {transactions_created} creadas, "
                            f"{transactions_skipped} omitidas"
                        )

            # Limpiar archivo temporal si no se guardó permanentemente
            if not save_pdf and downloaded_path.exists():
                downloaded_path.unlink()

            return ProcessedStatement(
                email_info=stmt_info,
                statement_result=result,
                pdf_path=pdf_path if save_pdf else None,
                saved_to_db=saved_to_db,
                transactions_created=transactions_created,
                transactions_skipped=transactions_skipped,
            )

        except Exception as e:
            logger.error(f"Error parseando PDF: {e}")
            return ProcessedStatement(
                email_info=stmt_info,
                statement_result=None,
                error=str(e),
            )

    def process_all_pending(
        self,
        profile_id: str,
        days_back: int = 60,
        save_pdfs: bool = True,
        save_to_db: bool = True,
    ) -> list[ProcessedStatement]:
        """
        Procesa todos los estados de cuenta pendientes y los guarda en la BD.

        Este es el método principal para el onboarding automático:
        1. Busca correos con estados de cuenta de los últimos N días
        2. Descarga y parsea cada PDF
        3. Crea tarjetas/cuentas si no existen
        4. Guarda las transacciones evitando duplicados

        Args:
            profile_id: ID del perfil del usuario (requerido)
            days_back: Días hacia atrás para buscar (default: 60 = ~2 meses)
            save_pdfs: Si True, guarda los PDFs permanentemente
            save_to_db: Si True, consolida transacciones en la BD

        Returns:
            Lista de resultados de procesamiento
        """
        logger.info(f"🚀 Procesando estados de cuenta de los últimos {days_back} días...")

        # Buscar correos
        statements = self.fetch_statement_emails(days_back)

        if not statements:
            logger.info("📭 No hay estados de cuenta nuevos")
            return []

        # Procesar cada uno
        results: list[ProcessedStatement] = []
        total_created = 0
        total_skipped = 0

        for stmt_info in statements:
            result = self.process_statement(
                stmt_info,
                profile_id=profile_id,
                save_pdf=save_pdfs,
                save_to_db=save_to_db,
            )
            results.append(result)

            if result.error is None:
                total_created += result.transactions_created
                total_skipped += result.transactions_skipped

        # Resumen
        successful = sum(1 for r in results if r.error is None)
        failed = len(results) - successful

        logger.success(
            f"📊 Procesamiento completado:\n"
            f"   📄 Estados: {successful} exitosos, {failed} fallidos\n"
            f"   ✅ Transacciones creadas: {total_created}\n"
            f"   ⏭️  Transacciones omitidas: {total_skipped}"
        )

        return results


# Singleton para uso global
statement_email_service = StatementEmailService()


__all__ = [
    "StatementEmailService",
    "StatementEmailInfo",
    "ProcessedStatement",
    "statement_email_service",
]
