"""Tests for CardService.

Coverage target: Core CRUD operations, billing cycles, payments,
and calculations for credit card management.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from finanzas_tracker.models.billing_cycle import BillingCycle
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.card_payment import CardPayment
from finanzas_tracker.models.enums import (
    BankName,
    BillingCycleStatus,
    CardPaymentType,
    CardType,
)
from finanzas_tracker.services.card_service import CardService


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_db() -> MagicMock:
    """Create a mock database session."""
    db = MagicMock(spec=Session)
    return db


@pytest.fixture
def card_service(mock_db: MagicMock) -> CardService:
    """Create CardService with mock db."""
    return CardService(mock_db)


@pytest.fixture
def sample_credit_card() -> Card:
    """Create a sample credit card."""
    return Card(
        id=str(uuid4()),
        profile_id=str(uuid4()),
        banco=BankName.BAC,
        tipo=CardType.CREDIT,
        ultimos_4_digitos="6380",
        alias="AMEX Personal",
        limite_credito=Decimal("1000000.00"),
        interest_rate_annual=Decimal("52.00"),
        minimum_payment_percentage=Decimal("10.00"),
        fecha_corte=15,
        fecha_vencimiento=28,
        activa=True,
    )


@pytest.fixture
def sample_billing_cycle(sample_credit_card: Card) -> BillingCycle:
    """Create a sample billing cycle."""
    today = date.today()
    return BillingCycle(
        id=str(uuid4()),
        card_id=sample_credit_card.id,
        fecha_inicio=today - timedelta(days=30),
        fecha_corte=today - timedelta(days=15),
        fecha_pago=today + timedelta(days=5),
        saldo_anterior=Decimal("50000.00"),
        total_periodo=Decimal("150000.00"),
        pago_minimo=Decimal("20000.00"),
        total_a_pagar=Decimal("200000.00"),
        monto_pagado=Decimal("0.00"),
        status=BillingCycleStatus.CLOSED,
    )


@pytest.fixture
def sample_payment(sample_credit_card: Card) -> CardPayment:
    """Create a sample card payment."""
    return CardPayment(
        id=str(uuid4()),
        card_id=sample_credit_card.id,
        monto=Decimal("100000.00"),
        tipo=CardPaymentType.PARTIAL,
        fecha_pago=date.today(),
    )


# =============================================================================
# Tests: Card Retrieval
# =============================================================================


class TestGetCard:
    """Tests for get_card method."""

    def test_get_card_returns_card_when_exists(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
    ) -> None:
        """Should return card when found."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_credit_card

        result = card_service.get_card(sample_credit_card.id)

        assert result == sample_credit_card
        mock_db.execute.assert_called_once()

    def test_get_card_returns_none_when_not_exists(
        self,
        card_service: CardService,
        mock_db: MagicMock,
    ) -> None:
        """Should return None when card not found."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = card_service.get_card("non-existent-id")

        assert result is None


class TestGetCardsByProfile:
    """Tests for get_cards_by_profile method."""

    def test_get_cards_by_profile_returns_all_cards(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
    ) -> None:
        """Should return all cards for profile."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_credit_card]

        result = card_service.get_cards_by_profile(sample_credit_card.profile_id)

        assert len(result) == 1
        assert result[0] == sample_credit_card

    def test_get_cards_by_profile_filters_by_type(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
    ) -> None:
        """Should filter by card type when specified."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_credit_card]

        result = card_service.get_cards_by_profile(
            sample_credit_card.profile_id,
            tipo=CardType.CREDIT,
        )

        assert len(result) == 1
        mock_db.execute.assert_called_once()

    def test_get_credit_cards_calls_with_credit_type(
        self,
        card_service: CardService,
        mock_db: MagicMock,
    ) -> None:
        """Should call get_cards_by_profile with CREDIT type."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        profile_id = str(uuid4())
        card_service.get_credit_cards(profile_id)

        mock_db.execute.assert_called_once()


# =============================================================================
# Tests: Billing Cycles
# =============================================================================


