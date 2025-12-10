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
from finanzas_tracker.services.smart_categorizer import SmartCategorizer
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
        self.categorizer = SmartCategorizer()
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

                # Categorizar transacciones creadas automáticamente
                if created > 0:
                    logger.info(f"🏷️ Categorizando {created} transacciones...")
                    categorized = self._categorize_uncategorized(session, profile_id)
                    logger.info(f"✅ {categorized} transacciones categorizadas")
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

        # Determinar tipo de transacción y flags especiales
        excluir_de_presupuesto = False
        necesita_reconciliacion_sinpe = False
        es_ingreso = False
        
        if tx.tipo == "debito":
            if tx.es_transferencia or tx.es_sinpe:
                tipo_transaccion = TransactionType.TRANSFER
                # SINPE salientes necesitan reconciliación si no tienen beneficiario claro
                if tx.es_sinpe and self._necesita_reconciliacion(tx):
                    necesita_reconciliacion_sinpe = True
            else:
                tipo_transaccion = TransactionType.PURCHASE
        elif tx.es_transferencia or tx.es_sinpe:
            # Transferencia entrante
            tipo_transaccion = TransactionType.TRANSFER
            excluir_de_presupuesto = True  # No afecta presupuesto
        elif tx.es_interes:
            tipo_transaccion = TransactionType.INTEREST_EARNED
            excluir_de_presupuesto = True  # Intereses no son gastos
            es_ingreso = True
        elif self._es_salario(tx):
            # Depósitos de salario
            tipo_transaccion = TransactionType.DEPOSIT
            excluir_de_presupuesto = True
            es_ingreso = True
        else:
            tipo_transaccion = TransactionType.DEPOSIT
            excluir_de_presupuesto = True
            es_ingreso = True

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
            # IMPORTANTE: Guardar a mediodía UTC para evitar desfase de timezone
            # Costa Rica es UTC-6, si guardamos 00:00 UTC, al convertir queda en el día anterior
            fecha_transaccion=datetime(
                tx.fecha.year,
                tx.fecha.month,
                tx.fecha.day,
                12, 0, 0,  # Mediodía para evitar problemas de timezone
                tzinfo=UTC,
            ),
            # Flags
            es_desconocida=False,
            necesita_revision=False,
            es_comercio_ambiguo=False,
            confirmada=True,
            confianza_categoria=100,
            excluir_de_presupuesto=excluir_de_presupuesto,
            necesita_reconciliacion_sinpe=necesita_reconciliacion_sinpe,
            # Notas con contexto
            notas=(
                f"🏦 Importado de estado de cuenta BAC\n"
                f"Ref: {tx.referencia}\n"
                f"IBAN: {tx.cuenta_iban[-8:]}"
                + (f"\n💰 Ingreso detectado" if es_ingreso else "")
            ),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        session.add(transaction)
        return "created"

    def _necesita_reconciliacion(self, tx: BACTransaction) -> bool:
        """
        Determina si una transacción SINPE necesita reconciliación.
        
        Retorna True si:
        - El comercio es solo un número de referencia
        - No tiene beneficiario claro
        - Tiene descripción genérica
        """
        comercio = tx.comercio_normalizado or tx.concepto
        
        # Si es solo números, es una referencia bancaria
        if comercio.replace(" ", "").isdigit():
            return True
        
        # Descripciones genéricas
        genericos = [
            "sin_descripcion",
            "transferencia",
            "sinpe movil",
            "pago sinpe",
        ]
        comercio_lower = comercio.lower()
        for gen in genericos:
            if gen in comercio_lower:
                return True
        
        return False

    def _es_salario(self, tx: BACTransaction) -> bool:
        """
        Determina si una transacción es un depósito de salario.
        """
        concepto_lower = (tx.concepto or "").lower()
        comercio_lower = (tx.comercio_normalizado or "").lower()
        
        indicadores_salario = [
            "salario",
            "nomina",
            "payroll",
            "planilla",
            "bosch",  # Empleador conocido
            "robert bosch",
        ]
        
        for indicador in indicadores_salario:
            if indicador in concepto_lower or indicador in comercio_lower:
                return True
        
        return False

    def _categorize_uncategorized(
        self,
        session: Session,
        profile_id: str,
    ) -> int:
        """
        Categoriza transacciones sin categoría del perfil.
        
        Returns:
            Número de transacciones categorizadas
        """
        from finanzas_tracker.models.enums import TransactionType
        
        # Obtener transacciones sin categoría
        stmt = select(Transaction).where(
            Transaction.profile_id == profile_id,
            Transaction.subcategory_id.is_(None),
            Transaction.deleted_at.is_(None),
            # Solo gastos (no depósitos/intereses)
            Transaction.tipo_transaccion.in_([
                TransactionType.PURCHASE,
                TransactionType.TRANSFER,
            ]),
            Transaction.excluir_de_presupuesto == False,  # noqa: E712
        )
        
        transactions = list(session.execute(stmt).scalars())
        categorized = 0
        
        for tx in transactions:
            try:
                result = self.categorizer.categorize(
                    comercio=tx.comercio,
                    monto=tx.monto_crc,
                    profile_id=profile_id,
                )
                if result.subcategory_id:
                    tx.subcategory_id = result.subcategory_id
                    # confidence ya viene 0-100, no multiplicar
                    tx.confianza_categoria = min(result.confidence, 100)
                    categorized += 1
            except Exception as e:
                logger.warning(f"Error categorizando {tx.comercio}: {e}")
        
        return categorized


# Singleton para uso global
bank_account_service = BankAccountStatementService()


__all__ = [
    "BankAccountStatementService",
    "BankConsolidationResult",
    "bank_account_service",
]
