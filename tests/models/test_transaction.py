"""Tests for Transaction model."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from finanzas_tracker.models.enums import Currency, TransactionType, BankName
from finanzas_tracker.models.transaction import Transaction


class TestTransactionProperties:
    """Tests for Transaction model properties."""

    @pytest.fixture
    def base_transaction(self) -> Transaction:
        """Create a basic transaction for testing."""
        return Transaction(
            id="test-uuid-1234",
            email_id="email-123",
            profile_id="profile-123",
            banco=BankName.BAC,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio="DUNKIN TRES RIOS",
            monto_crc=Decimal("5000.00"),
            monto_original=Decimal("5000.00"),
            moneda_original=Currency.CRC,
            fecha_transaccion=datetime(2025, 11, 6, 10, 30, tzinfo=UTC),
            confianza_categoria=85,
            es_desconocida=False,
            excluir_de_presupuesto=False,
        )

    def test_monto_display_crc(self, base_transaction: Transaction) -> None:
        """Should format CRC amount correctly."""
        display = base_transaction.monto_display
        assert "₡5,000.00" in display
        assert "USD" not in display

    def test_monto_display_usd(self, base_transaction: Transaction) -> None:
        """Should format USD amount with exchange rate."""
        base_transaction.moneda_original = Currency.USD
        base_transaction.monto_original = Decimal("10.00")
        base_transaction.monto_crc = Decimal("5200.00")
        base_transaction.tipo_cambio_usado = Decimal("520.00")

        display = base_transaction.monto_display
        assert "₡5,200.00" in display
        assert "$10.00 USD" in display
        assert "520.00" in display

    def test_es_internacional_true(self, base_transaction: Transaction) -> None:
        """Should return True for international transaction."""
        base_transaction.pais = "United States"
        assert base_transaction.es_internacional is True

    def test_es_internacional_false_costa_rica(self, base_transaction: Transaction) -> None:
        """Should return False for Costa Rica."""
        base_transaction.pais = "Costa Rica"
        assert base_transaction.es_internacional is False

    def test_es_internacional_false_none(self, base_transaction: Transaction) -> None:
        """Should return False when country is None."""
        base_transaction.pais = None
        assert base_transaction.es_internacional is False

    def test_es_especial_true(self, base_transaction: Transaction) -> None:
        """Should return True when tipo_especial is set."""
        base_transaction.tipo_especial = "intermediaria"
        assert base_transaction.es_especial is True

    def test_es_especial_false(self, base_transaction: Transaction) -> None:
        """Should return False when tipo_especial is None."""
        base_transaction.tipo_especial = None
        assert base_transaction.es_especial is False

    def test_es_refund_true(self, base_transaction: Transaction) -> None:
        """Should return True when refund_transaction_id is set."""
        base_transaction.refund_transaction_id = "original-tx-123"
        assert base_transaction.es_refund is True

    def test_es_refund_false(self, base_transaction: Transaction) -> None:
        """Should return False when no refund reference."""
        base_transaction.refund_transaction_id = None
        assert base_transaction.es_refund is False

    def test_necesita_atencion_desconocida(self, base_transaction: Transaction) -> None:
        """Should return True when transaction is unknown."""
        base_transaction.es_desconocida = True
        assert base_transaction.necesita_atencion is True

    def test_necesita_atencion_baja_confianza(self, base_transaction: Transaction) -> None:
        """Should return True when confidence is below 70."""
        base_transaction.confianza_categoria = 50
        assert base_transaction.necesita_atencion is True

    def test_necesita_atencion_false(self, base_transaction: Transaction) -> None:
        """Should return False when known and high confidence."""
        base_transaction.es_desconocida = False
        base_transaction.confianza_categoria = 85
        assert base_transaction.necesita_atencion is False

    def test_debe_contar_en_presupuesto_true(self, base_transaction: Transaction) -> None:
        """Should return True for normal transactions."""
        assert base_transaction.debe_contar_en_presupuesto is True

    def test_debe_contar_en_presupuesto_false_excluida(self, base_transaction: Transaction) -> None:
        """Should return False when excluded."""
        base_transaction.excluir_de_presupuesto = True
        assert base_transaction.debe_contar_en_presupuesto is False

    def test_esta_activa_true(self, base_transaction: Transaction) -> None:
        """Should return True when not deleted."""
        assert base_transaction.esta_activa is True

    def test_esta_activa_false(self, base_transaction: Transaction) -> None:
        """Should return False when soft deleted."""
        base_transaction.deleted_at = datetime.now(UTC)
        assert base_transaction.esta_activa is False


class TestTransactionMethods:
    """Tests for Transaction model methods."""

    @pytest.fixture
    def transaction(self) -> Transaction:
        """Create a transaction for testing."""
        return Transaction(
            id="test-uuid-1234",
            email_id="email-123",
            profile_id="profile-123",
            banco=BankName.BAC,
            tipo_transaccion=TransactionType.PURCHASE,
            comercio="TEST MERCHANT",
            monto_crc=Decimal("10000.00"),
            monto_original=Decimal("10000.00"),
            moneda_original=Currency.CRC,
            fecha_transaccion=datetime(2025, 11, 6, 10, 30, tzinfo=UTC),
            confianza_categoria=85,
            es_desconocida=False,
            excluir_de_presupuesto=False,
        )

    def test_soft_delete(self, transaction: Transaction) -> None:
        """Should set deleted_at timestamp."""
        assert transaction.deleted_at is None
        transaction.soft_delete()
        assert transaction.deleted_at is not None

    def test_restore(self, transaction: Transaction) -> None:
        """Should clear deleted_at timestamp."""
        transaction.soft_delete()
        assert transaction.deleted_at is not None
        transaction.restore()
        assert transaction.deleted_at is None

    def test_marcar_como_refund(self, transaction: Transaction) -> None:
        """Should mark transaction as refund."""
        original_id = "original-tx-12345678"
        transaction.marcar_como_refund(original_id)

        assert transaction.refund_transaction_id == original_id
        assert transaction.tipo_especial == "reembolso"
        assert "Refund de transacción" in transaction.relacionada_con

    def test_calcular_monto_patrimonio_normal(self, transaction: Transaction) -> None:
        """Should return full amount for normal transactions."""
        result = transaction.calcular_monto_patrimonio()
        assert result == Decimal("10000.00")

    def test_calcular_monto_patrimonio_excluida(self, transaction: Transaction) -> None:
        """Should return 0 for excluded transactions."""
        transaction.excluir_de_presupuesto = True
        result = transaction.calcular_monto_patrimonio()
        assert result == Decimal("0")

    def test_repr(self, transaction: Transaction) -> None:
        """Should return readable string representation."""
        repr_str = repr(transaction)
        assert "Transaction" in repr_str
        assert "TEST MERCHANT" in repr_str
        assert "10,000.00" in repr_str
