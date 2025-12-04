"""Servicio de Transacciones - Gestión de ciclo de vida y estados.

Maneja operaciones de alto nivel sobre transacciones:
- Cambios de estado (pendiente → confirmada → reconciliada)
- Marcado de transacciones históricas (antes de FECHA_BASE)
- Filtros por estado
- Operaciones batch
"""

from datetime import date, datetime
from decimal import Decimal
import logging

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from finanzas_tracker.models.enums import TransactionStatus
from finanzas_tracker.models.transaction import Transaction


logger = logging.getLogger(__name__)


class TransactionService:
    """Servicio para gestión de transacciones y sus estados."""

    def __init__(self, db: Session) -> None:
        """Inicializa el servicio.

        Args:
            db: Sesión de base de datos SQLAlchemy.
        """
        self.db = db

    def get(self, transaction_id: int) -> Transaction | None:
        """Obtiene una transacción por ID.

        Args:
            transaction_id: ID de la transacción.

        Returns:
            Transaction o None si no existe.
        """
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_profile(
        self,
        profile_id: str,
        *,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        estado: TransactionStatus | None = None,
        solo_historicas: bool | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> list[Transaction]:
        """Lista transacciones con filtros.

        Args:
            profile_id: ID del perfil.
            fecha_inicio: Fecha inicio del rango.
            fecha_fin: Fecha fin del rango.
            estado: Filtrar por estado.
            solo_historicas: None=todas, True=solo históricas, False=solo activas.
            skip: Registros a saltar.
            limit: Máximo de registros.

        Returns:
            Lista de transacciones.
        """
        stmt = select(Transaction).where(
            Transaction.profile_id == profile_id,
            Transaction.deleted_at.is_(None),
        )

        if fecha_inicio:
            stmt = stmt.where(Transaction.fecha_transaccion >= fecha_inicio)

        if fecha_fin:
            stmt = stmt.where(Transaction.fecha_transaccion <= fecha_fin)

        if estado:
            stmt = stmt.where(Transaction.estado == estado)

        if solo_historicas is not None:
            stmt = stmt.where(Transaction.es_historica == solo_historicas)

        stmt = stmt.order_by(Transaction.fecha_transaccion.desc()).offset(skip).limit(limit)

        return list(self.db.execute(stmt).scalars().all())

    def cambiar_estado(
        self,
        transaction_id: int,
        nuevo_estado: TransactionStatus,
        razon: str | None = None,
    ) -> Transaction:
        """Cambia el estado de una transacción.

        Args:
            transaction_id: ID de la transacción.
            nuevo_estado: Nuevo estado a asignar.
            razon: Razón del cambio (opcional).

        Returns:
            Transaction actualizada.

        Raises:
            ValueError: Si la transacción no existe.
        """
        txn = self.get(transaction_id)
        if not txn:
            raise ValueError(f"Transacción {transaction_id} no encontrada")

        estado_anterior = txn.estado
        txn.estado = nuevo_estado

        if nuevo_estado == TransactionStatus.CANCELLED and razon:
            txn.razon_ajuste = razon

        if nuevo_estado == TransactionStatus.RECONCILED:
            txn.reconciliada_en = datetime.utcnow()

        self.db.commit()
        self.db.refresh(txn)

        logger.info(
            "Estado cambiado txn %d: %s → %s",
            transaction_id,
            estado_anterior.value if estado_anterior else "None",
            nuevo_estado.value,
        )

        return txn

    def confirmar_transaccion(
        self,
        transaction_id: int,
    ) -> Transaction:
        """Confirma una transacción pendiente.

        Shortcut para cambiar estado a CONFIRMED.

        Args:
            transaction_id: ID de la transacción.

        Returns:
            Transaction confirmada.
        """
        return self.cambiar_estado(transaction_id, TransactionStatus.CONFIRMED)

    def cancelar_transaccion(
        self,
        transaction_id: int,
        razon: str = "Cancelada por usuario",
    ) -> Transaction:
        """Cancela una transacción.

        Args:
            transaction_id: ID de la transacción.
            razon: Razón de la cancelación.

        Returns:
            Transaction cancelada.
        """
        return self.cambiar_estado(
            transaction_id,
            TransactionStatus.CANCELLED,
            razon=razon,
        )

    def marcar_como_historicas(
        self,
        profile_id: str,
        fecha_base: date,
    ) -> int:
        """Marca todas las transacciones anteriores a FECHA_BASE como históricas.

        Esto se usa durante el onboarding para separar las transacciones
        que existían antes del inicio del tracking de patrimonio.

        Args:
            profile_id: ID del perfil.
            fecha_base: Fecha de inicio del tracking (FECHA_BASE).

        Returns:
            Número de transacciones marcadas.
        """
        stmt = (
            update(Transaction)
            .where(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion < fecha_base,
                Transaction.deleted_at.is_(None),
                Transaction.es_historica.is_(False),
            )
            .values(
                es_historica=True,
                fecha_registro_sistema=datetime.utcnow(),
            )
        )

        result = self.db.execute(stmt)
        self.db.commit()

        count = result.rowcount
        logger.info(
            "Marcadas %d transacciones como históricas (antes de %s) para profile %s",
            count,
            fecha_base,
            profile_id,
        )

        return count

    def get_pendientes(
        self,
        profile_id: str,
        limite: int = 50,
    ) -> list[Transaction]:
        """Obtiene transacciones pendientes de revisión.

        Args:
            profile_id: ID del perfil.
            limite: Máximo de registros.

        Returns:
            Lista de transacciones pendientes.
        """
        return self.get_by_profile(
            profile_id,
            estado=TransactionStatus.PENDING,
            limit=limite,
        )

    def get_huerfanas(
        self,
        profile_id: str,
        limite: int = 50,
    ) -> list[Transaction]:
        """Obtiene transacciones huérfanas (no encontradas en reconciliación).

        Args:
            profile_id: ID del perfil.
            limite: Máximo de registros.

        Returns:
            Lista de transacciones huérfanas.
        """
        return self.get_by_profile(
            profile_id,
            estado=TransactionStatus.ORPHAN,
            limit=limite,
        )

    def confirmar_batch(
        self,
        transaction_ids: list[int],
    ) -> int:
        """Confirma múltiples transacciones.

        Args:
            transaction_ids: Lista de IDs a confirmar.

        Returns:
            Número de transacciones confirmadas.
        """
        if not transaction_ids:
            return 0

        stmt = (
            update(Transaction)
            .where(
                Transaction.id.in_(transaction_ids),
                Transaction.deleted_at.is_(None),
                Transaction.estado == TransactionStatus.PENDING,
            )
            .values(estado=TransactionStatus.CONFIRMED)
        )

        result = self.db.execute(stmt)
        self.db.commit()

        count = result.rowcount
        logger.info("Confirmadas %d transacciones en batch", count)
        return count

    def get_resumen_estados(
        self,
        profile_id: str,
    ) -> dict[str, int]:
        """Obtiene conteo de transacciones por estado.

        Args:
            profile_id: ID del perfil.

        Returns:
            Diccionario con conteo por estado.
        """
        from sqlalchemy import func

        stmt = (
            select(Transaction.estado, func.count(Transaction.id))
            .where(
                Transaction.profile_id == profile_id,
                Transaction.deleted_at.is_(None),
            )
            .group_by(Transaction.estado)
        )

        result = self.db.execute(stmt).all()

        resumen = {
            "pendiente": 0,
            "confirmada": 0,
            "reconciliada": 0,
            "cancelada": 0,
            "huerfana": 0,
        }

        for estado, count in result:
            if estado:
                resumen[estado.value] = count

        return resumen

    def marcar_transferencia_interna(
        self,
        transaction_id_origen: int,
        transaction_id_destino: int,
    ) -> tuple[Transaction, Transaction]:
        """Marca dos transacciones como transferencia interna.

        Útil para identificar movimientos entre cuentas propias
        que no deben afectar el cálculo de gastos netos.

        Args:
            transaction_id_origen: ID de la transacción de salida.
            transaction_id_destino: ID de la transacción de entrada.

        Returns:
            Tuple con ambas transacciones actualizadas.

        Raises:
            ValueError: Si alguna transacción no existe.
        """
        origen = self.get(transaction_id_origen)
        destino = self.get(transaction_id_destino)

        if not origen:
            raise ValueError(f"Transacción origen {transaction_id_origen} no encontrada")
        if not destino:
            raise ValueError(f"Transacción destino {transaction_id_destino} no encontrada")

        # Marcar ambas como transferencias internas
        origen.es_transferencia_interna = True
        origen.cuenta_destino_id = destino.cuenta_destino_id or destino.cuenta_origen_id

        destino.es_transferencia_interna = True
        destino.cuenta_origen_id = origen.cuenta_origen_id or origen.cuenta_destino_id

        self.db.commit()
        self.db.refresh(origen)
        self.db.refresh(destino)

        logger.info(
            "Marcadas txn %d y %d como transferencia interna",
            transaction_id_origen,
            transaction_id_destino,
        )

        return origen, destino

    def ajustar_monto(
        self,
        transaction_id: int,
        nuevo_monto: Decimal,
        razon: str = "Ajuste manual",
    ) -> Transaction:
        """Ajusta el monto de una transacción.

        Guarda el monto original estimado y registra la razón.

        Args:
            transaction_id: ID de la transacción.
            nuevo_monto: Nuevo monto corregido.
            razon: Razón del ajuste.

        Returns:
            Transaction actualizada.

        Raises:
            ValueError: Si la transacción no existe.
        """
        txn = self.get(transaction_id)
        if not txn:
            raise ValueError(f"Transacción {transaction_id} no encontrada")

        # Guardar monto original si no estaba ya guardado
        if not txn.monto_original_estimado:
            txn.monto_original_estimado = txn.monto_original

        txn.monto_ajustado = nuevo_monto
        txn.monto_original = nuevo_monto
        txn.monto_crc = nuevo_monto  # Asumiendo CRC
        txn.razon_ajuste = razon

        self.db.commit()
        self.db.refresh(txn)

        logger.info(
            "Monto ajustado txn %d: %s → %s (%s)",
            transaction_id,
            txn.monto_original_estimado,
            nuevo_monto,
            razon,
        )

        return txn
