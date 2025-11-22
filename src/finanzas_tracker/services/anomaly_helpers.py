"""Helper functions para anomaly detection en el dashboard."""

__all__ = ["get_anomaly_detector_status", "retrain_anomaly_detector"]

from datetime import datetime, timedelta
from pathlib import Path

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.services.anomaly_detector import AnomalyDetectionService


logger = get_logger(__name__)


def get_anomaly_detector_status(profile_id: str) -> dict:
    """
    Obtiene el estado del detector de anomalías para un perfil.

    Args:
        profile_id: ID del perfil

    Returns:
        dict con:
        - is_active: bool - Si el modelo está entrenado
        - transactions_count: int - Cantidad de transacciones disponibles
        - min_required: int - Mínimo requerido (30)
        - can_train: bool - Si se puede entrenar
        - model_path: Path - Ruta del modelo
        - model_exists: bool - Si existe el archivo del modelo
        - message: str - Mensaje para mostrar al usuario
    """
    detector = AnomalyDetectionService()

    # Contar transacciones
    with get_session() as session:
        six_months_ago = datetime.now() - timedelta(days=180)

        tx_count = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion >= six_months_ago,
                Transaction.deleted_at.is_(None),
                Transaction.excluir_de_presupuesto == False,  # noqa: E712
            )
            .count()
        )

    min_required = 30
    can_train = tx_count >= min_required
    is_active = detector.model is not None
    model_exists = detector.model_path.exists() if detector.model_path else False

    # Generar mensaje
    if is_active:
        message = (
            f"✅ Detección de anomalías ACTIVA\n"
            f"El modelo está entrenado con tus datos históricos.\n"
            f"Transacciones anómalas se detectarán automáticamente."
        )
    elif can_train:
        message = (
            f"⚠️ Detección de anomalías INACTIVA\n"
            f"Tienes {tx_count} transacciones disponibles.\n"
            f"La detección se activará automáticamente en el próximo procesamiento."
        )
    else:
        needed = min_required - tx_count
        message = (
            f"ℹ️ Detección de anomalías NO DISPONIBLE\n"
            f"Necesitas {needed} transacciones más (tienes {tx_count}/{min_required}).\n"
            f"Procesa más correos para activar esta función."
        )

    return {
        "is_active": is_active,
        "transactions_count": tx_count,
        "min_required": min_required,
        "can_train": can_train,
        "model_path": detector.model_path,
        "model_exists": model_exists,
        "message": message,
    }


def retrain_anomaly_detector(profile_id: str, min_transactions: int = 30) -> dict:
    """
    Re-entrena el detector de anomalías manualmente.

    Args:
        profile_id: ID del perfil
        min_transactions: Mínimo de transacciones requeridas

    Returns:
        dict con:
        - success: bool
        - message: str
        - categories_count: int (si success)
    """
    logger.info(f"Re-entrenando detector de anomalías para perfil {profile_id[:8]}...")

    detector = AnomalyDetectionService()

    try:
        success = detector.train(profile_id=profile_id, min_transactions=min_transactions)

        if success:
            categories_count = len(detector.category_encoder)
            message = (
                f"✅ Modelo re-entrenado exitosamente!\n"
                f"Categorías aprendidas: {categories_count}\n"
                f"El modelo ahora detectará anomalías basándose en tus patrones más recientes."
            )
            return {
                "success": True,
                "message": message,
                "categories_count": categories_count,
            }
        else:
            return {
                "success": False,
                "message": (
                    f"❌ No se pudo entrenar el modelo.\n"
                    f"Asegúrate de tener al menos {min_transactions} transacciones."
                ),
            }

    except Exception as e:
        logger.error(f"Error re-entrenando detector: {e}")
        return {
            "success": False,
            "message": f"❌ Error durante el entrenamiento: {str(e)}",
        }