class TestGetBillingCycle:
    """Tests for billing cycle retrieval methods."""

    def test_get_billing_cycle_returns_cycle_when_exists(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_billing_cycle: BillingCycle,
    ) -> None:
        """Should return billing cycle when found."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_billing_cycle

        result = card_service.get_billing_cycle(sample_billing_cycle.id)

        assert result == sample_billing_cycle

    def test_get_billing_cycle_returns_none_when_not_exists(
        self,
        card_service: CardService,
        mock_db: MagicMock,
    ) -> None:
        """Should return None when cycle not found."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = card_service.get_billing_cycle("non-existent-id")

        assert result is None

    def test_get_current_cycle_returns_open_cycle(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_billing_cycle: BillingCycle,
    ) -> None:
        """Should return the open cycle for a card."""
        sample_billing_cycle.status = BillingCycleStatus.OPEN
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_billing_cycle

        result = card_service.get_current_cycle(sample_billing_cycle.card_id)

        assert result == sample_billing_cycle
        assert result.status == BillingCycleStatus.OPEN

    def test_get_pending_cycles_returns_closed_cycles(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_billing_cycle: BillingCycle,
    ) -> None:
        """Should return cycles with pending status."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_billing_cycle]

        result = card_service.get_pending_cycles(sample_billing_cycle.card_id)

        assert len(result) == 1
        assert result[0].status == BillingCycleStatus.CLOSED

    def test_get_cycles_by_card_returns_limited_cycles(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_billing_cycle: BillingCycle,
    ) -> None:
        """Should return limited cycles ordered by date."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_billing_cycle]

        result = card_service.get_cycles_by_card(sample_billing_cycle.card_id, limit=5)

        assert len(result) == 1


