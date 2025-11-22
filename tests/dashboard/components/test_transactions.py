"""Tests for dashboard transactions component."""

from finanzas_tracker.dashboard.components.transactions import (
    TIPOS_GASTO_COMUNES,
    _es_transferencia_o_sinpe,
)
from finanzas_tracker.models.enums import TransactionType


class TestEsTransferenciaOSinpe:
    """Tests for _es_transferencia_o_sinpe function."""

    def test_transfer_returns_true(self) -> None:
        """TRANSFER type should return True."""

        class MockTransaction:
            tipo_transaccion = TransactionType.TRANSFER

        assert _es_transferencia_o_sinpe(MockTransaction()) is True

    def test_sinpe_returns_true(self) -> None:
        """SINPE type should return True."""

        class MockTransaction:
            tipo_transaccion = TransactionType.SINPE

        assert _es_transferencia_o_sinpe(MockTransaction()) is True

    def test_purchase_returns_false(self) -> None:
        """PURCHASE type should return False."""

        class MockTransaction:
            tipo_transaccion = TransactionType.PURCHASE

        assert _es_transferencia_o_sinpe(MockTransaction()) is False

    def test_withdrawal_returns_false(self) -> None:
        """WITHDRAWAL type should return False."""

        class MockTransaction:
            tipo_transaccion = TransactionType.WITHDRAWAL

        assert _es_transferencia_o_sinpe(MockTransaction()) is False


class TestTiposGastoConstant:
    """Tests for TIPOS_GASTO_COMUNES constant."""

    def test_has_expected_entries(self) -> None:
        """TIPOS_GASTO_COMUNES should have common entry types."""
        assert "normal" in TIPOS_GASTO_COMUNES
        assert "dinero_ajeno" in TIPOS_GASTO_COMUNES
        assert "intermediaria" in TIPOS_GASTO_COMUNES
        assert "transferencia_propia" in TIPOS_GASTO_COMUNES
        assert "otro" in TIPOS_GASTO_COMUNES

    def test_all_entries_have_descriptions(self) -> None:
        """All entries should have non-empty descriptions."""
        for key, description in TIPOS_GASTO_COMUNES.items():
            assert key, "Key should not be empty"
            assert description, "Description should not be empty"
            assert len(description) > 3, "Description should be meaningful"

    def test_normal_is_in_dict(self) -> None:
        """Normal should be in the dictionary."""
        assert "normal" in TIPOS_GASTO_COMUNES
        assert TIPOS_GASTO_COMUNES["normal"] == "Normal"
