"""Tests para CreditCardStatementService.

Tests del servicio que procesa estados de cuenta de tarjetas de crédito BAC.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from finanzas_tracker.services.credit_card_statement_service import (
    ConsolidationResult,
    CreditCardStatementService,
)


class TestConsolidationResult:
    """Tests para el dataclass ConsolidationResult."""

    def test_result_success(self) -> None:
        """Resultado exitoso con valores correctos."""
        result = ConsolidationResult(
            success=True,
            card_id="card-123",
            billing_cycle_id="cycle-456",
            transactions_created=25,
            transactions_skipped=3,
            transactions_failed=0,
            total_compras=Decimal("150000.00"),
        )

        assert result.success is True
        assert result.card_id == "card-123"
        assert result.billing_cycle_id == "cycle-456"
        assert result.transactions_created == 25
        assert result.total_compras == Decimal("150000.00")

    def test_result_failure(self) -> None:
        """Resultado de error."""
        result = ConsolidationResult(
            success=False,
            errors=["PDF inválido", "Formato no reconocido"],
        )

        assert result.success is False
        assert result.errors is not None
        assert len(result.errors) == 2

    def test_total_processed_property(self) -> None:
        """total_processed suma created + skipped."""
        result = ConsolidationResult(
            success=True,
            transactions_created=20,
            transactions_skipped=5,
            transactions_failed=2,
        )

        assert result.total_processed == 25

    def test_default_values(self) -> None:
        """Valores por defecto cuando no se especifican."""
        result = ConsolidationResult(success=True)

        assert result.card_id is None
        assert result.billing_cycle_id is None
        assert result.transactions_created == 0
        assert result.transactions_skipped == 0
        assert result.transactions_failed == 0
        assert result.total_compras == Decimal("0")
        assert result.errors is None


class TestCreditCardStatementServiceInit:
    """Tests de inicialización del servicio."""

    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_init_creates_dependencies(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
    ) -> None:
        """El servicio inicializa parser y categorizer."""
        service = CreditCardStatementService()

        mock_parser.assert_called_once()
        mock_categorizer.assert_called_once()
        assert service.parser is not None
        assert service.categorizer is not None


class TestCreditCardStatementServiceProcessPdf:
    """Tests del método process_pdf."""

    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_process_pdf_success(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
    ) -> None:
        """Procesa PDF correctamente."""
        mock_statement = MagicMock()
        mock_statement.metadata.fecha_corte = date(2024, 11, 30)
        mock_statement.transactions = []
        mock_parser.return_value.parse.return_value = mock_statement

        service = CreditCardStatementService()

        with patch.object(service, "consolidate_statement") as mock_consolidate:
            mock_consolidate.return_value = ConsolidationResult(
                success=True,
                transactions_created=10,
            )

            result = service.process_pdf("/path/to/card.pdf", "profile-123")

            mock_parser.return_value.parse.assert_called_once_with("/path/to/card.pdf")
            mock_consolidate.assert_called_once()
            assert result.success is True

    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_process_pdf_parse_error(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
    ) -> None:
        """Maneja error de parsing."""
        mock_parser.return_value.parse.side_effect = Exception("PDF corrupto")

        service = CreditCardStatementService()
        result = service.process_pdf("/bad/file.pdf", "profile-123")

        assert result.success is False
        assert result.errors is not None
        assert "PDF corrupto" in result.errors[0]


class TestCreditCardStatementServiceConsolidate:
    """Tests del método consolidate_statement."""

    @pytest.fixture
    def mock_statement_metadata(self) -> MagicMock:
        """Crea metadata mock del estado de cuenta."""
        metadata = MagicMock()
        metadata.tarjeta_ultimos_4 = "1234"
        metadata.tarjeta_marca = "VISA"
        metadata.limite_credito_usd = Decimal("5000.00")
        metadata.fecha_corte = date(2024, 11, 30)
        metadata.fecha_pago_contado = date(2024, 12, 15)
        metadata.pago_minimo_crc = Decimal("25000.00")
        metadata.pago_contado_crc = Decimal("350000.00")
        return metadata

    @pytest.fixture
    def mock_transaction(self) -> MagicMock:
        """Crea una transacción mock del parser."""
        tx = MagicMock()
        tx.referencia = "AUTH001"
        tx.fecha = date(2024, 11, 15)
        tx.concepto = "STARBUCKS ESCAZU"
        tx.monto_crc = Decimal("5500.00")
        tx.moneda = "CRC"
        tx.tipo = "compra"
        return tx

    @patch("finanzas_tracker.services.credit_card_statement_service.get_session")
    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_consolidate_creates_new_card(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
        mock_get_session: MagicMock,
        mock_statement_metadata: MagicMock,
    ) -> None:
        """Crea nueva tarjeta si no existe."""
        mock_statement = MagicMock()
        mock_statement.metadata = mock_statement_metadata
        mock_statement.transactions = []

        mock_session = MagicMock()
        # No existe tarjeta
        mock_session.execute.return_value.scalar_one_or_none.return_value = None
        mock_get_session.return_value.__enter__.return_value = mock_session

        service = CreditCardStatementService()
        result = service.consolidate_statement(mock_statement, "profile-123")

        assert result.success is True
        # Verificar que se agregó la tarjeta
        assert mock_session.add.called

    @patch("finanzas_tracker.services.credit_card_statement_service.get_session")
    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_consolidate_updates_existing_card(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
        mock_get_session: MagicMock,
        mock_statement_metadata: MagicMock,
    ) -> None:
        """Actualiza tarjeta existente."""
        mock_statement = MagicMock()
        mock_statement.metadata = mock_statement_metadata
        mock_statement.transactions = []

        existing_card = MagicMock()
        existing_card.id = "existing-card-id"
        existing_card.marca = "VISA"
        existing_card.ultimos_4_digitos = "1234"

        mock_session = MagicMock()
        # Simular que la tarjeta existe y billing cycle no
        returns = [existing_card, None]
        mock_session.execute.return_value.scalar_one_or_none.side_effect = returns
        mock_get_session.return_value.__enter__.return_value = mock_session

        service = CreditCardStatementService()
        result = service.consolidate_statement(mock_statement, "profile-123")

        assert result.success is True
        assert result.card_id == "existing-card-id"

    @patch("finanzas_tracker.services.credit_card_statement_service.get_session")
    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_consolidate_creates_billing_cycle(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
        mock_get_session: MagicMock,
        mock_statement_metadata: MagicMock,
    ) -> None:
        """Crea ciclo de facturación."""
        mock_statement = MagicMock()
        mock_statement.metadata = mock_statement_metadata
        mock_statement.transactions = []

        mock_card = MagicMock()
        mock_card.id = "card-123"

        mock_session = MagicMock()
        # Tarjeta existe, billing cycle no
        mock_session.execute.return_value.scalar_one_or_none.side_effect = [mock_card, None]
        mock_get_session.return_value.__enter__.return_value = mock_session

        service = CreditCardStatementService()
        result = service.consolidate_statement(mock_statement, "profile-123")

        assert result.success is True
        assert result.billing_cycle_id is not None

    @patch("finanzas_tracker.services.credit_card_statement_service.get_session")
    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_consolidate_processes_transactions(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
        mock_get_session: MagicMock,
        mock_statement_metadata: MagicMock,
        mock_transaction: MagicMock,
    ) -> None:
        """Procesa transacciones correctamente."""
        mock_statement = MagicMock()
        mock_statement.metadata = mock_statement_metadata
        mock_statement.transactions = [mock_transaction]

        mock_card = MagicMock()
        mock_card.id = "card-123"
        mock_card.marca = "VISA"
        mock_card.ultimos_4_digitos = "1234"

        mock_cycle = MagicMock()
        mock_cycle.id = "cycle-456"

        mock_session = MagicMock()
        # tarjeta, billing cycle (None para crear), luego None para transacción (no duplicada)
        mock_session.execute.return_value.scalar_one_or_none.side_effect = [mock_card, None, None]
        mock_get_session.return_value.__enter__.return_value = mock_session

        service = CreditCardStatementService()
        result = service.consolidate_statement(mock_statement, "profile-123")

        assert result.success is True
        assert result.transactions_created == 1
        assert result.total_compras == Decimal("5500.00")

    @patch("finanzas_tracker.services.credit_card_statement_service.get_session")
    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_consolidate_skips_duplicate_transactions(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
        mock_get_session: MagicMock,
        mock_statement_metadata: MagicMock,
        mock_transaction: MagicMock,
    ) -> None:
        """Omite transacciones duplicadas."""
        mock_statement = MagicMock()
        mock_statement.metadata = mock_statement_metadata
        mock_statement.transactions = [mock_transaction]

        mock_card = MagicMock()
        mock_card.id = "card-123"

        existing_tx = MagicMock()

        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.side_effect = [
            mock_card,
            None,
            existing_tx,  # Transacción ya existe
        ]
        mock_get_session.return_value.__enter__.return_value = mock_session

        service = CreditCardStatementService()
        result = service.consolidate_statement(mock_statement, "profile-123")

        assert result.success is True
        assert result.transactions_created == 0
        assert result.transactions_skipped == 1

    @patch("finanzas_tracker.services.credit_card_statement_service.get_session")
    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_consolidate_handles_payment_type(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
        mock_get_session: MagicMock,
        mock_statement_metadata: MagicMock,
    ) -> None:
        """Procesa pagos correctamente."""
        tx = MagicMock()
        tx.referencia = "PAGO001"
        tx.fecha = date(2024, 11, 10)
        tx.concepto = "PAGO RECIBIDO GRACIAS"
        tx.monto_crc = Decimal("100000.00")
        tx.moneda = "CRC"
        tx.tipo = "pago"

        mock_statement = MagicMock()
        mock_statement.metadata = mock_statement_metadata
        mock_statement.transactions = [tx]

        mock_card = MagicMock()
        mock_card.id = "card-123"

        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.side_effect = [mock_card, None, None]
        mock_get_session.return_value.__enter__.return_value = mock_session

        service = CreditCardStatementService()
        result = service.consolidate_statement(mock_statement, "profile-123")

        assert result.success is True
        assert result.transactions_created == 1
        # Pagos no suman a total_compras
        assert result.total_compras == Decimal("0")

    @patch("finanzas_tracker.services.credit_card_statement_service.get_session")
    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_consolidate_handles_interest_charges(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
        mock_get_session: MagicMock,
        mock_statement_metadata: MagicMock,
    ) -> None:
        """Procesa cargos de intereses."""
        tx = MagicMock()
        tx.referencia = "INT001"
        tx.fecha = date(2024, 11, 30)
        tx.concepto = "INTERESES FINANCIAMIENTO"
        tx.monto_crc = Decimal("12500.00")
        tx.moneda = "CRC"
        tx.tipo = "interes"

        mock_statement = MagicMock()
        mock_statement.metadata = mock_statement_metadata
        mock_statement.transactions = [tx]

        mock_card = MagicMock()
        mock_card.id = "card-123"

        mock_session = MagicMock()
        mock_session.execute.return_value.scalar_one_or_none.side_effect = [mock_card, None, None]
        mock_get_session.return_value.__enter__.return_value = mock_session

        service = CreditCardStatementService()
        result = service.consolidate_statement(mock_statement, "profile-123")

        assert result.success is True
        assert result.transactions_created == 1

    @patch("finanzas_tracker.services.credit_card_statement_service.get_session")
    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_consolidate_rollback_on_error(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
        mock_get_session: MagicMock,
        mock_statement_metadata: MagicMock,
    ) -> None:
        """Hace rollback en caso de error."""
        mock_statement = MagicMock()
        mock_statement.metadata = mock_statement_metadata
        mock_statement.transactions = []

        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("DB Connection Lost")
        mock_get_session.return_value.__enter__.return_value = mock_session

        service = CreditCardStatementService()
        result = service.consolidate_statement(mock_statement, "profile-123")

        assert result.success is False
        mock_session.rollback.assert_called_once()


class TestCreditCardStatementServiceParseMarca:
    """Tests del método _parse_marca."""

    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_parse_visa(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
    ) -> None:
        """Normaliza VISA."""
        service = CreditCardStatementService()

        assert service._parse_marca("VISA") == "VISA"
        assert service._parse_marca("visa") == "VISA"
        assert service._parse_marca("Visa Gold") == "VISA"

    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_parse_mastercard(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
    ) -> None:
        """Normaliza MASTERCARD."""
        service = CreditCardStatementService()

        assert service._parse_marca("MASTERCARD") == "MASTERCARD"
        assert service._parse_marca("mastercard") == "MASTERCARD"
        assert service._parse_marca("Master Black") == "MASTERCARD"

    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_parse_amex(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
    ) -> None:
        """Normaliza AMEX."""
        service = CreditCardStatementService()

        assert service._parse_marca("AMEX") == "AMEX"
        assert service._parse_marca("American Express") == "AMEX"

    @patch("finanzas_tracker.services.credit_card_statement_service.BACCreditCardParser")
    @patch("finanzas_tracker.services.credit_card_statement_service.TransactionCategorizer")
    def test_parse_unknown(
        self,
        mock_categorizer: MagicMock,
        mock_parser: MagicMock,
    ) -> None:
        """Retorna marca original si no reconoce."""
        service = CreditCardStatementService()

        assert service._parse_marca("DISCOVER") == "DISCOVER"
        assert service._parse_marca("Custom Card") == "Custom Card"


class TestConsolidationResultMethods:
    """Tests adicionales para ConsolidationResult."""

    def test_total_processed_zero(self) -> None:
        """total_processed es cero cuando no hay transacciones."""
        result = ConsolidationResult(success=True)
        assert result.total_processed == 0

    def test_total_processed_excludes_failed(self) -> None:
        """total_processed no incluye failed."""
        result = ConsolidationResult(
            success=True,
            transactions_created=50,
            transactions_skipped=10,
            transactions_failed=5,
        )
        # failed no cuenta
        assert result.total_processed == 60
