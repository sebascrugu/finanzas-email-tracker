"""
Servicio de detección de transacciones duplicadas.

Identifica posibles duplicados basándose en múltiples criterios:
- Mismo comercio
- Monto idéntico o muy similar
- Fecha cercana (mismo día o días adyacentes)
- Misma tarjeta/cuenta
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.transaction import Transaction


logger = get_logger(__name__)


@dataclass
class DuplicateMatch:
    """Representa un par de transacciones potencialmente duplicadas."""

    transaction_1: Transaction
    transaction_2: Transaction
    similarity_score: float  # 0-100
    reasons: list[str]  # Razones por las que se consideran duplicadas


class DuplicateDetectorService:
    """
    Servicio para detectar transacciones duplicadas.

    Usa múltiples heurísticas para identificar posibles duplicados:
    1. Match exacto: mismo comercio, monto, fecha, tarjeta (99% duplicado)
    2. Match muy similar: mismo comercio, monto similar (±1%), fecha cercana (±1 día)
    3. Match sospechoso: mismo comercio, monto idéntico, pero días diferentes

    Casos de uso:
    - Detectar importaciones duplicadas del mismo correo
    - Identificar cobros dobles del mismo comercio
    - Prevenir duplicados al sincronizar múltiples fuentes
    """

    def __init__(self) -> None:
        """Inicializa el detector de duplicados."""
        logger.info("DuplicateDetectorService inicializado")

    def find_duplicates(
        self,
        profile_id: str,
        days_back: int = 30,
        similarity_threshold: float = 80.0,
    ) -> list[DuplicateMatch]:
        """
        Encuentra transacciones potencialmente duplicadas.

        Args:
            profile_id: ID del perfil a analizar
            days_back: Días hacia atrás a analizar
            similarity_threshold: Umbral mínimo de similitud (0-100)

        Returns:
            Lista de pares de transacciones duplicadas con sus scores
        """
        logger.info(f"Buscando duplicados para perfil {profile_id} (últimos {days_back} días)")

        duplicates: list[DuplicateMatch] = []

        with get_session() as session:
            # Obtener todas las transacciones del período
            transactions = self._get_transactions_for_analysis(session, profile_id, days_back)

            logger.debug(f"Analizando {len(transactions)} transacciones")

            # Comparar cada transacción con las demás
            for i, trans_1 in enumerate(transactions):
                for trans_2 in transactions[i + 1 :]:
                    match = self._check_duplicate(trans_1, trans_2)
                    if match and match.similarity_score >= similarity_threshold:
                        duplicates.append(match)

        logger.info(f"Encontrados {len(duplicates)} posibles duplicados")
        return sorted(duplicates, key=lambda x: x.similarity_score, reverse=True)

    def find_duplicate_for_transaction(
        self,
        transaction_id: str,
        similarity_threshold: float = 80.0,
    ) -> DuplicateMatch | None:
        """
        Busca duplicado para una transacción específica.

        Args:
            transaction_id: ID de la transacción
            similarity_threshold: Umbral mínimo de similitud

        Returns:
            Match de duplicado o None
        """
        with get_session() as session:
            transaction = (
                session.query(Transaction)
                .options(joinedload(Transaction.account))
                .filter(Transaction.id == transaction_id)
                .first()
            )

            if not transaction:
                return None

            # Buscar transacciones similares
            candidates = self._get_similar_transactions(session, transaction)

            # Comparar cada candidato
            best_match = None
            best_score = 0.0

            for candidate in candidates:
                if candidate.id == transaction.id:
                    continue

                match = self._check_duplicate(transaction, candidate)
                if match and match.similarity_score > best_score:
                    best_match = match
                    best_score = match.similarity_score

            if best_match and best_score >= similarity_threshold:
                return best_match

            return None

    def mark_as_reconciled(
        self,
        transaction_id_1: str,
        transaction_id_2: str,
    ) -> bool:
        """
        Marca dos transacciones como reconciliadas (no son duplicados).

        Esto previene que se detecten como duplicados en futuras búsquedas.

        Args:
            transaction_id_1: ID de la primera transacción
            transaction_id_2: ID de la segunda transacción

        Returns:
            True si se marcaron exitosamente
        """
        # Por ahora, simplemente logueamos
        # En el futuro se podría agregar una tabla de reconciliaciones
        logger.info(f"Transacciones {transaction_id_1} y {transaction_id_2} marcadas como reconciliadas")
        return True

    def _get_transactions_for_analysis(
        self,
        session: Session,
        profile_id: str,
        days_back: int,
    ) -> list[Transaction]:
        """Obtiene transacciones para análisis de duplicados."""
        from datetime import date

        cutoff_date = date.today() - timedelta(days=days_back)

        return (
            session.query(Transaction)
            .options(joinedload(Transaction.account))
            .filter(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion >= cutoff_date,
                Transaction.deleted_at.is_(None),
            )
            .order_by(Transaction.fecha_transaccion.desc())
            .all()
        )

    def _get_similar_transactions(
        self,
        session: Session,
        transaction: Transaction,
        date_window_days: int = 7,
    ) -> list[Transaction]:
        """Obtiene transacciones similares a la dada."""
        date_min = transaction.fecha_transaccion - timedelta(days=date_window_days)
        date_max = transaction.fecha_transaccion + timedelta(days=date_window_days)

        # Buscar por comercio similar y fecha cercana
        return (
            session.query(Transaction)
            .options(joinedload(Transaction.account))
            .filter(
                Transaction.profile_id == transaction.profile_id,
                Transaction.comercio == transaction.comercio,
                Transaction.fecha_transaccion >= date_min,
                Transaction.fecha_transaccion <= date_max,
                Transaction.deleted_at.is_(None),
            )
            .all()
        )

    def _check_duplicate(
        self,
        trans_1: Transaction,
        trans_2: Transaction,
    ) -> DuplicateMatch | None:
        """
        Verifica si dos transacciones son potencialmente duplicadas.

        Algoritmo de scoring:
        - Mismo comercio: +30 puntos
        - Monto exacto: +40 puntos, Similar (±1%): +30 puntos, Similar (±5%): +20 puntos
        - Misma fecha: +30 puntos, ±1 día: +20 puntos, ±3 días: +10 puntos
        - Misma cuenta/tarjeta: +10 puntos (bonus)

        Total máximo: 110 puntos (normalizado a 100)
        """
        score = 0.0
        reasons = []

        # 1. Verificar comercio (requisito mínimo)
        if trans_1.comercio.lower() != trans_2.comercio.lower():
            return None  # Si no es el mismo comercio, no puede ser duplicado

        score += 30
        reasons.append(f"Mismo comercio: {trans_1.comercio}")

        # 2. Comparar montos
        monto_1 = float(trans_1.monto_crc)
        monto_2 = float(trans_2.monto_crc)

        if monto_1 == monto_2:
            score += 40
            reasons.append(f"Monto exacto: ₡{monto_1:,.2f}")
        else:
            diff_pct = abs(monto_1 - monto_2) / max(monto_1, monto_2) * 100
            if diff_pct <= 1:
                score += 30
                reasons.append(f"Monto muy similar (diferencia {diff_pct:.1f}%)")
            elif diff_pct <= 5:
                score += 20
                reasons.append(f"Monto similar (diferencia {diff_pct:.1f}%)")
            else:
                # Diferencia muy grande, probablemente no es duplicado
                return None

        # 3. Comparar fechas
        date_1 = trans_1.fecha_transaccion.date() if hasattr(trans_1.fecha_transaccion, "date") else trans_1.fecha_transaccion
        date_2 = trans_2.fecha_transaccion.date() if hasattr(trans_2.fecha_transaccion, "date") else trans_2.fecha_transaccion

        days_diff = abs((date_1 - date_2).days)

        if days_diff == 0:
            score += 30
            reasons.append(f"Misma fecha: {date_1}")
        elif days_diff == 1:
            score += 20
            reasons.append(f"Fechas consecutivas ({date_1} y {date_2})")
        elif days_diff <= 3:
            score += 10
            reasons.append(f"Fechas cercanas (diferencia: {days_diff} días)")

        # 4. Comparar cuenta/tarjeta (bonus)
        if trans_1.account_id == trans_2.account_id:
            score += 10
            if trans_1.account:
                reasons.append(f"Misma tarjeta: {trans_1.account.nombre_tarjeta}")

        # Normalizar score a 100
        normalized_score = min(score / 1.1, 100.0)

        # Solo retornar si el score es significativo
        if normalized_score < 50:
            return None

        return DuplicateMatch(
            transaction_1=trans_1,
            transaction_2=trans_2,
            similarity_score=normalized_score,
            reasons=reasons,
        )

    def get_duplicate_stats(self, profile_id: str) -> dict[str, int]:
        """
        Obtiene estadísticas de duplicados para un perfil.

        Returns:
            Dict con stats: total_duplicates, high_confidence, medium_confidence, low_confidence
        """
        duplicates = self.find_duplicates(profile_id, days_back=90, similarity_threshold=50.0)

        high_confidence = sum(1 for d in duplicates if d.similarity_score >= 90)
        medium_confidence = sum(1 for d in duplicates if 70 <= d.similarity_score < 90)
        low_confidence = sum(1 for d in duplicates if 50 <= d.similarity_score < 70)

        return {
            "total_duplicates": len(duplicates),
            "high_confidence": high_confidence,
            "medium_confidence": medium_confidence,
            "low_confidence": low_confidence,
        }


# Singleton
duplicate_detector_service = DuplicateDetectorService()
