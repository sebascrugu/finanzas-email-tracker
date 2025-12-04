"""
Tests unitarios para DuplicateDetectorService.

Tests para el servicio de detección de transacciones duplicadas,
incluyendo:
- Creación de dataclasses
- Algoritmo de scoring
- Detección de duplicados
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest


class TestDuplicateMatch:
    """Tests para la dataclass DuplicateMatch."""

    def test_duplicate_match_creation(self):
        """Debería crear DuplicateMatch correctamente."""
        from finanzas_tracker.services.duplicate_detector import DuplicateMatch

        mock_trans_1 = MagicMock()
        mock_trans_2 = MagicMock()

        match = DuplicateMatch(
            transaction_1=mock_trans_1,
            transaction_2=mock_trans_2,
            similarity_score=85.5,
            reasons=["Mismo comercio: WALMART", "Monto exacto: ₡15,000.00"],
        )

        assert match.transaction_1 == mock_trans_1
        assert match.transaction_2 == mock_trans_2
        assert match.similarity_score == 85.5
        assert len(match.reasons) == 2

    def test_duplicate_match_is_dataclass(self):
        """DuplicateMatch debería ser un dataclass."""
        from dataclasses import is_dataclass

        from finanzas_tracker.services.duplicate_detector import DuplicateMatch

        assert is_dataclass(DuplicateMatch)


class TestDuplicateDetectorServiceInit:
    """Tests para la inicialización del servicio."""

    def test_service_init(self):
        """Debería inicializar el servicio correctamente."""
        from finanzas_tracker.services.duplicate_detector import DuplicateDetectorService

        service = DuplicateDetectorService()

        assert service is not None


class TestCheckDuplicate:
    """Tests para el método _check_duplicate."""

    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio."""
        from finanzas_tracker.services.duplicate_detector import DuplicateDetectorService

        return DuplicateDetectorService()

    @pytest.fixture
    def base_transaction(self):
        """Fixture para crear una transacción base."""
        mock = MagicMock()
        mock.comercio = "WALMART HEREDIA"
        mock.monto_crc = Decimal("15000.00")
        mock.fecha_transaccion = date(2024, 1, 15)
        mock.account_id = "account-123"
        mock.account = MagicMock()
        mock.account.nombre_tarjeta = "VISA ****1234"
        return mock

    def test_exact_duplicate(self, service, base_transaction):
        """Debería detectar duplicado exacto con score alto."""
        trans_2 = MagicMock()
        trans_2.comercio = "WALMART HEREDIA"
        trans_2.monto_crc = Decimal("15000.00")
        trans_2.fecha_transaccion = date(2024, 1, 15)
        trans_2.account_id = "account-123"

        match = service._check_duplicate(base_transaction, trans_2)

        assert match is not None
        assert match.similarity_score >= 90
        assert "Mismo comercio" in match.reasons[0]
        assert any("Monto exacto" in r for r in match.reasons)
        assert any("Misma fecha" in r for r in match.reasons)

    def test_different_comercio_not_duplicate(self, service, base_transaction):
        """No debería ser duplicado si comercio es diferente."""
        trans_2 = MagicMock()
        trans_2.comercio = "MAXIPALI ALAJUELA"
        trans_2.monto_crc = Decimal("15000.00")
        trans_2.fecha_transaccion = date(2024, 1, 15)

        match = service._check_duplicate(base_transaction, trans_2)

        assert match is None

    def test_similar_amount_same_day(self, service, base_transaction):
        """Debería detectar montos similares (±1%) mismo día."""
        trans_2 = MagicMock()
        trans_2.comercio = "WALMART HEREDIA"
        trans_2.monto_crc = Decimal("15100.00")  # 0.67% diferencia
        trans_2.fecha_transaccion = date(2024, 1, 15)
        trans_2.account_id = "account-456"  # Diferente cuenta

        match = service._check_duplicate(base_transaction, trans_2)

        assert match is not None
        assert any("Monto muy similar" in r for r in match.reasons)

    def test_consecutive_days(self, service, base_transaction):
        """Debería detectar fechas consecutivas."""
        trans_2 = MagicMock()
        trans_2.comercio = "WALMART HEREDIA"
        trans_2.monto_crc = Decimal("15000.00")
        trans_2.fecha_transaccion = date(2024, 1, 16)  # Día siguiente
        trans_2.account_id = "account-456"

        match = service._check_duplicate(base_transaction, trans_2)

        assert match is not None
        assert any("Fechas consecutivas" in r for r in match.reasons)

    def test_close_dates(self, service, base_transaction):
        """Debería detectar fechas cercanas (3 días)."""
        trans_2 = MagicMock()
        trans_2.comercio = "WALMART HEREDIA"
        trans_2.monto_crc = Decimal("15000.00")
        trans_2.fecha_transaccion = date(2024, 1, 18)  # 3 días después
        trans_2.account_id = "account-456"

        match = service._check_duplicate(base_transaction, trans_2)

        assert match is not None
        assert any("Fechas cercanas" in r for r in match.reasons)

    def test_very_different_amount_not_duplicate(self, service, base_transaction):
        """No debería ser duplicado si monto es muy diferente (>5%)."""
        trans_2 = MagicMock()
        trans_2.comercio = "WALMART HEREDIA"
        trans_2.monto_crc = Decimal("20000.00")  # 33% diferencia
        trans_2.fecha_transaccion = date(2024, 1, 15)

        match = service._check_duplicate(base_transaction, trans_2)

        assert match is None

    def test_case_insensitive_comercio(self, service, base_transaction):
        """Debería ignorar mayúsculas/minúsculas en comercio."""
        trans_2 = MagicMock()
        trans_2.comercio = "walmart heredia"  # Minúsculas
        trans_2.monto_crc = Decimal("15000.00")
        trans_2.fecha_transaccion = date(2024, 1, 15)
        trans_2.account_id = "account-456"

        match = service._check_duplicate(base_transaction, trans_2)

        assert match is not None

    def test_datetime_handled_correctly(self, service):
        """Debería manejar datetime además de date."""
        trans_1 = MagicMock()
        trans_1.comercio = "TEST STORE"
        trans_1.monto_crc = Decimal("5000.00")
        trans_1.fecha_transaccion = datetime(2024, 1, 15, 10, 30)
        trans_1.account_id = "account-1"
        trans_1.account = None

        trans_2 = MagicMock()
        trans_2.comercio = "TEST STORE"
        trans_2.monto_crc = Decimal("5000.00")
        trans_2.fecha_transaccion = datetime(2024, 1, 15, 14, 45)  # Mismo día, hora diferente
        trans_2.account_id = "account-2"

        match = service._check_duplicate(trans_1, trans_2)

        assert match is not None

    def test_same_account_bonus(self, service, base_transaction):
        """Debería dar bonus por misma cuenta/tarjeta."""
        trans_2 = MagicMock()
        trans_2.comercio = "WALMART HEREDIA"
        trans_2.monto_crc = Decimal("15000.00")
        trans_2.fecha_transaccion = date(2024, 1, 15)
        trans_2.account_id = "account-123"  # Misma cuenta

        match_same_account = service._check_duplicate(base_transaction, trans_2)

        # Ahora con diferente cuenta
        trans_2.account_id = "account-999"
        match_diff_account = service._check_duplicate(base_transaction, trans_2)

        assert match_same_account.similarity_score > match_diff_account.similarity_score

    def test_low_score_returns_none(self, service):
        """Debería retornar None si score es muy bajo (diferencia >5% en monto)."""
        trans_1 = MagicMock()
        trans_1.comercio = "TEST"
        trans_1.monto_crc = Decimal("1000.00")
        trans_1.fecha_transaccion = date(2024, 1, 15)
        trans_1.account_id = None
        trans_1.account = None

        trans_2 = MagicMock()
        trans_2.comercio = "TEST"
        trans_2.monto_crc = Decimal("1100.00")  # 10% diferencia - fuera de rango
        trans_2.fecha_transaccion = date(2024, 1, 15)
        trans_2.account_id = None

        # Diferencia de monto >5% hace que retorne None inmediatamente
        match = service._check_duplicate(trans_1, trans_2)

        assert match is None


