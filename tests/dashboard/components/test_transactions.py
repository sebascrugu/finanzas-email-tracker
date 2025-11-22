"""Tests for dashboard transactions component."""

import pytest

from finanzas_tracker.dashboard.components.transactions import (
    TIPOS_GASTO,
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
    """Tests for TIPOS_GASTO constant."""

    def test_has_expected_entries(self) -> None:
        """TIPOS_GASTO should have all expected entry types."""
        keys = [t[0] for t in TIPOS_GASTO]
        assert "normal" in keys
        assert "gasto_ajeno" in keys
        assert "intermediaria" in keys
        assert "reembolso" in keys
        assert "compartida" in keys
        assert "transferencia_propia" in keys

    def test_all_entries_have_descriptions(self) -> None:
        """All entries should have non-empty descriptions."""
        for key, description in TIPOS_GASTO:
            assert key, "Key should not be empty"
            assert description, "Description should not be empty"
            assert len(description) > 10, "Description should be meaningful"

    def test_normal_is_first(self) -> None:
        """Normal should be the first option (default)."""
        assert TIPOS_GASTO[0][0] == "normal"
