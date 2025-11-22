"""Tests for Budget model."""

from datetime import date
from decimal import Decimal

import pytest

from finanzas_tracker.models.budget import Budget


class TestBudget:
    """Tests for Budget model."""

    @pytest.fixture
    def budget(self) -> Budget:
        """Create a basic budget for testing."""
        return Budget(
            profile_id="profile-123",
            salario_mensual=Decimal("500000"),
            porcentaje_necesidades=Decimal("50"),
            porcentaje_gustos=Decimal("30"),
            porcentaje_ahorros=Decimal("20"),
            fecha_inicio=date(2025, 1, 1),
        )

    def test_monto_necesidades(self, budget: Budget) -> None:
        """Should calculate necessities amount correctly."""
        assert budget.monto_necesidades == Decimal("250000")  # 50% of 500000

    def test_monto_gustos(self, budget: Budget) -> None:
        """Should calculate wants amount correctly."""
        assert budget.monto_gustos == Decimal("150000")  # 30% of 500000

    def test_monto_ahorros(self, budget: Budget) -> None:
        """Should calculate savings amount correctly."""
        assert budget.monto_ahorros == Decimal("100000")  # 20% of 500000

    def test_esta_activo_true(self, budget: Budget) -> None:
        """Should return True when no end date."""
        budget.fecha_fin = None
        assert budget.esta_activo is True

    def test_esta_activo_false(self, budget: Budget) -> None:
        """Should return False when end date is set."""
        budget.fecha_fin = date(2025, 12, 31)
        assert budget.esta_activo is False

    def test_validar_porcentajes_valid(self, budget: Budget) -> None:
        """Should return True when percentages sum to 100."""
        assert budget.validar_porcentajes() is True

    def test_validar_porcentajes_invalid(self, budget: Budget) -> None:
        """Should return False when percentages don't sum to 100."""
        budget.porcentaje_ahorros = Decimal("25")  # Now sums to 105
        assert budget.validar_porcentajes() is False

    def test_repr(self, budget: Budget) -> None:
        """Should return readable string representation."""
        repr_str = repr(budget)
        assert "Budget" in repr_str
        assert "500,000" in repr_str
        assert "2025-01-01" in repr_str
