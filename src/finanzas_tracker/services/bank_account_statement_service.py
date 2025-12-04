"""Servicio para procesar y consolidar estados de cuenta bancarias.

Toma las transacciones extraídas del PDF de cuenta bancaria BAC
y las guarda en la base de datos como transacciones.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import hashlib
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models import Transaction
from finanzas_tracker.models.enums import (
    BankName,
    Currency,
    TransactionType,
)
from finanzas_tracker.parsers.bac_pdf_parser import (
    BACPDFParser,
    BACStatementResult,
    BACTransaction,
)
from finanzas_tracker.services.categorizer import TransactionCategorizer
from finanzas_tracker.services.exchange_rate import ExchangeRateService


logger = get_logger(__name__)


@dataclass
class BankConsolidationResult:
    """Resultado de la consolidación de un estado de cuenta bancaria."""

    success: bool
    statement_date: str | None = None
    transactions_created: int = 0
    transactions_skipped: int = 0  # Duplicados
    transactions_failed: int = 0
    total_debitos: Decimal = Decimal("0")
    total_creditos: Decimal = Decimal("0")
    errors: list[str] | None = None

    @property
    def total_processed(self) -> int:
        """Total de transacciones procesadas."""
        return self.transactions_created + self.transactions_skipped


class BankAccountStatementService:
    """
    Servicio para consolidar estados de cuenta bancarias.

    Flujo:
    1. Recibe PDF parseado (BACStatementResult)
    2. Crea transacciones (evitando duplicados)
    3. Categoriza automáticamente

    Uso:
        >>> service = BankAccountStatementService()
        >>> result = service.consolidate_statement(pdf_result, profile_id)
        >>> print(f"Creadas {result.transactions_created} transacciones")
    """

    def __init__(self) -> None:
        """Inicializa el servicio."""
        self.parser = BACPDFParser()
        self.categorizer = TransactionCategorizer()
        self.exchange_rate_service = ExchangeRateService()
        logger.info("BankAccountStatementService inicializado")

    def process_pdf(
        self,
        pdf_path: str | Path,
        profile_id: str,
    ) -> BankConsolidationResult:
        """
        Procesa un PDF de cuenta bancaria y consolida en la BD.

        Args:
            pdf_path: Ruta al archivo PDF
            profile_id: ID del perfil del usuario

        Returns:
            Resultado de la consolidación
        """
        try:
            # Parsear PDF
            logger.info(f"📄 Parseando PDF de cuenta: {pdf_path}")
            statement_result = self.parser.parse(str(pdf_path))

            # Consolidar
            return self.consolidate_statement(statement_result, profile_id)

        except Exception as e:
            logger.error(f"Error procesando PDF: {e}")
            return BankConsolidationResult(
                success=False,
                errors=[str(e)],
            )

    def consolidate_statement(
        self,
        statement: BACStatementResult,
        profile_id: str,
    ) -> BankConsolidationResult:
        """
        Consolida un estado de cuenta ya parseado en la base de datos.

        Args:
            statement: Resultado del parser de cuenta bancaria
            profile_id: ID del perfil del usuario

        Returns:
            Resultado de la consolidación
        """
        errors: list[str] = []

        with get_session() as session:
            try:
                fecha_corte = statement.metadata.fecha_corte
                logger.info(f"🏦 Procesando estado de cuenta: {fecha_corte}")
                logger.info(f"📊 {len(statement.transactions)} transacciones a procesar")

                # Crear transacciones
                created = 0
                skipped = 0
                failed = 0
                total_debitos = Decimal("0")
                total_creditos = Decimal("0")

                for tx in statement.transactions:
                    try:
                        result = self._create_transaction(
                            session,
                            tx,
                            profile_id,
                        )

                        if result == "created":
                            created += 1
                            if tx.tipo == "debito":
                                total_debitos += tx.monto
                            else:
                                total_creditos += tx.monto
                        elif result == "skipped":
                            skipped += 1
                        else:
                            failed += 1

                    except Exception as e:
                        failed += 1
                        errors.append(f"Error en {tx.concepto}: {e}")

                session.commit()

                logger.success(
                    f"✅ Consolidación completada: {created} creadas, "
                    f"{skipped} omitidas, {failed} fallidas"
                )

                return BankConsolidationResult(
                    success=True,
                    statement_date=str(fecha_corte),
                    transactions_created=created,
                    transactions_skipped=skipped,
                    transactions_failed=failed,
                    total_debitos=total_debitos,
                    total_creditos=total_creditos,
                    errors=errors if errors else None,
                )

            except Exception as e:
                logger.error(f"Error en consolidación: {e}")
                session.rollback()
                return BankConsolidationResult(
                    success=False,
                    errors=[str(e)],
                )

    def _create_transaction(
        self,
        session: Session,
        tx: BACTransaction,
        profile_id: str,
    ) -> str:
        """
        Crea una transacción en la BD.

        Returns:
            "created", "skipped" (duplicado), o "failed"
        """

        # Generar ID único para detectar duplicados
        # Incluye referencia + fecha + concepto + monto para ser único
        unique_str = (
            f"bank_{tx.cuenta_iban}_{tx.referencia}_{tx.fecha.isoformat()}_{tx.concepto}_{tx.monto}"
        )
        hash_suffix = hashlib.md5(unique_str.encode()).hexdigest()[:8]
        email_id = f"bank_{tx.referencia}_{hash_suffix}"

        # Verificar duplicado
        existing = session.execute(
            select(Transaction).where(Transaction.email_id == email_id)
        ).scalar_one_or_none()

        if existing:
            return "skipped"

        # Determinar tipo de transacción
        if tx.tipo == "debito":
            if tx.es_transferencia or tx.es_sinpe:
                tipo_transaccion = TransactionType.TRANSFER
            else:
                tipo_transaccion = TransactionType.PURCHASE
        elif tx.es_transferencia or tx.es_sinpe:
            tipo_transaccion = TransactionType.TRANSFER
        elif tx.es_interes:
            tipo_transaccion = TransactionType.INTEREST_EARNED
        else:
            tipo_transaccion = TransactionType.DEPOSIT

        # Determinar moneda
        moneda = Currency.USD if tx.moneda == "USD" else Currency.CRC

        # Calcular monto_crc: si es USD, convertir usando tipo de cambio
        tipo_cambio_usado: Decimal | None = None
        if moneda == Currency.USD:
            rate = self.exchange_rate_service.get_rate(tx.fecha)
            tipo_cambio_usado = Decimal(str(rate))
            monto_crc = abs(tx.monto) * tipo_cambio_usado
        else:
            monto_crc = abs(tx.monto)

        # Crear transacción
        transaction = Transaction(
            id=str(uuid4()),
            email_id=email_id,
            profile_id=profile_id,
            banco=BankName.BAC,
            tipo_transaccion=tipo_transaccion,
            comercio=tx.comercio_normalizado or tx.concepto[:100],
            monto_original=abs(tx.monto),
            moneda_original=moneda,
            monto_crc=monto_crc,
            tipo_cambio_usado=tipo_cambio_usado,
            fecha_transaccion=datetime(
                tx.fecha.year,
                tx.fecha.month,
                tx.fecha.day,
                tzinfo=UTC,
            ),
            # Flags
            es_desconocida=False,
            necesita_revision=False,
            es_comercio_ambiguo=False,
            confirmada=True,
            confianza_categoria=100,
            # Notas con contexto
            notas=(
                f"🏦 Importado de estado de cuenta BAC\n"
                f"Ref: {tx.referencia}\n"
                f"IBAN: {tx.cuenta_iban[-8:]}"
            ),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add(transaction)
        return "created"


# Singleton para uso global
bank_account_service = BankAccountStatementService()


__all__ = [
    "BankAccountStatementService",
    "BankConsolidationResult",
    "bank_account_service",
]
