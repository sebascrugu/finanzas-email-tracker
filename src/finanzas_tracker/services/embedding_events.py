"""
Eventos SQLAlchemy para auto-generar embeddings de transacciones.

Este módulo configura listeners que generan embeddings automáticamente
cuando se crean o actualizan transacciones.
"""

from queue import Queue
import threading
from typing import TYPE_CHECKING

from sqlalchemy import event

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.transaction import Transaction


if TYPE_CHECKING:
    from finanzas_tracker.services.embedding_service import EmbeddingService

logger = get_logger(__name__)

# Cola para procesar embeddings en background
_embedding_queue: Queue[str] = Queue()
_worker_thread: threading.Thread | None = None
_shutdown_flag = threading.Event()


def _get_embedding_service() -> "EmbeddingService":
    """Importación lazy para evitar imports circulares."""
    from finanzas_tracker.services.embedding_service import EmbeddingService
    return EmbeddingService()


def _embedding_worker() -> None:
    """Worker thread que procesa embeddings de la cola."""
    from finanzas_tracker.core.database import get_session

    logger.info("🔄 Embedding worker thread iniciado")

    while not _shutdown_flag.is_set():
        try:
            # Esperar por trabajo con timeout para poder verificar shutdown
            try:
                transaction_id = _embedding_queue.get(timeout=1.0)
            except Exception:
                continue

            if transaction_id is None:  # Señal de shutdown
                break

            logger.debug(f"Procesando embedding para transacción: {transaction_id}")

            try:
                with get_session() as session:
                    service = _get_embedding_service()
                    service.embed_transaction(session, transaction_id)
                    session.commit()
                    logger.info(f"✅ Embedding generado para transacción: {transaction_id}")
            except Exception as e:
                logger.error(f"Error generando embedding para {transaction_id}: {e}")
            finally:
                _embedding_queue.task_done()

        except Exception as e:
            logger.error(f"Error en embedding worker: {e}")

    logger.info("🛑 Embedding worker thread detenido")


def start_embedding_worker() -> None:
    """Inicia el worker thread para procesar embeddings."""
    global _worker_thread

    if _worker_thread is not None and _worker_thread.is_alive():
        logger.debug("Embedding worker ya está corriendo")
        return

    _shutdown_flag.clear()
    _worker_thread = threading.Thread(target=_embedding_worker, daemon=True, name="embedding-worker")
    _worker_thread.start()
    logger.info("🚀 Embedding worker iniciado")


def stop_embedding_worker() -> None:
    """Detiene el worker thread."""
    global _worker_thread

    if _worker_thread is None:
        return

    _shutdown_flag.set()
    _embedding_queue.put(None)  # Señal de shutdown
    _worker_thread.join(timeout=5.0)
    _worker_thread = None
    logger.info("🛑 Embedding worker detenido")


def queue_embedding(transaction_id: str) -> None:
    """Agrega una transacción a la cola para generar embedding."""
    _embedding_queue.put(transaction_id)
    logger.debug(f"Transacción {transaction_id} agregada a cola de embeddings")


# ============================================================================
# SQLAlchemy Event Listeners
# ============================================================================

def _after_insert_transaction(mapper: object, connection: object, target: Transaction) -> None:
    """
    Evento que se dispara después de insertar una transacción.
    Agrega la transacción a la cola para generar embedding.
    """
    if target.id:
        queue_embedding(str(target.id))
        logger.debug(f"Transaction {target.id} queued for embedding after insert")


def _after_update_transaction(mapper: object, connection: object, target: Transaction) -> None:
    """
    Evento que se dispara después de actualizar una transacción.
    Re-genera embedding si campos relevantes cambiaron.
    """
    # Verificar si campos relevantes para el embedding cambiaron
    # (comercio, tipo_transaccion, monto_crc, notas)
    from sqlalchemy import inspect

    try:
        insp = inspect(target)

        # Verificar historial de cambios
        comercio_history = insp.attrs.comercio.history
        notas_history = insp.attrs.notas.history

        comercio_changed = comercio_history.has_changes()
        notas_changed = notas_history.has_changes()

        if comercio_changed or notas_changed:
            queue_embedding(str(target.id))
            logger.debug(f"Transaction {target.id} queued for embedding after update")
    except Exception as e:
        # Si falla la inspección, logueamos pero no interrumpimos
        logger.warning(f"Error checking changes for embedding: {e}")


def register_embedding_events() -> None:
    """
    Registra los event listeners de SQLAlchemy para auto-embeddings.
    Llama esta función al iniciar la aplicación.
    """
    event.listen(Transaction, "after_insert", _after_insert_transaction)
    event.listen(Transaction, "after_update", _after_update_transaction)
    logger.info("✅ Embedding events registrados para Transaction model")


def unregister_embedding_events() -> None:
    """Desregistra los event listeners."""
    event.remove(Transaction, "after_insert", _after_insert_transaction)
    event.remove(Transaction, "after_update", _after_update_transaction)
    logger.info("Embedding events desregistrados")


# ============================================================================
# Función de utilidad para generar embeddings manualmente
# ============================================================================

def generate_all_embeddings_sync(batch_size: int = 50) -> dict[str, int]:
    """
    Genera embeddings para todas las transacciones pendientes de forma síncrona.
    Útil para migración inicial o re-generación masiva.

    Args:
        batch_size: Número de transacciones a procesar por lote

    Returns:
        dict: Estadísticas del procesamiento
    """
    from finanzas_tracker.core.database import get_session

    stats = {"generated": 0, "errors": 0, "skipped": 0}

    with get_session() as session:
        service = _get_embedding_service()

        result = service.embed_pending_transactions(session, batch_size=batch_size)
        stats["generated"] = result

        session.commit()

    logger.info(f"Generación de embeddings completada: {stats}")
    return stats
