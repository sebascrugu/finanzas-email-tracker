"""Servicio para procesar transacciones desde correos."""

from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.parsers.bac_parser import BACParser
from finanzas_tracker.parsers.popular_parser import PopularParser
from finanzas_tracker.services.smart_categorizer import SmartCategorizer
from finanzas_tracker.services.exchange_rate import exchange_rate_service
from finanzas_tracker.services.internal_transfer_detector import InternalTransferDetector
from finanzas_tracker.services.merchant_service import MerchantNormalizationService
from finanzas_tracker.services.merchant_lookup_service import MerchantLookupService


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
        self.categorizer = SmartCategorizer() if auto_categorize else None
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

                # Convert TypedDict to mutable dict for adding extra fields
                transaction_data: dict[str, Any] = dict(parsed_data)

                # Agregar perfil
                transaction_data["profile_id"] = profile_id

                # Aplicar conversión de moneda
                if transaction_data["moneda_original"] == "USD":
                    self._apply_currency_conversion(transaction_data)
                    stats["usd_convertidos"] += 1
                else:
                    transaction_data["monto_crc"] = transaction_data["monto_original"]
                    transaction_data["tipo_cambio_usado"] = None

                # Categorización automática con IA
                if self.auto_categorize and self.categorizer:
                    self._categorize_transaction(transaction_data, stats)

                # Guardar en base de datos
                success, _ = self._save_transaction(transaction_data)
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
        """Categoriza una transacción usando SmartCategorizer (4 capas)."""
        if self.categorizer is None:
            return

        try:
            comercio = transaction_data["comercio"]
            
            # SmartCategorizer retorna CategorizationResult, no dict
            result = self.categorizer.categorize(
                comercio=comercio,
                monto=transaction_data["monto_crc"],
                profile_id=transaction_data.get("profile_id"),
                tipo_transaccion=transaction_data.get("tipo_transaccion"),
            )

            # Usar propiedades del CategorizationResult
            transaction_data["subcategory_id"] = result.subcategory_id
            transaction_data["categoria_sugerida_por_ia"] = result.subcategory_name
            transaction_data["necesita_revision"] = result.needs_review
            transaction_data["confianza_categoria"] = result.confidence

            if result.needs_review:
                stats["necesitan_revision"] += 1
            else:
                stats["categorizadas_automaticamente"] += 1

            logger.debug(
                f"Categorizado: {transaction_data['comercio']} → "
                f"{result.subcategory_name} ({result.source.value}, {result.confidence}%)"
            )

        except Exception as e:
            logger.error(f"Error categorizando transacción: {e}")
            transaction_data["subcategory_id"] = None
            transaction_data["necesita_revision"] = True
            stats["necesitan_revision"] += 1

    def _save_transaction(
        self, transaction_data: dict[str, Any]
    ) -> tuple[bool, Transaction | None]:
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
                    
                    # Si la categorización tuvo baja confianza, intentar con MerchantLookup
                    needs_review = transaction_data.get("necesita_revision", False)
                    confidence = transaction_data.get("confianza_categoria", 0)
                    
                    if needs_review and confidence < 70 and not transaction_data.get("subcategory_id"):
                        try:
                            lookup_service = MerchantLookupService(session)
                            merchant_info = lookup_service.buscar_o_identificar(comercio_raw)
                            
                            if merchant_info and merchant_info.confianza >= 60:
                                # Buscar subcategory_id por nombre
                                from finanzas_tracker.models.category import Subcategory
                                from sqlalchemy import select
                                
                                stmt = select(Subcategory).where(
                                    Subcategory.nombre.ilike(f"%{merchant_info.subcategoria or merchant_info.categoria}%")
                                ).limit(1)
                                subcat = session.execute(stmt).scalar_one_or_none()
                                
                                if subcat:
                                    transaction_data["subcategory_id"] = subcat.id
                                    transaction_data["categoria_sugerida_por_ia"] = subcat.nombre
                                    transaction_data["confianza_categoria"] = merchant_info.confianza
                                    transaction_data["necesita_revision"] = merchant_info.confianza < 70
                                    logger.info(
                                        f"MerchantLookup identificó: {comercio_raw} → {subcat.nombre}"
                                    )
                        except Exception as e:
                            logger.warning(f"MerchantLookup falló para {comercio_raw}: {e}")

                # Extraer campos de metadata para transferencias
                self._extract_transfer_metadata(transaction_data)

                # Eliminar metadata del dict antes de crear Transaction
                # (el modelo no tiene un campo 'metadata')
                transaction_data.pop("metadata", None)

                transaction = Transaction(**transaction_data)
                session.add(transaction)
                session.commit()
                session.refresh(transaction)

                # Detectar transferencias internas (pagos de tarjeta, etc.)
                transfer_detector = InternalTransferDetector(session)
                if transfer_detector.es_transferencia_interna(transaction):
                    transfer_detector.procesar_pago_tarjeta(
                        transaction,
                        transaction.profile_id,
                    )
                    session.refresh(transaction)

                session.expunge(transaction)

                logger.debug(
                    f"Transacción guardada: {transaction.comercio} - {transaction.monto_crc:,.2f}"
                )
                return (True, transaction)

        except IntegrityError:
            logger.debug(f"Transacción duplicada: {transaction_data['email_id']}")
            return (False, None)

    def _extract_transfer_metadata(self, transaction_data: dict[str, Any]) -> None:
        """
        Extrae campos de metadata de transferencias y los asigna a columnas del modelo.
        
        El parser de BAC genera un dict 'metadata' con campos como:
        - beneficiario: quien recibe el dinero
        - concepto: descripción de la transferencia
        - subtipo: sinpe_enviado, transferencia_local, etc.
        - es_transferencia_propia: si es entre cuentas propias
        - necesita_reconciliacion: si la descripción es ambigua
        """
        metadata = transaction_data.get("metadata", {})
        if not metadata:
            return
        
        # Extraer beneficiario
        if "beneficiario" in metadata:
            transaction_data["beneficiario"] = metadata["beneficiario"]
        elif "destinatario" in metadata:  # Compatibilidad con formato anterior
            transaction_data["beneficiario"] = metadata["destinatario"]
        
        # Extraer concepto de transferencia
        if "concepto" in metadata:
            transaction_data["concepto_transferencia"] = metadata["concepto"]
        
        # Extraer subtipo de transacción
        if "subtipo" in metadata:
            transaction_data["subtipo_transaccion"] = metadata["subtipo"]
        
        # Extraer referencia bancaria
        if "referencia" in metadata:
            transaction_data["referencia_banco"] = metadata["referencia"]
        
        # Marcar si es transferencia propia
        if metadata.get("es_transferencia_propia"):
            transaction_data["es_transferencia_interna"] = True
            # Las transferencias propias no deben contar como gasto
            transaction_data["excluir_de_presupuesto"] = True
            transaction_data["tipo_especial"] = "transferencia_propia"
        
        # Marcar si necesita reconciliación
        if metadata.get("necesita_reconciliacion"):
            transaction_data["necesita_reconciliacion_sinpe"] = True
            # También marcar como que necesita revisión general
            transaction_data["necesita_revision"] = True
        
        logger.debug(
            f"Metadata extraído: beneficiario={transaction_data.get('beneficiario')}, "
            f"subtipo={transaction_data.get('subtipo_transaccion')}, "
            f"necesita_reconciliacion={transaction_data.get('necesita_reconciliacion_sinpe')}"
        )


# Instancia singleton
transaction_processor = TransactionProcessor()
