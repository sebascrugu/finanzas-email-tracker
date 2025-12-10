"""
Servicio de Reconciliación de Estados de Cuenta.

Compara las transacciones de un nuevo PDF con las ya existentes:
- Identifica transacciones que coinciden
- Detecta transacciones nuevas (solo en PDF, probablemente efectivo)
- Detecta transacciones faltantes (solo en sistema, no en PDF)
- Detecta discrepancias de montos

También persiste reportes de reconciliación en la base de datos.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.models import Transaction
from finanzas_tracker.models.enums import BankName, ReconciliationStatus, TransactionStatus
from finanzas_tracker.models.reconciliation_report import ReconciliationReport


logger = logging.getLogger(__name__)


class MatchStatus(str, Enum):
    """Estado de coincidencia de una transacción."""

    MATCHED = "matched"  # Coincide perfectamente
    AMOUNT_MISMATCH = "amount_mismatch"  # Mismo comercio/fecha, monto diferente
    ONLY_IN_PDF = "only_in_pdf"  # Solo está en el PDF (nueva)
    ONLY_IN_SYSTEM = "only_in_system"  # Solo está en sistema (falta en PDF)


@dataclass
class ReconciliationMatch:
    """Resultado de reconciliación para una transacción."""

    status: MatchStatus
    pdf_transaction: dict | None = None
    system_transaction: Transaction | None = None
    amount_difference: Decimal | None = None
    confidence: float = 1.0  # 0-1, qué tan seguro del match

    def to_dict(self) -> dict[str, Any]:
        """Convierte a diccionario para API/UI."""
        result: dict[str, Any] = {
            "status": self.status.value,
            "confidence": self.confidence,
        }

        if self.pdf_transaction:
            result["pdf"] = {
                "fecha": str(self.pdf_transaction.get("fecha", "")),
                "comercio": self.pdf_transaction.get("comercio", ""),
                "monto": float(self.pdf_transaction.get("monto", 0)),
            }

        if self.system_transaction:
            result["system"] = {
                "id": self.system_transaction.id,
                "fecha": str(self.system_transaction.fecha_transaccion),
                "comercio": self.system_transaction.comercio_original,
                "monto": float(self.system_transaction.monto_original),
            }

        if self.amount_difference:
            result["amount_difference"] = float(self.amount_difference)

        return result


@dataclass
class ReconciliationResult:
    """Resultado en memoria de reconciliación (antes de persistir)."""

    periodo_inicio: date
    periodo_fin: date
    total_pdf: int = 0
    total_system: int = 0
    matched: list[ReconciliationMatch] = field(default_factory=list)
    amount_mismatches: list[ReconciliationMatch] = field(default_factory=list)
    only_in_pdf: list[ReconciliationMatch] = field(default_factory=list)
    only_in_system: list[ReconciliationMatch] = field(default_factory=list)

    @property
    def match_rate(self) -> float:
        """Porcentaje de transacciones que coinciden."""
        if self.total_pdf == 0:
            return 0.0
        return len(self.matched) / self.total_pdf * 100

    @property
    def has_issues(self) -> bool:
        """Indica si hay problemas que revisar."""
        return bool(self.amount_mismatches or self.only_in_pdf or self.only_in_system)

    def to_dict(self) -> dict:
        """Convierte a diccionario para API."""
        return {
            "periodo": {
                "inicio": str(self.periodo_inicio),
                "fin": str(self.periodo_fin),
            },
            "resumen": {
                "total_pdf": self.total_pdf,
                "total_sistema": self.total_system,
                "coinciden": len(self.matched),
                "diferencia_monto": len(self.amount_mismatches),
                "solo_en_pdf": len(self.only_in_pdf),
                "solo_en_sistema": len(self.only_in_system),
                "porcentaje_match": round(self.match_rate, 1),
            },
            "tiene_problemas": self.has_issues,
            "detalles": {
                "matched": [m.to_dict() for m in self.matched[:10]],  # Limitar para no sobrecargar
                "amount_mismatches": [m.to_dict() for m in self.amount_mismatches],
                "only_in_pdf": [m.to_dict() for m in self.only_in_pdf],
                "only_in_system": [m.to_dict() for m in self.only_in_system],
            },
        }


class ReconciliationService:
    """
    Servicio para reconciliar estados de cuenta con transacciones del sistema.

    Flujo:
    1. Usuario sube PDF del mes
    2. Sistema parsea transacciones del PDF
    3. Reconciliamos con transacciones ya existentes
    4. Mostramos reporte de diferencias
    5. Usuario confirma/ajusta
    """

    def __init__(self, db: Session) -> None:
        """Inicializa el servicio."""
        self.db = db

    def reconcile(
        self,
        profile_id: str,
        pdf_transactions: list[dict],
        periodo_inicio: date,
        periodo_fin: date,
        tolerance_days: int = 2,
        tolerance_amount: Decimal = Decimal("100"),
    ) -> ReconciliationResult:
        """
        Reconcilia transacciones del PDF con las del sistema.

        Args:
            profile_id: ID del perfil
            pdf_transactions: Lista de transacciones parseadas del PDF
            periodo_inicio: Fecha inicio del período
            periodo_fin: Fecha fin del período
            tolerance_days: Tolerancia en días para match de fechas
            tolerance_amount: Tolerancia en colones para match de montos

        Returns:
            ReconciliationResult con resultados
        """
        # Obtener transacciones del sistema en el período
        system_txns = self._get_system_transactions(profile_id, periodo_inicio, periodo_fin)

        report = ReconciliationResult(
            periodo_inicio=periodo_inicio,
            periodo_fin=periodo_fin,
            total_pdf=len(pdf_transactions),
            total_system=len(system_txns),
        )

        # Set para trackear transacciones ya matcheadas
        matched_pdf_indices: set[int] = set()
        matched_system_ids: set[str] = set()

        # Intentar matchear cada transacción del PDF
        for i, pdf_tx in enumerate(pdf_transactions):
            best_match = self._find_best_match(
                pdf_tx, system_txns, matched_system_ids, tolerance_days, tolerance_amount
            )

            if best_match:
                sys_tx, confidence, amount_diff = best_match

                if amount_diff and abs(amount_diff) > tolerance_amount:
                    # Monto diferente
                    report.amount_mismatches.append(
                        ReconciliationMatch(
                            status=MatchStatus.AMOUNT_MISMATCH,
                            pdf_transaction=pdf_tx,
                            system_transaction=sys_tx,
                            amount_difference=amount_diff,
                            confidence=confidence,
                        )
                    )
                else:
                    # Match perfecto o dentro de tolerancia
                    report.matched.append(
                        ReconciliationMatch(
                            status=MatchStatus.MATCHED,
                            pdf_transaction=pdf_tx,
                            system_transaction=sys_tx,
                            confidence=confidence,
                        )
                    )

                matched_pdf_indices.add(i)
                matched_system_ids.add(sys_tx.id)
            else:
                # No hay match - transacción solo en PDF
                report.only_in_pdf.append(
                    ReconciliationMatch(
                        status=MatchStatus.ONLY_IN_PDF,
                        pdf_transaction=pdf_tx,
                    )
                )

        # Transacciones del sistema sin match
        for sys_tx in system_txns:
            if sys_tx.id not in matched_system_ids:
                report.only_in_system.append(
                    ReconciliationMatch(
                        status=MatchStatus.ONLY_IN_SYSTEM,
                        system_transaction=sys_tx,
                    )
                )

        logger.info(
            f"Reconciliación completada: {len(report.matched)} matches, "
            f"{len(report.only_in_pdf)} solo PDF, "
            f"{len(report.only_in_system)} solo sistema"
        )

        return report

    def _get_system_transactions(
        self,
        profile_id: str,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> list[Transaction]:
        """Obtiene transacciones del sistema en el período."""
        stmt = (
            select(Transaction)
            .where(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion >= fecha_inicio,
                Transaction.fecha_transaccion <= fecha_fin,
                Transaction.deleted_at.is_(None),
            )
            .order_by(Transaction.fecha_transaccion)
        )

        return list(self.db.execute(stmt).scalars().all())

    def _find_best_match(
        self,
        pdf_tx: dict,
        system_txns: list[Transaction],
        already_matched: set[str],
        tolerance_days: int,
        tolerance_amount: Decimal,
    ) -> tuple[Transaction, float, Decimal | None] | None:
        """
        Encuentra el mejor match para una transacción del PDF.

        Retorna (transacción, confianza, diferencia_monto) o None.
        """
        pdf_fecha = pdf_tx.get("fecha")
        pdf_monto = Decimal(str(pdf_tx.get("monto", 0)))
        pdf_comercio = str(pdf_tx.get("comercio", "")).lower()

        if not pdf_fecha:
            return None

        # Convertir fecha si es string
        if isinstance(pdf_fecha, str):
            pdf_fecha = date.fromisoformat(pdf_fecha)

        best_match = None
        best_score = 0.0
        best_amount_diff = None

        for sys_tx in system_txns:
            if sys_tx.id in already_matched:
                continue

            score = 0.0

            # Comparar fecha (peso: 30%)
            sys_date = sys_tx.fecha_transaccion.date() if isinstance(
                sys_tx.fecha_transaccion, datetime
            ) else sys_tx.fecha_transaccion
            date_diff = abs((sys_date - pdf_fecha).days)
            if date_diff <= tolerance_days:
                date_score = 1.0 - (date_diff / (tolerance_days + 1))
                score += date_score * 0.3

            # Comparar monto (peso: 40%)
            amount_diff = pdf_monto - sys_tx.monto_original
            if abs(amount_diff) <= tolerance_amount:
                amount_score = 1.0 - (float(abs(amount_diff)) / float(tolerance_amount + 1))
                score += amount_score * 0.4
            elif abs(amount_diff) <= tolerance_amount * 5:
                # Match parcial de monto
                score += 0.1

            # Comparar comercio (peso: 30%)
            sys_comercio = (sys_tx.comercio_original or "").lower()
            if pdf_comercio and sys_comercio:
                # Similitud básica
                if pdf_comercio in sys_comercio or sys_comercio in pdf_comercio:
                    score += 0.3
                elif self._comercio_similarity(pdf_comercio, sys_comercio) > 0.5:
                    score += 0.2

            # Actualizar mejor match
            if score > best_score and score > 0.4:  # Umbral mínimo
                best_match = sys_tx
                best_score = score
                best_amount_diff = amount_diff if abs(amount_diff) > Decimal("1") else None

        if best_match:
            return (best_match, best_score, best_amount_diff)
        return None

    def _comercio_similarity(self, a: str, b: str) -> float:
        """Calcula similitud básica entre nombres de comercio."""
        # Similitud simple basada en palabras comunes
        words_a = set(a.split())
        words_b = set(b.split())

        if not words_a or not words_b:
            return 0.0

        common = words_a & words_b
        total = words_a | words_b

        return len(common) / len(total) if total else 0.0

    # =========================================================================
    # Acciones sobre Reconciliación
    # =========================================================================

    def accept_all_matches(
        self,
        report: ReconciliationResult,
    ) -> int:
        """
        Acepta todos los matches perfectos.
        Marca transacciones como reconciliadas.

        Returns:
            Número de transacciones marcadas
        """
        count = 0
        for match in report.matched:
            if match.system_transaction:
                # Podríamos agregar un campo 'reconciled' al modelo
                # Por ahora solo loggeamos
                count += 1

        logger.info(f"Aceptados {count} matches")
        return count

    def import_pdf_only_transactions(
        self,
        profile_id: str,
        transactions: list[ReconciliationMatch],
        default_card_id: str | None = None,
    ) -> list[Transaction]:
        """
        Importa las transacciones que solo están en el PDF.

        Args:
            profile_id: ID del perfil
            transactions: Lista de ReconciliationMatch con solo PDF
            default_card_id: Tarjeta por defecto para asignar

        Returns:
            Lista de transacciones creadas
        """
        created = []

        for match in transactions:
            if match.status != MatchStatus.ONLY_IN_PDF or not match.pdf_transaction:
                continue

            pdf_tx = match.pdf_transaction

            tx = Transaction(
                profile_id=profile_id,
                card_id=default_card_id,
                fecha_transaccion=date.fromisoformat(str(pdf_tx["fecha"]))
                if isinstance(pdf_tx["fecha"], str)
                else pdf_tx["fecha"],
                comercio_original=pdf_tx.get("comercio", "Transacción importada"),
                monto_original=Decimal(str(pdf_tx.get("monto", 0))),
                moneda_original=pdf_tx.get("moneda", "CRC"),
                monto_crc=Decimal(str(pdf_tx.get("monto", 0))),
                # Marcar como importada de PDF
                notas="Importada de estado de cuenta PDF",
            )
            self.db.add(tx)
            created.append(tx)

        if created:
            self.db.commit()
            for tx in created:
                self.db.refresh(tx)

        logger.info(f"Importadas {len(created)} transacciones del PDF")
        return created

    def fix_amount_mismatch(
        self,
        transaction_id: str,
        new_amount: Decimal,
        reason: str = "Corregido según estado de cuenta",
    ) -> Transaction | None:
        """
        Corrige el monto de una transacción con discrepancia.

        Args:
            transaction_id: ID de la transacción
            new_amount: Nuevo monto correcto
            reason: Razón del cambio

        Returns:
            Transacción actualizada
        """
        tx = self.db.get(Transaction, transaction_id)
        if not tx:
            return None

        old_amount = tx.monto_original
        tx.monto_original = new_amount
        tx.monto_crc = new_amount  # Asumir CRC, ajustar si USD
        tx.notas = f"{tx.notas or ''}\n{reason} (antes: ₡{old_amount:,.0f})".strip()

        self.db.commit()
        self.db.refresh(tx)

        logger.info(f"Corregido monto de {transaction_id}: ₡{old_amount:,.0f} → ₡{new_amount:,.0f}")
        return tx

    # =========================================================================
    # Reconciliación desde PDF directo
    # =========================================================================

    def reconcile_from_pdf(
        self,
        profile_id: str,
        pdf_content: bytes,
        banco: BankName = BankName.BAC,
    ) -> ReconciliationResult:
        """
        Reconcilia directamente desde un PDF.

        Args:
            profile_id: ID del perfil
            pdf_content: Contenido del PDF
            banco: Banco del estado de cuenta

        Returns:
            ReconciliationResult
        """
        from pathlib import Path
        import tempfile

        from finanzas_tracker.parsers.bac_pdf_parser import BACPDFParser

        if banco == BankName.BAC:
            parser = BACPDFParser()
            # Guardar bytes en archivo temporal para parsear
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                tmp.write(pdf_content)
                tmp_path = tmp.name

            try:
                result = parser.parse(tmp_path)
            finally:
                Path(tmp_path).unlink()

            if not result:
                raise ValueError("No se pudo parsear el PDF")

            # Convertir transacciones a formato dict para reconciliación
            transactions_dict: list[dict[str, Any]] = [
                {
                    "fecha": tx.fecha,
                    "comercio": tx.concepto,  # BACTransaction uses 'concepto' not 'comercio'
                    "monto": tx.monto,
                    "tipo": tx.tipo,
                }
                for tx in result.transactions
            ]

            # Determinar período basado en fecha de corte
            fecha_corte = result.metadata.fecha_corte
            # Estimar período como el mes que termina en fecha_corte
            fecha_fin = fecha_corte
            fecha_inicio = fecha_corte.replace(day=1)

            return self.reconcile(
                profile_id=profile_id,
                pdf_transactions=transactions_dict,
                periodo_inicio=fecha_inicio,
                periodo_fin=fecha_fin,
            )
        raise ValueError(f"Banco {banco} no soportado para reconciliación")

    # =========================================================================
    # Persistencia de Reportes de Reconciliación
    # =========================================================================

    def guardar_reporte(
        self,
        profile_id: str,
        result: ReconciliationResult,
        banco: str = "BAC",
    ) -> ReconciliationReport:
        """
        Persiste el resultado de reconciliación en la base de datos.

        Args:
            profile_id: ID del perfil.
            result: Resultado de la reconciliación en memoria.
            banco: Nombre del banco.

        Returns:
            ReconciliationReport guardado en DB.
        """
        # Determinar estado basado en resultados
        if not result.amount_mismatches and not result.only_in_pdf and not result.only_in_system:
            estado = ReconciliationStatus.COMPLETADO
        elif result.only_in_pdf or result.only_in_system:
            estado = ReconciliationStatus.CON_DISCREPANCIAS
        else:
            estado = ReconciliationStatus.PENDIENTE

        # Calcular totales
        total_banco = sum(
            Decimal(str(m.pdf_transaction.get("monto", 0)))
            for m in result.matched + result.amount_mismatches + result.only_in_pdf
            if m.pdf_transaction
        )
        total_sistema = sum(
            m.system_transaction.monto_original if m.system_transaction else Decimal("0")
            for m in result.matched + result.amount_mismatches
        )

        # Extraer IDs de transacciones del sistema
        ids_coincidentes = [m.system_transaction.id for m in result.matched if m.system_transaction]
        ids_discrepantes = [
            m.system_transaction.id for m in result.amount_mismatches if m.system_transaction
        ]
        ids_huerfanas = [
            m.system_transaction.id for m in result.only_in_system if m.system_transaction
        ]

        reporte = ReconciliationReport(
            profile_id=profile_id,
            periodo_inicio=result.periodo_inicio,
            periodo_fin=result.periodo_fin,
            banco=banco,
            total_segun_estado_cuenta=total_banco,
            total_segun_sistema=total_sistema,
            diferencia=total_banco - total_sistema,
            transacciones_coincidentes=len(result.matched),
            transacciones_discrepantes=len(result.amount_mismatches),
            transacciones_faltantes=len(result.only_in_pdf),
            transacciones_huerfanas=len(result.only_in_system),
            estado=estado,
            ids_coincidentes=ids_coincidentes,
            ids_discrepantes=ids_discrepantes,
            ids_faltantes=[],  # No tenemos IDs para transacciones solo en PDF
            ids_huerfanas=ids_huerfanas,
        )

        self.db.add(reporte)
        self.db.commit()
        self.db.refresh(reporte)

        logger.info(
            "Reporte de reconciliación guardado: ID %d, estado %s",
            reporte.id,
            estado.value,
        )

        return reporte

    def marcar_transacciones_reconciliadas(
        self,
        reporte_id: str,
        transaction_ids: list[str],
    ) -> int:
        """
        Marca transacciones como reconciliadas.

        Args:
            reporte_id: ID del reporte de reconciliación.
            transaction_ids: IDs de transacciones a marcar.

        Returns:
            Número de transacciones actualizadas.
        """
        if not transaction_ids:
            return 0

        ahora = datetime.utcnow()
        count = 0

        for txn_id in transaction_ids:
            stmt = select(Transaction).where(Transaction.id == txn_id)
            txn = self.db.execute(stmt).scalar_one_or_none()

            if txn and hasattr(txn, "estado"):
                txn.estado = TransactionStatus.RECONCILED
                txn.reconciliacion_id = reporte_id
                txn.reconciliada_en = ahora
                count += 1

        self.db.commit()
        logger.info(
            "Marcadas %d transacciones como reconciliadas (reporte %d)",
            count,
            reporte_id,
        )

        return count

    def get_reportes(
        self,
        profile_id: str,
        limite: int = 10,
    ) -> list[ReconciliationReport]:
        """
        Obtiene reportes de reconciliación recientes.

        Args:
            profile_id: ID del perfil.
            limite: Máximo de reportes a retornar.

        Returns:
            Lista de reportes ordenados por fecha descendente.
        """
        stmt = (
            select(ReconciliationReport)
            .where(
                ReconciliationReport.profile_id == profile_id,
                ReconciliationReport.deleted_at.is_(None),
            )
            .order_by(ReconciliationReport.created_at.desc())
            .limit(limite)
        )

        return list(self.db.execute(stmt).scalars().all())

    def get_reporte(
        self,
        reporte_id: str,
    ) -> ReconciliationReport | None:
        """
        Obtiene un reporte específico por ID.

        Args:
            reporte_id: ID del reporte (UUID string).

        Returns:
            ReconciliationReport o None si no existe.
        """
        stmt = select(ReconciliationReport).where(
            ReconciliationReport.id == reporte_id,
            ReconciliationReport.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def resolver_discrepancia(
        self,
        reporte_id: str,
        transaction_id: str,
        accion: str,
        monto_ajustado: Decimal | None = None,
        razon: str | None = None,
    ) -> Transaction:
        """
        Resuelve una discrepancia de monto.

        Args:
            reporte_id: ID del reporte de reconciliación.
            transaction_id: ID de la transacción a ajustar.
            accion: "ajustar_monto", "confirmar", "cancelar"
            monto_ajustado: Nuevo monto si acción es ajustar.
            razon: Razón del ajuste.

        Returns:
            Transaction actualizada.

        Raises:
            ValueError: Si la acción no es válida.
        """
        stmt = select(Transaction).where(Transaction.id == transaction_id)
        txn = self.db.execute(stmt).scalar_one_or_none()

        if not txn:
            raise ValueError(f"Transacción {transaction_id} no encontrada")

        if accion == "ajustar_monto":
            if monto_ajustado is None:
                raise ValueError("monto_ajustado es requerido para ajustar")

            # Guardar monto original si tiene los campos
            if hasattr(txn, "monto_original_estimado"):
                txn.monto_original_estimado = txn.monto_original
                txn.monto_ajustado = monto_ajustado
            txn.monto_original = monto_ajustado
            txn.monto_crc = monto_ajustado

            if hasattr(txn, "razon_ajuste"):
                txn.razon_ajuste = razon or "Ajuste por reconciliación"
            if hasattr(txn, "estado"):
                txn.estado = TransactionStatus.RECONCILED
                txn.reconciliacion_id = reporte_id
                txn.reconciliada_en = datetime.utcnow()

        elif accion == "confirmar":
            if hasattr(txn, "estado"):
                txn.estado = TransactionStatus.CONFIRMED
                txn.reconciliacion_id = reporte_id
                txn.reconciliada_en = datetime.utcnow()

        elif accion == "cancelar":
            if hasattr(txn, "estado"):
                txn.estado = TransactionStatus.CANCELLED
            if hasattr(txn, "razon_ajuste"):
                txn.razon_ajuste = razon or "Cancelada durante reconciliación"

        else:
            raise ValueError(f"Acción no válida: {accion}")

        self.db.commit()
        self.db.refresh(txn)

        logger.info(
            "Discrepancia resuelta: txn %d, acción %s",
            transaction_id,
            accion,
        )

        return txn
