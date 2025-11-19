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
        "alerta@baccredomatic.com": "bac",  # Retiros sin tarjeta y alertas
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

        logger.info(f" Procesando {len(emails)} correos...")

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
                    # Si ya es CRC, no hay conversión
                    parsed_data["monto_crc"] = parsed_data["monto_original"]
                    parsed_data["tipo_cambio_usado"] = None

                # Categorización automática con IA
                if self.auto_categorize and self.categorizer:
                    self._categorize_transaction(parsed_data, stats)

                # Guardar en base de datos
                success = self._save_transaction(parsed_data)
                if success:
                    stats["procesados"] += 1
                else:
                    stats["duplicados"] += 1

            except Exception as e:
                logger.error(f"Error procesando correo: {e}")
                stats["errores"] += 1

        logger.success(
            f" Procesamiento completado: "
            f"{stats['procesados']} nuevas, "
            f"{stats['duplicados']} duplicadas, "
            f"{stats['errores']} errores"
        )

        return stats

    def _identify_bank(self, email: dict[str, Any]) -> str | None:
        """
        Identifica el banco del correo basándose en el sender.

        Args:
            email: Datos del correo

        Returns:
            str | None: 'bac', 'popular' o None
        """
        sender = email.get("from", {}).get("emailAddress", {}).get("address", "").lower()

        for sender_pattern, banco in self.SENDER_TO_BANK.items():
            if sender_pattern.lower() in sender:
                return banco

        return None

    def _apply_currency_conversion(self, transaction_data: dict[str, Any]) -> None:
        """
        Aplica conversión de moneda USD→CRC usando el tipo de cambio histórico.

        Args:
            transaction_data: Datos de la transacción (se modifica in-place)
        """
        fecha_transaccion = transaction_data["fecha_transaccion"]
        monto_usd = transaction_data["monto_original"]

        # Convertir fecha a date si es datetime
        if hasattr(fecha_transaccion, "date"):
            fecha_date = fecha_transaccion.date()
        else:
            fecha_date = fecha_transaccion

        # Obtener tipo de cambio del día
        tipo_cambio = exchange_rate_service.get_rate(fecha_date)

        # Convertir
        monto_crc = Decimal(str(monto_usd)) * Decimal(str(tipo_cambio))

        # Actualizar datos
        transaction_data["monto_crc"] = monto_crc
        transaction_data["tipo_cambio_usado"] = Decimal(str(tipo_cambio))

        logger.debug(
            f" Conversión: ${monto_usd} USD x ₡{tipo_cambio:.2f} = "
            f"₡{monto_crc:,.2f} CRC ({fecha_date})"
        )

    def _categorize_transaction(
        self,
        transaction_data: dict[str, Any],
        stats: dict[str, Any],
    ) -> None:
        """
        Categoriza una transacción usando IA.

        Args:
            transaction_data: Datos de la transacción (se modifica in-place)
            stats: Diccionario de estadísticas (se actualiza)
        """
        try:
            result = self.categorizer.categorize(
                comercio=transaction_data["comercio"],
                monto_crc=float(transaction_data["monto_crc"]),
                tipo_transaccion=transaction_data["tipo_transaccion"],
                user_email=transaction_data.get("user_email"),
            )

            # Agregar resultado a transaction_data
            transaction_data["subcategory_id"] = result.get("subcategory_id")
            transaction_data["categoria_sugerida_por_ia"] = result.get("categoria_sugerida")
            transaction_data["necesita_revision"] = result.get("necesita_revision", False)

            # Actualizar estadísticas
            if result.get("necesita_revision"):
                stats["necesitan_revision"] += 1
                logger.info(
                    f" {transaction_data['comercio']}: "
                    f"Sugerencia: {result.get('categoria_sugerida')} "
                    f"(necesita revisión - confianza: {result.get('confianza')}%)"
                )
            else:
                stats["categorizadas_automaticamente"] += 1
                logger.success(
                    f" {transaction_data['comercio']}: "
                    f"{result.get('categoria_sugerida')} "
                    f"(confianza: {result.get('confianza')}%)"
                )

        except Exception as e:
            logger.error(f"Error categorizando transacción: {e}")
            # En caso de error, marcar para revisión
            transaction_data["subcategory_id"] = None
            transaction_data["categoria_sugerida_por_ia"] = None
            transaction_data["necesita_revision"] = True
            stats["necesitan_revision"] += 1

    def _save_transaction(self, transaction_data: dict[str, Any]) -> bool:
        """
        Guarda una transacción en la base de datos.

        Args:
            transaction_data: Datos de la transacción

        Returns:
            bool: True si se guardó exitosamente, False si es duplicada
        """
        try:
            with get_session() as session:
                transaction = Transaction(**transaction_data)
                session.add(transaction)
                session.commit()

                logger.debug(
                    f" Transacción guardada: {transaction.comercio} - "
                    f"₡{transaction.monto_crc:,.2f}"
                )
                return True

        except IntegrityError:
            # Ya existe (email_id es único)
            logger.debug(f"  Transacción duplicada (ya existe): {transaction_data['email_id']}")
            return False

        except Exception as e:
            logger.error(f"Error guardando transacción: {e}")
            raise


# Instancia singleton
transaction_processor = TransactionProcessor()
