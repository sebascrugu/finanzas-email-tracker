"""Smart Learning Service - Sistema Avanzado de Aprendizaje con Embeddings.

Este es el servicio CORE del sistema de inteligencia del Finanzas Tracker.
Combina embeddings vectoriales con pgvector para:

1. **Búsqueda Semántica**: Encuentra transacciones similares por significado
   - "UBER TRIP" ≈ "DIDI VIAJE" ≈ "INDRIVER" (todos son transporte)
   
2. **Auto-categorización Inteligente**: 
   - Si no hay match exacto, busca patrones similares
   - Usa embeddings para encontrar la categoría más probable
   
3. **Clustering de Transacciones**:
   - Agrupa transacciones similares automáticamente
   - Detecta nuevos tipos de gastos

4. **Aprendizaje Crowdsourced**:
   - Patrones de usuarios CR mejoran las sugerencias
   - Auto-aprueba patrones con 5+ usuarios coincidentes

Stack técnico:
- Embeddings: Local (all-MiniLM-L6-v2) o Voyage AI/OpenAI
- Vector DB: PostgreSQL 16 + pgvector con índices HNSW
- Similarity: Cosine distance para matching semántico
- Clustering: K-means sobre embeddings

Arquitectura de 4 capas de aprendizaje:
┌─────────────────────────────────────────────────────────┐
│  1. USUARIO: Patrones personales del usuario           │
├─────────────────────────────────────────────────────────┤
│  2. PERFIL: Cluster de usuarios similares              │
├─────────────────────────────────────────────────────────┤
│  3. PAÍS: Patrones crowdsourced de Costa Rica          │
├─────────────────────────────────────────────────────────┤
│  4. BASE: Conocimiento base (Automercado, Uber, etc.)  │
└─────────────────────────────────────────────────────────┘
"""

__all__ = [
    "SmartLearningService",
    "SimilarPattern",
    "ClusterInfo",
    "LearningResult",
]

import logging
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

import numpy as np
from sqlalchemy import and_, func, select, text
from sqlalchemy.orm import Session

from finanzas_tracker.models.category import Subcategory
from finanzas_tracker.models.smart_learning import (
    GlobalPattern,
    LearningEvent,
    LearningEventType,
    PatternCluster,
    PatternSource,
    PatternType,
    TransactionPattern,
    UserLearningProfile,
)
from finanzas_tracker.services.local_embedding_service import LocalEmbeddingService

if TYPE_CHECKING:
    from finanzas_tracker.models.transaction import Transaction


logger = logging.getLogger(__name__)


# ============================================================================
# Data Classes para resultados
# ============================================================================

@dataclass
class SimilarPattern:
    """Un patrón similar encontrado por búsqueda semántica."""
    pattern_id: UUID
    pattern_text: str
    subcategory_id: str
    subcategory_name: str | None
    user_label: str | None
    similarity: float  # 0-1, mayor = más similar
    source: str  # "user", "global", "cluster"
    confidence: float  # Confianza del patrón original
    
    @property
    def combined_score(self) -> float:
        """Score combinado de similarity y confidence."""
        return (self.similarity * 0.7) + (self.confidence * 0.3)


@dataclass
class ClusterInfo:
    """Información sobre un cluster de transacciones."""
    cluster_id: int
    name: str | None
    pattern_count: int
    primary_category: str | None
    avg_amount: Decimal | None
    representative_patterns: list[str]


@dataclass
class LearningResult:
    """Resultado de una operación de aprendizaje."""
    success: bool
    pattern_id: UUID | None
    pattern_type: str
    message: str
    confidence: float
    is_new_pattern: bool
    similar_patterns_count: int


@dataclass
class CategorizationSuggestion:
    """Sugerencia de categorización basada en ML."""
    subcategory_id: str
    subcategory_name: str
    confidence: float
    source: str  # "exact_match", "semantic_similarity", "cluster", "global"
    reason: str
    similar_patterns: list[SimilarPattern] = field(default_factory=list)


# ============================================================================
# Smart Learning Service
# ============================================================================