class TestCreateCycle:
    """Tests for create_cycle method."""

    def test_create_cycle_with_all_fields(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
    ) -> None:
        """Should create a cycle with all provided fields."""
        today = date.today()
        fecha_inicio = today - timedelta(days=30)
        fecha_corte = today - timedelta(days=15)
        fecha_pago = today + timedelta(days=5)
        saldo_anterior = Decimal("25000.00")

        card_service.create_cycle(
            card_id=sample_credit_card.id,
            fecha_inicio=fecha_inicio,
            fecha_corte=fecha_corte,
            fecha_pago=fecha_pago,
            saldo_anterior=saldo_anterior,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        # Verify the cycle was created correctly
        added_cycle = mock_db.add.call_args[0][0]
        assert isinstance(added_cycle, BillingCycle)
        assert added_cycle.card_id == sample_credit_card.id
        assert added_cycle.fecha_inicio == fecha_inicio
        assert added_cycle.fecha_corte == fecha_corte
        assert added_cycle.fecha_pago == fecha_pago
        assert added_cycle.saldo_anterior == saldo_anterior
        assert added_cycle.status == BillingCycleStatus.OPEN

    def test_create_cycle_with_default_saldo(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
    ) -> None:
        """Should create a cycle with zero saldo_anterior by default."""
        today = date.today()

        card_service.create_cycle(
            card_id=sample_credit_card.id,
            fecha_inicio=today - timedelta(days=30),
            fecha_corte=today - timedelta(days=15),
            fecha_pago=today + timedelta(days=5),
        )

        added_cycle = mock_db.add.call_args[0][0]
        assert added_cycle.saldo_anterior == Decimal("0.00")


class TestCreateNextCycleForCard:
    """Tests for create_next_cycle_for_card method."""

    def test_create_next_cycle_returns_none_for_debit_card(
        self,
        card_service: CardService,
        mock_db: MagicMock,
    ) -> None:
        """Should return None for debit cards."""
        debit_card = Card(
            id=str(uuid4()),
            profile_id=str(uuid4()),
            banco=BankName.BAC,
            tipo=CardType.DEBIT,
            ultimos_4_digitos="1234",
        )

        result = card_service.create_next_cycle_for_card(debit_card)

        assert result is None

    def test_create_next_cycle_returns_none_without_fecha_corte(
        self,
        card_service: CardService,
        mock_db: MagicMock,
    ) -> None:
        """Should return None if card has no fecha_corte."""
        credit_card = Card(
            id=str(uuid4()),
            profile_id=str(uuid4()),
            banco=BankName.BAC,
            tipo=CardType.CREDIT,
            ultimos_4_digitos="1234",
            fecha_corte=None,
        )

        result = card_service.create_next_cycle_for_card(credit_card)

        assert result is None

    def test_create_next_cycle_creates_cycle_for_credit_card(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
    ) -> None:
        """Should create a cycle for valid credit card."""
        # Mock get_pending_cycles to return empty list
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = card_service.create_next_cycle_for_card(sample_credit_card)

        # Should have created a cycle
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestCloseCycle:
    """Tests for close_cycle method."""

    def test_close_cycle_returns_none_when_not_found(
        self,
        card_service: CardService,
        mock_db: MagicMock,
    ) -> None:
        """Should return None when cycle doesn't exist."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = card_service.close_cycle("non-existent-id")

        assert result is None

    def test_close_cycle_closes_and_returns_cycle(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_billing_cycle: BillingCycle,
    ) -> None:
        """Should close cycle and return it."""
        sample_billing_cycle.status = BillingCycleStatus.OPEN
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_billing_cycle

        # Mock cerrar_ciclo method
        sample_billing_cycle.cerrar_ciclo = MagicMock()

        result = card_service.close_cycle(sample_billing_cycle.id)

        assert result == sample_billing_cycle
        sample_billing_cycle.cerrar_ciclo.assert_called_once()
        mock_db.commit.assert_called_once()


class TestAddPurchaseToCycle:
    """Tests for add_purchase_to_cycle method."""

    def test_add_purchase_returns_none_when_cycle_not_found(
        self,
        card_service: CardService,
        mock_db: MagicMock,
    ) -> None:
        """Should return None when cycle doesn't exist."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = card_service.add_purchase_to_cycle(
            cycle_id="non-existent-id",
            monto=Decimal("10000.00"),
        )

        assert result is None

    def test_add_purchase_returns_none_when_cycle_not_open(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_billing_cycle: BillingCycle,
    ) -> None:
        """Should return None when cycle is not open."""
        sample_billing_cycle.status = BillingCycleStatus.CLOSED
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_billing_cycle

        result = card_service.add_purchase_to_cycle(
            cycle_id=sample_billing_cycle.id,
            monto=Decimal("10000.00"),
        )

        assert result is None

    def test_add_purchase_updates_total_periodo(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_billing_cycle: BillingCycle,
    ) -> None:
        """Should add monto to total_periodo."""
        sample_billing_cycle.status = BillingCycleStatus.OPEN
        sample_billing_cycle.total_periodo = Decimal("100000.00")
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_billing_cycle

        monto = Decimal("25000.00")
        result = card_service.add_purchase_to_cycle(
            cycle_id=sample_billing_cycle.id,
            monto=monto,
        )

        assert result.total_periodo == Decimal("125000.00")
        mock_db.commit.assert_called_once()


# =============================================================================
# Tests: Payments
# =============================================================================


