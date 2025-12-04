"""Servicio para procesar y consolidar estados de cuenta de tarjetas de crédito.

Toma las transacciones extraídas del PDF de tarjeta de crédito
y las guarda en la base de datos, creando:
- BillingCycle para el período
- Transactions para cada compra
- Card si no existe
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models import (
    BillingCycle,
    Card,
    Transaction,
)
from finanzas_tracker.models.enums import (
    BankName,
    BillingCycleStatus,
    CardType,
    Currency,
    TransactionType,
)
from finanzas_tracker.parsers.bac_credit_card_parser import (
    BACCreditCardParser,
    CreditCardStatementResult,
    CreditCardTransaction,
)
from finanzas_tracker.services.categorizer import TransactionCategorizer


logger = get_logger(__name__)


@dataclass
class ConsolidationResult:
    """Resultado de la consolidación de un estado de cuenta."""

    success: bool
    card_id: str | None = None
    billing_cycle_id: str | None = None
    transactions_created: int = 0
    transactions_skipped: int = 0  # Duplicados
    transactions_failed: int = 0
    total_compras: Decimal = Decimal("0")
    errors: list[str] | None = None

    @property
    def total_processed(self) -> int:
        """Total de transacciones procesadas."""
        return self.transactions_created + self.transactions_skipped


class CreditCardStatementService:
    """
    Servicio para consolidar estados de cuenta de tarjetas de crédito.

    Flujo:
    1. Recibe PDF parseado (CreditCardStatementResult)
    2. Crea o encuentra la tarjeta
    3. Crea BillingCycle para el período
    4. Crea transacciones (evitando duplicados)
    5. Categoriza automáticamente

    Uso:
        >>> service = CreditCardStatementService()
        >>> result = service.consolidate_statement(pdf_result, profile_id)
        >>> print(f"Creadas {result.transactions_created} transacciones")
    """

    def __init__(self) -> None:
        """Inicializa el servicio."""
        self.parser = BACCreditCardParser()
        self.categorizer = TransactionCategorizer()
        logger.info("CreditCardStatementService inicializado")

    def process_pdf(
        self,
        pdf_path: str | Path,
        profile_id: str,
    ) -> ConsolidationResult:
        """
        Procesa un PDF de tarjeta de crédito y consolida en la BD.

        Args:
            pdf_path: Ruta al archivo PDF
            profile_id: ID del perfil del usuario

        Returns:
            Resultado de la consolidación
        """
        try:
            # Parsear PDF
            logger.info(f"📄 Parseando PDF: {pdf_path}")
            statement_result = self.parser.parse(str(pdf_path))

            # Consolidar
            return self.consolidate_statement(statement_result, profile_id)

        except Exception as e:
            logger.error(f"Error procesando PDF: {e}")
            return ConsolidationResult(
                success=False,
                errors=[str(e)],
            )

    def consolidate_statement(
        self,
        statement: CreditCardStatementResult,
        profile_id: str,
    ) -> ConsolidationResult:
        """
        Consolida un estado de cuenta ya parseado en la base de datos.

        Args:
            statement: Resultado del parser de tarjeta
            profile_id: ID del perfil del usuario

        Returns:
            Resultado de la consolidación
        """
        errors: list[str] = []

        with get_session() as session:
            try:
                # 1. Crear o encontrar tarjeta
                card = self._find_or_create_card(
                    session,
                    profile_id,
                    statement,
                )
                logger.info(f"💳 Tarjeta: {card.marca} ***{card.ultimos_4_digitos}")

                # 2. Crear BillingCycle
                billing_cycle = self._create_billing_cycle(
                    session,
                    card,
                    statement,
                )
                logger.info(f"📅 Ciclo de facturación: {billing_cycle.fecha_corte}")

                # 3. Crear transacciones
                created = 0
                skipped = 0
                failed = 0
                total_compras = Decimal("0")

                for tx in statement.transactions:
                    try:
                        result = self._create_transaction(
                            session,
                            tx,
                            card,
                            billing_cycle,
                            profile_id,
                        )

                        if result == "created":
                            created += 1
                            if tx.tipo == "compra":
                                total_compras += tx.monto_crc or Decimal("0")
                        elif result == "skipped":
                            skipped += 1
                        else:
                            failed += 1

                    except Exception as e:
                        failed += 1
                        errors.append(f"Error en {tx.concepto}: {e}")
                        logger.warning(f"Error creando transacción: {e}")

                # 4. Commit
                session.commit()

                logger.success(
                    f"✅ Consolidación completada: "
                    f"{created} creadas, {skipped} omitidas, {failed} fallidas"
                )

                return ConsolidationResult(
                    success=True,
                    card_id=card.id,
                    billing_cycle_id=billing_cycle.id,
                    transactions_created=created,
                    transactions_skipped=skipped,
                    transactions_failed=failed,
                    total_compras=total_compras,
                    errors=errors if errors else None,
                )

            except Exception as e:
                session.rollback()
                logger.error(f"Error en consolidación: {e}")
                return ConsolidationResult(
                    success=False,
                    errors=[str(e)],
                )

    def _find_or_create_card(
        self,
        session: Session,
        profile_id: str,
        statement: CreditCardStatementResult,
    ) -> Card:
        """Encuentra o crea la tarjeta de crédito."""

        ultimos_4 = statement.metadata.tarjeta_ultimos_4

        # Buscar tarjeta existente
        stmt = select(Card).where(
            Card.profile_id == profile_id,
            Card.ultimos_4_digitos == ultimos_4,
            Card.deleted_at.is_(None),
        )
        existing = session.execute(stmt).scalar_one_or_none()

        if existing:
            # Actualizar información
            if statement.metadata.limite_credito_usd:
                existing.limite_credito = statement.metadata.limite_credito_usd * Decimal(
                    "500"
                )  # Aprox USD→CRC
            existing.fecha_corte = statement.metadata.fecha_corte.day
            existing.updated_at = datetime.now(UTC)
            return existing

        # Crear nueva tarjeta
        marca = self._parse_marca(statement.metadata.tarjeta_marca)

        card = Card(
            id=str(uuid4()),
            profile_id=profile_id,
            ultimos_4_digitos=ultimos_4,
            tipo=CardType.CREDIT,
            banco=BankName.BAC,
            marca=marca,
            limite_credito=statement.metadata.limite_credito_usd * Decimal("500")
            if statement.metadata.limite_credito_usd
            else None,
            fecha_corte=statement.metadata.fecha_corte.day,
            fecha_vencimiento=statement.metadata.fecha_pago_contado.day,
            alias=f"{marca} BAC" if marca else "Tarjeta BAC",
            activa=True,
        )

        session.add(card)
        session.flush()

        logger.info(f"💳 Nueva tarjeta creada: {marca} ***{ultimos_4}")
        return card

    def _create_billing_cycle(
        self,
        session: Session,
        card: Card,
        statement: CreditCardStatementResult,
    ) -> BillingCycle:
        """Crea el ciclo de facturación para este estado."""

        fecha_corte = statement.metadata.fecha_corte

        # Verificar si ya existe
        stmt = select(BillingCycle).where(
            BillingCycle.card_id == card.id,
            BillingCycle.fecha_corte == fecha_corte,
            BillingCycle.deleted_at.is_(None),
        )
        existing = session.execute(stmt).scalar_one_or_none()

        if existing:
            # Actualizar montos
            existing.pago_minimo = statement.metadata.pago_minimo_crc
            existing.total_a_pagar = statement.metadata.pago_contado_crc
            existing.fecha_pago = statement.metadata.fecha_pago_contado
            existing.updated_at = datetime.now(UTC)
            return existing

        # Crear nuevo ciclo
        # Calcular fecha inicio (un mes antes del corte aprox)
        from dateutil.relativedelta import relativedelta

        fecha_inicio = fecha_corte - relativedelta(months=1) + relativedelta(days=1)

        cycle = BillingCycle(
            id=str(uuid4()),
            card_id=card.id,
            fecha_inicio=fecha_inicio,
            fecha_corte=fecha_corte,
            fecha_pago=statement.metadata.fecha_pago_contado,
            pago_minimo=statement.metadata.pago_minimo_crc,
            total_a_pagar=statement.metadata.pago_contado_crc,
            status=BillingCycleStatus.CLOSED,  # Ya está cerrado cuando llega el estado
        )

        session.add(cycle)
        session.flush()

        logger.info(
            f"📅 Nuevo ciclo creado: {fecha_corte} - Pago: ₡{statement.metadata.pago_contado_crc:,.2f}"
        )
        return cycle

    def _create_transaction(
        self,
        session: Session,
        tx: CreditCardTransaction,
        card: Card,
        billing_cycle: BillingCycle,
        profile_id: str,
    ) -> str:
        """
        Crea una transacción en la BD.

        Returns:
            "created", "skipped" (duplicado), o "failed"
        """

        # Generar ID único para detectar duplicados
        # Incluye concepto + monto para hacer único cuando hay múltiples compras en un voucher
        import hashlib

        unique_str = (
            f"{card.id}_{tx.referencia}_{tx.fecha.isoformat()}_{tx.concepto}_{tx.monto_crc}"
        )
        hash_suffix = hashlib.md5(unique_str.encode()).hexdigest()[:8]
        email_id = f"cc_{card.id}_{tx.referencia}_{hash_suffix}"

        # Verificar duplicado
        existing = session.execute(
            select(Transaction).where(Transaction.email_id == email_id)
        ).scalar_one_or_none()

        if existing:
            return "skipped"

        # Determinar tipo según la transacción
        tipo_map = {
            "compra": TransactionType.PURCHASE,
            "pago": TransactionType.SERVICE_PAYMENT,
            "interes": TransactionType.INTEREST_CHARGE,
            "seguro": TransactionType.INSURANCE,
            "cargo": TransactionType.OTHER,
            "nota_credito": TransactionType.ADJUSTMENT,
        }
        tx_type = tipo_map.get(tx.tipo, TransactionType.PURCHASE)

        monto = tx.monto_crc or Decimal("0")
        moneda = Currency.CRC if tx.moneda == "CRC" else Currency.USD

        # Categorizar
        subcategoria = None
        categoria = None
        try:
            categoria_result = self.categorizer.categorize(tx.concepto, monto)
            if categoria_result:
                subcategoria = categoria_result.get("subcategory_id")
                categoria = categoria_result.get("category_name")
        except Exception:
            pass  # Categorización opcional

        # Crear transacción con campos correctos del modelo
        transaction = Transaction(
            id=str(uuid4()),
            profile_id=profile_id,
            card_id=card.id,
            email_id=email_id,
            banco=BankName.BAC,
            tipo_transaccion=tx_type,
            comercio=tx.concepto,
            monto_original=monto,
            moneda_original=moneda,
            monto_crc=monto,
            fecha_transaccion=datetime.combine(tx.fecha, datetime.min.time()).replace(tzinfo=UTC),
            subcategory_id=subcategoria,
            categoria_sugerida_por_ia=categoria,
            notas=f"💳 Importado de estado de cuenta {card.marca} ***{card.ultimos_4_digitos}\nRef: {tx.referencia}",
            confirmada=True,
            necesita_revision=False,
        )

        session.add(transaction)
        return "created"

    def _parse_marca(self, marca_str: str) -> str:
        """Normaliza la marca de la tarjeta."""
        marca_upper = marca_str.upper()

        if "VISA" in marca_upper:
            return "VISA"
        if "MASTER" in marca_upper:
            return "MASTERCARD"
        if "AMEX" in marca_upper or "AMERICAN" in marca_upper:
            return "AMEX"
        return marca_str


# Singleton
credit_card_statement_service = CreditCardStatementService()


__all__ = [
    "CreditCardStatementService",
    "ConsolidationResult",
    "credit_card_statement_service",
]
