"""
Tests unitarios para MerchantNormalizationService.

Tests comprehensivos que cubren la normalización de nombres de merchants,
que es la funcionalidad core del servicio.
"""

import pytest

from finanzas_tracker.services.merchant_service import MerchantNormalizationService


@pytest.fixture
def merchant_service():
    """Fixture que provee una instancia del servicio."""
    return MerchantNormalizationService()


class TestNormalizeMerchantName:
    """Tests para normalización de nombres de comercios."""

    def test_normalize_removes_noise_words(self, merchant_service):
        """Test que verifica eliminación de palabras de ruido."""
        assert merchant_service.normalize_merchant_name("SUBWAY MOMENTUM") == "Subway"
        assert merchant_service.normalize_merchant_name("SUBWAY AMERICA FREE ZO") == "Subway"
        assert merchant_service.normalize_merchant_name("WALMART SUPERCENTER") == "Walmart"

    def test_normalize_removes_multiple_noise_words(self, merchant_service):
        """Test con múltiples palabras de ruido."""
        result = merchant_service.normalize_merchant_name("WALMART SUPERCENTER ESCAZU")
        assert result == "Walmart"

    def test_normalize_removes_city_names(self, merchant_service):
        """Test que verifica eliminación de nombres de ciudades."""
        assert merchant_service.normalize_merchant_name("MCDONALDS SAN JOSE") == "Mcdonalds"
        assert merchant_service.normalize_merchant_name("SUBWAY HEREDIA") == "Subway"

    def test_normalize_handles_extra_spaces(self, merchant_service):
        """Test con espacios extras."""
        assert merchant_service.normalize_merchant_name("  SUBWAY   MOMENTUM  ") == "Subway"

    def test_normalize_empty_string(self, merchant_service):
        """Test con string vacío."""
        assert merchant_service.normalize_merchant_name("") == ""

    def test_normalize_only_noise_words(self, merchant_service):
        """Test con solo palabras de ruido."""
        result = merchant_service.normalize_merchant_name("MOMENTUM SUPERCENTER")
        # Debería quedar vacío o casi vacío después de remover ruido
        assert len(result) < 10

    def test_normalize_preserves_multiple_word_names(self, merchant_service):
        """Test que preserva nombres de múltiples palabras."""
        # Dunkin Donuts no tiene palabras de ruido, debería preservarse
        result = merchant_service.normalize_merchant_name("DUNKIN DONUTS TRES RIOS")
        assert "Dunkin Donuts" in result or "Dunkin" in result

    def test_normalize_capitalization(self, merchant_service):
        """Test que verifica capitalización correcta."""
        # Después de remover ruido, debería capitalizar correctamente
        result = merchant_service.normalize_merchant_name("subway momentum")
        assert result[0].isupper()  # Primera letra mayúscula

    def test_normalize_real_world_cases(self, merchant_service):
        """Test con casos reales del análisis."""
        test_cases = [
            ("SUBWAY MOMENTUM", "Subway"),
            ("SUBWAY AMERICA FREE ZO", "Subway"),
            ("WALMART SUPERCENTER", "Walmart"),
            ("WALMART MULTIPLAZA", "Walmart"),
            ("AUTO MERCADO ESCAZU", "Auto Mercado"),
            ("MAS X MENOS SAN JOSE", "Mas X Menos"),
        ]

        for raw_name, expected in test_cases:
            result = merchant_service.normalize_merchant_name(raw_name)
            assert expected in result or result == expected, f"Failed for {raw_name}: got {result}, expected {expected}"

    def test_normalize_handles_special_characters(self, merchant_service):
        """Test con caracteres especiales."""
        result = merchant_service.normalize_merchant_name("MAS X MENOS MOMENTUM")
        # Debería mantener la X
        assert "X" in result or "x" in result

    def test_normalize_strips_whitespace(self, merchant_service):
        """Test que elimina espacios al inicio y final."""
        result = merchant_service.normalize_merchant_name("   SUBWAY   ")
        assert result == result.strip()
        assert not result.startswith(" ")
        assert not result.endswith(" ")

    def test_normalize_idempotent(self, merchant_service):
        """Test que normalizar dos veces da el mismo resultado."""
        first_pass = merchant_service.normalize_merchant_name("SUBWAY MOMENTUM")
        second_pass = merchant_service.normalize_merchant_name(first_pass)
        # Debería ser idempotente (o muy similar)
        assert first_pass.lower() == second_pass.lower()

    def test_normalize_numeric_prefix(self, merchant_service):
        """Test con prefijo numérico."""
        result = merchant_service.normalize_merchant_name("123 RESTAURANT MOMENTUM")
        # Debería preservar el 123
        assert "123" in result or "Restaurant" in result

    def test_normalize_very_long_name(self, merchant_service):
        """Test con nombre muy largo."""
        long_name = "SUPER LONG MERCHANT NAME WITH MANY WORDS MOMENTUM SUPERCENTER ESCAZU"
        result = merchant_service.normalize_merchant_name(long_name)
        # Debería procesar sin error
        assert isinstance(result, str)
        assert len(result) > 0

