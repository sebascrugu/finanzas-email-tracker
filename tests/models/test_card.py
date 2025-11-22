"""Tests for Card model."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from finanzas_tracker.models.card import Card
from finanzas_tracker.models.enums import BankName, CardType


class TestCardProperties:
    """Tests for Card model properties."""

    @pytest.fixture
    def credit_card(self) -> Card:
        """Create a credit card for testing."""
        return Card(
            id="card-uuid-1234",
            profile_id="profile-123",
            banco=BankName.BAC,
            tipo=CardType.CREDIT,
            ultimos_4_digitos="6380",
            alias="AMEX Personal",
            limite_credito=Decimal("1000000.00"),
            activa=True,
        )

    @pytest.fixture
    def debit_card(self) -> Card:
        """Create a debit card for testing."""
        return Card(
            id="card-uuid-5678",
            profile_id="profile-123",
            banco=BankName.POPULAR,
            tipo=CardType.DEBIT,
            ultimos_4_digitos="1234",
            activa=True,
        )

    def test_nombre_display_with_alias(self, credit_card: Card) -> None:
        """Should return alias with last 4 digits."""
        assert credit_card.nombre_display == "AMEX Personal (****6380)"

    def test_nombre_display_without_alias(self, debit_card: Card) -> None:
        """Should return type and bank with last 4 digits."""
        assert "Débito" in debit_card.nombre_display
        assert "POPULAR" in debit_card.nombre_display
        assert "1234" in debit_card.nombre_display

    def test_es_credito_true(self, credit_card: Card) -> None:
        """Should return True for credit card."""
        assert credit_card.es_credito is True

    def test_es_credito_false(self, debit_card: Card) -> None:
        """Should return False for debit card."""
        assert debit_card.es_credito is False

    def test_es_debito_true(self, debit_card: Card) -> None:
        """Should return True for debit card."""
        assert debit_card.es_debito is True

    def test_es_debito_false(self, credit_card: Card) -> None:
        """Should return False for credit card."""
        assert credit_card.es_debito is False

    def test_esta_activa_true(self, credit_card: Card) -> None:
        """Should return True when active and not deleted."""
        assert credit_card.esta_activa is True

    def test_esta_activa_false_deleted(self, credit_card: Card) -> None:
        """Should return False when soft deleted."""
        credit_card.deleted_at = datetime.now(UTC)
        assert credit_card.esta_activa is False

    def test_esta_activa_false_inactive(self, credit_card: Card) -> None:
        """Should return False when inactive."""
        credit_card.activa = False
        assert credit_card.esta_activa is False


class TestCardMethods:
    """Tests for Card model methods."""

    @pytest.fixture
    def card(self) -> Card:
        """Create a card for testing."""
        return Card(
            id="card-uuid-9999",
            profile_id="profile-123",
            banco=BankName.BAC,
            tipo=CardType.CREDIT,
            ultimos_4_digitos="0000",
            limite_credito=Decimal("500000.00"),
            activa=True,
        )

    def test_soft_delete(self, card: Card) -> None:
        """Should set deleted_at and deactivate."""
        assert card.deleted_at is None
        assert card.activa is True

        card.soft_delete()

        assert card.deleted_at is not None
        assert card.activa is False

    def test_restore(self, card: Card) -> None:
        """Should clear deleted_at and activate."""
        card.soft_delete()

        card.restore()

        assert card.deleted_at is None
        assert card.activa is True

    def test_calcular_disponible_credito_debit_card(self, card: Card) -> None:
        """Should return None for debit cards."""
        card.tipo = CardType.DEBIT
        result = card.calcular_disponible_credito(11, 2025)
        assert result is None

    def test_calcular_disponible_credito_no_limit(self, card: Card) -> None:
        """Should return None when no credit limit."""
        card.limite_credito = None
        result = card.calcular_disponible_credito(11, 2025)
        assert result is None

    def test_repr(self, card: Card) -> None:
        """Should return readable string representation."""
        repr_str = repr(card)
        assert "Card" in repr_str
        assert "0000" in repr_str

    def test_calcular_gasto_mensual_with_transactions(self, card: Card) -> None:
        """Should calculate total monthly expenses."""
        from finanzas_tracker.models.transaction import Transaction
        from finanzas_tracker.models.enums import BankName, TransactionType
        from datetime import datetime, UTC

        # Create test transactions
        tx1 = Transaction(
            email_id="email-1",
            profile_id=card.profile_id,
            card_id=card.id,
            banco=BankName.BAC,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio="Store 1",
            monto_crc=Decimal("5000"),
            monto_original=Decimal("5000"),
            moneda_original="CRC",
            fecha_transaccion=datetime(2025, 11, 15, tzinfo=UTC),
            excluir_de_presupuesto=False,
        )
        tx2 = Transaction(
            email_id="email-2",
            profile_id=card.profile_id,
            card_id=card.id,
            banco=BankName.BAC,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio="Store 2",
            monto_crc=Decimal("3000"),
            monto_original=Decimal("3000"),
            moneda_original="CRC",
            fecha_transaccion=datetime(2025, 11, 20, tzinfo=UTC),
            excluir_de_presupuesto=False,
        )
        card.transactions = [tx1, tx2]

        result = card.calcular_gasto_mensual(11, 2025)
        assert result == Decimal("8000")

    def test_calcular_disponible_credito_with_limit(self, card: Card) -> None:
        """Should calculate available credit correctly."""
        from finanzas_tracker.models.transaction import Transaction
        from finanzas_tracker.models.enums import BankName, TransactionType
        from datetime import datetime, UTC

        card.tipo = CardType.CREDIT
        card.limite_credito = Decimal("100000")

        # Add transaction
        tx = Transaction(
            email_id="email-1",
            profile_id=card.profile_id,
            card_id=card.id,
            banco=BankName.BAC,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio="Store",
            monto_crc=Decimal("25000"),
            monto_original=Decimal("25000"),
            moneda_original="CRC",
            fecha_transaccion=datetime(2025, 11, 15, tzinfo=UTC),
            excluir_de_presupuesto=False,
        )
        card.transactions = [tx]

        result = card.calcular_disponible_credito(11, 2025)
        assert result == Decimal("75000")  # 100000 - 25000


class TestCardValidations:
    """Tests for Card model validations."""

    def test_validate_ultimos_4_digitos_empty(self) -> None:
        """Should reject empty ultimos_4_digitos."""
        with pytest.raises(ValueError, match="Los últimos 4 dígitos son obligatorios"):
            Card(
                profile_id="profile-123",
                banco=BankName.BAC,
                ultimos_4_digitos="",  # Empty
            )

    def test_validate_ultimos_4_digitos_wrong_length(self) -> None:
        """Should reject wrong length."""
        with pytest.raises(ValueError, match="Deben ser exactamente 4 dígitos"):
            Card(
                profile_id="profile-123",
                banco=BankName.BAC,
                ultimos_4_digitos="123",  # Only 3 digits
            )

    def test_validate_ultimos_4_digitos_non_numeric(self) -> None:
        """Should reject non-numeric values."""
        with pytest.raises(ValueError, match="deben ser solo números"):
            Card(
                profile_id="profile-123",
                banco=BankName.BAC,
                ultimos_4_digitos="12AB",  # Contains letters
            )

    def test_validate_limite_credito_negative(self) -> None:
        """Should reject negative credit limit."""
        with pytest.raises(ValueError, match="El límite de crédito debe ser positivo"):
            Card(
                profile_id="profile-123",
                banco=BankName.BAC,
                ultimos_4_digitos="1234",
                limite_credito=Decimal("-10000"),  # Negative
            )
