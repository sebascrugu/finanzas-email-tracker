"""
Tests unitarios para ExchangeRateCache y caché persistente en ExchangeRateService.

Tests que cubren:
- Modelo ExchangeRateCache (CRUD operations)
- Cache-aside pattern con dos niveles (memoria + DB)
- Cache hits/misses
- Persistencia entre sesiones
- Performance optimization
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from finanzas_tracker.core.database import Base, engine, get_session
from finanzas_tracker.models.exchange_rate_cache import ExchangeRateCache
from finanzas_tracker.services.exchange_rate import ExchangeRateService


@pytest.fixture(scope="module", autouse=True)
def setup_database() -> None:
    """Setup: Crear tablas necesarias para los tests."""
    # Crear todas las tablas
    Base.metadata.create_all(bind=engine)
    yield
    # Cleanup: Eliminar todas las tablas después de los tests
    Base.metadata.drop_all(bind=engine)


class TestExchangeRateCacheModel:
    """Tests para el modelo ExchangeRateCache."""

    def test_create_cache_entry(self) -> None:
        """Test creando un entry en el cache."""
        with get_session() as session:
            target_date = date(2025, 11, 1)
            cache_entry = ExchangeRateCache.save_rate(
                session, target_date, rate=530.50, source="hacienda_cr"
            )
            session.commit()

            assert cache_entry.date == target_date
            assert cache_entry.rate == Decimal("530.50")
            assert cache_entry.source == "hacienda_cr"
            assert cache_entry.created_at is not None

    def test_get_by_date_existing(self) -> None:
        """Test obteniendo un entry existente por fecha."""
        with get_session() as session:
            target_date = date(2025, 11, 2)
            # Crear entry
            ExchangeRateCache.save_rate(session, target_date, rate=531.00, source="exchangerate_api")
            session.commit()

            # Recuperar entry
            cached = ExchangeRateCache.get_by_date(session, target_date)
            assert cached is not None
            assert cached.date == target_date
            assert float(cached.rate) == 531.00
            assert cached.source == "exchangerate_api"

    def test_get_by_date_not_existing(self) -> None:
        """Test obteniendo un entry que no existe."""
        with get_session() as session:
            target_date = date(2099, 12, 31)  # Fecha futura
            cached = ExchangeRateCache.get_by_date(session, target_date)
            assert cached is None

    def test_update_existing_entry(self) -> None:
        """Test actualizando un entry existente."""
        with get_session() as session:
            target_date = date(2025, 11, 3)
            # Crear entry con source default
            ExchangeRateCache.save_rate(session, target_date, rate=530.00, source="default")
            session.commit()

            # Actualizar con mejor source
            updated = ExchangeRateCache.save_rate(
                session, target_date, rate=531.25, source="hacienda_cr"
            )
            session.commit()

            assert updated.rate == Decimal("531.25")
            assert updated.source == "hacienda_cr"

            # Verificar que no se creó duplicado
            all_entries = session.query(ExchangeRateCache).filter_by(date=target_date).all()
            assert len(all_entries) == 1


class TestExchangeRateServiceCache:
    """Tests para el cache-aside pattern en ExchangeRateService."""

    def setup_method(self) -> None:
        """Setup antes de cada test."""
        # Limpiar cache en memoria
        ExchangeRateService._cache.clear()

        # Limpiar cache en DB
        with get_session() as session:
            session.query(ExchangeRateCache).delete()
            session.commit()

    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_hacienda_cr")
    def test_cache_miss_calls_api(self, mock_hacienda: MagicMock) -> None:
        """Test que cuando no hay cache, se llama a la API."""
        mock_hacienda.return_value = 530.50

        service = ExchangeRateService()
        rate = service.get_rate("2025-11-01")

        assert rate == 530.50
        mock_hacienda.assert_called_once_with("2025-11-01")

    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_hacienda_cr")
    def test_cache_hit_memory_no_api_call(self, mock_hacienda: MagicMock) -> None:
        """Test que cache hit en memoria no llama a la API."""
        service = ExchangeRateService()

        # Primera llamada - llena el cache
        mock_hacienda.return_value = 530.50
        rate1 = service.get_rate("2025-11-01")
        assert rate1 == 530.50
        assert mock_hacienda.call_count == 1

        # Segunda llamada - debe usar cache en memoria
        rate2 = service.get_rate("2025-11-01")
        assert rate2 == 530.50
        assert mock_hacienda.call_count == 1  # NO se llamó de nuevo

    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_hacienda_cr")
    def test_cache_hit_db_no_api_call(self, mock_hacienda: MagicMock) -> None:
        """Test que cache hit en DB no llama a la API."""
        # Guardar en DB directamente
        with get_session() as session:
            ExchangeRateCache.save_rate(
                session, date(2025, 11, 1), rate=530.50, source="hacienda_cr"
            )
            session.commit()

        # Crear servicio nuevo (cache en memoria vacío)
        service = ExchangeRateService()
        rate = service.get_rate("2025-11-01")

        assert rate == 530.50
        mock_hacienda.assert_not_called()  # NO se llamó a la API

    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_hacienda_cr")
    def test_cache_persists_to_db(self, mock_hacienda: MagicMock) -> None:
        """Test que el cache se persiste en la DB."""
        mock_hacienda.return_value = 530.50

        service = ExchangeRateService()
        service.get_rate("2025-11-01")

        # Verificar que se guardó en DB
        with get_session() as session:
            cached = ExchangeRateCache.get_by_date(session, date(2025, 11, 1))
            assert cached is not None
            assert float(cached.rate) == 530.50
            assert cached.source == "hacienda_cr"

    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_hacienda_cr")
    def test_cache_db_to_memory_propagation(self, mock_hacienda: MagicMock) -> None:
        """Test que cache hit en DB se propaga a memoria."""
        # Guardar en DB
        with get_session() as session:
            ExchangeRateCache.save_rate(
                session, date(2025, 11, 1), rate=530.50, source="hacienda_cr"
            )
            session.commit()

        service = ExchangeRateService()

        # Primera llamada - lee de DB y guarda en memoria
        rate1 = service.get_rate("2025-11-01")
        assert rate1 == 530.50

        # Segunda llamada - debe leer de memoria
        rate2 = service.get_rate("2025-11-01")
        assert rate2 == 530.50

        # Verificar que está en cache de memoria
        assert "2025-11-01" in service._cache

    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_exchangerate_api")
    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_hacienda_cr")
    def test_cache_saves_with_correct_source(
        self, mock_hacienda: MagicMock, mock_exchange: MagicMock
    ) -> None:
        """Test que se guarda la fuente correcta en el cache."""
        # Hacienda falla, exchangerate funciona
        mock_hacienda.return_value = None
        mock_exchange.return_value = 531.00

        service = ExchangeRateService()
        service.get_rate("2025-11-01")

        # Verificar que se guardó con source correcto
        with get_session() as session:
            cached = ExchangeRateCache.get_by_date(session, date(2025, 11, 1))
            assert cached is not None
            assert cached.source == "exchangerate_api"

    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_exchangerate_api")
    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_hacienda_cr")
    def test_cache_saves_default_rate(
        self, mock_hacienda: MagicMock, mock_exchange: MagicMock
    ) -> None:
        """Test que se guarda el default rate cuando APIs fallan."""
        mock_hacienda.return_value = None
        mock_exchange.return_value = None

        service = ExchangeRateService()
        rate = service.get_rate("2025-11-01")

        assert rate == service.default_rate

        # Verificar que se guardó en DB con source="default"
        with get_session() as session:
            cached = ExchangeRateCache.get_by_date(session, date(2025, 11, 1))
            assert cached is not None
            assert cached.source == "default"
            assert float(cached.rate) == service.default_rate

    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_hacienda_cr")
    def test_cache_with_datetime_input(self, mock_hacienda: MagicMock) -> None:
        """Test que el cache funciona con datetime objects."""
        mock_hacienda.return_value = 530.50

        service = ExchangeRateService()
        transaction_dt = datetime(2025, 11, 1, 10, 30, 0)

        rate = service.get_rate(transaction_dt)
        assert rate == 530.50

        # Verificar que se guardó con la fecha correcta
        with get_session() as session:
            cached = ExchangeRateCache.get_by_date(session, date(2025, 11, 1))
            assert cached is not None

    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_hacienda_cr")
    def test_cache_with_date_input(self, mock_hacienda: MagicMock) -> None:
        """Test que el cache funciona con date objects."""
        mock_hacienda.return_value = 530.50

        service = ExchangeRateService()
        transaction_date = date(2025, 11, 1)

        rate = service.get_rate(transaction_date)
        assert rate == 530.50

        # Verificar que se guardó
        with get_session() as session:
            cached = ExchangeRateCache.get_by_date(session, transaction_date)
            assert cached is not None


class TestExchangeRateCachePerformance:
    """Tests de performance para el caché."""

    def setup_method(self) -> None:
        """Setup antes de cada test."""
        ExchangeRateService._cache.clear()
        with get_session() as session:
            session.query(ExchangeRateCache).delete()
            session.commit()

    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_hacienda_cr")
    def test_multiple_transactions_same_date_one_api_call(
        self, mock_hacienda: MagicMock
    ) -> None:
        """
        Test que procesar 100 transacciones de la misma fecha
        solo hace 1 API call (no 100).
        """
        mock_hacienda.return_value = 530.50

        service = ExchangeRateService()

        # Simular procesar 100 transacciones del mismo día
        for _ in range(100):
            rate = service.get_rate("2025-11-01")
            assert rate == 530.50

        # Solo debió llamarse UNA VEZ a la API
        assert mock_hacienda.call_count == 1

    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_hacienda_cr")
    def test_cache_survives_service_restart(self, mock_hacienda: MagicMock) -> None:
        """
        Test que el cache persiste entre "reinicios" de la aplicación.

        Simula:
        1. Primera sesión: fetch rate y guarda en cache
        2. Segunda sesión: crea servicio nuevo, debería usar cache DB
        """
        # Primera "sesión" - llena el cache
        mock_hacienda.return_value = 530.50
        service1 = ExchangeRateService()
        rate1 = service1.get_rate("2025-11-01")
        assert rate1 == 530.50
        assert mock_hacienda.call_count == 1

        # Simular "reinicio" - limpiar cache en memoria
        ExchangeRateService._cache.clear()

        # Segunda "sesión" - crear servicio nuevo
        service2 = ExchangeRateService()
        rate2 = service2.get_rate("2025-11-01")

        assert rate2 == 530.50
        # NO debió llamar a la API de nuevo, usó cache DB
        assert mock_hacienda.call_count == 1
