"""Servicio de detección de anomalías en transacciones usando Machine Learning."""

__all__ = ["AnomalyDetectionService", "AnomalyResult"]

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import pickle

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.transaction import Transaction


logger = get_logger(__name__)


@dataclass
class AnomalyResult:
    """Resultado de detección de anomalía."""

    is_anomaly: bool
    score: float  # -1 a 1 (< 0 es anómalo)
    reason: str
    confidence: float  # 0-100%


class AnomalyDetectionService:
    """
    Servicio para detectar transacciones anómalas usando Isolation Forest.

    Detecta:
    - Montos inusualmente altos o bajos para una categoría
    - Transacciones en horarios inusuales
    - Gastos en días atípicos
    - Comercios nuevos con montos altos
    - Patrones de compra diferentes al historial

    Features usados para detección:
    - monto_crc (normalizado)
    - hora_del_dia (0-23)
    - dia_semana (0-6)
    - categoria_id (encoded)
    - es_internacional (0/1)
    - monto_promedio_categoria (últimos 3 meses)
    """

    def __init__(self, model_path: Path | None = None) -> None:
        """
        Inicializa el detector de anomalías.

        Args:
            model_path: Ruta donde guardar/cargar el modelo entrenado
        """
        self.model_path = model_path or Path("data/anomaly_model.pkl")
        self.model: IsolationForest | None = None
        self.category_encoder: dict[str, int] = {}
        self.category_stats: dict[str, dict[str, float]] = {}

        # Intentar cargar modelo existente
        if self.model_path.exists():
            self._load_model()
            logger.info(f"Modelo de anomalías cargado desde {self.model_path}")
        else:
            logger.info("No se encontró modelo pre-entrenado. Usar train() primero.")

    def train(self, profile_id: str, min_transactions: int = 30) -> bool:
        """
        Entrena el modelo con datos históricos del perfil.

        Args:
            profile_id: ID del perfil
            min_transactions: Mínimo de transacciones para entrenar

        Returns:
            True si se entrenó exitosamente, False si no hay suficientes datos
        """
        logger.info(f"Entrenando modelo de anomalías para perfil {profile_id[:8]}...")

        with get_session() as session:
            # Obtener transacciones de los últimos 6 meses
            six_months_ago = datetime.now() - timedelta(days=180)

            transactions = (
                session.query(Transaction)
                .filter(
                    Transaction.profile_id == profile_id,
                    Transaction.fecha_transaccion >= six_months_ago,
                    Transaction.deleted_at.is_(None),
                    Transaction.excluir_de_presupuesto == False,  # noqa: E712
                )
                .all()
            )

            if len(transactions) < min_transactions:
                logger.warning(
                    f"Insuficientes transacciones para entrenar: {len(transactions)} < {min_transactions}"
                )
                return False

            # Preparar features
            df = self._prepare_training_data(transactions)

            if df.empty:
                logger.warning("No se pudieron extraer features de las transacciones")
                return False

            # Calcular estadísticas por categoría
            self._calculate_category_stats(df)

            # Entrenar Isolation Forest
            self.model = IsolationForest(
                contamination=0.1,  # Esperamos ~10% de anomalías
                random_state=42,
                n_estimators=100,
                max_samples="auto",
            )

            features = df[
                [
                    "monto_normalizado",
                    "hora",
                    "dia_semana",
                    "categoria_encoded",
                    "es_internacional",
                    "monto_vs_promedio",
                ]
            ].values

            self.model.fit(features)

            # Guardar modelo
            self._save_model()

            logger.info(
                f"✅ Modelo entrenado con {len(transactions)} transacciones y guardado en {self.model_path}"
            )
            return True

    def detect(self, transaction: Transaction) -> AnomalyResult:
        """
        Detecta si una transacción es anómala.

        Args:
            transaction: Transacción a analizar

        Returns:
            AnomalyResult con información de la detección
        """
        if self.model is None:
            logger.warning("Modelo no entrenado. Llamar train() primero.")
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                reason="Modelo no entrenado",
                confidence=0.0,
            )

        # Extraer features
        features = self._extract_features(transaction)

        if features is None:
            return AnomalyResult(
                is_anomaly=False,
                score=0.0,
                reason="No se pudieron extraer features",
                confidence=0.0,
            )

        # Predecir
        feature_array = np.array([features])
        prediction = self.model.predict(feature_array)[0]  # 1 = normal, -1 = anomalía
        score = self.model.score_samples(feature_array)[0]  # Score de anomalía

        is_anomaly = prediction == -1

        # Determinar razón si es anómala
        reason = self._determine_reason(transaction, features, score) if is_anomaly else "Normal"

        # Calcular confianza (convertir score a probabilidad)
        # Score típicamente va de -0.5 a 0.5
        # Convertimos a 0-100%
        confidence = min(100.0, max(0.0, (0.5 - abs(score)) * 100))

        logger.debug(
            f"Transacción {transaction.comercio}: {'ANÓMALA' if is_anomaly else 'Normal'} "
            f"(score: {score:.4f}, confianza: {confidence:.1f}%)"
        )

        return AnomalyResult(
            is_anomaly=is_anomaly,
            score=float(score),
            reason=reason,
            confidence=confidence,
        )

    def _prepare_training_data(self, transactions: list[Transaction]) -> pd.DataFrame:
        """Prepara datos de entrenamiento desde transacciones."""
        data = []

        for t in transactions:
            # Encodear categoría
            if t.subcategory_id:
                if t.subcategory_id not in self.category_encoder:
                    self.category_encoder[t.subcategory_id] = len(self.category_encoder)
                categoria_encoded = self.category_encoder[t.subcategory_id]
            else:
                categoria_encoded = -1  # Sin categoría

            data.append(
                {
                    "monto_crc": float(t.monto_crc),
                    "hora": t.fecha_transaccion.hour,
                    "dia_semana": t.fecha_transaccion.weekday(),
                    "categoria_encoded": categoria_encoded,
                    "categoria_id": t.subcategory_id or "sin_categoria",
                    "es_internacional": 1 if t.es_internacional else 0,
                }
            )

        df = pd.DataFrame(data)

        # Normalizar monto (log para manejar rangos grandes)
        df["monto_normalizado"] = np.log1p(df["monto_crc"])

        # Calcular monto vs promedio de categoría
        category_means = df.groupby("categoria_id")["monto_crc"].mean().to_dict()
        df["monto_vs_promedio"] = df.apply(
            lambda row: row["monto_crc"] / category_means.get(row["categoria_id"], row["monto_crc"]),
            axis=1,
        )

        return df

    def _calculate_category_stats(self, df: pd.DataFrame) -> None:
        """Calcula estadísticas por categoría."""
        for cat_id in df["categoria_id"].unique():
            cat_data = df[df["categoria_id"] == cat_id]["monto_crc"]
            self.category_stats[cat_id] = {
                "mean": float(cat_data.mean()),
                "std": float(cat_data.std()),
                "min": float(cat_data.min()),
                "max": float(cat_data.max()),
            }

    def _extract_features(self, transaction: Transaction) -> list[float] | None:
        """Extrae features de una transacción para predicción."""
        # Encodear categoría
        if transaction.subcategory_id:
            categoria_encoded = self.category_encoder.get(
                transaction.subcategory_id,
                -1,  # Categoría nueva (sospechoso)
            )
        else:
            categoria_encoded = -1

        categoria_id = transaction.subcategory_id or "sin_categoria"

        # Calcular monto vs promedio de categoría
        stats = self.category_stats.get(categoria_id)
        if stats:
            monto_vs_promedio = float(transaction.monto_crc) / stats["mean"]
        else:
            monto_vs_promedio = 1.0  # Sin referencia

        return [
            float(np.log1p(float(transaction.monto_crc))),  # monto_normalizado
            transaction.fecha_transaccion.hour,  # hora
            transaction.fecha_transaccion.weekday(),  # dia_semana
            categoria_encoded,
            1 if transaction.es_internacional else 0,
            monto_vs_promedio,
        ]


    def _determine_reason(
        self,
        transaction: Transaction,
        features: list[float],
        score: float,
    ) -> str:
        """Determina la razón de por qué una transacción es anómala."""
        reasons = []

        # 1. Monto inusualmente alto
        categoria_id = transaction.subcategory_id or "sin_categoria"
        stats = self.category_stats.get(categoria_id)

        if stats:
            monto = float(transaction.monto_crc)
            mean = stats["mean"]
            std = stats["std"]

            if monto > mean + (2 * std):
                reasons.append(f"Monto alto para esta categoría (₡{monto:,.0f} vs promedio ₡{mean:,.0f})")
            elif monto < mean - (2 * std):
                reasons.append(f"Monto bajo inusual (₡{monto:,.0f} vs promedio ₡{mean:,.0f})")

        # 2. Horario inusual
        hora = transaction.fecha_transaccion.hour
        if hora < 6 or hora > 23:
            reasons.append(f"Horario inusual ({hora:02d}:00)")

        # 3. Transacción internacional
        if transaction.es_internacional:
            reasons.append(f"Transacción internacional ({transaction.pais})")

        # 4. Categoría nueva
        if transaction.subcategory_id and transaction.subcategory_id not in self.category_encoder:
            reasons.append("Categoría nunca vista antes")

        # 5. Si no hay razones específicas
        if not reasons:
            reasons.append(f"Patrón inusual detectado (score: {score:.4f})")

        return "; ".join(reasons)

    def _save_model(self) -> None:
        """Guarda el modelo entrenado."""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.model_path, "wb") as f:
            pickle.dump(
                {
                    "model": self.model,
                    "category_encoder": self.category_encoder,
                    "category_stats": self.category_stats,
                },
                f,
            )

    def _load_model(self) -> None:
        """Carga el modelo guardado."""
        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
                self.model = data["model"]
                self.category_encoder = data["category_encoder"]
                self.category_stats = data["category_stats"]
        except (FileNotFoundError, pickle.PickleError, KeyError) as e:
            logger.error(f"Error cargando modelo: {e}")
            self.model = None