class SmartLearningService:
    """
    Servicio de aprendizaje inteligente con embeddings y pgvector.
    
    Este servicio es el corazón del sistema de ML:
    
    1. Aprende de cada interacción del usuario
    2. Usa embeddings para encontrar patrones similares
    3. Mejora con crowdsourcing de todos los usuarios CR
    4. Mantiene estadísticas y métricas de precisión
    
    Ejemplo de uso:
        >>> service = SmartLearningService(db)
        >>> 
        >>> # Aprender de una categorización
        >>> result = service.learn_from_categorization(
        ...     profile_id="user-123",
        ...     text="JUAN PEREZ",
        ...     subcategory_id="subcat-456",
        ...     user_label="Papá"
        ... )
        >>> 
        >>> # Buscar sugerencias para una nueva transacción
        >>> suggestions = service.get_smart_suggestions(
        ...     profile_id="user-123",
        ...     text="SINPE a Juan Pérez Mora"
        ... )
    """
    
    # Configuración de umbrales
    AUTO_APPROVE_THRESHOLD = 0.90  # Confianza mínima para auto-aprobar
    SIMILARITY_THRESHOLD = 0.75   # Similitud mínima para considerar un match
    MIN_USERS_FOR_GLOBAL = 5       # Usuarios mínimos para patrón global
    
    def __init__(self, db: Session) -> None:
        """Inicializa el servicio."""
        self.db = db
        self._embedding_service: LocalEmbeddingService | None = None
    
    @property
    def embedding_service(self) -> LocalEmbeddingService:
        """Lazy loading del servicio de embeddings."""
        if self._embedding_service is None:
            self._embedding_service = LocalEmbeddingService()
        return self._embedding_service
    
    # ========================================================================
    # Aprendizaje
    # ========================================================================
    
    def learn_from_categorization(
        self,
        profile_id: str,
        text: str,
        subcategory_id: str,
        user_label: str | None = None,
        pattern_type: PatternType = PatternType.BENEFICIARIO,
        transaction_id: str | None = None,
        amount: Decimal | None = None,
    ) -> LearningResult:
        """
        Aprende de una categorización del usuario.
        
        Se llama cuando el usuario:
        - Categoriza una transacción manualmente
        - Confirma una sugerencia
        - Crea un alias para un contacto
        
        Args:
            profile_id: ID del perfil del usuario
            text: Texto del patrón (beneficiario, comercio, etc.)
            subcategory_id: Categoría asignada
            user_label: Alias del usuario (ej: "Mamá", "Casero")
            pattern_type: Tipo de patrón
            transaction_id: ID de la transacción (opcional)
            amount: Monto de la transacción (para estadísticas)
            
        Returns:
            Resultado del aprendizaje con métricas
        """
        if not text or not text.strip():
            return LearningResult(
                success=False,
                pattern_id=None,
                pattern_type=pattern_type.value,
                message="Texto vacío",
                confidence=0.0,
                is_new_pattern=False,
                similar_patterns_count=0,
            )
        
        normalized_text = self._normalize_text(text)
        
        # Buscar patrón existente del usuario
        existing = self._find_existing_pattern(profile_id, normalized_text)
        
        if existing:
            # Actualizar patrón existente
            return self._update_existing_pattern(
                existing, subcategory_id, user_label, amount, transaction_id
            )
        else:
            # Crear nuevo patrón
            return self._create_new_pattern(
                profile_id, text, normalized_text, subcategory_id,
                user_label, pattern_type, transaction_id, amount
            )
    
    def learn_from_correction(
        self,
        profile_id: str,
        text: str,
        old_subcategory_id: str | None,
        new_subcategory_id: str,
        transaction_id: str | None = None,
    ) -> LearningResult:
        """
        Aprende cuando el usuario corrige una categorización incorrecta.
        
        Las correcciones tienen más peso que las confirmaciones porque
        indican que el sistema se equivocó.
        """
        normalized_text = self._normalize_text(text)
        
        # Buscar patrón que causó el error
        existing = self._find_existing_pattern(profile_id, normalized_text)
        
        if existing:
            # Incrementar rechazos y actualizar categoría
            existing.times_rejected += 1
            existing.subcategory_id = new_subcategory_id
            existing.update_confidence()  # Recalcula confianza
            existing.updated_at = datetime.now(UTC)
        else:
            # Crear nuevo patrón con la corrección
            return self.learn_from_categorization(
                profile_id=profile_id,
                text=text,
                subcategory_id=new_subcategory_id,
                pattern_type=PatternType.BENEFICIARIO,
                transaction_id=transaction_id,
            )
        
        # Registrar evento de corrección
        self._log_learning_event(
            profile_id=profile_id,
            event_type=LearningEventType.CORRECTION,
            input_text=text,
            old_subcategory_id=old_subcategory_id,
            new_subcategory_id=new_subcategory_id,
            transaction_id=transaction_id,
            pattern_id=existing.id if existing else None,
        )
        
        self.db.commit()
        
        return LearningResult(
            success=True,
            pattern_id=existing.id if existing else None,
            pattern_type="correction",
            message="Patrón corregido, confianza reducida",
            confidence=float(existing.confidence) if existing else 0.8,
            is_new_pattern=False,
            similar_patterns_count=0,
        )
    
    # ========================================================================
    # Sugerencias Inteligentes
    # ========================================================================
    
    def get_smart_suggestions(
        self,
        profile_id: str,
        text: str,
        amount: Decimal | None = None,
        max_suggestions: int = 3,
    ) -> list[CategorizationSuggestion]:
        """
        Obtiene sugerencias inteligentes de categorización.
        
        Busca en múltiples capas:
        1. Match exacto del usuario
        2. Similarity search en patrones del usuario
        3. Patrones globales aprobados
        4. Cluster más cercano
        
        Args:
            profile_id: ID del perfil
            text: Texto de la transacción
            amount: Monto (para filtrar por rango)
            max_suggestions: Máximo de sugerencias a retornar
            
        Returns:
            Lista de sugerencias ordenadas por confianza
        """
        suggestions: list[CategorizationSuggestion] = []
        normalized_text = self._normalize_text(text)
        
        # 1. Match exacto del usuario
        exact_match = self._find_existing_pattern(profile_id, normalized_text)
        if exact_match:
            subcat = self.db.get(Subcategory, exact_match.subcategory_id)
            suggestions.append(CategorizationSuggestion(
                subcategory_id=exact_match.subcategory_id,
                subcategory_name=subcat.nombre if subcat else "Desconocida",
                confidence=float(exact_match.confidence),
                source="exact_match",
                reason=f"Patrón guardado: {exact_match.user_label or exact_match.pattern_text}",
            ))
        
        # 2. Búsqueda semántica en patrones del usuario
        if not exact_match or float(exact_match.confidence) < self.AUTO_APPROVE_THRESHOLD:
            similar = self._find_similar_patterns(profile_id, text)
            for pattern in similar[:2]:  # Top 2 similares
                if pattern.similarity >= self.SIMILARITY_THRESHOLD:
                    suggestions.append(CategorizationSuggestion(
                        subcategory_id=pattern.subcategory_id,
                        subcategory_name=pattern.subcategory_name,
                        confidence=pattern.combined_score,
                        source="semantic_similarity",
                        reason=f"Similar a: {pattern.user_label or pattern.pattern_text}",
                        similar_patterns=[pattern],
                    ))
        
        # 3. Patrones globales aprobados
        global_pattern = self._find_global_pattern(normalized_text)
        if global_pattern:
            subcat = self.db.get(Subcategory, global_pattern.primary_subcategory_id)
            suggestions.append(CategorizationSuggestion(
                subcategory_id=global_pattern.primary_subcategory_id,
                subcategory_name=subcat.nombre if subcat else "Desconocida",
                confidence=float(global_pattern.confidence),
                source="global",
                reason=f"Patrón común en Costa Rica ({global_pattern.user_count} usuarios)",
            ))
        
        # Eliminar duplicados y ordenar por confianza
        seen_subcats: set[str] = set()
        unique_suggestions: list[CategorizationSuggestion] = []
        for sug in sorted(suggestions, key=lambda s: s.confidence, reverse=True):
            if sug.subcategory_id not in seen_subcats:
                seen_subcats.add(sug.subcategory_id)
                unique_suggestions.append(sug)
        
        return unique_suggestions[:max_suggestions]
    
    def auto_categorize(
        self,
        profile_id: str,
        text: str,
        amount: Decimal | None = None,
    ) -> CategorizationSuggestion | None:
        """
        Auto-categoriza si hay una sugerencia con alta confianza.
        
        Returns:
            La sugerencia usada para auto-categorizar, o None
        """
        suggestions = self.get_smart_suggestions(profile_id, text, amount, max_suggestions=1)
        
        if suggestions and suggestions[0].confidence >= self.AUTO_APPROVE_THRESHOLD:
            logger.info(
                f"🤖 Auto-categorizado: '{text[:30]}...' → {suggestions[0].subcategory_name} "
                f"({suggestions[0].confidence:.0%} via {suggestions[0].source})"
            )
            return suggestions[0]
        
        return None
    
    # ========================================================================
    # Búsqueda Semántica con Embeddings
    # ========================================================================
    
    def _find_similar_patterns(
        self,
        profile_id: str,
        text: str,
        limit: int = 5,
    ) -> list[SimilarPattern]:
        """
        Encuentra patrones similares usando embeddings y pgvector.
        
        Usa cosine similarity para encontrar patrones con significado similar,
        aunque el texto sea diferente.
        """
        # Generar embedding del texto
        embedding = self.embedding_service.embed_text(text)
        
        if not embedding or all(v == 0 for v in embedding):
            return []
        
        # Búsqueda de similitud con pgvector
        # Nota: pgvector usa distancia, no similitud
        # similarity = 1 - distance
        try:
            # Query con pgvector cosine distance
            # El operador <=> calcula distancia coseno
            result = self.db.execute(
                text("""
                    SELECT 
                        tp.id,
                        tp.pattern_text,
                        tp.subcategory_id,
                        tp.user_label,
                        tp.confidence,
                        1 - (tp.embedding <=> :embedding::vector) as similarity
                    FROM transaction_patterns tp
                    WHERE tp.profile_id = :profile_id
                      AND tp.deleted_at IS NULL
                      AND tp.embedding IS NOT NULL
                    ORDER BY tp.embedding <=> :embedding::vector
                    LIMIT :limit
                """),
                {
                    "profile_id": profile_id,
                    "embedding": str(embedding),  # pgvector acepta string de lista
                    "limit": limit,
                }
            ).fetchall()
        except Exception as e:
            logger.warning(f"Error en búsqueda semántica: {e}")
            return []
        
        patterns: list[SimilarPattern] = []
        for row in result:
            # Obtener nombre de subcategoría
            subcat = self.db.get(Subcategory, row.subcategory_id)
            
            patterns.append(SimilarPattern(
                pattern_id=row.id,
                pattern_text=row.pattern_text,
                subcategory_id=row.subcategory_id,
                subcategory_name=subcat.nombre if subcat else None,
                user_label=row.user_label,
                similarity=float(row.similarity),
                source="user",
                confidence=float(row.confidence),
            ))
        
        return patterns
    
    def _generate_and_store_embedding(
        self,
        pattern: TransactionPattern,
    ) -> None:
        """Genera y almacena el embedding para un patrón."""
        try:
            embedding = self.embedding_service.embed_text(pattern.pattern_text)
            
            # Padear o truncar a 1536 dimensiones (para compatibilidad con OpenAI)
            current_dim = len(embedding)
            target_dim = 1536
            
            if current_dim < target_dim:
                # Padear con ceros
                embedding = embedding + [0.0] * (target_dim - current_dim)
            elif current_dim > target_dim:
                # Truncar (no debería pasar con all-MiniLM-L6-v2)
                embedding = embedding[:target_dim]
            
            pattern.embedding = embedding
            pattern.embedding_model = LocalEmbeddingService.MODEL_NAME
            
        except Exception as e:
            logger.error(f"Error generando embedding: {e}")
    
    # ========================================================================
    # Patrones Globales (Crowdsourced)
    # ========================================================================
    
    def _find_global_pattern(self, normalized_text: str) -> GlobalPattern | None:
        """Busca un patrón global aprobado."""
        return self.db.query(GlobalPattern).filter(
            GlobalPattern.pattern_text_normalized == normalized_text,
            GlobalPattern.is_approved == True,  # noqa: E712
        ).first()
    
    def _update_global_pattern(
        self,
        normalized_text: str,
        subcategory_id: str,
        pattern_type: PatternType,
    ) -> None:
        """
        Actualiza o crea un patrón global con el voto del usuario.
        
        Los patrones globales se auto-aprueban cuando:
        - 5+ usuarios votan por la misma categoría
        - 90%+ de los votos coinciden
        """
        existing = self.db.query(GlobalPattern).filter(
            GlobalPattern.pattern_text_normalized == normalized_text,
        ).first()
        
        if existing:
            # Actualizar votos
            existing.user_count += 1
            votes = existing.vote_distribution or {}
            votes[subcategory_id] = votes.get(subcategory_id, 0) + 1
            existing.vote_distribution = votes
            
            # Determinar categoría con más votos
            max_votes = max(votes.values())
            winning_subcat = max(votes, key=lambda k: votes[k])
            
            existing.primary_subcategory_id = winning_subcat
            existing.confidence = Decimal(str(max_votes / existing.user_count))
            
            # Auto-aprobar si cumple condiciones
            if (
                existing.user_count >= self.MIN_USERS_FOR_GLOBAL
                and float(existing.confidence) >= 0.90
            ):
                existing.is_approved = True
                existing.is_auto_approved = True
                logger.info(
                    f"✅ Patrón global auto-aprobado: '{normalized_text}' "
                    f"({existing.user_count} usuarios, {existing.confidence:.0%} confianza)"
                )
        else:
            # Crear nuevo patrón global
            new_pattern = GlobalPattern(
                pattern_text=normalized_text,
                pattern_text_normalized=normalized_text,
                pattern_type=pattern_type,
                primary_subcategory_id=subcategory_id,
                vote_distribution={subcategory_id: 1},
                user_count=1,
                confidence=Decimal("0.5"),
            )
            self.db.add(new_pattern)
    
    # ========================================================================
    # Helpers Internos
    # ========================================================================
    
    def _normalize_text(self, text: str) -> str:
        """
        Normaliza texto para matching.
        
        - Convierte a mayúsculas
        - Quita acentos
        - Quita caracteres especiales
        - Normaliza espacios
        """
        if not text:
            return ""
        
        # Uppercase y strip
        normalized = text.upper().strip()
        
        # Quitar acentos
        normalized = unicodedata.normalize("NFD", normalized)
        normalized = "".join(c for c in normalized if unicodedata.category(c) != "Mn")
        
        # Solo alfanumérico y espacios
        normalized = "".join(c for c in normalized if c.isalnum() or c.isspace())
        
        # Normalizar espacios
        normalized = " ".join(normalized.split())
        
        return normalized
    
    def _find_existing_pattern(
        self,
        profile_id: str,
        normalized_text: str,
    ) -> TransactionPattern | None:
        """Busca un patrón exacto del usuario."""
        return self.db.query(TransactionPattern).filter(
            TransactionPattern.profile_id == profile_id,
            TransactionPattern.pattern_text_normalized == normalized_text,
            TransactionPattern.deleted_at.is_(None),
        ).first()
    
    def _update_existing_pattern(
        self,
        pattern: TransactionPattern,
        subcategory_id: str,
        user_label: str | None,
        amount: Decimal | None,
        transaction_id: str | None,
    ) -> LearningResult:
        """Actualiza un patrón existente."""
        pattern.times_matched += 1
        pattern.times_confirmed += 1
        pattern.last_seen_at = datetime.now(UTC)
        pattern.updated_at = datetime.now(UTC)
        
        # Actualizar categoría si cambió
        if pattern.subcategory_id != subcategory_id:
            pattern.subcategory_id = subcategory_id
        
        # Actualizar label si se proporciona
        if user_label:
            pattern.user_label = user_label
        
        # Actualizar estadísticas de monto
        if amount:
            pattern.total_amount += amount
            if pattern.min_amount is None or amount < pattern.min_amount:
                pattern.min_amount = amount
            if pattern.max_amount is None or amount > pattern.max_amount:
                pattern.max_amount = amount
            pattern.avg_amount = pattern.total_amount / pattern.times_matched
        
        pattern.update_confidence()
        
        # Log evento
        self._log_learning_event(
            profile_id=pattern.profile_id,
            event_type=LearningEventType.CONFIRMATION,
            input_text=pattern.pattern_text,
            new_subcategory_id=subcategory_id,
            transaction_id=transaction_id,
            pattern_id=pattern.id,
        )
        
        self.db.commit()
        
        return LearningResult(
            success=True,
            pattern_id=pattern.id,
            pattern_type=pattern.pattern_type.value,
            message=f"Patrón actualizado (x{pattern.times_matched})",
            confidence=float(pattern.confidence),
            is_new_pattern=False,
            similar_patterns_count=0,
        )
    
    def _create_new_pattern(
        self,
        profile_id: str,
        text: str,
        normalized_text: str,
        subcategory_id: str,
        user_label: str | None,
        pattern_type: PatternType,
        transaction_id: str | None,
        amount: Decimal | None,
    ) -> LearningResult:
        """Crea un nuevo patrón."""
        pattern = TransactionPattern(
            profile_id=profile_id,
            pattern_text=text,
            pattern_text_normalized=normalized_text,
            pattern_type=pattern_type,
            subcategory_id=subcategory_id,
            user_label=user_label,
            confidence=Decimal("0.80"),  # Confianza inicial
            source=PatternSource.USER_EXPLICIT,
        )
        
        # Estadísticas de monto
        if amount:
            pattern.min_amount = amount
            pattern.max_amount = amount
            pattern.avg_amount = amount
            pattern.total_amount = amount
        
        self.db.add(pattern)
        self.db.flush()  # Para obtener el ID
        
        # Generar embedding en background
        self._generate_and_store_embedding(pattern)
        
        # Log evento
        self._log_learning_event(
            profile_id=profile_id,
            event_type=LearningEventType.CATEGORIZATION,
            input_text=text,
            new_subcategory_id=subcategory_id,
            transaction_id=transaction_id,
            pattern_id=pattern.id,
            user_label=user_label,
        )
        
        # Actualizar patrón global (crowdsourcing)
        self._update_global_pattern(normalized_text, subcategory_id, pattern_type)
        
        self.db.commit()
        
        logger.info(
            f"📚 Nuevo patrón guardado: '{text[:30]}...' → "
            f"{user_label or subcategory_id}"
        )
        
        return LearningResult(
            success=True,
            pattern_id=pattern.id,
            pattern_type=pattern_type.value,
            message="Nuevo patrón creado",
            confidence=0.80,
            is_new_pattern=True,
            similar_patterns_count=0,
        )
    
    def _log_learning_event(
        self,
        profile_id: str,
        event_type: LearningEventType,
        input_text: str | None = None,
        old_subcategory_id: str | None = None,
        new_subcategory_id: str | None = None,
        transaction_id: str | None = None,
        pattern_id: UUID | None = None,
        user_label: str | None = None,
    ) -> None:
        """Registra un evento de aprendizaje."""
        event = LearningEvent(
            profile_id=profile_id,
            event_type=event_type,
            transaction_id=transaction_id,
            pattern_id=pattern_id,
            input_text=input_text,
            old_subcategory_id=old_subcategory_id,
            new_subcategory_id=new_subcategory_id,
            user_label=user_label,
        )
        self.db.add(event)
    
    # ========================================================================
    # Estadísticas y Métricas
    # ========================================================================
    
    def get_learning_stats(self, profile_id: str) -> dict:
        """
        Obtiene estadísticas de aprendizaje para un perfil.
        
        Returns:
            Dict con métricas del sistema de aprendizaje
        """
        # Total de patrones
        total_patterns = self.db.query(func.count(TransactionPattern.id)).filter(
            TransactionPattern.profile_id == profile_id,
            TransactionPattern.deleted_at.is_(None),
        ).scalar()
        
        # Patrones con alta confianza
        high_confidence = self.db.query(func.count(TransactionPattern.id)).filter(
            TransactionPattern.profile_id == profile_id,
            TransactionPattern.confidence >= Decimal("0.85"),
            TransactionPattern.deleted_at.is_(None),
        ).scalar()
        
        # Eventos de aprendizaje últimos 30 días
        since = datetime.now(UTC) - timedelta(days=30)
        events_30d = self.db.query(func.count(LearningEvent.id)).filter(
            LearningEvent.profile_id == profile_id,
            LearningEvent.created_at >= since,
        ).scalar()
        
        # Correcciones vs confirmaciones
        corrections = self.db.query(func.count(LearningEvent.id)).filter(
            LearningEvent.profile_id == profile_id,
            LearningEvent.event_type == LearningEventType.CORRECTION,
            LearningEvent.created_at >= since,
        ).scalar()
        
        confirmations = self.db.query(func.count(LearningEvent.id)).filter(
            LearningEvent.profile_id == profile_id,
            LearningEvent.event_type == LearningEventType.CONFIRMATION,
            LearningEvent.created_at >= since,
        ).scalar()
        
        # Tasa de acierto
        total_decisions = (corrections or 0) + (confirmations or 0)
        accuracy = (confirmations / total_decisions * 100) if total_decisions > 0 else 0
        
        return {
            "total_patterns": total_patterns or 0,
            "high_confidence_patterns": high_confidence or 0,
            "events_last_30_days": events_30d or 0,
            "corrections_30d": corrections or 0,
            "confirmations_30d": confirmations or 0,
            "accuracy_rate": round(accuracy, 1),
            "patterns_with_embeddings": self._count_patterns_with_embeddings(profile_id),
        }
    
    def _count_patterns_with_embeddings(self, profile_id: str) -> int:
        """Cuenta patrones que tienen embedding generado."""
        return self.db.query(func.count(TransactionPattern.id)).filter(
            TransactionPattern.profile_id == profile_id,
            TransactionPattern.embedding.isnot(None),
            TransactionPattern.deleted_at.is_(None),
        ).scalar() or 0
    
    # ========================================================================
    # Mantenimiento y Optimización
    # ========================================================================
    
    def regenerate_embeddings(self, profile_id: str) -> int:
        """
        Regenera embeddings para todos los patrones de un usuario.
        
        Útil cuando:
        - Se actualiza el modelo de embeddings
        - Se cambia de proveedor
        - Se detectan embeddings corruptos
        
        Returns:
            Número de patrones actualizados
        """
        patterns = self.db.query(TransactionPattern).filter(
            TransactionPattern.profile_id == profile_id,
            TransactionPattern.deleted_at.is_(None),
        ).all()
        
        count = 0
        for pattern in patterns:
            self._generate_and_store_embedding(pattern)
            count += 1
        
        self.db.commit()
        logger.info(f"🔄 Regenerados {count} embeddings para perfil {profile_id}")
        
        return count
    
    def merge_similar_patterns(
        self,
        profile_id: str,
        similarity_threshold: float = 0.95,
    ) -> int:
        """
        Fusiona patrones muy similares para reducir duplicados.
        
        Returns:
            Número de patrones fusionados
        """
        # TODO: Implementar con clustering
        # Por ahora, placeholder
        logger.warning("merge_similar_patterns aún no implementado")
        return 0
