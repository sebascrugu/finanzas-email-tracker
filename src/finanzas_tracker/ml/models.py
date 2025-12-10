"""Modelos de Deep Learning para Predicción Financiera.

Este módulo implementa modelos avanzados de ML usando PyTorch:
1. TransactionClassifier - Clasificación de transacciones con embeddings
2. SpendingPredictor - Predicción de gastos futuros con LSTM/Transformer
3. AnomalyDetector - Detección de anomalías en patrones de gasto
4. UserEmbedding - Embeddings de comportamiento financiero de usuarios

Arquitectura:
- PyTorch para modelos
- sentence-transformers para embeddings de texto
- LSTM/Transformer para secuencias temporales
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import numpy as np

# Importaciones opcionales de PyTorch
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, Dataset
    PYTORCH_AVAILABLE = True
except ImportError:
    PYTORCH_AVAILABLE = False
    torch = None
    nn = None

from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class TransactionFeatures:
    """Features extraídas de una transacción para ML."""
    
    # Embeddings de texto (384 dims para MiniLM)
    merchant_embedding: np.ndarray
    
    # Features numéricas
    amount_normalized: float  # Normalizado 0-1
    amount_log: float  # log(amount) para manejar outliers
    
    # Features temporales (cíclicas)
    hour_sin: float
    hour_cos: float
    day_of_week_sin: float
    day_of_week_cos: float
    day_of_month_sin: float
    day_of_month_cos: float
    month_sin: float
    month_cos: float
    
    # Features categóricas (one-hot encoded)
    transaction_type: np.ndarray  # One-hot de tipo
    currency: np.ndarray  # One-hot de moneda
    
    # Contexto
    is_weekend: float
    is_holiday: float  # Feriados CR
    days_since_last_transaction: float
    
    def to_tensor(self) -> "torch.Tensor":
        """Convierte a tensor de PyTorch."""
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch no está instalado")
        
        # Concatenar todas las features
        features = np.concatenate([
            self.merchant_embedding,
            np.array([
                self.amount_normalized,
                self.amount_log,
                self.hour_sin, self.hour_cos,
                self.day_of_week_sin, self.day_of_week_cos,
                self.day_of_month_sin, self.day_of_month_cos,
                self.month_sin, self.month_cos,
                self.is_weekend,
                self.is_holiday,
                self.days_since_last_transaction,
            ]),
            self.transaction_type,
            self.currency,
        ])
        
        return torch.tensor(features, dtype=torch.float32)


@dataclass  
class SpendingWindow:
    """Ventana temporal de gastos para predicción."""
    
    # Secuencia de features (N transacciones x features)
    transaction_features: list[TransactionFeatures]
    
    # Agregaciones de la ventana
    total_spent: float
    avg_transaction: float
    num_transactions: int
    unique_merchants: int
    
    # Distribución por categoría
    category_distribution: np.ndarray  # Proporción por categoría
    
    # Target (para entrenamiento)
    next_day_spending: float | None = None
    next_week_spending: float | None = None
    next_category: int | None = None


# ============================================================================
# Feature Engineering
# ============================================================================

class FinancialFeatureExtractor:
    """Extrae features de transacciones para modelos ML."""
    
    # Feriados de Costa Rica (fechas fijas)
    CR_HOLIDAYS = [
        (1, 1),   # Año Nuevo
        (4, 11),  # Juan Santamaría
        (5, 1),   # Día del Trabajo
        (7, 25),  # Anexión de Guanacaste
        (8, 2),   # Virgen de los Ángeles
        (8, 15),  # Día de la Madre
        (9, 15),  # Independencia
        (10, 12), # Día de las Culturas
        (12, 25), # Navidad
    ]
    
    # Tipos de transacción conocidos
    TRANSACTION_TYPES = [
        "compra", "transferencia", "retiro", "pago", 
        "deposito", "sinpe", "quasi_cash", "otro"
    ]
    
    # Monedas soportadas
    CURRENCIES = ["CRC", "USD"]
    
    def __init__(self):
        self.embedding_service = None
        self._init_embedding_service()
        
        # Estadísticas para normalización (se actualizan con datos)
        self.amount_mean = 10000.0  # Promedio inicial estimado en CRC
        self.amount_std = 20000.0
        self.amount_max = 500000.0
    
    def _init_embedding_service(self) -> None:
        """Inicializa servicio de embeddings."""
        try:
            from finanzas_tracker.services.local_embedding_service import LocalEmbeddingService
            self.embedding_service = LocalEmbeddingService()
            logger.info("Servicio de embeddings inicializado para features")
        except Exception as e:
            logger.warning(f"No se pudo inicializar embeddings: {e}")
    
    def extract_features(
        self,
        merchant: str,
        amount: float,
        transaction_date: datetime,
        transaction_type: str = "compra",
        currency: str = "CRC",
        last_transaction_date: datetime | None = None,
    ) -> TransactionFeatures:
        """Extrae features de una transacción."""
        
        # 1. Embedding del comercio
        if self.embedding_service:
            merchant_embedding = self.embedding_service.embed_text(merchant)
        else:
            merchant_embedding = np.zeros(384)  # Placeholder
        
        # 2. Normalizar monto
        amount_normalized = min(amount / self.amount_max, 1.0)
        amount_log = np.log1p(amount)  # log(1 + amount) para manejar 0
        
        # 3. Features temporales cíclicas
        hour = transaction_date.hour
        hour_sin = np.sin(2 * np.pi * hour / 24)
        hour_cos = np.cos(2 * np.pi * hour / 24)
        
        dow = transaction_date.weekday()
        dow_sin = np.sin(2 * np.pi * dow / 7)
        dow_cos = np.cos(2 * np.pi * dow / 7)
        
        dom = transaction_date.day
        dom_sin = np.sin(2 * np.pi * dom / 31)
        dom_cos = np.cos(2 * np.pi * dom / 31)
        
        month = transaction_date.month
        month_sin = np.sin(2 * np.pi * month / 12)
        month_cos = np.cos(2 * np.pi * month / 12)
        
        # 4. Weekend
        is_weekend = 1.0 if dow >= 5 else 0.0
        
        # 5. Feriado
        is_holiday = 1.0 if (transaction_date.month, transaction_date.day) in self.CR_HOLIDAYS else 0.0
        
        # 6. Días desde última transacción
        if last_transaction_date:
            days_since = (transaction_date - last_transaction_date).days
            days_since_normalized = min(days_since / 30.0, 1.0)  # Normalizar a 30 días
        else:
            days_since_normalized = 0.5  # Valor neutral
        
        # 7. One-hot transaction type
        type_idx = self.TRANSACTION_TYPES.index(transaction_type) if transaction_type in self.TRANSACTION_TYPES else -1
        transaction_type_onehot = np.zeros(len(self.TRANSACTION_TYPES))
        if type_idx >= 0:
            transaction_type_onehot[type_idx] = 1.0
        
        # 8. One-hot currency
        curr_idx = self.CURRENCIES.index(currency) if currency in self.CURRENCIES else 0
        currency_onehot = np.zeros(len(self.CURRENCIES))
        currency_onehot[curr_idx] = 1.0
        
        return TransactionFeatures(
            merchant_embedding=merchant_embedding,
            amount_normalized=amount_normalized,
            amount_log=amount_log,
            hour_sin=hour_sin,
            hour_cos=hour_cos,
            day_of_week_sin=dow_sin,
            day_of_week_cos=dow_cos,
            day_of_month_sin=dom_sin,
            day_of_month_cos=dom_cos,
            month_sin=month_sin,
            month_cos=month_cos,
            transaction_type=transaction_type_onehot,
            currency=currency_onehot,
            is_weekend=is_weekend,
            is_holiday=is_holiday,
            days_since_last_transaction=days_since_normalized,
        )
    
    def create_spending_window(
        self,
        transactions: list[dict],
        window_days: int = 30,
        num_categories: int = 12,
    ) -> SpendingWindow:
        """Crea una ventana temporal de gastos."""
        
        features_list = []
        last_date = None
        
        for txn in transactions:
            features = self.extract_features(
                merchant=txn.get("comercio", ""),
                amount=float(txn.get("monto_crc", 0)),
                transaction_date=txn.get("fecha_transaccion", datetime.now()),
                transaction_type=txn.get("tipo_transaccion", "compra"),
                currency=txn.get("moneda_original", "CRC"),
                last_transaction_date=last_date,
            )
            features_list.append(features)
            last_date = txn.get("fecha_transaccion")
        
        # Calcular agregaciones
        amounts = [float(t.get("monto_crc", 0)) for t in transactions]
        merchants = set(t.get("comercio", "") for t in transactions)
        
        # Distribución de categorías (placeholder)
        category_dist = np.zeros(num_categories)
        for txn in transactions:
            cat_idx = hash(txn.get("categoria_sugerida_por_ia", "")) % num_categories
            category_dist[cat_idx] += 1
        if category_dist.sum() > 0:
            category_dist = category_dist / category_dist.sum()
        
        return SpendingWindow(
            transaction_features=features_list,
            total_spent=sum(amounts),
            avg_transaction=np.mean(amounts) if amounts else 0.0,
            num_transactions=len(transactions),
            unique_merchants=len(merchants),
            category_distribution=category_dist,
        )


# ============================================================================
# Modelos PyTorch
# ============================================================================

if PYTORCH_AVAILABLE:
    
    class TransactionClassifier(nn.Module):
        """
        Clasificador de transacciones usando embeddings + MLP.
        
        Input: Transaction features (embedding + features numéricas)
        Output: Probabilidad por categoría
        """
        
        def __init__(
            self,
            input_dim: int = 410,  # 384 (embedding) + 26 (features)
            hidden_dims: list[int] = [256, 128, 64],
            num_categories: int = 12,
            dropout: float = 0.3,
        ):
            super().__init__()
            
            layers = []
            prev_dim = input_dim
            
            for hidden_dim in hidden_dims:
                layers.extend([
                    nn.Linear(prev_dim, hidden_dim),
                    nn.BatchNorm1d(hidden_dim),
                    nn.ReLU(),
                    nn.Dropout(dropout),
                ])
                prev_dim = hidden_dim
            
            layers.append(nn.Linear(prev_dim, num_categories))
            
            self.classifier = nn.Sequential(*layers)
        
        def forward(self, x: torch.Tensor) -> torch.Tensor:
            return self.classifier(x)
        
        def predict(self, x: torch.Tensor) -> torch.Tensor:
            """Retorna probabilidades (softmax)."""
            with torch.no_grad():
                logits = self.forward(x)
                return F.softmax(logits, dim=-1)
    
    
    class SpendingLSTM(nn.Module):
        """
        Predictor de gastos usando LSTM.
        
        Procesa secuencias de transacciones para predecir:
        1. Gasto del próximo día/semana
        2. Próxima categoría probable
        3. Patrones de comportamiento
        """
        
        def __init__(
            self,
            input_dim: int = 410,
            hidden_dim: int = 128,
            num_layers: int = 2,
            num_categories: int = 12,
            dropout: float = 0.3,
        ):
            super().__init__()
            
            self.lstm = nn.LSTM(
                input_size=input_dim,
                hidden_size=hidden_dim,
                num_layers=num_layers,
                batch_first=True,
                dropout=dropout if num_layers > 1 else 0,
                bidirectional=True,
            )
            
            # Heads para diferentes predicciones
            lstm_output_dim = hidden_dim * 2  # Bidireccional
            
            # Predicción de monto
            self.amount_head = nn.Sequential(
                nn.Linear(lstm_output_dim, 64),
                nn.ReLU(),
                nn.Linear(64, 1),
            )
            
            # Predicción de categoría
            self.category_head = nn.Sequential(
                nn.Linear(lstm_output_dim, 64),
                nn.ReLU(),
                nn.Linear(64, num_categories),
            )
            
            # Embedding de comportamiento
            self.behavior_head = nn.Linear(lstm_output_dim, 64)
        
        def forward(
            self, 
            x: torch.Tensor,
            lengths: torch.Tensor | None = None,
        ) -> dict[str, torch.Tensor]:
            """
            Args:
                x: (batch, seq_len, input_dim)
                lengths: longitudes reales de secuencias
            
            Returns:
                Dict con predicciones
            """
            # LSTM forward
            lstm_out, (hidden, cell) = self.lstm(x)
            
            # Usar último hidden state (concatenar direcciones)
            # hidden shape: (num_layers * 2, batch, hidden_dim)
            last_hidden = torch.cat([hidden[-2], hidden[-1]], dim=-1)
            
            return {
                "amount": self.amount_head(last_hidden).squeeze(-1),
                "category": self.category_head(last_hidden),
                "behavior_embedding": self.behavior_head(last_hidden),
            }
        
        def predict_next_spending(
            self, 
            x: torch.Tensor,
        ) -> dict[str, Any]:
            """Predice el próximo gasto."""
            with torch.no_grad():
                outputs = self.forward(x)
                
                amount = outputs["amount"].item()
                category_probs = F.softmax(outputs["category"], dim=-1)
                top_categories = torch.topk(category_probs, k=3)
                
                return {
                    "predicted_amount": amount,
                    "top_categories": top_categories.indices.tolist(),
                    "category_probabilities": top_categories.values.tolist(),
                    "behavior_embedding": outputs["behavior_embedding"].numpy(),
                }
    
    
    class SpendingTransformer(nn.Module):
        """
        Predictor de gastos usando Transformer.
        
        Más moderno que LSTM, mejor para capturar
        patrones complejos en secuencias.
        """
        
        def __init__(
            self,
            input_dim: int = 410,
            d_model: int = 128,
            nhead: int = 4,
            num_layers: int = 3,
            num_categories: int = 12,
            max_seq_len: int = 100,
            dropout: float = 0.1,
        ):
            super().__init__()
            
            self.input_projection = nn.Linear(input_dim, d_model)
            
            # Positional encoding
            self.pos_encoding = nn.Parameter(
                torch.randn(1, max_seq_len, d_model) * 0.1
            )
            
            # Transformer encoder
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_model,
                nhead=nhead,
                dim_feedforward=d_model * 4,
                dropout=dropout,
                activation='gelu',
                batch_first=True,
            )
            self.transformer = nn.TransformerEncoder(
                encoder_layer, 
                num_layers=num_layers
            )
            
            # Output heads
            self.amount_head = nn.Sequential(
                nn.Linear(d_model, 64),
                nn.GELU(),
                nn.Linear(64, 1),
            )
            
            self.category_head = nn.Sequential(
                nn.Linear(d_model, 64),
                nn.GELU(),
                nn.Linear(64, num_categories),
            )
            
            self.pattern_head = nn.Linear(d_model, 32)
        
        def forward(
            self, 
            x: torch.Tensor,
            mask: torch.Tensor | None = None,
        ) -> dict[str, torch.Tensor]:
            """
            Args:
                x: (batch, seq_len, input_dim)
                mask: attention mask
            
            Returns:
                Dict con predicciones
            """
            batch_size, seq_len, _ = x.shape
            
            # Project to d_model
            x = self.input_projection(x)
            
            # Add positional encoding
            x = x + self.pos_encoding[:, :seq_len, :]
            
            # Transformer forward
            transformer_out = self.transformer(x, src_key_padding_mask=mask)
            
            # Global pooling (mean over sequence)
            pooled = transformer_out.mean(dim=1)
            
            return {
                "amount": self.amount_head(pooled).squeeze(-1),
                "category": self.category_head(pooled),
                "pattern_embedding": self.pattern_head(pooled),
            }


# ============================================================================
# Trainer
# ============================================================================

class FinancialModelTrainer:
    """Entrena modelos de predicción financiera."""
    
    def __init__(
        self,
        model_type: str = "lstm",  # "lstm", "transformer", "classifier"
        device: str | None = None,
    ):
        if not PYTORCH_AVAILABLE:
            raise ImportError("PyTorch no está instalado. Ejecuta: pip install torch")
        
        self.device = device or ("mps" if torch.backends.mps.is_available() 
                                 else "cuda" if torch.cuda.is_available() 
                                 else "cpu")
        self.model_type = model_type
        self.model: nn.Module | None = None
        self.feature_extractor = FinancialFeatureExtractor()
        
        logger.info(f"Trainer inicializado - Modelo: {model_type}, Device: {self.device}")
    
    def create_model(self, **kwargs) -> nn.Module:
        """Crea el modelo según el tipo."""
        if self.model_type == "lstm":
            self.model = SpendingLSTM(**kwargs)
        elif self.model_type == "transformer":
            self.model = SpendingTransformer(**kwargs)
        elif self.model_type == "classifier":
            self.model = TransactionClassifier(**kwargs)
        else:
            raise ValueError(f"Tipo de modelo desconocido: {self.model_type}")
        
        self.model = self.model.to(self.device)
        return self.model
    
    def train(
        self,
        train_data: list[dict],
        val_data: list[dict] | None = None,
        epochs: int = 50,
        batch_size: int = 32,
        learning_rate: float = 0.001,
    ) -> dict[str, list[float]]:
        """Entrena el modelo."""
        if self.model is None:
            self.create_model()
        
        optimizer = torch.optim.AdamW(
            self.model.parameters(), 
            lr=learning_rate,
            weight_decay=0.01,
        )
        
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, 
            T_max=epochs
        )
        
        history = {"train_loss": [], "val_loss": []}
        
        for epoch in range(epochs):
            self.model.train()
            epoch_loss = 0.0
            
            # Training loop simplificado
            # En producción usaríamos DataLoader con batching apropiado
            
            # TODO: Implementar training loop completo
            
            scheduler.step()
            history["train_loss"].append(epoch_loss)
            
            if epoch % 10 == 0:
                logger.info(f"Epoch {epoch}/{epochs} - Loss: {epoch_loss:.4f}")
        
        return history
    
    def save_model(self, path: str | Path) -> None:
        """Guarda el modelo entrenado."""
        if self.model is None:
            raise ValueError("No hay modelo para guardar")
        
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "model_type": self.model_type,
        }, path)
        
        logger.info(f"Modelo guardado en: {path}")
    
    def load_model(self, path: str | Path) -> nn.Module:
        """Carga un modelo guardado."""
        path = Path(path)
        
        checkpoint = torch.load(path, map_location=self.device)
        self.model_type = checkpoint["model_type"]
        
        self.create_model()
        self.model.load_state_dict(checkpoint["model_state_dict"])
        self.model.eval()
        
        logger.info(f"Modelo cargado desde: {path}")
        return self.model


# ============================================================================
# Utilidades
# ============================================================================

def check_pytorch_availability() -> dict[str, Any]:
    """Verifica disponibilidad de PyTorch y GPUs."""
    result = {
        "pytorch_available": PYTORCH_AVAILABLE,
        "pytorch_version": None,
        "cuda_available": False,
        "mps_available": False,
        "device": "cpu",
    }
    
    if PYTORCH_AVAILABLE:
        result["pytorch_version"] = torch.__version__
        result["cuda_available"] = torch.cuda.is_available()
        result["mps_available"] = torch.backends.mps.is_available()
        
        if result["mps_available"]:
            result["device"] = "mps"  # Apple Silicon
        elif result["cuda_available"]:
            result["device"] = "cuda"
    
    return result
