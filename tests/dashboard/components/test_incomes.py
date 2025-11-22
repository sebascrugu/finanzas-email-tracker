"""Tests for dashboard incomes component."""

from datetime import date

import pytest

from finanzas_tracker.dashboard.components.incomes import (
    calcular_proximo_ingreso,
    es_tipo_recurrente,
    TIPOS_RECURRENTES,
    OPCIONES_TIPO_INGRESO,
    TIPOS_ESPECIALES,
)
from finanzas_tracker.models.enums import IncomeType


class TestEsTipoRecurrente:
    """Tests for es_tipo_recurrente function."""

    def test_salary_is_recurrent(self) -> None:
        """Salary should be marked as recurrent."""
        assert es_tipo_recurrente(IncomeType.SALARY) is True

    def test_pension_is_recurrent(self) -> None:
        """Pension should be marked as recurrent."""
        assert es_tipo_recurrente(IncomeType.PENSION) is True

    def test_freelance_not_recurrent(self) -> None:
        """Freelance should not be recurrent."""
        assert es_tipo_recurrente(IncomeType.FREELANCE) is False

    def test_sale_not_recurrent(self) -> None:
        """Sale should not be recurrent."""
        assert es_tipo_recurrente(IncomeType.SALE) is False

    def test_gift_not_recurrent(self) -> None:
        """Gift should not be recurrent."""
        assert es_tipo_recurrente(IncomeType.GIFT) is False

    def test_other_not_recurrent(self) -> None:
        """Other should not be recurrent."""
        assert es_tipo_recurrente(IncomeType.OTHER) is False


class TestCalcularProximoIngreso:
    """Tests for calcular_proximo_ingreso function."""

    def test_salary_returns_next_month(self) -> None:
        """Salary should return next month same day."""
        result = calcular_proximo_ingreso(IncomeType.SALARY, date(2025, 11, 15))
        assert result == date(2025, 12, 15)

    def test_pension_returns_next_month(self) -> None:
        """Pension should return next month same day."""
        result = calcular_proximo_ingreso(IncomeType.PENSION, date(2025, 6, 10))
        assert result == date(2025, 7, 10)

    def test_december_wraps_to_january(self) -> None:
        """December should wrap to January next year."""
        result = calcular_proximo_ingreso(IncomeType.SALARY, date(2025, 12, 15))
        assert result == date(2026, 1, 15)

    def test_day_31_adjusts_to_28(self) -> None:
        """Day 31 in month without 31 days should adjust to 28."""
        result = calcular_proximo_ingreso(IncomeType.SALARY, date(2025, 1, 31))
        # February doesn't have 31 days, should return 28
        assert result == date(2025, 2, 28)

    def test_non_recurrent_returns_none(self) -> None:
        """Non-recurrent types should return None."""
        assert calcular_proximo_ingreso(IncomeType.FREELANCE, date(2025, 11, 15)) is None
        assert calcular_proximo_ingreso(IncomeType.SALE, date(2025, 11, 15)) is None
        assert calcular_proximo_ingreso(IncomeType.GIFT, date(2025, 11, 15)) is None


class TestConstants:
    """Tests for module constants."""

    def test_tipos_recurrentes_contains_salary_and_pension(self) -> None:
        """TIPOS_RECURRENTES should contain salary and pension."""
        assert IncomeType.SALARY in TIPOS_RECURRENTES
        assert IncomeType.PENSION in TIPOS_RECURRENTES

    def test_opciones_tipo_ingreso_has_all_types(self) -> None:
        """OPCIONES_TIPO_INGRESO should have entries for all common income types."""
        tipos = [opt[0] for opt in OPCIONES_TIPO_INGRESO]
        assert IncomeType.SALARY in tipos
        assert IncomeType.PENSION in tipos
        assert IncomeType.FREELANCE in tipos
        assert IncomeType.SALE in tipos
        assert IncomeType.OTHER in tipos

    def test_tipos_especiales_has_expected_keys(self) -> None:
        """TIPOS_ESPECIALES should have expected keys."""
        assert "ninguno" in TIPOS_ESPECIALES
        assert "dinero_ajeno" in TIPOS_ESPECIALES
        assert "transferencia_propia" in TIPOS_ESPECIALES
        assert "ajuste_inicial" in TIPOS_ESPECIALES
        assert "otro" in TIPOS_ESPECIALES
