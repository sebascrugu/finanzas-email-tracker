"""
Servicio para manejar comercios ambiguos que pueden tener múltiples categorías.

Comercios como Walmart, Amazon, PriceSmart pueden ser:
- Supermercado (comida)
- Electrónica
- Ropa
- Hogar
- etc.

Este servicio detecta estos casos y marca las transacciones para confirmación.
"""

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from finanzas_tracker.models.merchant import (
    COMERCIOS_AMBIGUOS,
    es_comercio_ambiguo,
    obtener_categorias_posibles,
)
from finanzas_tracker.models.transaction import Transaction


logger = logging.getLogger(__name__)


class AmbiguousMerchantService:
    """Servicio para manejar comercios con múltiples categorías posibles."""

    def __init__(self, db: Session) -> None:
        """Inicializa el servicio."""
        self.db = db

    def detectar_y_marcar(self, transaction: Transaction) -> bool:
        """
        Detecta si una transacción es de un comercio ambiguo y la marca.

        Args:
            transaction: Transacción a analizar

        Returns:
            True si es ambiguo y fue marcado, False si no
        """
        comercio = transaction.comercio

        if not es_comercio_ambiguo(comercio):
            return False

        categorias = obtener_categorias_posibles(comercio)

        if not categorias:
            return False

        # Marcar la transacción
        transaction.es_comercio_ambiguo = True
        transaction.categorias_opciones = json.dumps(categorias, ensure_ascii=False)
        transaction.necesita_revision = True
        transaction.confirmada = False

        logger.info(f"Comercio ambiguo detectado: {comercio} - " f"Opciones: {categorias}")

        return True

    def confirmar_categoria(
        self,
        transaction_id: str,
        categoria_seleccionada: str,
        notas: str | None = None,
    ) -> Transaction | None:
        """
        Confirma la categoría de una transacción ambigua.

        Args:
            transaction_id: ID de la transacción
            categoria_seleccionada: Categoría elegida por el usuario
            notas: Notas adicionales (opcional)

        Returns:
            Transacción actualizada o None si no existe
        """
        stmt = select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.deleted_at.is_(None),
        )
        transaction = self.db.execute(stmt).scalar_one_or_none()

        if not transaction:
            return None

        # Validar que la categoría sea una de las opciones
        if transaction.categorias_opciones:
            opciones = json.loads(transaction.categorias_opciones)
            if categoria_seleccionada not in opciones:
                logger.warning(
                    f"Categoría '{categoria_seleccionada}' no está en opciones: {opciones}"
                )
                # Permitir de todos modos - el usuario sabe mejor

        # Actualizar
        transaction.categoria_confirmada_usuario = categoria_seleccionada
        transaction.categoria_sugerida_por_ia = categoria_seleccionada
        transaction.confirmada = True
        transaction.necesita_revision = False

        if notas:
            transaction.notas = notas

        # Flush para enviar los cambios, dejar commit al caller
        self.db.flush()

        logger.info(
            f"Transacción {transaction_id[:8]}... confirmada como: {categoria_seleccionada}"
        )

        return transaction

    def obtener_pendientes(self, profile_id: str) -> list[dict[str, Any]]:
        """
        Obtiene transacciones ambiguas pendientes de confirmación.

        Args:
            profile_id: ID del perfil

        Returns:
            Lista de transacciones con sus opciones
        """
        stmt = (
            select(Transaction)
            .where(
                Transaction.profile_id == profile_id,
                Transaction.es_comercio_ambiguo == True,
                Transaction.confirmada == False,
                Transaction.deleted_at.is_(None),
            )
            .order_by(Transaction.fecha_transaccion.desc())
        )

        transactions = self.db.execute(stmt).scalars().all()

        resultado = []
        for txn in transactions:
            opciones = []
            if txn.categorias_opciones:
                opciones = json.loads(txn.categorias_opciones)

            resultado.append(
                {
                    "id": txn.id,
                    "comercio": txn.comercio,
                    "monto_crc": float(txn.monto_crc),
                    "fecha": txn.fecha_transaccion.isoformat(),
                    "opciones_categoria": opciones,
                }
            )

        return resultado

    def obtener_estadisticas(self, profile_id: str) -> dict[str, Any]:
        """Estadísticas de comercios ambiguos."""
        # Total ambiguos
        stmt_total = select(Transaction).where(
            Transaction.profile_id == profile_id,
            Transaction.es_comercio_ambiguo == True,
            Transaction.deleted_at.is_(None),
        )
        total = len(self.db.execute(stmt_total).scalars().all())

        # Pendientes
        stmt_pendientes = select(Transaction).where(
            Transaction.profile_id == profile_id,
            Transaction.es_comercio_ambiguo == True,
            Transaction.confirmada == False,
            Transaction.deleted_at.is_(None),
        )
        pendientes = len(self.db.execute(stmt_pendientes).scalars().all())

        # Confirmados
        confirmados = total - pendientes

        return {
            "total_ambiguos": total,
            "pendientes_confirmacion": pendientes,
            "confirmados": confirmados,
            "porcentaje_completado": round(confirmados / total * 100, 1) if total > 0 else 100,
        }

    def marcar_transacciones_existentes(self, profile_id: str) -> int:
        """
        Revisa transacciones existentes y marca las que son de comercios ambiguos.

        Útil para aplicar la lógica a datos históricos.

        Args:
            profile_id: ID del perfil

        Returns:
            Número de transacciones marcadas
        """
        stmt = select(Transaction).where(
            Transaction.profile_id == profile_id,
            Transaction.es_comercio_ambiguo == False,
            Transaction.deleted_at.is_(None),
        )

        transactions = self.db.execute(stmt).scalars().all()
        count = 0

        for txn in transactions:
            if self.detectar_y_marcar(txn):
                count += 1

        # Flush para enviar los cambios pero dejar el commit al caller
        if count > 0:
            self.db.flush()

        logger.info(f"Marcadas {count} transacciones como comercios ambiguos")
        return count


# Lista de comercios conocidos para referencia rápida
def listar_comercios_ambiguos() -> dict[str, list[str]]:
    """Retorna el diccionario de comercios ambiguos conocidos."""
    return COMERCIOS_AMBIGUOS.copy()
