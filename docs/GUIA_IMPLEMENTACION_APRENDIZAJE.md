# 🔧 Guía Técnica de Implementación - Sistema de Aprendizaje

## Resumen Rápido

**Objetivo:** Sistema de categorización que aprende de usuarios SIN pagar por APIs caras.

**Stack Gratuito:**
- `SentenceTransformers` (embeddings locales, gratis)
- `PostgreSQL + pgvector` (vector search, gratis)
- `Render/Railway` (hosting free tier)
- `Claude API` (solo 2% de casos, ~$0.01/mes para 10 usuarios)

---

## 1. Migrar a Embeddings Locales (SentenceTransformers)

### Instalación

```bash
poetry add sentence-transformers
```

### Nuevo EmbeddingService (Reemplaza Voyage AI)

```python
# src/finanzas_tracker/services/embedding_service.py

from sentence_transformers import SentenceTransformer
import numpy as np
from functools import lru_cache


class LocalEmbeddingService:
    """
    Servicio de embeddings usando SentenceTransformers (100% gratis).
    
    Modelo: all-MiniLM-L6-v2
    - Tamaño: 80MB
    - Dimensiones: 384
    - Idiomas: Multilingüe (incluye español)
    - Velocidad: ~14,000 sentencias/segundo en CPU
    """
    
    _instance = None
    _model = None
    
    def __new__(cls):
        """Singleton para no cargar el modelo múltiples veces."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self) -> None:
        if LocalEmbeddingService._model is None:
            # Cargar modelo una sola vez (toma ~2 segundos la primera vez)
            LocalEmbeddingService._model = SentenceTransformer(
                'sentence-transformers/all-MiniLM-L6-v2'
            )
    
    @property
    def model(self) -> SentenceTransformer:
        return LocalEmbeddingService._model
    
    @property
    def embedding_dimension(self) -> int:
        return 384  # Dimensión fija de all-MiniLM-L6-v2
    
    def embed_text(self, text: str) -> list[float]:
        """
        Genera embedding para un texto.
        
        Args:
            text: Descripción de transacción
            
        Returns:
            Vector de 384 dimensiones
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()
    
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Genera embeddings para múltiples textos (más eficiente).
        
        Args:
            texts: Lista de descripciones
            
        Returns:
            Lista de vectores
        """
        embeddings = self.model.encode(texts, convert_to_numpy=True)
        return embeddings.tolist()
    
    def similarity(self, text1: str, text2: str) -> float:
        """
        Calcula similitud coseno entre dos textos.
        
        Returns:
            Valor entre 0 y 1 (1 = idénticos)
        """
        embeddings = self.model.encode([text1, text2])
        similarity = np.dot(embeddings[0], embeddings[1]) / (
            np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1])
        )
        return float(similarity)


# Instancia global (singleton)
embedding_service = LocalEmbeddingService()
```

### Uso

```python
from src.finanzas_tracker.services.embedding_service import embedding_service

# Embedding de una transacción
vector = embedding_service.embed_text("AUTOMERCADO ESCAZU CRC 45000")

# Batch para eficiencia
vectors = embedding_service.embed_batch([
    "UBER *TRIP",
    "NETFLIX.COM",
    "SINPE MAMA ROSA"
])

# Similitud
sim = embedding_service.similarity("SINPE MAMA ROSA", "SINPE PAPA CARLOS")
# → ~0.85 (alta similitud, ambos son SINPE familiares)
```

---

## 2. Tablas de Aprendizaje

### Migración Alembic