class TestRegisterPayment:
    """Tests for register_payment method."""

    def test_register_payment_creates_payment(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
    ) -> None:
        """Should create a payment record."""
        monto = Decimal("50000.00")

        card_service.register_payment(
            card_id=sample_credit_card.id,
            monto=monto,
        )

        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

        added_payment = mock_db.add.call_args[0][0]
        assert isinstance(added_payment, CardPayment)
        assert added_payment.card_id == sample_credit_card.id
        assert added_payment.monto == monto

    def test_register_payment_with_cycle_updates_cycle(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
        sample_billing_cycle: BillingCycle,
    ) -> None:
        """Should update cycle's monto_pagado when cycle is provided."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_billing_cycle
        sample_billing_cycle.registrar_pago = MagicMock()

        monto = Decimal("100000.00")
        card_service.register_payment(
            card_id=sample_credit_card.id,
            monto=monto,
            billing_cycle_id=sample_billing_cycle.id,
        )

        sample_billing_cycle.registrar_pago.assert_called_once_with(monto)

    def test_register_payment_detects_full_payment(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
        sample_billing_cycle: BillingCycle,
    ) -> None:
        """Should detect FULL payment type when monto >= total_a_pagar."""
        sample_billing_cycle.total_a_pagar = Decimal("100000.00")
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_billing_cycle
        sample_billing_cycle.registrar_pago = MagicMock()

        card_service.register_payment(
            card_id=sample_credit_card.id,
            monto=Decimal("100000.00"),
            billing_cycle_id=sample_billing_cycle.id,
        )

        added_payment = mock_db.add.call_args[0][0]
        assert added_payment.tipo == CardPaymentType.FULL

    def test_register_payment_detects_minimum_payment(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
        sample_billing_cycle: BillingCycle,
    ) -> None:
        """Should detect MINIMUM payment type when monto <= pago_minimo."""
        sample_billing_cycle.pago_minimo = Decimal("20000.00")
        sample_billing_cycle.total_a_pagar = Decimal("200000.00")
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_billing_cycle
        sample_billing_cycle.registrar_pago = MagicMock()

        card_service.register_payment(
            card_id=sample_credit_card.id,
            monto=Decimal("20000.00"),
            billing_cycle_id=sample_billing_cycle.id,
        )

        added_payment = mock_db.add.call_args[0][0]
        assert added_payment.tipo == CardPaymentType.MINIMUM


class TestGetPayments:
    """Tests for payment retrieval methods."""

    def test_get_payments_by_card_returns_payments(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_payment: CardPayment,
    ) -> None:
        """Should return payments for a card."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_payment]

        result = card_service.get_payments_by_card(sample_payment.card_id)

        assert len(result) == 1
        assert result[0] == sample_payment

    def test_get_payments_by_cycle_returns_payments(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_payment: CardPayment,
    ) -> None:
        """Should return payments for a cycle."""
        sample_payment.billing_cycle_id = str(uuid4())
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_payment]

        result = card_service.get_payments_by_cycle(sample_payment.billing_cycle_id)

        assert len(result) == 1


# =============================================================================
# Tests: Calculations
# =============================================================================


