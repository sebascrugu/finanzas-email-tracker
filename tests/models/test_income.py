"""Tests for Income model."""

from datetime import UTC, datetime, date
from decimal import Decimal

import pytest

from finanzas_tracker.models.enums import Currency, IncomeType, RecurrenceFrequency
from finanzas_tracker.models.income import Income


class TestIncomeProperties:
    """Tests for Income model properties."""

    @pytest.fixture
    def base_income(self) -> Income:
        """Create a basic income for testing."""
        return Income(
            id="test-uuid-1234",
            profile_id="profile-123",
            tipo=IncomeType.SALARY,
            descripcion="Salario Noviembre",
            monto_crc=Decimal("500000.00"),
            monto_original=Decimal("500000.00"),
            moneda_original=Currency.CRC,
            fecha=date(2025, 11, 15),
            es_recurrente=True,
            frecuencia=RecurrenceFrequency.MONTHLY,
            es_dinero_ajeno=False,
            excluir_de_presupuesto=False,
        )

    def test_monto_display_crc(self, base_income: Income) -> None:
        """Should format CRC amount correctly."""
        display = base_income.monto_display
        assert "₡500,000.00" in display
        assert "USD" not in display

    def test_monto_display_usd(self, base_income: Income) -> None:
        """Should format USD amount with original."""
        base_income.moneda_original = Currency.USD
        base_income.monto_original = Decimal("100.00")
        base_income.monto_crc = Decimal("52000.00")

        display = base_income.monto_display
        assert "₡52,000.00" in display
        assert "$100.00 USD" in display

    def test_esta_activo_true(self, base_income: Income) -> None:
        """Should return True when not deleted."""
        assert base_income.esta_activo is True

    def test_esta_activo_false(self, base_income: Income) -> None:
        """Should return False when soft deleted."""
        base_income.deleted_at = datetime.now(UTC)
        assert base_income.esta_activo is False


class TestIncomeMethods:
    """Tests for Income model methods."""

    @pytest.fixture
    def income(self) -> Income:
        """Create an income for testing."""
        return Income(
            id="test-uuid-5678",
            profile_id="profile-123",
            tipo=IncomeType.FREELANCE,
            descripcion="Proyecto Web",
            monto_crc=Decimal("200000.00"),
            monto_original=Decimal("200000.00"),
            moneda_original=Currency.CRC,
            fecha=date(2025, 11, 10),
            es_recurrente=False,
            es_dinero_ajeno=False,
            excluir_de_presupuesto=False,
        )

    def test_soft_delete(self, income: Income) -> None:
        """Should set deleted_at timestamp."""
        assert income.deleted_at is None
        income.soft_delete()
        assert income.deleted_at is not None

    def test_restore(self, income: Income) -> None:
        """Should clear deleted_at timestamp."""
        income.soft_delete()
        assert income.deleted_at is not None
        income.restore()
        assert income.deleted_at is None

    def test_calcular_monto_patrimonio_normal(self, income: Income) -> None:
        """Should return full amount for normal income."""
        result = income.calcular_monto_patrimonio()
        assert result == Decimal("200000.00")

    def test_calcular_monto_patrimonio_dinero_ajeno_con_sobrante(self, income: Income) -> None:
        """Should return sobrante when dinero ajeno."""
        income.es_dinero_ajeno = True
        income.monto_sobrante = Decimal("50000.00")

        result = income.calcular_monto_patrimonio()
        assert result == Decimal("50000.00")

    def test_calcular_monto_patrimonio_excluido(self, income: Income) -> None:
        """Should return 0 when excluded and not dinero ajeno."""
        income.excluir_de_presupuesto = True
        income.es_dinero_ajeno = False

        result = income.calcular_monto_patrimonio()
        assert result == Decimal("0")

    def test_repr(self, income: Income) -> None:
        """Should return readable string representation."""
        repr_str = repr(income)
        assert "Income" in repr_str
        assert "freelance" in repr_str
        assert "200,000.00" in repr_str
