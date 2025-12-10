"""Modelos avanzados para el Sistema de Aprendizaje Inteligente.

Este es el CORE del sistema de ML/Inteligencia del Finanzas Tracker.
Diseñado para:
1. Aprender patrones de cada usuario (personalizado)
2. Aprender patrones globales (crowdsourced)
3. Detectar clusters de transacciones similares
4. Almacenar embeddings para búsqueda semántica
5. Soportar datos para Costa Rica (SINPE, BAC, Popular)

Stack:
- PostgreSQL 16 + pgvector para vector similarity search
- Embeddings: OpenAI text-embedding-3-small (1536 dims) o modelo local
- Clustering: K-means sobre embeddings para agrupar transacciones similares
- Búsqueda: Cosine similarity con índice HNSW

Arquitectura de 4 capas de aprendizaje:
1. Usuario Individual: Sus patrones personales
2. Perfil Financiero: Clustering de usuarios similares
3. Global Costa Rica: Patrones de todos los usuarios CR
4. Conocimiento Base: Comercios conocidos (Automercado, Uber, etc.)
"""

__all__ = [
    "TransactionPattern",
    "UserLearningProfile",
    "GlobalPattern",
    "PatternCluster",
    "LearningEvent",
]

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from finanzas_tracker.core.database import Base


if TYPE_CHECKING:
    from finanzas_tracker.models.category import Subcategory
    from finanzas_tracker.models.profile import Profile


class PatternType(str, Enum):
    """Tipos de patrones que el sistema puede aprender."""
    BENEFICIARIO = "beneficiario"  # Patrón por nombre del beneficiario SINPE
    COMERCIO = "comercio"  # Patrón por nombre del comercio
    DESCRIPCION = "descripcion"  # Patrón por descripción/concepto
    MONTO = "monto"  # Patrón por rango de monto
    RECURRENTE = "recurrente"  # Patrón de transacción recurrente
    COMBINADO = "combinado"  # Combinación de múltiples señales


class PatternSource(str, Enum):
    """Origen del patrón aprendido."""
    USER_EXPLICIT = "user_explicit"  # Usuario lo categorizó manualmente
    USER_CONFIRMED = "user_confirmed"  # Usuario confirmó sugerencia
    AUTO_DETECTED = "auto_detected"  # Sistema lo detectó automáticamente
    CROWDSOURCED = "crowdsourced"  # Múltiples usuarios coinciden
    IMPORTED = "imported"  # Importado de base de conocimiento


class LearningEventType(str, Enum):
    """Tipos de eventos de aprendizaje."""
    CATEGORIZATION = "categorization"  # Usuario categoriza transacción
    CORRECTION = "correction"  # Usuario corrige categoría incorrecta
    CONFIRMATION = "confirmation"  # Usuario confirma sugerencia
    REJECTION = "rejection"  # Usuario rechaza sugerencia
    ALIAS_CREATED = "alias_created"  # Usuario crea alias (ej: "Mamá")
    PATTERN_MERGED = "pattern_merged"  # Patrones similares fueron fusionados


