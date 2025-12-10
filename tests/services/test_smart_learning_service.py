"""Tests para SmartLearningService.

Estos tests verifican el funcionamiento del servicio de aprendizaje
inteligente con embeddings y pgvector.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.smart_learning import (
    GlobalPattern,
    LearningEvent,
    LearningEventType,
    PatternSource,
    PatternType,
    TransactionPattern,
)
from finanzas_tracker.services.smart_learning_service import (
    CategorizationSuggestion,
    LearningResult,
    SmartLearningService,
)


class TestSmartLearningService:
    """Tests para el servicio de aprendizaje inteligente."""
    
    @pytest.fixture
    def profile(self, db_session) -> Profile:
        """Crea un perfil de prueba."""
        profile = Profile(
            id=str(uuid4()),
            name="Test User",
            email="test@example.com",
        )
        db_session.add(profile)
        db_session.commit()
        return profile
    
    @pytest.fixture
    def category_and_subcategory(self, db_session) -> tuple[Category, Subcategory]:
        """Crea una categoría y subcategoría de prueba."""
        category = Category(
            id=str(uuid4()),
            nombre="Gastos Personales",
            tipo="gasto",
        )
        db_session.add(category)
        db_session.flush()
        
        subcategory = Subcategory(
            id=str(uuid4()),
            nombre="Supermercado",
            category_id=category.id,
        )
        db_session.add(subcategory)
        db_session.commit()
        
        return category, subcategory
    
    @pytest.fixture
    def service(self, db_session) -> SmartLearningService:
        """Crea el servicio de aprendizaje."""
        return SmartLearningService(db_session)
    
    def test_normalize_text(self, service: SmartLearningService) -> None:
        """Test normalización de texto."""
        assert service._normalize_text("AUTOMERCADO ESCAZÚ") == "AUTOMERCADO ESCAZU"
        assert service._normalize_text("  Juan  Pérez  ") == "JUAN PEREZ"
        assert service._normalize_text("café-123") == "CAFE123"
        assert service._normalize_text("") == ""
    
    def test_learn_from_categorization_new_pattern(
        self,
        db_session,
        profile: Profile,
        category_and_subcategory: tuple[Category, Subcategory],
        service: SmartLearningService,
    ) -> None:
        """Test aprendizaje de un nuevo patrón."""
        _, subcategory = category_and_subcategory
        
        result = service.learn_from_categorization(
            profile_id=profile.id,
            text="AUTOMERCADO ESCAZU",
            subcategory_id=subcategory.id,
            user_label="Auto Escazú",
        )
        
        assert result.success is True
        assert result.is_new_pattern is True
        assert result.pattern_type == PatternType.BENEFICIARIO.value
        assert result.confidence == 0.80
        
        # Verificar que se guardó el patrón
        pattern = db_session.query(TransactionPattern).filter(
            TransactionPattern.profile_id == profile.id,
        ).first()
        
        assert pattern is not None
        assert pattern.pattern_text == "AUTOMERCADO ESCAZU"
        assert pattern.user_label == "Auto Escazú"
        assert pattern.subcategory_id == subcategory.id
    
    def test_learn_from_categorization_update_existing(
        self,
        db_session,
        profile: Profile,
        category_and_subcategory: tuple[Category, Subcategory],
        service: SmartLearningService,
    ) -> None:
        """Test actualización de patrón existente."""
        _, subcategory = category_and_subcategory
        
        # Primera categorización
        service.learn_from_categorization(
            profile_id=profile.id,
            text="AUTOMERCADO ESCAZU",
            subcategory_id=subcategory.id,
        )
        
        # Segunda categorización del mismo patrón
        result = service.learn_from_categorization(
            profile_id=profile.id,
            text="Automercado Escazú",  # Diferente case
            subcategory_id=subcategory.id,
        )
        
        assert result.success is True
        assert result.is_new_pattern is False
        
        # Verificar que solo hay un patrón
        patterns = db_session.query(TransactionPattern).filter(
            TransactionPattern.profile_id == profile.id,
        ).all()
        
        assert len(patterns) == 1
        assert patterns[0].times_matched == 2
        assert patterns[0].times_confirmed == 2
    
    def test_learn_from_correction(
        self,
        db_session,
        profile: Profile,
        category_and_subcategory: tuple[Category, Subcategory],
        service: SmartLearningService,
    ) -> None:
        """Test aprendizaje de una corrección."""
        _, subcategory = category_and_subcategory
        
        # Crear una segunda subcategoría para la corrección
        new_subcategory = Subcategory(
            id=str(uuid4()),
            nombre="Restaurante",
            category_id=subcategory.category_id,
        )
        db_session.add(new_subcategory)
        db_session.commit()
        
        # Primera categorización
        service.learn_from_categorization(
            profile_id=profile.id,
            text="UBER EATS",
            subcategory_id=subcategory.id,
        )
        
        # Corrección
        result = service.learn_from_correction(
            profile_id=profile.id,
            text="UBER EATS",
            old_subcategory_id=subcategory.id,
            new_subcategory_id=new_subcategory.id,
        )
        
        assert result.success is True
        
        # Verificar que el patrón se actualizó
        pattern = db_session.query(TransactionPattern).filter(
            TransactionPattern.profile_id == profile.id,
        ).first()
        
        assert pattern.subcategory_id == new_subcategory.id
        assert pattern.times_rejected == 1
    
    def test_get_smart_suggestions_exact_match(
        self,
        db_session,
        profile: Profile,
        category_and_subcategory: tuple[Category, Subcategory],
        service: SmartLearningService,
    ) -> None:
        """Test sugerencias con match exacto."""
        _, subcategory = category_and_subcategory
        
        # Crear patrón
        service.learn_from_categorization(
            profile_id=profile.id,
            text="AUTOMERCADO ESCAZU",
            subcategory_id=subcategory.id,
            user_label="Auto Escazú",
        )
        
        # Actualizar confianza para que pase el threshold
        pattern = db_session.query(TransactionPattern).first()
        pattern.confidence = Decimal("0.95")
        pattern.times_matched = 10
        pattern.times_confirmed = 10
        db_session.commit()
        
        # Obtener sugerencias
        suggestions = service.get_smart_suggestions(
            profile_id=profile.id,
            text="AUTOMERCADO ESCAZU",
        )
        
        assert len(suggestions) > 0
        assert suggestions[0].source == "exact_match"
        assert suggestions[0].subcategory_id == subcategory.id
    
    def test_get_learning_stats(
        self,
        db_session,
        profile: Profile,
        category_and_subcategory: tuple[Category, Subcategory],
        service: SmartLearningService,
    ) -> None:
        """Test obtención de estadísticas."""
        _, subcategory = category_and_subcategory
        
        # Crear algunos patrones
        for i in range(5):
            service.learn_from_categorization(
                profile_id=profile.id,
                text=f"COMERCIO TEST {i}",
                subcategory_id=subcategory.id,
            )
        
        stats = service.get_learning_stats(profile.id)
        
        assert stats["total_patterns"] == 5
        assert "accuracy_rate" in stats
        assert "events_last_30_days" in stats
    
    def test_auto_categorize_high_confidence(
        self,
        db_session,
        profile: Profile,
        category_and_subcategory: tuple[Category, Subcategory],
        service: SmartLearningService,
    ) -> None:
        """Test auto-categorización con alta confianza."""
        _, subcategory = category_and_subcategory
        
        # Crear patrón con alta confianza
        pattern = TransactionPattern(
            profile_id=profile.id,
            pattern_text="AUTOMERCADO ESCAZU",
            pattern_text_normalized="AUTOMERCADO ESCAZU",
            pattern_type=PatternType.BENEFICIARIO,
            subcategory_id=subcategory.id,
            confidence=Decimal("0.95"),
            times_matched=10,
            times_confirmed=10,
            source=PatternSource.USER_EXPLICIT,
        )
        db_session.add(pattern)
        db_session.commit()
        
        # Auto-categorizar
        result = service.auto_categorize(
            profile_id=profile.id,
            text="AUTOMERCADO ESCAZU",
        )
        
        assert result is not None
        assert result.subcategory_id == subcategory.id
        assert result.confidence >= service.AUTO_APPROVE_THRESHOLD
    
    def test_auto_categorize_low_confidence(
        self,
        db_session,
        profile: Profile,
        category_and_subcategory: tuple[Category, Subcategory],
        service: SmartLearningService,
    ) -> None:
        """Test que no auto-categoriza con baja confianza."""
        _, subcategory = category_and_subcategory
        
        # Crear patrón con baja confianza
        pattern = TransactionPattern(
            profile_id=profile.id,
            pattern_text="TIENDA NUEVA",
            pattern_text_normalized="TIENDA NUEVA",
            pattern_type=PatternType.BENEFICIARIO,
            subcategory_id=subcategory.id,
            confidence=Decimal("0.50"),
            times_matched=1,
            source=PatternSource.USER_EXPLICIT,
        )
        db_session.add(pattern)
        db_session.commit()
        
        # Intentar auto-categorizar
        result = service.auto_categorize(
            profile_id=profile.id,
            text="TIENDA NUEVA",
        )
        
        # No debería auto-categorizar
        assert result is None
    
    def test_global_pattern_creation(
        self,
        db_session,
        profile: Profile,
        category_and_subcategory: tuple[Category, Subcategory],
        service: SmartLearningService,
    ) -> None:
        """Test que se crea patrón global al categorizar."""
        _, subcategory = category_and_subcategory
        
        # Crear patrón (esto debería crear/actualizar patrón global)
        service.learn_from_categorization(
            profile_id=profile.id,
            text="AUTOMERCADO ESCAZU",
            subcategory_id=subcategory.id,
        )
        
        # Verificar que se creó patrón global
        global_pattern = db_session.query(GlobalPattern).filter(
            GlobalPattern.pattern_text_normalized == "AUTOMERCADO ESCAZU",
        ).first()
        
        assert global_pattern is not None
        assert global_pattern.user_count == 1
        assert global_pattern.primary_subcategory_id == subcategory.id
    
    def test_learning_event_logged(
        self,
        db_session,
        profile: Profile,
        category_and_subcategory: tuple[Category, Subcategory],
        service: SmartLearningService,
    ) -> None:
        """Test que se registran eventos de aprendizaje."""
        _, subcategory = category_and_subcategory
        
        # Categorizar
        service.learn_from_categorization(
            profile_id=profile.id,
            text="AUTOMERCADO ESCAZU",
            subcategory_id=subcategory.id,
            user_label="Auto",
        )
        
        # Verificar evento
        event = db_session.query(LearningEvent).filter(
            LearningEvent.profile_id == profile.id,
        ).first()
        
        assert event is not None
        assert event.event_type == LearningEventType.CATEGORIZATION
        assert event.input_text == "AUTOMERCADO ESCAZU"
        assert event.new_subcategory_id == subcategory.id
        assert event.user_label == "Auto"
    
    def test_pattern_with_amount_stats(
        self,
        db_session,
        profile: Profile,
        category_and_subcategory: tuple[Category, Subcategory],
        service: SmartLearningService,
    ) -> None:
        """Test que se calculan estadísticas de monto."""
        _, subcategory = category_and_subcategory
        
        # Primera categorización con monto
        service.learn_from_categorization(
            profile_id=profile.id,
            text="SUPERMERCADO X",
            subcategory_id=subcategory.id,
            amount=Decimal("25000.00"),
        )
        
        # Segunda con diferente monto
        service.learn_from_categorization(
            profile_id=profile.id,
            text="SUPERMERCADO X",
            subcategory_id=subcategory.id,
            amount=Decimal("35000.00"),
        )
        
        pattern = db_session.query(TransactionPattern).first()
        
        assert pattern.min_amount == Decimal("25000.00")
        assert pattern.max_amount == Decimal("35000.00")
        assert pattern.total_amount == Decimal("60000.00")
        assert pattern.avg_amount == Decimal("30000.00")