class TestCalculateTotalDebt:
    """Tests for calculate_total_debt method."""

    def test_calculate_total_debt_with_no_cycles(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
    ) -> None:
        """Should return zero when no cycles exist."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = card_service.calculate_total_debt(sample_credit_card.id)

        assert result == Decimal("0.00")

    def test_calculate_total_debt_includes_current_cycle(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
    ) -> None:
        """Should include current cycle amounts."""
        current_cycle = BillingCycle(
            id=str(uuid4()),
            card_id=sample_credit_card.id,
            fecha_inicio=date.today() - timedelta(days=15),
            fecha_corte=date.today() + timedelta(days=15),
            fecha_pago=date.today() + timedelta(days=30),
            saldo_anterior=Decimal("10000.00"),
            total_periodo=Decimal("50000.00"),
            status=BillingCycleStatus.OPEN,
        )

        # First call returns current cycle, second returns empty pending list
        mock_db.execute.return_value.scalar_one_or_none.return_value = current_cycle
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = card_service.calculate_total_debt(sample_credit_card.id)

        assert result == Decimal("60000.00")  # 10000 + 50000


class TestCalculateInterestProjection:
    """Tests for calculate_interest_projection method."""

    def test_interest_projection_returns_error_when_card_not_found(
        self,
        card_service: CardService,
        mock_db: MagicMock,
    ) -> None:
        """Should return error when card doesn't exist."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = card_service.calculate_interest_projection("non-existent-id")

        assert "error" in result

    def test_interest_projection_returns_error_without_interest_rate(
        self,
        card_service: CardService,
        mock_db: MagicMock,
    ) -> None:
        """Should return error when card has no interest rate."""
        card = Card(
            id=str(uuid4()),
            profile_id=str(uuid4()),
            banco=BankName.BAC,
            tipo=CardType.CREDIT,
            ultimos_4_digitos="1234",
            interest_rate_annual=None,
        )
        mock_db.execute.return_value.scalar_one_or_none.return_value = card

        result = card_service.calculate_interest_projection(card.id)

        assert "error" in result

    def test_interest_projection_calculates_correctly(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
    ) -> None:
        """Should calculate interest projection with correct values."""
        # Mock card retrieval
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [
            sample_credit_card,  # get_card
            None,  # get_current_cycle
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = card_service.calculate_interest_projection(
            card_id=sample_credit_card.id,
            meses=3,
        )

        assert "deuda_inicial" in result
        assert "total_intereses" in result
        assert "meses_proyectados" in result
        assert result["meses_proyectados"] == 3
        assert "historial" in result
        assert len(result["historial"]) == 3


# =============================================================================
# Tests: Alerts
# =============================================================================


class TestGetUpcomingPayments:
    """Tests for get_upcoming_payments method."""

    def test_get_upcoming_payments_returns_empty_when_no_cards(
        self,
        card_service: CardService,
        mock_db: MagicMock,
    ) -> None:
        """Should return empty list when no credit cards."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = card_service.get_upcoming_payments(str(uuid4()))

        assert result == []

    def test_get_upcoming_payments_returns_due_payments(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
    ) -> None:
        """Should return payments due within specified days."""
        # Create a pending cycle with saldo_pendiente property
        pending_cycle = MagicMock(spec=BillingCycle)
        pending_cycle.id = str(uuid4())
        pending_cycle.card_id = sample_credit_card.id
        pending_cycle.fecha_pago = date.today() + timedelta(days=3)  # Due in 3 days
        pending_cycle.saldo_pendiente = Decimal("100000.00")
        pending_cycle.pago_minimo = Decimal("10000.00")
        pending_cycle.status = BillingCycleStatus.CLOSED

        # Mock: first call returns cards, second returns pending cycles
        mock_db.execute.return_value.scalars.return_value.all.side_effect = [
            [sample_credit_card],  # get_credit_cards
            [pending_cycle],  # get_pending_cycles
        ]

        result = card_service.get_upcoming_payments(sample_credit_card.profile_id, dias=7)

        assert len(result) == 1
        assert result[0]["dias_restantes"] == 3
        assert result[0]["es_urgente"] is True


class TestGetOverdueCycles:
    """Tests for get_overdue_cycles method."""

    def test_get_overdue_cycles_returns_empty_when_no_overdue(
        self,
        card_service: CardService,
        mock_db: MagicMock,
    ) -> None:
        """Should return empty list when no overdue cycles."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        result = card_service.get_overdue_cycles(str(uuid4()))

        assert result == []


# =============================================================================
# Tests: Card Summary
# =============================================================================


class TestGetCardSummary:
    """Tests for get_card_summary method."""

    def test_get_card_summary_returns_none_when_card_not_found(
        self,
        card_service: CardService,
        mock_db: MagicMock,
    ) -> None:
        """Should return None when card doesn't exist."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None

        result = card_service.get_card_summary("non-existent-id")

        assert result is None

    def test_get_card_summary_returns_complete_summary(
        self,
        card_service: CardService,
        mock_db: MagicMock,
        sample_credit_card: Card,
    ) -> None:
        """Should return complete card summary."""
        # Create mock that returns card first, then None for current cycle
        call_count = 0
        
        def mock_scalar_one_or_none():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return sample_credit_card  # get_card
            return None  # get_current_cycle and others
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.side_effect = mock_scalar_one_or_none
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        result = card_service.get_card_summary(sample_credit_card.id)

        assert result is not None
        assert "tarjeta" in result
        assert result["tarjeta"]["id"] == sample_credit_card.id
        assert "deuda_total" in result
        assert "ultimos_pagos" in result
