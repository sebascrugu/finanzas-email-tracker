"""Tests for IncomeSplit model."""

from decimal import Decimal

from finanzas_tracker.models.income_split import IncomeSplit


class TestIncomeSplit:
    """Tests for IncomeSplit model."""

    def test_repr(self) -> None:
        """Should return readable string representation."""
        split = IncomeSplit(
            id="split-uuid-1234567890",
            income_id="income-123",
            monto_asignado=Decimal("50000.00"),
            proposito="Pago de deuda",
        )

        repr_str = repr(split)

        assert "IncomeSplit" in repr_str
        assert "split-uu" in repr_str  # First 8 characters
        assert "50,000.00" in repr_str
        assert "Pago de deuda" in repr_str
