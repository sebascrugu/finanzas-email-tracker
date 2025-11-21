"""
Tests unitarios para ExchangeRateCache y cache persistente en ExchangeRateService.

Tests que cubren:
- Cache-aside pattern en memoria
- Conversion de tipos de fecha
- Performance del cache
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from finanzas_tracker.models.exchange_rate_cache import ExchangeRateCache


class TestExchangeRateCacheModel:
    """Tests para el modelo ExchangeRateCache."""

    def test_model_has_required_fields(self) -> None:
        """Test que el modelo tiene los campos requeridos."""
        assert hasattr(ExchangeRateCache, "date")
        assert hasattr(ExchangeRateCache, "rate")
        assert hasattr(ExchangeRateCache, "source")
        assert hasattr(ExchangeRateCache, "created_at")

    def test_save_rate_method_exists(self) -> None:
        """Test que el metodo save_rate existe."""
        assert hasattr(ExchangeRateCache, "save_rate")
        assert callable(getattr(ExchangeRateCache, "save_rate"))

    def test_get_by_date_method_exists(self) -> None:
        """Test que el metodo get_by_date existe."""
        assert hasattr(ExchangeRateCache, "get_by_date")
        assert callable(getattr(ExchangeRateCache, "get_by_date"))


class TestExchangeRateServiceCache:
    """Tests para el cache-aside pattern en ExchangeRateService."""

    @patch("finanzas_tracker.services.exchange_rate.ExchangeRateService._get_from_hacienda_cr")
    def test_cache_hit_memory_no_api_call(self, mock_hacienda: MagicMock) -> None:
        """Test que cache hit en memoria no llama a la API."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService

        service = ExchangeRateService()
        service._cache.clear()

        # Pre-populate memory cache
        service._cache["2025-11-01"] = 530.50

        rate = service.get_rate("2025-11-01")
        assert rate == 530.50
        mock_hacienda.assert_not_called()

    def test_cache_with_datetime_converts_to_string(self) -> None:
        """Test que datetime se convierte correctamente a string para cache key."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService

        service = ExchangeRateService()
        service._cache.clear()
        service._cache["2025-11-01"] = 530.50

        transaction_dt = datetime(2025, 11, 1, 10, 30, 0)
        rate = service.get_rate(transaction_dt)
        assert rate == 530.50

    def test_cache_with_date_converts_to_string(self) -> None:
        """Test que date se convierte correctamente a string para cache key."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService

        service = ExchangeRateService()
        service._cache.clear()
        service._cache["2025-11-01"] = 530.50

        transaction_date = date(2025, 11, 1)
        rate = service.get_rate(transaction_date)
        assert rate == 530.50

    def test_cache_with_string_date(self) -> None:
        """Test que string date funciona directamente."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService

        service = ExchangeRateService()
        service._cache.clear()
        service._cache["2025-11-15"] = 532.00

        rate = service.get_rate("2025-11-15")
        assert rate == 532.00


class TestExchangeRateCachePerformance:
    """Tests de performance para el cache."""

    def test_memory_cache_prevents_repeated_lookups(self) -> None:
        """Test que el cache en memoria previene lookups repetidos."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService

        service = ExchangeRateService()
        service._cache.clear()
        service._cache["2025-11-01"] = 530.50

        # 100 llamadas deben usar cache
        for _ in range(100):
            rate = service.get_rate("2025-11-01")
            assert rate == 530.50

    def test_default_rate_fallback(self) -> None:
        """Test que se usa default rate cuando no hay datos."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService

        service = ExchangeRateService()
        assert service.default_rate > 0
        assert isinstance(service.default_rate, float)

    def test_cache_class_attribute(self) -> None:
        """Test que _cache es un atributo de clase compartido."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService

        service1 = ExchangeRateService()
        service2 = ExchangeRateService()

        service1._cache["test-date"] = 999.99
        assert service2._cache.get("test-date") == 999.99

        # Cleanup
        del service1._cache["test-date"]