```python
# alembic/versions/xxx_add_learning_tables.py

"""add learning tables for categorization

Revision ID: xxx
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from pgvector.sqlalchemy import Vector


def upgrade() -> None:
    # Tabla 1: Preferencias de comercio por usuario
    op.create_table(
        'user_merchant_preferences',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),  # NULL = global
        sa.Column('profile_id', UUID(as_uuid=True), sa.ForeignKey('profiles.id'), nullable=True),
        sa.Column('merchant_pattern', sa.String(200), nullable=False),
        sa.Column('subcategory_id', UUID(as_uuid=True), sa.ForeignKey('subcategories.id'), nullable=False),
        sa.Column('times_used', sa.Integer, default=1),
        sa.Column('confidence', sa.Numeric(3, 2), default=0.95),
        sa.Column('source', sa.String(50), default='user_correction'),  # user_correction, auto_detected
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_user_merchant_pattern', 'user_merchant_preferences', ['user_id', 'merchant_pattern'])
    
    # Tabla 2: Contactos SINPE aprendidos
    op.create_table(
        'user_contacts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('user_id', UUID(as_uuid=True), nullable=True),
        sa.Column('profile_id', UUID(as_uuid=True), sa.ForeignKey('profiles.id'), nullable=True),
        sa.Column('phone_number', sa.String(20)),  # 8888-1234
        sa.Column('sinpe_name', sa.String(200)),  # Nombre que aparece en SINPE
        sa.Column('alias', sa.String(100)),  # Nombre que el usuario le pone
        sa.Column('default_subcategory_id', UUID(as_uuid=True), sa.ForeignKey('subcategories.id')),
        sa.Column('relationship_type', sa.String(50)),  # family, friend, business, service
        sa.Column('total_transactions', sa.Integer, default=0),
        sa.Column('total_amount_crc', sa.Numeric(15, 2), default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_user_contacts_phone', 'user_contacts', ['user_id', 'phone_number'], unique=True)
    
    # Tabla 3: Sugerencias globales (crowdsourced)
    op.create_table(
        'global_merchant_suggestions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('merchant_pattern', sa.String(200), nullable=False),
        sa.Column('suggested_subcategory_id', UUID(as_uuid=True), sa.ForeignKey('subcategories.id'), nullable=False),
        sa.Column('user_count', sa.Integer, default=1),
        sa.Column('confidence_score', sa.Numeric(3, 2)),
        sa.Column('status', sa.String(20), default='pending'),  # pending, approved, rejected
        sa.Column('approved_by', UUID(as_uuid=True)),  # Admin que aprobó
        sa.Column('approved_at', sa.DateTime),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_global_merchant_pattern', 'global_merchant_suggestions', ['merchant_pattern', 'suggested_subcategory_id'], unique=True)
    
    # Tabla 4: Embeddings de transacciones (para similarity search)
    op.create_table(
        'transaction_embeddings',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('transaction_id', sa.Integer, sa.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('embedding', Vector(384), nullable=False),  # all-MiniLM-L6-v2 dimension
        sa.Column('comercio_normalizado', sa.String(200)),  # Texto limpio usado para embedding
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    
    # Índice para búsqueda de similitud eficiente
    op.execute('''
        CREATE INDEX ix_transaction_embeddings_vector 
        ON transaction_embeddings 
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    ''')


def downgrade() -> None:
    op.drop_table('transaction_embeddings')
    op.drop_table('global_merchant_suggestions')
    op.drop_table('user_contacts')
    op.drop_table('user_merchant_preferences')
```

---

## 3. Modelos SQLAlchemy

```python
# src/finanzas_tracker/models/learning.py

from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
import uuid

from src.finanzas_tracker.core.database import Base


class UserMerchantPreference(Base):
    """Preferencias de categorización por usuario."""
    
    __tablename__ = "user_merchant_preferences"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=True)
    merchant_pattern = Column(String(200), nullable=False)
    subcategory_id = Column(UUID(as_uuid=True), ForeignKey("subcategories.id"), nullable=False)
    times_used = Column(Integer, default=1)
    confidence = Column(Numeric(3, 2), default=0.95)
    source = Column(String(50), default="user_correction")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    subcategory = relationship("Subcategory")
    profile = relationship("Profile")


class UserContact(Base):
    """Contactos SINPE aprendidos del usuario."""
    
    __tablename__ = "user_contacts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    profile_id = Column(UUID(as_uuid=True), ForeignKey("profiles.id"), nullable=True)
    phone_number = Column(String(20))
    sinpe_name = Column(String(200))  # "ROSA MARIA CRUZ VARGAS"
    alias = Column(String(100))  # "Mamá"
    default_subcategory_id = Column(UUID(as_uuid=True), ForeignKey("subcategories.id"))
    relationship_type = Column(String(50))  # family, friend, business
    total_transactions = Column(Integer, default=0)
    total_amount_crc = Column(Numeric(15, 2), default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    default_subcategory = relationship("Subcategory")
    profile = relationship("Profile")


class GlobalMerchantSuggestion(Base):
    """Sugerencias de categorización crowdsourced."""
    
    __tablename__ = "global_merchant_suggestions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merchant_pattern = Column(String(200), nullable=False)
    suggested_subcategory_id = Column(UUID(as_uuid=True), ForeignKey("subcategories.id"), nullable=False)
    user_count = Column(Integer, default=1)
    confidence_score = Column(Numeric(3, 2))
    status = Column(String(20), default="pending")
    approved_by = Column(UUID(as_uuid=True))
    approved_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    suggested_subcategory = relationship("Subcategory")
    
    @property
    def is_approved(self) -> bool:
        return self.status == "approved"
    
    @property
    def should_auto_approve(self) -> bool:
        """Auto-aprobar si 5+ usuarios sugirieron lo mismo."""
        return self.user_count >= 5 and self.confidence_score >= 0.90


class TransactionEmbedding(Base):
    """Embeddings para búsqueda de similitud."""
    
    __tablename__ = "transaction_embeddings"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(Integer, ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, unique=True)
    embedding = Column(Vector(384), nullable=False)
    comercio_normalizado = Column(String(200))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    transaction = relationship("Transaction")
```

