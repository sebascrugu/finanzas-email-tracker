"""
Tests unitarios para ExchangeRateService.

Tests para el servicio de tipos de cambio USD a CRC,
incluyendo:
- Cache en memoria y DB
- Llamadas a APIs externas
- Fallbacks
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


class TestExchangeRateServiceInit:
    """Tests para la inicialización del servicio."""
    
    def test_service_init(self):
        """Debería inicializar el servicio correctamente."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService
        
        service = ExchangeRateService()
        
        assert service is not None
        assert service.default_rate > 0
    
    def test_service_has_default_rate_from_settings(self):
        """Debería tener rate default desde settings."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService
        from finanzas_tracker.config.settings import settings
        
        service = ExchangeRateService()
        
        assert service.default_rate == settings.usd_to_crc_rate


class TestGetRateDateNormalization:
    """Tests para normalización de fechas en get_rate."""
    
    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService
        return ExchangeRateService()
    
    def test_accepts_date_object(self, service):
        """Debería aceptar date object."""
        with patch.object(service, '_get_rate_from_apis', return_value=(520.0, 'test')):
            with patch('finanzas_tracker.services.exchange_rate.get_session'):
                # Limpiar cache primero
                service._cache.clear()
                
                result = service.get_rate(date(2024, 1, 15))
                
                assert isinstance(result, float)
    
    def test_accepts_datetime_object(self, service):
        """Debería aceptar datetime object."""
        with patch.object(service, '_get_rate_from_apis', return_value=(520.0, 'test')):
            with patch('finanzas_tracker.services.exchange_rate.get_session'):
                service._cache.clear()
                
                result = service.get_rate(datetime(2024, 1, 15, 10, 30))
                
                assert isinstance(result, float)
    
    def test_accepts_string_date(self, service):
        """Debería aceptar fecha como string ISO."""
        with patch.object(service, '_get_rate_from_apis', return_value=(520.0, 'test')):
            with patch('finanzas_tracker.services.exchange_rate.get_session'):
                service._cache.clear()
                
                result = service.get_rate("2024-01-15")
                
                assert isinstance(result, float)


class TestGetRateMemoryCache:
    """Tests para el cache en memoria."""
    
    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService
        service = ExchangeRateService()
        service._cache.clear()
        return service
    
    def test_memory_cache_hit(self, service):
        """Debería retornar valor de cache en memoria si existe."""
        # Poblar cache directamente
        service._cache["2024-01-15"] = 525.00
        
        result = service.get_rate(date(2024, 1, 15))
        
        assert result == 525.00
    
    def test_memory_cache_stores_value(self, service):
        """Debería guardar valor en cache de memoria."""
        with patch.object(service, '_get_rate_from_apis', return_value=(530.0, 'test')):
            with patch('finanzas_tracker.services.exchange_rate.get_session') as mock_session:
                mock_session_instance = MagicMock()
                mock_session.return_value.__enter__ = MagicMock(return_value=mock_session_instance)
                mock_session.return_value.__exit__ = MagicMock(return_value=None)
                
                # Mockear cache de DB vacío
                with patch('finanzas_tracker.services.exchange_rate.ExchangeRateCache') as mock_cache:
                    mock_cache.get_by_date.return_value = None
                    
                    result = service.get_rate(date(2024, 2, 20))
        
        assert result == 530.0
        assert "2024-02-20" in service._cache


class TestGetRateFromAPIs:
    """Tests para _get_rate_from_apis."""
    
    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService
        return ExchangeRateService()
    
    def test_returns_hacienda_rate_first(self, service):
        """Debería retornar rate de Hacienda CR si está disponible."""
        with patch.object(service, '_get_from_hacienda_cr', return_value=520.50):
            rate, source = service._get_rate_from_apis("2024-01-15")
            
            assert rate == 520.50
            assert source == "hacienda_cr"
    
    def test_fallback_to_exchangerate_api(self, service):
        """Debería usar exchangerate_api si Hacienda falla."""
        with patch.object(service, '_get_from_hacienda_cr', return_value=None):
            with patch.object(service, '_get_from_exchangerate_api', return_value=521.00):
                rate, source = service._get_rate_from_apis("2024-01-15")
                
                assert rate == 521.00
                assert source == "exchangerate_api"
    
    def test_returns_none_if_all_apis_fail(self, service):
        """Debería retornar None si todas las APIs fallan."""
        with patch.object(service, '_get_from_hacienda_cr', return_value=None):
            with patch.object(service, '_get_from_exchangerate_api', return_value=None):
                rate, source = service._get_rate_from_apis("2024-01-15")
                
                assert rate is None
                assert source == ""


class TestGetFromHaciendaCR:
    """Tests para _get_from_hacienda_cr."""
    
    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService
        return ExchangeRateService()
    
    def test_successful_api_call(self, service):
        """Debería parsear respuesta exitosa de Hacienda."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"venta": 520.50}]
        mock_response.raise_for_status.return_value = None
        
        with patch('finanzas_tracker.services.exchange_rate.requests.get', return_value=mock_response):
            rate = service._get_from_hacienda_cr("2024-01-15")
            
            assert rate == 520.50
    
    def test_empty_response_returns_none(self, service):
        """Debería retornar None si respuesta está vacía."""
        mock_response = MagicMock()
        mock_response.json.return_value = []
        mock_response.raise_for_status.return_value = None
        
        with patch('finanzas_tracker.services.exchange_rate.requests.get', return_value=mock_response):
            rate = service._get_from_hacienda_cr("2024-01-15")
            
            assert rate is None
    
    def test_invalid_rate_returns_none(self, service):
        """Debería retornar None si rate es 0 o inválido."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"venta": 0}]
        mock_response.raise_for_status.return_value = None
        
        with patch('finanzas_tracker.services.exchange_rate.requests.get', return_value=mock_response):
            rate = service._get_from_hacienda_cr("2024-01-15")
            
            assert rate is None
    
    def test_malformed_response_returns_none(self, service):
        """Debería retornar None si respuesta está malformada."""
        mock_response = MagicMock()
        mock_response.json.return_value = [{"compra": 510.00}]  # Sin "venta"
        mock_response.raise_for_status.return_value = None
        
        with patch('finanzas_tracker.services.exchange_rate.requests.get', return_value=mock_response):
            rate = service._get_from_hacienda_cr("2024-01-15")
            
            # Debería retornar None porque .get("venta", 0) retorna 0
            assert rate is None


class TestDefaultRateFallback:
    """Tests para fallback a rate default."""
    
    def test_uses_default_when_all_fail(self):
        """Debería usar rate default cuando todas las APIs fallan."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService
        
        service = ExchangeRateService()
        service._cache.clear()
        
        with patch.object(service, '_get_rate_from_apis', return_value=(None, '')):
            with patch('finanzas_tracker.services.exchange_rate.get_session') as mock_session:
                mock_session_instance = MagicMock()
                mock_session.return_value.__enter__ = MagicMock(return_value=mock_session_instance)
                mock_session.return_value.__exit__ = MagicMock(return_value=None)
                
                with patch('finanzas_tracker.services.exchange_rate.ExchangeRateCache') as mock_cache:
                    mock_cache.get_by_date.return_value = None
                    
                    result = service.get_rate(date(2024, 1, 15))
        
        assert result == service.default_rate


class TestCacheClassVariable:
    """Tests para la variable de clase _cache."""
    
    def test_cache_is_shared_between_instances(self):
        """El cache debería ser compartido entre instancias."""
        from finanzas_tracker.services.exchange_rate import ExchangeRateService
        
        service1 = ExchangeRateService()
        service2 = ExchangeRateService()
        
        # Limpiar y agregar a cache desde service1
        service1._cache.clear()
        service1._cache["shared-test"] = 500.0
        
        # Debería estar disponible en service2
        assert "shared-test" in service2._cache
        assert service2._cache["shared-test"] == 500.0
        
        # Limpiar
        service1._cache.clear()


class TestExchangeRateServiceSingleton:
    """Tests para la instancia singleton."""
    
    def test_singleton_exists(self):
        """Debería existir instancia singleton."""
        from finanzas_tracker.services.exchange_rate import exchange_rate_service
        
        assert exchange_rate_service is not None
    
    def test_singleton_is_service_instance(self):
        """Singleton debería ser instancia de ExchangeRateService."""
        from finanzas_tracker.services.exchange_rate import (
            ExchangeRateService,
            exchange_rate_service,
        )
        
        assert isinstance(exchange_rate_service, ExchangeRateService)
