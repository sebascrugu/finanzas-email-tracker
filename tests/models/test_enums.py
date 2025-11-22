"""Tests for model enums."""

import pytest

from finanzas_tracker.models.enums import (
    BankName,
    Currency,
    TransactionType,
    IncomeType,
    RecurrenceFrequency,
    CardType,
)


class TestBankName:
    """Tests for BankName enum."""

    def test_bac_value(self) -> None:
        assert BankName.BAC.value == "bac"

    def test_popular_value(self) -> None:
        assert BankName.POPULAR.value == "popular"

    def test_all_banks(self) -> None:
        banks = list(BankName)
        assert len(banks) >= 2


class TestCurrency:
    """Tests for Currency enum."""

    def test_crc_value(self) -> None:
        assert Currency.CRC.value == "CRC"

    def test_usd_value(self) -> None:
        assert Currency.USD.value == "USD"


class TestTransactionType:
    """Tests for TransactionType enum."""

    def test_purchase(self) -> None:
        assert TransactionType.PURCHASE.value == "compra"

    def test_transfer(self) -> None:
        assert TransactionType.TRANSFER.value == "transferencia"

    def test_sinpe(self) -> None:
        assert TransactionType.SINPE.value == "sinpe"

    def test_withdrawal(self) -> None:
        assert TransactionType.WITHDRAWAL.value == "retiro"


class TestIncomeType:
    """Tests for IncomeType enum."""

    def test_salary(self) -> None:
        assert IncomeType.SALARY.value == "salario"

    def test_freelance(self) -> None:
        assert IncomeType.FREELANCE.value == "freelance"

    def test_other(self) -> None:
        assert IncomeType.OTHER.value == "otro"


class TestRecurrenceFrequency:
    """Tests for RecurrenceFrequency enum."""

    def test_monthly(self) -> None:
        assert RecurrenceFrequency.MONTHLY.value == "mensual"

    def test_weekly(self) -> None:
        assert RecurrenceFrequency.WEEKLY.value == "semanal"


class TestCardType:
    """Tests for CardType enum."""

    def test_credit(self) -> None:
        assert CardType.CREDIT.value == "credito"

    def test_debit(self) -> None:
        assert CardType.DEBIT.value == "debito"


class TestEnumStringMethods:
    """Tests for enum __str__ methods."""

    def test_bank_name_str(self) -> None:
        """Should return value as string."""
        assert str(BankName.BAC) == "bac"

    def test_currency_str(self) -> None:
        """Should return value as string."""
        assert str(Currency.CRC) == "CRC"

    def test_transaction_type_str(self) -> None:
        """Should return value as string."""
        assert str(TransactionType.PURCHASE) == "compra"

    def test_income_type_str(self) -> None:
        """Should return value as string."""
        assert str(IncomeType.SALARY) == "salario"

    def test_recurrence_frequency_str(self) -> None:
        """Should return value as string."""
        assert str(RecurrenceFrequency.MONTHLY) == "mensual"