class TransactionPattern(Base):
    """
    Patrón aprendido de transacciones.
    
    CORE del sistema de aprendizaje. Cada patrón representa una regla
    que el sistema ha aprendido para categorizar automáticamente.
    
    Ejemplo:
    - pattern_text: "JUAN PEREZ MORA"
    - pattern_type: "beneficiario"
    - subcategory: "Personal > Préstamos Familiares"
    - user_label: "Papá"
    - confidence: 0.95
    
    Cuando una nueva transacción tiene beneficiario similar,
    se usa este patrón para sugerir categoría.
    """

    __tablename__ = "transaction_patterns"

    # Identificadores
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Scope del patrón
    profile_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=True,  # NULL = patrón global
        index=True,
    )
    is_global: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="True = aplica a todos los usuarios",
    )

    # El patrón en sí
    pattern_text: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Texto del patrón (beneficiario, comercio, descripción)",
    )
    pattern_text_normalized: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Texto normalizado (uppercase, sin acentos)",
    )
    pattern_type: Mapped[PatternType] = mapped_column(
        SQLEnum(PatternType, name="pattern_type_enum"),
        nullable=False,
    )
    
    # Embedding del patrón para similarity search
    # Usamos 1536 dims para compatibilidad con OpenAI text-embedding-3-small
    # Si usamos modelo local, se regenera con las dimensiones correctas
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536),  # OpenAI text-embedding-3-small
        nullable=True,
        comment="Vector embedding para similarity search",
    )
    embedding_model: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default="text-embedding-3-small",
    )

    # Categorización
    subcategory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("subcategories.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Metadatos del usuario
    user_label: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Etiqueta del usuario (ej: 'Mamá', 'Casero')",
    )
    user_description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Descripción del usuario sobre qué es esto",
    )

    # Métricas de confianza
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.9000"),
        comment="Confianza de 0 a 1",
    )
    times_matched: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Veces que este patrón ha matcheado",
    )
    times_confirmed: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Veces que usuario confirmó la sugerencia",
    )
    times_rejected: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Veces que usuario rechazó la sugerencia",
    )
    
    # Origen del patrón
    source: Mapped[PatternSource] = mapped_column(
        SQLEnum(PatternSource, name="pattern_source_enum"),
        default=PatternSource.USER_EXPLICIT,
    )

    # Estadísticas financieras
    avg_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
        comment="Monto promedio de transacciones con este patrón",
    )
    min_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    max_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(15, 2),
        nullable=True,
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(15, 2),
        default=Decimal("0"),
    )

    # Detección de recurrencia
    is_recurring: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="True si es una transacción recurrente (mensual, etc.)",
    )
    recurring_day: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Día del mes si es recurrente (1-31)",
    )
    recurring_frequency: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="weekly, biweekly, monthly, yearly",
    )

    # Timestamps
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relaciones
    subcategory: Mapped["Subcategory"] = relationship("Subcategory")
    profile: Mapped["Profile | None"] = relationship("Profile")

    # Índices optimizados
    __table_args__ = (
        # Búsqueda rápida por perfil y texto normalizado
        Index("ix_txn_pattern_profile_text", "profile_id", "pattern_text_normalized"),
        # Patrones globales
        Index("ix_txn_pattern_global", "is_global", "pattern_text_normalized"),
        # Por tipo de patrón
        Index("ix_txn_pattern_type", "pattern_type"),
        # Activos (no eliminados)
        Index("ix_txn_pattern_active", "deleted_at"),
        # Para embedding similarity search - se crea con HNSW
        # CREATE INDEX ON transaction_patterns USING hnsw (embedding vector_cosine_ops)
    )

    def __repr__(self) -> str:
        return f"<TransactionPattern('{self.pattern_text[:30]}', type={self.pattern_type.value}, conf={self.confidence})>"

    @property
    def accuracy(self) -> float:
        """Tasa de acierto del patrón."""
        total = self.times_confirmed + self.times_rejected
        if total == 0:
            return 0.9  # Default para patrones nuevos
        return self.times_confirmed / total

    def update_confidence(self) -> None:
        """Recalcula la confianza basada en confirmaciones/rechazos."""
        accuracy = self.accuracy
        # Factor de decaimiento por poco uso
        usage_factor = min(1.0, self.times_matched / 10)
        self.confidence = Decimal(str(round(accuracy * usage_factor, 4)))


class UserLearningProfile(Base):
    """
    Perfil de aprendizaje del usuario.
    
    Almacena métricas sobre cómo el usuario categoriza y
    permite personalizar las sugerencias.
    
    También se usa para:
    - Encontrar usuarios similares (clustering)
    - Mejorar modelos con feedback
    - Analytics de uso
    """

    __tablename__ = "user_learning_profiles"

    # Identificadores
    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    
    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    # Estadísticas de categorización
    total_transactions_categorized: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    total_auto_categorized: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Categorizaciones automáticas aceptadas",
    )
    total_manual_categorized: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Categorizaciones manuales",
    )
    total_corrections: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="Veces que corrigió categoría automática",
    )

    # Tasa de acierto
    auto_categorization_accuracy: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.8000"),
        comment="Precisión de auto-categorización (0-1)",
    )

    # Preferencias aprendidas
    preferred_categories: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Top categorías del usuario {subcategory_id: count}",
    )
    spending_patterns: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Patrones de gasto {weekday: amount, category: amount}",
    )
    
    # Clustering
    cluster_id: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="ID del cluster de usuarios similares",
    )
    cluster_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    # Embedding del perfil financiero del usuario
    # Permite encontrar usuarios similares
    profile_embedding: Mapped[list[float] | None] = mapped_column(
        Vector(256),  # Embedding más pequeño para perfiles
        nullable=True,
        comment="Embedding del perfil financiero",
    )

    # Timestamps
    last_learning_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Última vez que el sistema aprendió de este usuario",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    profile: Mapped["Profile"] = relationship("Profile")

    def __repr__(self) -> str:
        return f"<UserLearningProfile(profile={self.profile_id}, accuracy={self.auto_categorization_accuracy})>"

    @property
    def automation_rate(self) -> float:
        """Porcentaje de transacciones auto-categorizadas."""
        if self.total_transactions_categorized == 0:
            return 0.0
        return self.total_auto_categorized / self.total_transactions_categorized