---

## 4. Servicio de Feedback Loop

```python
# src/finanzas_tracker/services/feedback_service.py

from sqlalchemy.orm import Session
from sqlalchemy import select, func
from typing import Optional
import re
import logging

from src.finanzas_tracker.models.learning import (
    UserMerchantPreference,
    UserContact,
    GlobalMerchantSuggestion,
    TransactionEmbedding,
)
from src.finanzas_tracker.models.transaction import Transaction
from src.finanzas_tracker.models.subcategory import Subcategory
from src.finanzas_tracker.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)


class FeedbackService:
    """
    Servicio de aprendizaje continuo.
    
    Cuando un usuario corrige una categorización:
    1. Guarda la preferencia del usuario
    2. Actualiza el embedding de la transacción
    3. Propone mejora global si hay consenso
    """
    
    def __init__(self, db: Session) -> None:
        self.db = db
    
    def record_correction(
        self,
        transaction_id: int,
        new_subcategory_id: str,
        user_id: str | None = None,
        profile_id: str | None = None,
    ) -> None:
        """
        Registra cuando un usuario corrige una categorización.
        
        Args:
            transaction_id: ID de la transacción corregida
            new_subcategory_id: Nueva categoría correcta
            user_id: ID del usuario (opcional)
            profile_id: ID del perfil (opcional)
        """
        # 1. Obtener transacción
        transaction = self.db.execute(
            select(Transaction).where(Transaction.id == transaction_id)
        ).scalar_one_or_none()
        
        if not transaction:
            logger.error(f"Transacción {transaction_id} no encontrada")
            return
        
        # 2. Crear patrón del comercio
        merchant_pattern = self._create_merchant_pattern(transaction.comercio)
        
        # 3. Guardar preferencia del usuario
        self._save_user_preference(
            user_id=user_id,
            profile_id=profile_id,
            merchant_pattern=merchant_pattern,
            subcategory_id=new_subcategory_id,
        )
        
        # 4. Actualizar la transacción
        transaction.subcategory_id = new_subcategory_id
        transaction.categoria_confirmada_usuario = True
        transaction.necesita_revision = False
        
        # 5. Actualizar embedding
        self._update_embedding(transaction)
        
        # 6. Proponer mejora global
        self._propose_global_improvement(
            merchant_pattern=merchant_pattern,
            subcategory_id=new_subcategory_id,
        )
        
        # 7. Si es SINPE, aprender el contacto
        if "SINPE" in transaction.comercio.upper():
            self._learn_sinpe_contact(
                transaction=transaction,
                user_id=user_id,
                profile_id=profile_id,
                subcategory_id=new_subcategory_id,
            )
        
        self.db.commit()
        logger.info(f"Corrección registrada: {merchant_pattern} → {new_subcategory_id}")
    
    def _create_merchant_pattern(self, comercio: str) -> str:
        """
        Crea un patrón generalizable del comercio.
        
        Ej: "SINPE MARIA ROSA CRUZ" → "SINPE MARIA%"
            "UBER *TRIP 12345" → "UBER%"
            "AUTOMERCADO ESCAZU" → "AUTOMERCADO%"
        """
        comercio = comercio.upper().strip()
        
        # Remover códigos de referencia
        comercio = re.sub(r'\b[A-Z0-9]{8,}\b', '', comercio)
        comercio = re.sub(r'\*\w+', '', comercio)
        
        # Para SINPE, mantener nombre pero generalizar
        if comercio.startswith("SINPE"):
            parts = comercio.split()
            if len(parts) >= 2:
                return f"SINPE {parts[1]}%"
            return "SINPE%"
        
        # Para otros, tomar primera palabra significativa
        words = comercio.split()
        if words:
            return f"{words[0]}%"
        
        return comercio
    
    def _save_user_preference(
        self,
        user_id: str | None,
        profile_id: str | None,
        merchant_pattern: str,
        subcategory_id: str,
    ) -> None:
        """Guarda o actualiza preferencia del usuario."""
        # Buscar si ya existe
        existing = self.db.execute(
            select(UserMerchantPreference).where(
                UserMerchantPreference.user_id == user_id,
                UserMerchantPreference.merchant_pattern == merchant_pattern,
            )
        ).scalar_one_or_none()
        
        if existing:
            # Actualizar
            existing.subcategory_id = subcategory_id
            existing.times_used += 1
            existing.confidence = min(0.99, existing.confidence + 0.01)
        else:
            # Crear nuevo
            preference = UserMerchantPreference(
                user_id=user_id,
                profile_id=profile_id,
                merchant_pattern=merchant_pattern,
                subcategory_id=subcategory_id,
            )
            self.db.add(preference)
    
    def _update_embedding(self, transaction: Transaction) -> None:
        """Actualiza o crea embedding de la transacción."""
        comercio_norm = transaction.comercio.lower().strip()
        vector = embedding_service.embed_text(comercio_norm)
        
        existing = self.db.execute(
            select(TransactionEmbedding).where(
                TransactionEmbedding.transaction_id == transaction.id
            )
        ).scalar_one_or_none()
        
        if existing:
            existing.embedding = vector
            existing.comercio_normalizado = comercio_norm
        else:
            emb = TransactionEmbedding(
                transaction_id=transaction.id,
                embedding=vector,
                comercio_normalizado=comercio_norm,
            )
            self.db.add(emb)
    
    def _propose_global_improvement(
        self,
        merchant_pattern: str,
        subcategory_id: str,
    ) -> None:
        """Propone mejora global si hay suficiente consenso."""
        # Buscar si ya existe sugerencia
        existing = self.db.execute(
            select(GlobalMerchantSuggestion).where(
                GlobalMerchantSuggestion.merchant_pattern == merchant_pattern,
                GlobalMerchantSuggestion.suggested_subcategory_id == subcategory_id,
            )
        ).scalar_one_or_none()
        
        if existing:
            existing.user_count += 1
            existing.confidence_score = min(0.99, 0.70 + (existing.user_count * 0.05))
            
            # Auto-aprobar si hay consenso
            if existing.should_auto_approve and existing.status == "pending":
                existing.status = "approved"
                existing.approved_at = func.now()
                logger.info(f"Auto-aprobada sugerencia global: {merchant_pattern}")
        else:
            suggestion = GlobalMerchantSuggestion(
                merchant_pattern=merchant_pattern,
                suggested_subcategory_id=subcategory_id,
                confidence_score=0.75,
            )
            self.db.add(suggestion)
    
    def _learn_sinpe_contact(
        self,
        transaction: Transaction,
        user_id: str | None,
        profile_id: str | None,
        subcategory_id: str,
    ) -> None:
        """Aprende un contacto SINPE del usuario."""
        # Extraer nombre del SINPE
        match = re.search(r'SINPE\s+(.+)', transaction.comercio.upper())
        if not match:
            return
        
        sinpe_name = match.group(1).strip()
        
        # Buscar si ya existe
        existing = self.db.execute(
            select(UserContact).where(
                UserContact.user_id == user_id,
                UserContact.sinpe_name.ilike(f"%{sinpe_name[:10]}%"),
            )
        ).scalar_one_or_none()
        
        if existing:
            existing.total_transactions += 1
            existing.total_amount_crc += transaction.monto_crc or 0
            if not existing.default_subcategory_id:
                existing.default_subcategory_id = subcategory_id
        else:
            contact = UserContact(
                user_id=user_id,
                profile_id=profile_id,
                sinpe_name=sinpe_name,
                default_subcategory_id=subcategory_id,
                total_transactions=1,
                total_amount_crc=transaction.monto_crc or 0,
            )
            self.db.add(contact)


# Función helper para usar desde el dashboard
def record_user_correction(
    db: Session,
    transaction_id: int,
    new_subcategory_id: str,
    user_id: str | None = None,
    profile_id: str | None = None,
) -> None:
    """Helper para registrar corrección desde cualquier parte de la app."""
    service = FeedbackService(db)
    service.record_correction(
        transaction_id=transaction_id,
        new_subcategory_id=new_subcategory_id,
        user_id=user_id,
        profile_id=profile_id,
    )
```

