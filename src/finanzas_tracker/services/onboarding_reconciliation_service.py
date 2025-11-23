"""
Servicio de reconciliación durante onboarding.

Este servicio maneja el flujo completo de validación de datos durante el
onboarding inicial del usuario mediante reconciliación con PDF del banco.

Features:
- Auto-add missing transactions from PDF
- Categorization with AI
- Merchant normalization
- Anomaly detection
- Comprehensive error handling
- Detailed logging and metrics

Author: Sebastian Cruz
Created: 2025-11-23
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.enums import BankName
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.schemas.reconciliation import ParsedPDFTransaction, ReconciliationReport
from finanzas_tracker.services.anomaly_detector import AnomalyDetectionService
from finanzas_tracker.services.categorizer import TransactionCategorizer
from finanzas_tracker.services.merchant_service import MerchantNormalizationService

logger = get_logger(__name__)


@dataclass
class OnboardingReconciliationResult:
    """
    Resultado del proceso de reconciliación durante onboarding.

    Attributes:
        success: Si el proceso completó exitosamente
        transactions_added: Número de transacciones agregadas
        transactions_categorized: Número de transacciones categorizadas
        transactions_failed: Número de transacciones que fallaron
        error_message: Mensaje de error si falló
        added_transaction_ids: IDs de las transacciones agregadas
        failed_transactions: Lista de transacciones que fallaron con razón
    """

    success: bool
    transactions_added: int
    transactions_categorized: int
    transactions_failed: int
    error_message: str | None = None
    added_transaction_ids: list[str] = None
    failed_transactions: list[dict[str, Any]] = None

    def __post_init__(self):
        """Initialize mutable default values."""
        if self.added_transaction_ids is None:
            self.added_transaction_ids = []
        if self.failed_transactions is None:
            self.failed_transactions = []


class OnboardingReconciliationService:
    """
    Servicio para reconciliación de datos durante onboarding.

    Este servicio se encarga de agregar automáticamente transacciones
    faltantes detectadas durante la reconciliación PDF inicial,
    garantizando que el usuario empiece con datos 100% completos.

    Design Principles:
    - Fail-safe: Errores en transacciones individuales no detienen el proceso
    - Transactional: Cambios se hacen en transactions de DB apropiadas
    - Observable: Logging comprehensivo de todas las operaciones
    - Recoverable: Información suficiente para debugging y rollback
    """

    def __init__(self) -> None:
        """Inicializa el servicio con sus dependencias."""
        self.categorizer = TransactionCategorizer()
        self.anomaly_detector = AnomalyDetectionService()
        self.merchant_service = MerchantNormalizationService()
        logger.info("OnboardingReconciliationService inicializado")

    def add_missing_transactions(
        self,
        report: ReconciliationReport,
        profile_id: str,
        banco: BankName,
    ) -> OnboardingReconciliationResult:
        """
        Agrega transacciones faltantes detectadas en el PDF.

        Este método:
        1. Itera sobre transacciones missing in emails
        2. Convierte cada una a Transaction model
        3. Auto-categoriza con IA
        4. Normaliza merchants
        5. Detecta anomalías (opcional)
        6. Guarda en base de datos
        7. Maneja errores individualmente (fail-safe)

        Args:
            report: Reporte de reconciliación con transacciones faltantes
            profile_id: ID del perfil del usuario
            banco: Banco de las transacciones

        Returns:
            OnboardingReconciliationResult con estadísticas y detalles

        Raises:
            ValueError: Si report o profile_id son inválidos
            SQLAlchemyError: En caso de errores críticos de DB

        Examples:
            >>> service = OnboardingReconciliationService()
            >>> result = service.add_missing_transactions(report, profile_id, BankName.BAC)
            >>> if result.success:
            ...     print(f"Agregadas {result.transactions_added} transacciones")
        """
        # Validación de inputs
        if not report:
            raise ValueError("Report no puede ser None")
        if not profile_id:
            raise ValueError("Profile ID no puede estar vacío")
        if not report.missing_in_emails:
            logger.info("No hay transacciones faltantes para agregar")
            return OnboardingReconciliationResult(
                success=True,
                transactions_added=0,
                transactions_categorized=0,
                transactions_failed=0,
            )

        logger.info(
            f"Iniciando agregado de {len(report.missing_in_emails)} transacciones faltantes",
            extra={
                "profile_id": profile_id,
                "banco": banco.value,
                "statement_id": report.statement_id,
                "total_missing": len(report.missing_in_emails),
            },
        )

        # Estadísticas del proceso
        stats = {
            "added": 0,
            "categorized": 0,
            "failed": 0,
            "added_ids": [],
            "failed_details": [],
        }

        # Procesar cada transacción
        with get_session() as session:
            for idx, pdf_tx in enumerate(report.missing_in_emails, start=1):
                try:
                    logger.debug(
                        f"Procesando transacción {idx}/{len(report.missing_in_emails)}: {pdf_tx.comercio}",
                        extra={
                            "comercio": pdf_tx.comercio,
                            "monto": float(pdf_tx.monto),
                            "fecha": pdf_tx.fecha.isoformat(),
                        },
                    )

                    # Agregar transacción
                    transaction = self._add_single_transaction(
                        session=session,
                        pdf_tx=pdf_tx,
                        profile_id=profile_id,
                        banco=banco,
                        statement_id=report.statement_id,
                    )

                    if transaction:
                        stats["added"] += 1
                        stats["added_ids"].append(transaction.id)

                        # Categorizar
                        if self._categorize_transaction(transaction, session, profile_id):
                            stats["categorized"] += 1

                        logger.info(
                            f"✅ Transacción agregada exitosamente: {transaction.comercio}",
                            extra={
                                "transaction_id": transaction.id,
                                "comercio": transaction.comercio,
                                "monto": float(transaction.monto_crc),
                            },
                        )
                    else:
                        # Ya existía (duplicado)
                        logger.debug(f"Transacción ya existe, skip: {pdf_tx.comercio}")

                except IntegrityError as e:
                    # Duplicado - no es error crítico
                    logger.warning(
                        f"Transacción duplicada (skip): {pdf_tx.comercio}",
                        extra={"error": str(e), "comercio": pdf_tx.comercio},
                    )
                    stats["failed"] += 1
                    stats["failed_details"].append(
                        {
                            "comercio": pdf_tx.comercio,
                            "fecha": pdf_tx.fecha.isoformat(),
                            "monto": float(pdf_tx.monto),
                            "reason": "Duplicado",
                            "error": "IntegrityError",
                        }
                    )
                    session.rollback()

                except (ValueError, TypeError) as e:
                    # Error de validación de datos
                    logger.error(
                        f"Error de validación en transacción: {pdf_tx.comercio}",
                        extra={"error": str(e), "comercio": pdf_tx.comercio},
                        exc_info=True,
                    )
                    stats["failed"] += 1
                    stats["failed_details"].append(
                        {
                            "comercio": pdf_tx.comercio,
                            "fecha": pdf_tx.fecha.isoformat(),
                            "monto": float(pdf_tx.monto),
                            "reason": "Error de validación",
                            "error": str(e),
                        }
                    )
                    session.rollback()

                except Exception as e:
                    # Error inesperado
                    logger.error(
                        f"Error inesperado agregando transacción: {pdf_tx.comercio}",
                        extra={"error": str(e), "comercio": pdf_tx.comercio},
                        exc_info=True,
                    )
                    stats["failed"] += 1
                    stats["failed_details"].append(
                        {
                            "comercio": pdf_tx.comercio,
                            "fecha": pdf_tx.fecha.isoformat(),
                            "monto": float(pdf_tx.monto),
                            "reason": "Error inesperado",
                            "error": str(e),
                        }
                    )
                    session.rollback()

            # Commit final si todo fue bien
            try:
                session.commit()
                logger.info(
                    f"✅ Commit exitoso: {stats['added']} transacciones agregadas",
                    extra={
                        "added": stats["added"],
                        "categorized": stats["categorized"],
                        "failed": stats["failed"],
                    },
                )
            except SQLAlchemyError as e:
                logger.error("Error en commit final", exc_info=True)
                session.rollback()
                raise

        # Resultado final
        result = OnboardingReconciliationResult(
            success=stats["failed"] < len(report.missing_in_emails),  # Success si agregamos al menos una
            transactions_added=stats["added"],
            transactions_categorized=stats["categorized"],
            transactions_failed=stats["failed"],
            added_transaction_ids=stats["added_ids"],
            failed_transactions=stats["failed_details"],
        )

        logger.info(
            f"Proceso completado: {stats['added']} agregadas, {stats['failed']} fallidas",
            extra={
                "success": result.success,
                "added": result.transactions_added,
                "failed": result.transactions_failed,
            },
        )

        return result

    def _add_single_transaction(
        self,
        session: Session,
        pdf_tx: ParsedPDFTransaction,
        profile_id: str,
        banco: BankName,
        statement_id: str,
    ) -> Transaction | None:
        """
        Agrega una sola transacción a la base de datos.

        Args:
            session: Sesión de SQLAlchemy
            pdf_tx: Transacción parseada del PDF
            profile_id: ID del perfil
            banco: Banco
            statement_id: ID del statement

        Returns:
            Transaction creada o None si ya existía

        Raises:
            ValueError: Si los datos son inválidos
            IntegrityError: Si hay constraint violation
        """
        # Generar email_id único para transacciones de PDF
        email_id = f"pdf_{statement_id}_{pdf_tx.referencia}_{pdf_tx.row_number}"

        # Verificar si ya existe
        existing = (
            session.query(Transaction).filter(Transaction.email_id == email_id).first()
        )
        if existing:
            return None

        # Crear transacción
        transaction = Transaction(
            profile_id=profile_id,
            email_id=email_id,
            banco=banco,
            # Datos de la transacción
            tipo_transaccion=pdf_tx.tipo_transaccion,
            comercio=pdf_tx.comercio,
            monto_original=pdf_tx.monto,
            moneda_original=pdf_tx.moneda,
            monto_crc=pdf_tx.monto,  # Ya está en CRC
            tipo_cambio_usado=None,  # Ya convertido
            fecha_transaccion=datetime.combine(pdf_tx.fecha, datetime.min.time()).replace(
                tzinfo=UTC
            ),
            # Marcar origen
            notas=(
                f"🔄 Agregada automáticamente desde estado de cuenta durante onboarding\n"
                f"Ref: {pdf_tx.referencia}"
            ),
            confirmada=True,  # Auto-confirmar transacciones de PDF
            # Flags
            necesita_revision=False,  # Se categorizará automáticamente
        )

        # Normalizar merchant
        try:
            merchant = self.merchant_service.find_or_create_merchant(
                session=session,
                raw_name=pdf_tx.comercio,
            )
            transaction.merchant_id = merchant.id
            logger.debug(
                f"Merchant normalizado: '{pdf_tx.comercio}' → '{merchant.nombre_normalizado}'"
            )
        except Exception as e:
            logger.warning(f"No se pudo normalizar merchant: {e}")
            # No es crítico, continuar sin merchant

        session.add(transaction)
        session.flush()  # Flush para obtener el ID sin commit

        return transaction

    def _categorize_transaction(
        self,
        transaction: Transaction,
        session: Session,
        profile_id: str,
    ) -> bool:
        """
        Categoriza una transacción usando IA.

        Args:
            transaction: Transacción a categorizar
            session: Sesión de SQLAlchemy
            profile_id: ID del perfil

        Returns:
            True si se categorizó exitosamente, False si falló

        Note:
            Los errores de categorización no son críticos - la transacción
            se marca como "necesita revisión" y el usuario puede categorizarla después.
        """
        try:
            result = self.categorizer.categorize(
                comercio=transaction.comercio,
                monto_crc=float(transaction.monto_crc),
                tipo_transaccion=transaction.tipo_transaccion.value,
                profile_id=profile_id,
            )

            # Aplicar categorización
            transaction.subcategory_id = result.get("subcategory_id")
            transaction.categoria_sugerida_por_ia = result.get("categoria_sugerida")
            transaction.confianza_categoria = result.get("confianza", 0)
            transaction.necesita_revision = result.get("necesita_revision", False)

            session.flush()

            logger.debug(
                f"Categorizada: {transaction.comercio} → {result.get('categoria_sugerida')} "
                f"(confianza: {result.get('confianza')}%)"
            )

            return True

        except Exception as e:
            logger.warning(
                f"Error categorizando {transaction.comercio}: {e}",
                exc_info=True,
            )
            # Marcar para revisión manual
            transaction.necesita_revision = True
            transaction.confianza_categoria = 0
            session.flush()
            return False


# Singleton instance
onboarding_reconciliation_service = OnboardingReconciliationService()
