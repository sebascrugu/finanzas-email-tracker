"""Servicio para procesar transacciones desde correos."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.parsers.bac_parser import BACParser
from finanzas_tracker.parsers.popular_parser import PopularParser
from finanzas_tracker.services.alert_service import alert_service
from finanzas_tracker.services.anomaly_detector import AnomalyDetectionService
from finanzas_tracker.services.categorizer import TransactionCategorizer
from finanzas_tracker.services.exchange_rate import exchange_rate_service
from finanzas_tracker.services.merchant_service import MerchantNormalizationService
from finanzas_tracker.services.subscription_detector import subscription_detector


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

    def __init__(
        self,
        auto_categorize: bool = True,
        detect_anomalies: bool = True,
    ) -> None:
        """
        Inicializa el processor.

        Args:
            auto_categorize: Si debe categorizar automáticamente con IA
            detect_anomalies: Si debe detectar anomalías con ML
        """
        self.bac_parser = BACParser()
        self.popular_parser = PopularParser()
        self.auto_categorize = auto_categorize
        self.detect_anomalies = detect_anomalies
        self.categorizer = TransactionCategorizer() if auto_categorize else None
        self.anomaly_detector = AnomalyDetectionService() if detect_anomalies else None
        self.merchant_service = MerchantNormalizationService()
        logger.info(
            f"TransactionProcessor inicializado "
            f"(auto_categorize={auto_categorize}, detect_anomalies={detect_anomalies})"
        )

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
            "anomalias_detectadas": 0,
        }

        logger.info(f" Procesando {len(emails)} correos...")

        # Auto-entrenar detector de anomalías si es necesario
        if self.detect_anomalies and self.anomaly_detector:
            self._auto_train_anomaly_detector(profile_id)

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

                # Detección de anomalías con ML (después de categorizar)
                if self.detect_anomalies and self.anomaly_detector:
                    self._detect_anomaly(parsed_data, stats)

                # Guardar en base de datos
                success, transaction = self._save_transaction(parsed_data)
                if success:
                    stats["procesados"] += 1

                    # Generar alertas para esta transacción
                    if transaction:
                        try:
                            alerts = alert_service.generate_alerts_for_transaction(
                                transaction, profile_id
                            )
                            if alerts:
                                logger.info(
                                    f"  🔔 {len(alerts)} alerta(s) generada(s) "
                                    f"para {transaction.comercio}"
                                )
                        except Exception as e:
                            logger.warning(f"Error generando alertas: {e}")
                            # No fallar el procesamiento por esto
                else:
                    stats["duplicados"] += 1

            except (KeyError, ValueError) as e:
                logger.error(f"Error de datos en correo '{email.get('subject', 'unknown')}': {e}")
                stats["errores"] += 1
            except Exception as e:
                logger.error(
                    f"Error inesperado procesando correo '{email.get('subject', 'unknown')}': {type(e).__name__}: {e}"
                )
                stats["errores"] += 1

        # Sincronizar suscripciones automáticamente después de procesar
        if stats["procesados"] > 0:  # Solo si se agregaron nuevas transacciones
            try:
                logger.info("\n📋 Actualizando suscripciones recurrentes...")
                sub_stats = subscription_detector.sync_subscriptions_to_db(profile_id)

                if sub_stats["created"] > 0 or sub_stats["updated"] > 0:
                    logger.info(
                        f"✅ Suscripciones: "
                        f"{sub_stats['created']} nuevas, "
                        f"{sub_stats['updated']} actualizadas"
                    )
                    stats["suscripciones_nuevas"] = sub_stats["created"]
                    stats["suscripciones_actualizadas"] = sub_stats["updated"]

            except Exception as e:
                logger.warning(f"⚠️  No se pudieron actualizar suscripciones: {e}")
                # No fallar el procesamiento por esto

        # Generar alertas de suscripciones y presupuesto
        try:
            logger.info("\n🔔 Generando alertas inteligentes...")

            # Alertas de suscripciones próximas (3 días)
            sub_alerts = alert_service.generate_subscription_alerts(profile_id, days_ahead=3)

            # Alertas de presupuesto excedido
            budget_alerts = alert_service.generate_budget_alerts(profile_id)

            # Alertas de comparación mensual (gastos vs mes anterior)
            comparison_alerts = alert_service.generate_monthly_comparison_alerts(profile_id)

            # Alertas de cierre de tarjetas de crédito
            card_alerts = alert_service.generate_credit_card_closing_alerts(profile_id)

            # Alertas de progreso de metas de ahorro
            goal_alerts = alert_service.generate_savings_goal_progress_alerts(profile_id)

            # Alertas de predicciones de gasto mensual
            forecast_alerts = alert_service.generate_spending_forecast_alerts(profile_id)

            # Alertas de predicción de exceso de presupuesto
            budget_forecast_alerts = alert_service.generate_budget_forecast_alerts(profile_id)

            total_alerts = (
                len(sub_alerts)
                + len(budget_alerts)
                + len(comparison_alerts)
                + len(card_alerts)
                + len(goal_alerts)
                + len(forecast_alerts)
                + len(budget_forecast_alerts)
            )
            if total_alerts > 0:
                logger.info(
                    f"✅ Alertas: "
                    f"{len(sub_alerts)} suscripciones, "
                    f"{len(budget_alerts)} presupuesto, "
                    f"{len(comparison_alerts)} comparaciones, "
                    f"{len(card_alerts)} tarjetas, "
                    f"{len(goal_alerts)} metas, "
                    f"{len(forecast_alerts)} predicciones, "
                    f"{len(budget_forecast_alerts)} forecast presupuesto"
                )
                stats["alertas_suscripciones"] = len(sub_alerts)
                stats["alertas_presupuesto"] = len(budget_alerts)
                stats["alertas_comparacion"] = len(comparison_alerts)
                stats["alertas_tarjetas"] = len(card_alerts)
                stats["alertas_metas"] = len(goal_alerts)
                stats["alertas_predicciones"] = len(forecast_alerts)
                stats["alertas_forecast_presupuesto"] = len(budget_forecast_alerts)

        except Exception as e:
            logger.warning(f"⚠️  No se pudieron generar alertas: {e}")
            # No fallar el procesamiento por esto

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
                profile_id=transaction_data.get("profile_id"),
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

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error de datos categorizando transacción: {type(e).__name__}: {e}")
            transaction_data["subcategory_id"] = None
            transaction_data["categoria_sugerida_por_ia"] = None
            transaction_data["necesita_revision"] = True
            stats["necesitan_revision"] += 1
        except Exception as e:
            logger.error(f"Error inesperado categorizando transacción: {type(e).__name__}: {e}")
            transaction_data["subcategory_id"] = None
            transaction_data["categoria_sugerida_por_ia"] = None
            transaction_data["necesita_revision"] = True
            stats["necesitan_revision"] += 1

    def _detect_anomaly(
        self,
        transaction_data: dict[str, Any],
        stats: dict[str, Any],
    ) -> None:
        """
        Detecta si una transacción es anómala usando ML.

        Args:
            transaction_data: Datos de la transacción (se modifica in-place)
            stats: Diccionario de estadísticas (se actualiza)
        """
        try:
            # Crear transacción temporal para detección (no guardar aún)
            temp_transaction = Transaction(**transaction_data)

            # Detectar anomalía
            result = self.anomaly_detector.detect(temp_transaction)

            # Agregar resultado a transaction_data
            transaction_data["is_anomaly"] = result.is_anomaly
            transaction_data["anomaly_score"] = Decimal(str(result.score))
            transaction_data["anomaly_reason"] = result.reason if result.is_anomaly else None

            # Actualizar estadísticas
            if result.is_anomaly:
                stats["anomalias_detectadas"] += 1
                logger.warning(
                    f"⚠️  ANOMALÍA DETECTADA: {transaction_data['comercio']} - "
                    f"₡{transaction_data['monto_crc']:,.0f} | "
                    f"Razón: {result.reason} (confianza: {result.confidence:.1f}%)"
                )
            else:
                logger.debug(
                    f"✓ Normal: {transaction_data['comercio']} "
                    f"(score: {result.score:.4f})"
                )

        except (KeyError, ValueError, TypeError) as e:
            logger.debug(f"Error de datos detectando anomalía: {type(e).__name__}: {e}")
            # No fallar el procesamiento, solo skip detección
            transaction_data["is_anomaly"] = False
            transaction_data["anomaly_score"] = None
            transaction_data["anomaly_reason"] = None
        except Exception as e:
            logger.debug(f"Error inesperado detectando anomalía: {type(e).__name__}: {e}")
            # No fallar el procesamiento
            transaction_data["is_anomaly"] = False
            transaction_data["anomaly_score"] = None
            transaction_data["anomaly_reason"] = None

    def _auto_train_anomaly_detector(self, profile_id: str) -> None:
        """
        Auto-entrena el detector de anomalías si es necesario.

        Condiciones para entrenar:
        1. No existe un modelo entrenado
        2. Hay al menos 30 transacciones en los últimos 6 meses
        3. Hace más de 30 días desde el último entrenamiento

        Args:
            profile_id: ID del perfil
        """
        if not self.anomaly_detector:
            return

        # Chequear si ya hay un modelo entrenado
        if self.anomaly_detector.model is not None:
            # Ya está entrenado, no hacer nada (por ahora)
            # TODO: Implementar re-entrenamiento automático mensual
            return

        # Contar transacciones disponibles
        with get_session() as session:
            six_months_ago = datetime.now() - timedelta(days=180)

            tx_count = (
                session.query(Transaction)
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.fecha_transaccion >= six_months_ago,
                    Transaction.deleted_at.is_(None),
                    Transaction.excluir_de_presupuesto == False,  # noqa: E712
                )
                .count()
            )

        # Si hay suficientes datos, entrenar automáticamente
        if tx_count >= 30:
            logger.info(
                f"\n{'='*70}\n"
                f"🤖 ENTRENAMIENTO AUTOMÁTICO DE DETECTOR DE ANOMALÍAS\n"
                f"{'='*70}\n"
                f"  Detectamos {tx_count} transacciones históricas.\n"
                f"  Entrenando modelo de ML para detectar gastos inusuales...\n"
            )

            try:
                success = self.anomaly_detector.train(profile_id=profile_id, min_transactions=30)

                if success:
                    logger.success(
                        f"  ✅ Modelo entrenado exitosamente!\n"
                        f"  📊 Ahora se detectarán automáticamente transacciones anómalas\n"
                        f"  💡 El modelo aprende de tus patrones de gasto normales\n"
                        f"{'='*70}\n"
                    )
                else:
                    logger.warning(
                        f"  ⚠️  No se pudo entrenar (insuficientes datos)\n" f"{'='*70}\n"
                    )

            except Exception as e:
                logger.error(f"Error entrenando detector de anomalías: {e}")
                logger.info(
                    "  ℹ️  La detección de anomalías estará desactivada por ahora\n"
                    f"{'='*70}\n"
                )
        else:
            logger.info(
                f"  ℹ️  Detección de anomalías desactivada temporalmente\n"
                f"     (necesitas al menos 30 transacciones, tienes {tx_count})\n"
                f"     Se activará automáticamente cuando tengas suficientes datos\n"
            )

    def _save_transaction(self, transaction_data: dict[str, Any]) -> tuple[bool, Transaction | None]:
        """
        Guarda una transacción en la base de datos.

        Args:
            transaction_data: Datos de la transacción

        Returns:
            tuple: (success: bool, transaction: Transaction | None)
                   - True si se guardó exitosamente, False si es duplicada
                   - Transaction object si se guardó, None si es duplicada
        """
        try:
            with get_session() as session:
                # Normalizar el merchant antes de crear la transacción
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

                    logger.debug(
                        f"  Merchant normalizado: '{comercio_raw}' → '{merchant.nombre_normalizado}'"
                    )

                transaction = Transaction(**transaction_data)
                session.add(transaction)
                session.commit()

                # Expunge to use outside session
                session.refresh(transaction)
                session.expunge(transaction)

                logger.debug(
                    f" Transacción guardada: {transaction.comercio} - "
                    f"₡{transaction.monto_crc:,.2f}"
                )
                return (True, transaction)

        except IntegrityError:
            # Ya existe (email_id es único)
            logger.debug(f"  Transacción duplicada (ya existe): {transaction_data['email_id']}")
            return (False, None)

        except (ValueError, TypeError) as e:
            logger.error(f"Error de datos guardando transacción: {type(e).__name__}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error DB guardando transacción: {type(e).__name__}: {e}")
            raise


# Instancia singleton
transaction_processor = TransactionProcessor()