---

## 5. Integración en SmartCategorizer

Agregar búsqueda de preferencias de usuario como primera capa:

```python
# En SmartCategorizer._layer1_deterministic()

def _layer1_deterministic(
    self,
    comercio: str,
    monto: float,
    profile_id: str | None,
    user_id: str | None = None,  # NUEVO
) -> CategorizationResult | None:
    """
    Capa 1: Reglas determinísticas.
    
    Orden de prioridad:
    1. Preferencias del usuario (máxima prioridad)
    2. Contactos SINPE aprendidos
    3. Base de datos de comercios de CR
    4. Patrones SINPE genéricos
    5. Keywords de subcategorías
    """
    clean_comercio = self._clean_merchant_name(comercio)
    
    # 1. NUEVO: Buscar en preferencias del usuario
    if user_id or profile_id:
        user_pref = self._check_user_preferences(
            comercio=comercio,
            user_id=user_id,
            profile_id=profile_id,
        )
        if user_pref:
            return user_pref
    
    # 2. NUEVO: Buscar en contactos SINPE
    if "SINPE" in comercio.upper():
        contact_match = self._check_sinpe_contacts(
            comercio=comercio,
            user_id=user_id,
            profile_id=profile_id,
        )
        if contact_match:
            return contact_match
    
    # 3. Resto de la lógica existente...
    # (merchant_db, sinpe patterns, keywords)
```

