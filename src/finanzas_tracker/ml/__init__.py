"""ML Package - Modelos de Machine Learning para Finanzas.

Este paquete contiene:
- models.py: Modelos PyTorch (LSTM, Transformer, Classifier)
- predictor.py: Servicio de predicción de gastos
- trainer.py: Entrenamiento de modelos
- population.py: Análisis poblacional agregado
"""

from finanzas_tracker.ml.models import (
    PYTORCH_AVAILABLE,
    FinancialFeatureExtractor,
    FinancialModelTrainer,
    SpendingWindow,
    TransactionFeatures,
    check_pytorch_availability,
)

# Solo exportar modelos si PyTorch está disponible
if PYTORCH_AVAILABLE:
    from finanzas_tracker.ml.models import (
        SpendingLSTM,
        SpendingTransformer,
        TransactionClassifier,
    )

__all__ = [
    "PYTORCH_AVAILABLE",
    "check_pytorch_availability",
    "FinancialFeatureExtractor",
    "FinancialModelTrainer",
    "TransactionFeatures",
    "SpendingWindow",
]

if PYTORCH_AVAILABLE:
    __all__.extend([
        "TransactionClassifier",
        "SpendingLSTM", 
        "SpendingTransformer",
    ])
