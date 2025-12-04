"""Servicio para procesar transacciones desde correos."""

from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.parsers.bac_parser import BACParser
from finanzas_tracker.parsers.popular_parser import PopularParser
from finanzas_tracker.services.categorizer import TransactionCategorizer
from finanzas_tracker.services.exchange_rate import exchange_rate_service
from finanzas_tracker.services.merchant_service import MerchantNormalizationService


logger = get_logger(__name__)


class TransactionProcessor:
    """
    Servicio para procesar correos bancarios y convertirlos en transacciones.

    Este servicio:
    1. Identifica el banco del correo
    2. Usa el parser correspondiente
    3. Detecta y convierte moneda USD→CRC
    4. Guarda en la base de datos
    5. Maneja duplicados y errores
    """

    # Mapeo de senders a bancos
    SENDER_TO_BANK = {
        "notificacion@notificacionesbaccr.com": "bac",
        "notificaciones@bacnet.net": "bac",
        "notificaciones@notificacionesbaccr.com": "bac",
        "alerta@baccredomatic.com": "bac",
        "infopersonal@bancopopular.fi.cr": "popular",
        "cajero@bancopopular.fi.cr": "popular",
    }

    def __init__(self, auto_categorize: bool = True) -> None:
        """
        Inicializa el processor.

        Args:
            auto_categorize: Si debe categorizar automáticamente con IA
        """
        self.bac_parser = BACParser()
        self.popular_parser = PopularParser()
        self.auto_categorize = auto_categorize
        self.categorizer = TransactionCategorizer() if auto_categorize else None
        self.merchant_service = MerchantNormalizationService()
        logger.info(f"TransactionProcessor inicializado (auto_categorize={auto_categorize})")

    def process_emails(
        self,
        emails: list[dict[str, Any]],
        profile_id: str,
    ) -> dict[str, Any]:
        """
        Procesa una lista de correos y los convierte en transacciones.

        Args:
            emails: Lista de correos de Microsoft Graph
            profile_id: ID del perfil al que pertenecen las transacciones

        Returns:
            dict: Estadísticas del procesamiento
        """
        stats = {
            "total": len(emails),
            "procesados": 0,
            "duplicados": 0,
            "errores": 0,
            "bac": 0,
            "popular": 0,
            "usd_convertidos": 0,
            "categorizadas_automaticamente": 0,
            "necesitan_revision": 0,
        }

        logger.info(f"Procesando {len(emails)} correos...")

        for email in emails:
            try:
                # Identificar banco
                banco = self._identify_bank(email)
                if not banco:
                    logger.warning(f"No se pudo identificar banco: {email.get('subject')}")
                    stats["errores"] += 1
                    continue

                # Usar el parser correspondiente
                if banco == "bac":
                    parsed_data = self.bac_parser.parse(email)
                    stats["bac"] += 1
                else:
                    parsed_data = self.popular_parser.parse(email)
                    stats["popular"] += 1

                if not parsed_data:
                    logger.warning(f"No se pudo parsear correo: {email.get('subject')}")
                    stats["errores"] += 1
                    continue

                # Agregar perfil
                parsed_data["profile_id"] = profile_id

                # Aplicar conversión de moneda
                if parsed_data["moneda_original"] == "USD":
                    self._apply_currency_conversion(parsed_data)
                    stats["usd_convertidos"] += 1
                else:
                    parsed_data["monto_crc"] = parsed_data["monto_original"]
                    parsed_data["tipo_cambio_usado"] = None

                # Categorización automática con IA
                if self.auto_categorize and self.categorizer:
                    self._categorize_transaction(parsed_data, stats)

                # Guardar en base de datos
                success, _ = self._save_transaction(parsed_data)
                if success:
                    stats["procesados"] += 1
                else:
                    stats["duplicados"] += 1

            except (KeyError, ValueError) as e:
                logger.error(f"Error de datos en correo: {e}")
                stats["errores"] += 1
            except Exception as e:
                logger.error(f"Error procesando correo: {type(e).__name__}: {e}")
                stats["errores"] += 1

        logger.info(
            f"Procesamiento completado: "
            f"{stats['procesados']} nuevas, "
            f"{stats['duplicados']} duplicadas, "
            f"{stats['errores']} errores"
        )

        return stats

    def _identify_bank(self, email: dict[str, Any]) -> str | None:
        """Identifica el banco del correo basándose en el sender."""
        sender = email.get("from", {}).get("emailAddress", {}).get("address", "").lower()

        for sender_pattern, banco in self.SENDER_TO_BANK.items():
            if sender_pattern.lower() in sender:
                return banco

        return None

    def _apply_currency_conversion(self, transaction_data: dict[str, Any]) -> None:
        """Aplica conversión de moneda USD→CRC usando el tipo de cambio histórico."""
        fecha_transaccion = transaction_data["fecha_transaccion"]
        monto_usd = transaction_data["monto_original"]

        if hasattr(fecha_transaccion, "date"):
            fecha_date = fecha_transaccion.date()
        else:
            fecha_date = fecha_transaccion

        tipo_cambio = exchange_rate_service.get_rate(fecha_date)
        monto_crc = Decimal(str(monto_usd)) * Decimal(str(tipo_cambio))

        transaction_data["monto_crc"] = monto_crc
        transaction_data["tipo_cambio_usado"] = Decimal(str(tipo_cambio))

        logger.debug(f"Conversión: ${monto_usd} USD x {tipo_cambio:.2f} = {monto_crc:,.2f} CRC")

    def _categorize_transaction(
        self,
        transaction_data: dict[str, Any],
        stats: dict[str, Any],
    ) -> None:
        """Categoriza una transacción usando IA."""
        try:
            result = self.categorizer.categorize(
                comercio=transaction_data["comercio"],
                monto_crc=float(transaction_data["monto_crc"]),
                tipo_transaccion=transaction_data["tipo_transaccion"],
                profile_id=transaction_data.get("profile_id"),
            )

            transaction_data["subcategory_id"] = result.get("subcategory_id")
            transaction_data["categoria_sugerida_por_ia"] = result.get("categoria_sugerida")
            transaction_data["necesita_revision"] = result.get("necesita_revision", False)

            if result.get("necesita_revision"):
                stats["necesitan_revision"] += 1
            else:
                stats["categorizadas_automaticamente"] += 1

        except Exception as e:
            logger.error(f"Error categorizando transacción: {e}")
            transaction_data["subcategory_id"] = None
            transaction_data["necesita_revision"] = True
            stats["necesitan_revision"] += 1

    def _save_transaction(self, transaction_data: dict[str, Any]) -> tuple[bool, Transaction | None]:
        """Guarda una transacción en la base de datos."""
        try:
            with get_session() as session:
                # Normalizar merchant
                comercio_raw = transaction_data.get("comercio", "")
                ciudad = transaction_data.get("ciudad")
                pais = transaction_data.get("pais", "Costa Rica")

                if comercio_raw:
                    merchant = self.merchant_service.find_or_create_merchant(
                        session=session,
                        raw_name=comercio_raw,
                        ciudad=ciudad,
                        pais=pais,
                    )
                    transaction_data["merchant_id"] = merchant.id

                transaction = Transaction(**transaction_data)
                session.add(transaction)
                session.commit()
                session.refresh(transaction)
                session.expunge(transaction)

                logger.debug(f"Transacción guardada: {transaction.comercio} - {transaction.monto_crc:,.2f}")
                return (True, transaction)

        except IntegrityError:
            logger.debug(f"Transacción duplicada: {transaction_data['email_id']}")
            return (False, None)


# Instancia singleton
transaction_processor = TransactionProcessor()
