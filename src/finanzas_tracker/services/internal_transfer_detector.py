"""Detector de transferencias internas y pagos de tarjeta.

Detecta transacciones que son movimientos entre cuentas propias
del usuario, como pagos de tarjeta de crédito, transferencias
entre cuentas, etc.
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
import logging
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.models.card import Card
from finanzas_tracker.models.enums import CardType
from finanzas_tracker.models.transaction import Transaction


logger = logging.getLogger(__name__)


@dataclass
class PagoTarjetaDetectado:
    """Resultado de detección de pago de tarjeta."""

    transaccion: Transaction
    tarjeta: Card | None
    monto: Decimal
    ultimos_4_digitos: str | None
    confianza: int  # 0-100
    patron_matched: str


@dataclass
class TransferenciaInternaDetectada:
    """Resultado de detección de transferencia interna."""

    transaccion_origen: Transaction
    transaccion_destino: Transaction | None
    monto: Decimal
    tipo: str  # pago_tarjeta | entre_cuentas | ahorro
    confianza: int  # 0-100


class InternalTransferDetector:
    """Detecta transferencias internas (pagos de tarjeta, entre cuentas, etc)."""

    # Patrones para detectar pagos de tarjeta de crédito
    PATRONES_PAGO_TARJETA: list[tuple[str, int]] = [
        # (patrón regex, confianza base)
        (r"PAGO\s+(?:A\s+)?(?:SU\s+)?TARJETA\s+(?:DE\s+)?(?:CREDITO)?", 95),
        (r"PAGO\s+T\.?C\.?\s*(?:\d{4})?", 90),
        (r"PAG\.?\s*T\.?C\.?", 85),
        (r"PAGO\s+VISA\s*(?:\d{4})?", 90),
        (r"PAGO\s+MASTERCARD\s*(?:\d{4})?", 90),
        (r"PAGO\s+AMEX\s*(?:\d{4})?", 90),
        (r"PAGO\s+(?:DE\s+)?CREDITO", 85),
        (r"ABONO\s+(?:A\s+)?TARJETA", 80),
        (r"TRANSFERENCIA\s+PAGO\s+TC", 85),
        (r"PAG\s+TARJ\s+CRED", 85),
    ]

    # Patrones para detectar transferencias entre cuentas propias
    PATRONES_TRANSFERENCIA_INTERNA: list[tuple[str, int]] = [
        (r"TRANSF(?:ERENCIA)?\s+(?:A\s+)?CTA\s+PROPIA", 95),
        (r"TRANSF(?:ERENCIA)?\s+ENTRE\s+CUENTAS", 90),
        (r"TRASLADO\s+(?:A\s+)?(?:MI\s+)?CUENTA", 85),
        (r"AHORRO\s+PROGRAMADO", 90),
        (r"INVERSION\s+AUTOMATICA", 85),
    ]

    # Regex para extraer últimos 4 dígitos
    REGEX_ULTIMOS_4 = re.compile(r"(?:\*{4}|\d{4}[-\s]?)(\d{4})")

    def __init__(self, db: Session) -> None:
        """Inicializa el detector.

        Args:
            db: Sesión de base de datos SQLAlchemy.
        """
        self.db = db

    def es_pago_tarjeta(self, tx: Transaction) -> PagoTarjetaDetectado | None:
        """Detecta si la transacción es un pago de tarjeta de crédito.

        Args:
            tx: Transacción a analizar.

        Returns:
            PagoTarjetaDetectado si es un pago, None si no.
        """
        descripcion = tx.comercio.upper() if tx.comercio else ""

        for patron, confianza_base in self.PATRONES_PAGO_TARJETA:
            if re.search(patron, descripcion, re.IGNORECASE):
                # Extraer últimos 4 dígitos si están presentes
                ultimos_4 = self._extraer_ultimos_4(descripcion)

                # Buscar la tarjeta correspondiente
                tarjeta = self._buscar_tarjeta(tx.profile_id, ultimos_4)

                # Ajustar confianza si encontramos la tarjeta
                confianza = confianza_base
                if tarjeta:
                    confianza = min(100, confianza + 5)
                elif ultimos_4:
                    confianza = max(0, confianza - 10)

                logger.info(
                    "Pago de tarjeta detectado: txn=%s, monto=%s, tarjeta=%s, confianza=%d",
                    tx.id,
                    tx.monto_original,
                    ultimos_4 or "desconocida",
                    confianza,
                )

                return PagoTarjetaDetectado(
                    transaccion=tx,
                    tarjeta=tarjeta,
                    monto=tx.monto_original,
                    ultimos_4_digitos=ultimos_4,
                    confianza=confianza,
                    patron_matched=patron,
                )

        return None

    def es_transferencia_interna(
        self,
        tx: Transaction,
    ) -> TransferenciaInternaDetectada | None:
        """Detecta si la transacción es una transferencia interna.

        Args:
            tx: Transacción a analizar.

        Returns:
            TransferenciaInternaDetectada si es transferencia interna, None si no.
        """
        # Primero verificar si es pago de tarjeta
        pago_tarjeta = self.es_pago_tarjeta(tx)
        if pago_tarjeta:
            return TransferenciaInternaDetectada(
                transaccion_origen=tx,
                transaccion_destino=None,  # El "destino" es la tarjeta, no una transacción
                monto=tx.monto_original,
                tipo="pago_tarjeta",
                confianza=pago_tarjeta.confianza,
            )

        # Buscar otros patrones de transferencia interna
        descripcion = tx.comercio.upper() if tx.comercio else ""

        for patron, confianza in self.PATRONES_TRANSFERENCIA_INTERNA:
            if re.search(patron, descripcion, re.IGNORECASE):
                # Buscar transacción de contrapartida
                contrapartida = self._buscar_contrapartida(tx)

                return TransferenciaInternaDetectada(
                    transaccion_origen=tx,
                    transaccion_destino=contrapartida,
                    monto=tx.monto_original,
                    tipo="entre_cuentas" if contrapartida else "ahorro",
                    confianza=confianza if contrapartida else max(0, confianza - 15),
                )

        return None

    def procesar_pago_tarjeta(
        self,
        tx: Transaction,
        profile_id: str,
    ) -> tuple[Transaction, Card | None]:
        """Procesa un pago de tarjeta actualizando la transacción y el saldo.

        Args:
            tx: Transacción de pago de tarjeta.
            profile_id: ID del perfil.

        Returns:
            Tupla con (transacción actualizada, tarjeta si se encontró).
        """
        pago = self.es_pago_tarjeta(tx)
        if not pago:
            return tx, None

        # Marcar la transacción como transferencia interna
        tx.es_transferencia_interna = True
        tx.tipo_especial = "pago_tarjeta"
        tx.excluir_de_presupuesto = True

        # Si encontramos la tarjeta, actualizar su saldo
        if pago.tarjeta:
            if pago.tarjeta.current_balance:
                pago.tarjeta.current_balance -= pago.monto
                if pago.tarjeta.current_balance < 0:
                    pago.tarjeta.current_balance = Decimal("0.00")

            tx.card_id = pago.tarjeta.id

            logger.info(
                "Procesado pago de tarjeta: txn=%s, tarjeta=****%s, nuevo_saldo=%s",
                tx.id,
                pago.tarjeta.ultimos_4_digitos,
                pago.tarjeta.current_balance,
            )

        self.db.commit()
        self.db.refresh(tx)

        return tx, pago.tarjeta

    def vincular_pago_con_tarjeta(
        self,
        tx: Transaction,
        tarjetas: list[Card],
    ) -> Card | None:
        """Encuentra la tarjeta correspondiente al pago.

        Args:
            tx: Transacción de pago.
            tarjetas: Lista de tarjetas del usuario.

        Returns:
            Card correspondiente o None.
        """
        descripcion = tx.comercio.upper() if tx.comercio else ""
        ultimos_4 = self._extraer_ultimos_4(descripcion)

        if ultimos_4:
            for tarjeta in tarjetas:
                if tarjeta.ultimos_4_digitos == ultimos_4:
                    return tarjeta

        # Si no hay dígitos, buscar por monto similar en saldo de tarjeta
        # (heurística: el pago suele ser igual o cercano al saldo)
        for tarjeta in tarjetas:
            if tarjeta.tipo == CardType.CREDIT and tarjeta.current_balance:
                diferencia = abs(tarjeta.current_balance - tx.monto_original)
                if diferencia < Decimal("1000"):  # Tolerancia de ₡1000
                    return tarjeta

        return None

    def detectar_y_marcar_transferencias(
        self,
        transacciones: list[Transaction],
        profile_id: str,
    ) -> dict[str, int]:
        """Detecta y marca transferencias internas en una lista de transacciones.

        Args:
            transacciones: Lista de transacciones a procesar.
            profile_id: ID del perfil.

        Returns:
            Diccionario con conteo de detecciones por tipo.
        """
        conteo = {
            "pagos_tarjeta": 0,
            "entre_cuentas": 0,
            "ahorro": 0,
            "total_marcadas": 0,
        }

        for tx in transacciones:
            if tx.es_transferencia_interna:
                # Ya fue marcada
                continue

            deteccion = self.es_transferencia_interna(tx)
            if deteccion:
                tx.es_transferencia_interna = True
                tx.excluir_de_presupuesto = True
                tx.tipo_especial = deteccion.tipo

                conteo[deteccion.tipo] = conteo.get(deteccion.tipo, 0) + 1
                conteo["total_marcadas"] += 1

                # Si es pago de tarjeta, procesar
                if deteccion.tipo == "pago_tarjeta":
                    self.procesar_pago_tarjeta(tx, profile_id)

        self.db.commit()

        logger.info(
            "Transferencias internas detectadas para profile %s: %s",
            profile_id,
            conteo,
        )

        return conteo

    def _extraer_ultimos_4(self, texto: str) -> str | None:
        """Extrae los últimos 4 dígitos de una descripción.

        Args:
            texto: Texto a analizar.

        Returns:
            String con 4 dígitos o None.
        """
        match = self.REGEX_ULTIMOS_4.search(texto)
        if match:
            return match.group(1)

        # Buscar 4 dígitos al final
        match_simple = re.search(r"(\d{4})\s*$", texto)
        if match_simple:
            return match_simple.group(1)

        return None

    def _buscar_tarjeta(
        self,
        profile_id: str,
        ultimos_4: str | None,
    ) -> Card | None:
        """Busca una tarjeta por profile y últimos 4 dígitos.

        Args:
            profile_id: ID del perfil.
            ultimos_4: Últimos 4 dígitos de la tarjeta.

        Returns:
            Card encontrada o None.
        """
        if not ultimos_4:
            return None

        stmt = select(Card).where(
            Card.profile_id == profile_id,
            Card.ultimos_4_digitos == ultimos_4,
            Card.tipo == CardType.CREDIT,
            Card.deleted_at.is_(None),
        )

        return self.db.execute(stmt).scalar_one_or_none()

    def _buscar_contrapartida(
        self,
        tx: Transaction,
    ) -> Transaction | None:
        """Busca la transacción de contrapartida para una transferencia.

        Busca una transacción del mismo día o día siguiente con:
        - Monto igual pero signo opuesto
        - Diferente cuenta

        Args:
            tx: Transacción de origen.

        Returns:
            Transaction de destino o None.
        """
        fecha_inicio = tx.fecha_transaccion
        fecha_fin = fecha_inicio + timedelta(days=1)

        stmt = select(Transaction).where(
            Transaction.profile_id == tx.profile_id,
            Transaction.id != tx.id,
            Transaction.monto_original == tx.monto_original,
            Transaction.fecha_transaccion >= fecha_inicio,
            Transaction.fecha_transaccion <= fecha_fin,
            Transaction.deleted_at.is_(None),
            # Buscar tipo opuesto (si uno es gasto, el otro es ingreso)
            Transaction.tipo_transaccion != tx.tipo_transaccion,
        )

        return self.db.execute(stmt).scalar_one_or_none()

    def get_resumen_transferencias(
        self,
        profile_id: str,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
    ) -> dict:
        """Obtiene resumen de transferencias internas.

        Args:
            profile_id: ID del perfil.
            fecha_inicio: Fecha inicio del período.
            fecha_fin: Fecha fin del período.

        Returns:
            Diccionario con resumen.
        """
        stmt = select(Transaction).where(
            Transaction.profile_id == profile_id,
            Transaction.es_transferencia_interna.is_(True),
            Transaction.deleted_at.is_(None),
        )

        if fecha_inicio:
            stmt = stmt.where(Transaction.fecha_transaccion >= fecha_inicio)
        if fecha_fin:
            stmt = stmt.where(Transaction.fecha_transaccion <= fecha_fin)

        transacciones = list(self.db.execute(stmt).scalars().all())

        resumen = {
            "total": len(transacciones),
            "por_tipo": {},
            "monto_total": Decimal("0.00"),
        }

        for tx in transacciones:
            tipo = tx.tipo_especial or "otro"
            resumen["por_tipo"][tipo] = resumen["por_tipo"].get(tipo, 0) + 1
            resumen["monto_total"] += tx.monto_original

        return resumen
