"""Servicio de detección automática de suscripciones recurrentes."""

__all__ = ["SubscriptionDetectorService", "DetectionResult"]

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.subscription import Subscription
from finanzas_tracker.models.transaction import Transaction


logger = get_logger(__name__)


@dataclass
class DetectionResult:
    """Resultado de detección de suscripción."""

    comercio: str
    merchant_id: str | None
    monto_promedio: Decimal
    monto_min: Decimal
    monto_max: Decimal
    frecuencia_dias: int
    primera_fecha: date
    ultima_fecha: date
    occurrences: int
    confidence: Decimal
    subscription_id: str | None = None  # Si ya existe


class SubscriptionDetectorService:
    """
    Servicio para detectar suscripciones recurrentes automáticamente.

    Detecta patrones como:
    - Netflix: ₡5,500 cada 30 días
    - Spotify: ₡3,900 cada 30 días
    - Gimnasio: ₡15,000 cada 30 días
    - Amazon Prime: $14.99 cada 30 días

    Algoritmo:
    1. Agrupa transacciones por comercio
    2. Para cada grupo, busca patrones de recurrencia
    3. Calcula intervalos entre transacciones
    4. Si los intervalos son consistentes (~30 días ±5) y montos similares (±10%)
       → Es una suscripción
    5. Calcula confidence score basado en consistencia
    """

    def __init__(
        self,
        min_occurrences: int = 2,  # Mínimo 2 cobros para detectar patrón
        monto_tolerance_pct: Decimal = Decimal("10"),  # ±10% de variación en monto
        frecuencia_tolerance_days: int = 5,  # ±5 días de variación en frecuencia
    ) -> None:
        """
        Inicializa el detector de suscripciones.

        Args:
            min_occurrences: Mínimo de ocurrencias para considerar suscripción
            monto_tolerance_pct: Porcentaje de tolerancia en variación de monto (%)
            frecuencia_tolerance_days: Tolerancia en días para variación de frecuencia
        """
        self.min_occurrences = min_occurrences
        self.monto_tolerance_pct = monto_tolerance_pct
        self.frecuencia_tolerance_days = frecuencia_tolerance_days
        logger.info("SubscriptionDetectorService inicializado")

    def detect_all_subscriptions(self, profile_id: str, months_back: int = 6) -> list[DetectionResult]:
        """
        Detecta TODAS las suscripciones en el historial de un perfil.

        Args:
            profile_id: ID del perfil
            months_back: Cuántos meses atrás analizar (default: 6)

        Returns:
            Lista de suscripciones detectadas
        """
        logger.info(f"Detectando suscripciones para perfil {profile_id[:8]}...")

        with get_session() as session:
            # Obtener transacciones de los últimos N meses
            date_limit = date.today() - timedelta(days=30 * months_back)

            transactions = (
                session.query(Transaction)
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.fecha_transaccion >= date_limit,
                    Transaction.deleted_at.is_(None),
                    Transaction.excluir_de_presupuesto == False,  # noqa: E712
                )
                .order_by(Transaction.fecha_transaccion.asc())
                .all()
            )

            if not transactions:
                logger.info("No hay transacciones para analizar")
                return []

            # Agrupar por comercio (usar merchant_id si existe, sino comercio raw)
            groups = self._group_by_merchant(transactions)

            # Detectar patrones en cada grupo
            subscriptions = []
            for merchant_key, txs in groups.items():
                if len(txs) < self.min_occurrences:
                    continue  # No hay suficientes ocurrencias

                result = self._analyze_pattern(txs, merchant_key)
                if result:
                    subscriptions.append(result)

            logger.info(f"Detectadas {len(subscriptions)} suscripciones potenciales")
            return subscriptions

    def sync_subscriptions_to_db(self, profile_id: str) -> dict[str, int]:
        """
        Detecta suscripciones y sincroniza con la base de datos.

        Args:
            profile_id: ID del perfil

        Returns:
            dict con estadísticas: created, updated, deactivated
        """
        detected = self.detect_all_subscriptions(profile_id)

        stats = {"created": 0, "updated": 0, "deactivated": 0, "total_detected": len(detected)}

        with get_session() as session:
            # Obtener suscripciones existentes
            existing_subs = (
                session.query(Subscription)
                .filter(
                    Subscription.profile_id == profile_id,
                    Subscription.deleted_at.is_(None),
                )
                .all()
            )

            existing_by_comercio = {sub.comercio: sub for sub in existing_subs}

            # Procesar cada suscripción detectada
            for result in detected:
                if result.comercio in existing_by_comercio:
                    # Actualizar existente
                    sub = existing_by_comercio.pop(result.comercio)
                    self._update_subscription(sub, result)
                    stats["updated"] += 1
                    logger.info(f"  ✓ Actualizada: {result.comercio}")
                else:
                    # Crear nueva
                    sub = self._create_subscription(profile_id, result)
                    session.add(sub)
                    stats["created"] += 1
                    logger.info(f"  + Nueva: {result.comercio} - ₡{result.monto_promedio:,.0f}")

            # Las que quedaron en existing_by_comercio ya no se detectaron
            # → posiblemente canceladas
            for comercio, sub in existing_by_comercio.items():
                if sub.is_active and self._should_deactivate(sub):
                    sub.cancelar()
                    stats["deactivated"] += 1
                    logger.info(f"  - Desactivada: {comercio} (no se detectó recientemente)")

            session.commit()

        logger.success(
            f"✅ Sincronización completada: "
            f"{stats['created']} nuevas, "
            f"{stats['updated']} actualizadas, "
            f"{stats['deactivated']} desactivadas"
        )

        return stats

    def _group_by_merchant(self, transactions: list[Transaction]) -> dict[str, list[Transaction]]:
        """
        Agrupa transacciones por comercio (merchant_id o comercio raw).

        Returns:
            dict: {merchant_key: [transactions]}
        """
        groups: dict[str, list[Transaction]] = defaultdict(list)

        for tx in transactions:
            # Usar merchant_id si existe (normalizado), sino comercio raw
            key = tx.merchant_id if tx.merchant_id else tx.comercio
            groups[key].append(tx)

        return groups

    def _analyze_pattern(
        self, transactions: list[Transaction], merchant_key: str
    ) -> DetectionResult | None:
        """
        Analiza un grupo de transacciones para detectar patrón de suscripción.

        Args:
            transactions: Lista de transacciones del mismo comercio
            merchant_key: ID del merchant o nombre del comercio

        Returns:
            DetectionResult si es suscripción, None si no
        """
        if len(transactions) < self.min_occurrences:
            return None

        # Ordenar por fecha
        txs = sorted(transactions, key=lambda t: t.fecha_transaccion)

        # Extraer datos
        fechas = [tx.fecha_transaccion.date() for tx in txs]
        montos = [float(tx.monto_crc) for tx in txs]

        # Calcular intervalos entre transacciones (en días)
        intervals = []
        for i in range(1, len(fechas)):
            days = (fechas[i] - fechas[i - 1]).days
            intervals.append(days)

        if not intervals:
            return None

        # Calcular promedio de intervalo
        avg_interval = sum(intervals) / len(intervals)

        # Verificar si los intervalos son consistentes
        interval_variance = sum(abs(interval - avg_interval) for interval in intervals) / len(intervals)

        # Si la varianza es muy alta, no es una suscripción regular
        if interval_variance > self.frecuencia_tolerance_days:
            return None

        # Verificar si los montos son similares
        monto_promedio = sum(montos) / len(montos)
        monto_min = min(montos)
        monto_max = max(montos)

        monto_range_pct = ((monto_max - monto_min) / monto_promedio) * 100 if monto_promedio > 0 else 0

        # Si la variación es muy alta, no es una suscripción
        if monto_range_pct > float(self.monto_tolerance_pct):
            return None

        # Calcular confidence score (0-100)
        confidence = self._calculate_confidence(
            len(txs), interval_variance, float(monto_range_pct)
        )

        # Si la confianza es muy baja, no reportar
        if confidence < 50:
            return None

        # Es una suscripción!
        return DetectionResult(
            comercio=txs[0].comercio,
            merchant_id=txs[0].merchant_id,
            monto_promedio=Decimal(str(monto_promedio)),
            monto_min=Decimal(str(monto_min)),
            monto_max=Decimal(str(monto_max)),
            frecuencia_dias=int(avg_interval),
            primera_fecha=fechas[0],
            ultima_fecha=fechas[-1],
            occurrences=len(txs),
            confidence=Decimal(str(confidence)),
        )

    def _calculate_confidence(
        self, occurrences: int, interval_variance: float, monto_variance_pct: float
    ) -> float:
        """
        Calcula el score de confianza (0-100) de que sea una suscripción.

        Factores:
        - Más ocurrencias = mayor confianza
        - Menor varianza en intervalos = mayor confianza
        - Menor varianza en montos = mayor confianza
        """
        # Base score por número de ocurrencias (0-40 puntos)
        occurrence_score = min(40, occurrences * 10)

        # Score por consistencia de intervalos (0-30 puntos)
        # Varianza ideal = 0, varianza máxima aceptable = tolerance_days
        interval_score = max(
            0, 30 * (1 - interval_variance / self.frecuencia_tolerance_days)
        )

        # Score por consistencia de montos (0-30 puntos)
        # Varianza ideal = 0%, varianza máxima aceptable = tolerance_pct%
        monto_score = max(
            0, 30 * (1 - monto_variance_pct / float(self.monto_tolerance_pct))
        )

        total = occurrence_score + interval_score + monto_score
        return min(100, max(0, total))

    def _create_subscription(self, profile_id: str, result: DetectionResult) -> Subscription:
        """Crea una nueva suscripción desde DetectionResult."""
        proxima_fecha = result.ultima_fecha + timedelta(days=result.frecuencia_dias)

        return Subscription(
            profile_id=profile_id,
            merchant_id=result.merchant_id,
            comercio=result.comercio,
            monto_promedio=result.monto_promedio,
            monto_min=result.monto_min,
            monto_max=result.monto_max,
            frecuencia_dias=result.frecuencia_dias,
            primera_fecha_cobro=result.primera_fecha,
            ultima_fecha_cobro=result.ultima_fecha,
            proxima_fecha_estimada=proxima_fecha,
            occurrences_count=result.occurrences,
            confidence_score=result.confidence,
            is_active=True,
            is_confirmed=False,
        )

    def _update_subscription(self, subscription: Subscription, result: DetectionResult) -> None:
        """Actualiza una suscripción existente con nuevos datos."""
        subscription.monto_promedio = result.monto_promedio
        subscription.monto_min = result.monto_min
        subscription.monto_max = result.monto_max
        subscription.frecuencia_dias = result.frecuencia_dias
        subscription.ultima_fecha_cobro = result.ultima_fecha
        subscription.occurrences_count = result.occurrences
        subscription.confidence_score = result.confidence

        # Actualizar próxima fecha estimada
        subscription.actualizar_proximo_cobro()

        # Si estaba inactiva pero se detectó de nuevo, reactivarla
        if not subscription.is_active:
            subscription.activar()
            logger.info("    (reactivada - se detectó nuevamente)")

    def _should_deactivate(self, subscription: Subscription) -> bool:
        """
        Determina si una suscripción debería desactivarse.

        Criterios:
        - Si pasó más de 2x la frecuencia desde el último cobro
          → Probablemente fue cancelada
        """
        days_since_last = (date.today() - subscription.ultima_fecha_cobro).days
        threshold = subscription.frecuencia_dias * 2

        return days_since_last > threshold


# Instancia singleton
subscription_detector = SubscriptionDetectorService()