---

## 6. Costos Reales Calculados

### Para 10 usuarios de prueba:

```
Transacciones/mes: 10 usuarios × 100 txn = 1,000 txn

Capa 1 (reglas): ~900 txn → $0
Capa 2 (embeddings locales): ~80 txn → $0
Capa 3 (Claude): ~20 txn → 20 × 500 tokens × $0.00025/1K = $0.0025

Hosting (Render free tier): $0
PostgreSQL (Render free): $0

TOTAL: ~$0.01/mes
```

### Para 100 usuarios:

```
Transacciones/mes: 10,000 txn
Claude calls: ~200 txn → $0.025
Hosting (Render Starter): $9
PostgreSQL (Render Basic): $6

TOTAL: ~$15/mes
```

---

## 7. Checklist de Implementación

### Semana 1
- [ ] Instalar `sentence-transformers`
- [ ] Crear `LocalEmbeddingService`
- [ ] Crear migración para tablas de aprendizaje
- [ ] Crear modelos SQLAlchemy
- [ ] Implementar `FeedbackService`

### Semana 2
- [ ] Integrar preferencias de usuario en SmartCategorizer
- [ ] Agregar endpoint API para correcciones
- [ ] UI en dashboard para corregir categorías
- [ ] Tests unitarios

### Semana 3
- [ ] Batch embedding de transacciones históricas
- [ ] Similarity search con pgvector
- [ ] Métricas de accuracy
- [ ] Logging de aprendizaje

### Semana 4
- [ ] Deploy en Render free tier
- [ ] Configurar variables de entorno
- [ ] Monitoreo básico
- [ ] 10 usuarios de prueba

---

## 8. Comandos Útiles

```bash
# Instalar dependencias
poetry add sentence-transformers pgvector

# Crear migración
poetry run alembic revision --autogenerate -m "add learning tables"

# Aplicar migración
poetry run alembic upgrade head

# Test embeddings locales
poetry run python -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
print(model.encode('AUTOMERCADO ESCAZU').shape)  # (384,)
"

# Benchmark velocidad
poetry run python -c "
import time
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')
texts = ['Test ' + str(i) for i in range(1000)]
start = time.time()
model.encode(texts, batch_size=32)
print(f'1000 embeddings en {time.time()-start:.2f}s')
"
# → ~0.5-1 segundo para 1000 embeddings
```

---

*Documento técnico para Finanzas Tracker CR - Diciembre 2025*
