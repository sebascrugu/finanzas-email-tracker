"""Tests for Account model."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from finanzas_tracker.models.account import Account, AccountType


class TestAccountProperties:
    """Tests for Account model properties."""

    @pytest.fixture
    def savings_account(self) -> Account:
        """Create a savings account for testing."""
        return Account(
            id="account-uuid-1234",
            profile_id="profile-123",
            nombre="Ahorro BAC",
            tipo=AccountType.SAVINGS,
            moneda="CRC",
            saldo_actual=Decimal("500000.00"),
            tasa_interes=Decimal("3.5"),
            tipo_interes="simple",
            activa=True,
            incluir_en_patrimonio=True,
        )

    @pytest.fixture
    def investment_account(self) -> Account:
        """Create an investment account for testing."""
        return Account(
            id="account-uuid-5678",
            profile_id="profile-123",
            nombre="CDP Banco Popular",
            tipo=AccountType.INVESTMENT,
            moneda="CRC",
            saldo_actual=Decimal("1000000.00"),
            tasa_interes=Decimal("6.0"),
            tipo_interes="compuesto",
            activa=True,
            incluir_en_patrimonio=True,
        )

    def test_calcular_interes_mensual_simple(self, savings_account: Account) -> None:
        """Should calculate monthly interest for simple interest."""
        # 500000 * 3.5 / 12 / 100 = 1458.33
        result = savings_account.calcular_interes_mensual()
        assert result == Decimal("1458.33")

    def test_calcular_interes_mensual_zero_rate(self, savings_account: Account) -> None:
        """Should return 0 when no interest rate."""
        savings_account.tasa_interes = None
        result = savings_account.calcular_interes_mensual()
        assert result == Decimal("0")

    def test_calcular_interes_mensual_negative_rate(self, savings_account: Account) -> None:
        """Should return 0 when negative interest rate."""
        savings_account.tasa_interes = Decimal("-1.0")
        result = savings_account.calcular_interes_mensual()
        assert result == Decimal("0")

    def test_calcular_interes_anual_simple(self, savings_account: Account) -> None:
        """Should calculate annual interest for simple interest."""
        # 500000 * 3.5 / 100 = 17500
        result = savings_account.calcular_interes_anual()
        assert result == Decimal("17500.00")

    def test_calcular_interes_anual_compuesto(self, investment_account: Account) -> None:
        """Should calculate annual interest for compound interest."""
        # 1000000 * ((1 + 0.06)^1 - 1) = 60000
        result = investment_account.calcular_interes_anual()
        assert result == Decimal("60000.00")

    def test_calcular_interes_anual_zero_rate(self, savings_account: Account) -> None:
        """Should return 0 when no interest rate."""
        savings_account.tasa_interes = None
        result = savings_account.calcular_interes_anual()
        assert result == Decimal("0")

    def test_proyectar_saldo_simple(self, savings_account: Account) -> None:
        """Should project balance with simple interest."""
        # 12 months: 500000 + (500000 * 3.5 / 100 * 1) = 517500
        result = savings_account.proyectar_saldo(12)
        assert result == Decimal("517500.00")

    def test_proyectar_saldo_no_interest(self, savings_account: Account) -> None:
        """Should return same balance when no interest."""
        savings_account.tasa_interes = None
        result = savings_account.proyectar_saldo(12)
        assert result == savings_account.saldo_actual

    def test_repr(self, savings_account: Account) -> None:
        """Should return readable string representation."""
        repr_str = repr(savings_account)
        assert "Account" in repr_str
        assert "Ahorro BAC" in repr_str
        assert "CRC" in repr_str


class TestAccountType:
    """Tests for AccountType enum."""

    def test_savings_value(self) -> None:
        assert AccountType.SAVINGS.value == "savings"

    def test_checking_value(self) -> None:
        assert AccountType.CHECKING.value == "checking"

    def test_investment_value(self) -> None:
        assert AccountType.INVESTMENT.value == "investment"

    def test_cash_value(self) -> None:
        assert AccountType.CASH.value == "cash"