class TestMarkAsReconciled:
    """Tests para mark_as_reconciled."""

    def test_mark_reconciled_returns_true(self):
        """Debería retornar True al marcar como reconciliado."""
        from finanzas_tracker.services.duplicate_detector import DuplicateDetectorService

        service = DuplicateDetectorService()

        result = service.mark_as_reconciled("trans-1", "trans-2")

        assert result is True


class TestAmountSimilarityScoring:
    """Tests específicos para scoring de montos."""

    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio."""
        from finanzas_tracker.services.duplicate_detector import DuplicateDetectorService

        return DuplicateDetectorService()

    def test_exact_amount_highest_score(self, service):
        """Monto exacto debería dar 40 puntos."""
        trans_1 = MagicMock()
        trans_1.comercio = "TEST"
        trans_1.monto_crc = Decimal("10000.00")
        trans_1.fecha_transaccion = date(2024, 1, 15)
        trans_1.account_id = None
        trans_1.account = None

        trans_2 = MagicMock()
        trans_2.comercio = "TEST"
        trans_2.monto_crc = Decimal("10000.00")  # Exacto
        trans_2.fecha_transaccion = date(2024, 1, 15)
        trans_2.account_id = None

        match = service._check_duplicate(trans_1, trans_2)

        assert match is not None
        assert any("Monto exacto" in r for r in match.reasons)

    def test_one_percent_difference(self, service):
        """Diferencia de 1% debería dar 30 puntos."""
        trans_1 = MagicMock()
        trans_1.comercio = "TEST"
        trans_1.monto_crc = Decimal("10000.00")
        trans_1.fecha_transaccion = date(2024, 1, 15)
        trans_1.account_id = None
        trans_1.account = None

        trans_2 = MagicMock()
        trans_2.comercio = "TEST"
        trans_2.monto_crc = Decimal("10050.00")  # 0.5% diferencia
        trans_2.fecha_transaccion = date(2024, 1, 15)
        trans_2.account_id = None

        match = service._check_duplicate(trans_1, trans_2)

        assert match is not None
        assert any("Monto muy similar" in r for r in match.reasons)

    def test_five_percent_difference(self, service):
        """Diferencia de 5% debería dar 20 puntos."""
        trans_1 = MagicMock()
        trans_1.comercio = "TEST"
        trans_1.monto_crc = Decimal("10000.00")
        trans_1.fecha_transaccion = date(2024, 1, 15)
        trans_1.account_id = None
        trans_1.account = None

        trans_2 = MagicMock()
        trans_2.comercio = "TEST"
        trans_2.monto_crc = Decimal("10300.00")  # 3% diferencia
        trans_2.fecha_transaccion = date(2024, 1, 15)
        trans_2.account_id = None

        match = service._check_duplicate(trans_1, trans_2)

        assert match is not None
        assert any("Monto similar" in r for r in match.reasons)


class TestDateSimilarityScoring:
    """Tests específicos para scoring de fechas."""

    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio."""
        from finanzas_tracker.services.duplicate_detector import DuplicateDetectorService

        return DuplicateDetectorService()

    def test_same_date_highest_score(self, service):
        """Misma fecha debería dar 30 puntos."""
        trans_1 = MagicMock()
        trans_1.comercio = "TEST"
        trans_1.monto_crc = Decimal("1000.00")
        trans_1.fecha_transaccion = date(2024, 1, 15)
        trans_1.account_id = None
        trans_1.account = None

        trans_2 = MagicMock()
        trans_2.comercio = "TEST"
        trans_2.monto_crc = Decimal("1000.00")
        trans_2.fecha_transaccion = date(2024, 1, 15)  # Misma fecha
        trans_2.account_id = None

        match = service._check_duplicate(trans_1, trans_2)

        assert match is not None
        assert any("Misma fecha" in r for r in match.reasons)

    def test_one_day_difference(self, service):
        """Diferencia de 1 día debería dar 20 puntos."""
        trans_1 = MagicMock()
        trans_1.comercio = "TEST"
        trans_1.monto_crc = Decimal("1000.00")
        trans_1.fecha_transaccion = date(2024, 1, 15)
        trans_1.account_id = None
        trans_1.account = None

        trans_2 = MagicMock()
        trans_2.comercio = "TEST"
        trans_2.monto_crc = Decimal("1000.00")
        trans_2.fecha_transaccion = date(2024, 1, 16)  # 1 día después
        trans_2.account_id = None

        match = service._check_duplicate(trans_1, trans_2)

        assert match is not None
        assert any("consecutivas" in r for r in match.reasons)

    def test_three_days_difference(self, service):
        """Diferencia de 3 días debería dar 10 puntos."""
        trans_1 = MagicMock()
        trans_1.comercio = "TEST"
        trans_1.monto_crc = Decimal("1000.00")
        trans_1.fecha_transaccion = date(2024, 1, 15)
        trans_1.account_id = None
        trans_1.account = None

        trans_2 = MagicMock()
        trans_2.comercio = "TEST"
        trans_2.monto_crc = Decimal("1000.00")
        trans_2.fecha_transaccion = date(2024, 1, 17)  # 2 días después
        trans_2.account_id = None

        match = service._check_duplicate(trans_1, trans_2)

        assert match is not None
        assert any("cercanas" in r for r in match.reasons)