class GlobalPattern(Base):
    """
    Patrones globales aprendidos de TODOS los usuarios de Costa Rica.
    
    Cuando múltiples usuarios categorizan algo igual:
    - Se crea un patrón global
    - Se usa para usuarios nuevos
    - Se mejora con más data
    
    Ejemplo:
    - 100 usuarios en CR categorizan "AUTOMERCADO" como "Supermercado"
    - Se crea patrón global con alta confianza
    - Usuarios nuevos ven auto-categorización
    """

    __tablename__ = "global_patterns"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # El patrón
    pattern_text: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    pattern_text_normalized: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        unique=True,
    )
    pattern_type: Mapped[PatternType] = mapped_column(
        SQLEnum(PatternType, name="pattern_type_enum"),
        nullable=False,
    )

    # Categoría más votada
    primary_subcategory_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("subcategories.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Embedding
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536),
        nullable=True,
    )

    # Crowdsourcing
    user_count: Mapped[int] = mapped_column(
        Integer,
        default=1,
        comment="Usuarios que contribuyeron a este patrón",
    )
    vote_distribution: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="{subcategory_id: vote_count}",
    )
    confidence: Mapped[Decimal] = mapped_column(
        Numeric(5, 4),
        default=Decimal("0.5000"),
    )

    # Estado
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="Aprobado por admin o auto-aprobado",
    )
    is_auto_approved: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
    )
    
    # Geografía (para expansión futura)
    country_code: Mapped[str] = mapped_column(
        String(2),
        default="CR",
        comment="País: CR, PA, GT, etc.",
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    primary_subcategory: Mapped["Subcategory"] = relationship("Subcategory")

    __table_args__ = (
        Index("ix_global_pattern_country", "country_code", "is_approved"),
        Index("ix_global_pattern_text", "pattern_text_normalized"),
    )

    def __repr__(self) -> str:
        return f"<GlobalPattern('{self.pattern_text[:30]}', users={self.user_count}, approved={self.is_approved})>"


class PatternCluster(Base):
    """
    Clusters de patrones similares.
    
    Agrupa patrones que son semánticamente similares para:
    - Sugerir categorías aunque no haya match exacto
    - Detectar patrones emergentes
    - Reducir duplicados
    """

    __tablename__ = "pattern_clusters"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    # Descripción del cluster
    name: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Nombre descriptivo (puede ser generado por IA)",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Centroide del cluster
    centroid: Mapped[list[float] | None] = mapped_column(
        Vector(1536),
        nullable=True,
        comment="Centroide del cluster para similarity",
    )

    # Categoría predominante
    primary_subcategory_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("subcategories.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Estadísticas
    pattern_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    avg_confidence: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relaciones
    primary_subcategory: Mapped["Subcategory | None"] = relationship("Subcategory")


class LearningEvent(Base):
    """
    Log de eventos de aprendizaje.
    
    Registra cada interacción del usuario que genera aprendizaje:
    - Categorizaciones manuales
    - Confirmaciones de sugerencias
    - Correcciones
    - Creación de alias
    
    Útil para:
    - Debugging del sistema de ML
    - Análisis de patrones de uso
    - Rollback si algo sale mal
    - Métricas de engagement
    """

    __tablename__ = "learning_events"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    tenant_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    profile_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Tipo de evento
    event_type: Mapped[LearningEventType] = mapped_column(
        SQLEnum(LearningEventType, name="learning_event_type_enum"),
        nullable=False,
    )

    # Contexto del evento
    transaction_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    pattern_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True,
    )

    # Datos del evento
    input_text: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Texto original (comercio, beneficiario)",
    )
    old_subcategory_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    new_subcategory_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )
    user_label: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    
    # Metadatos adicionales
    extra_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Datos adicionales del evento",
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True,
    )

    __table_args__ = (
        Index("ix_learning_event_profile_time", "profile_id", "created_at"),
        Index("ix_learning_event_type", "event_type", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<LearningEvent(type={self.event_type.value}, profile={self.profile_id})>"
