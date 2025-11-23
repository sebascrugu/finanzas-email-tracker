"""
Tests unitarios para TransactionProcessor.

Tests comprehensivos que cubren el procesamiento completo de correos:
- Procesamiento de correos BAC
- Procesamiento de correos Popular
- Conversión de USD a CRC
- Categorización automática con IA
- Manejo de duplicados
- Manejo de errores
- Estadísticas de procesamiento
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import IntegrityError

from finanzas_tracker.services.transaction_processor import TransactionProcessor


def create_transaction_mock(
    comercio: str = "TEST", monto_crc: Decimal = Decimal("1000.00")
) -> MagicMock:
    """
    Crea un mock de Transaction con atributos necesarios para logging.

    Args:
        comercio: Nombre del comercio
        monto_crc: Monto en colones

    Returns:
        Mock configurado de Transaction
    """
    mock = MagicMock()
    mock.comercio = comercio
    mock.monto_crc = monto_crc
    return mock


class TestTransactionProcessorInitialization:
    """Tests para inicialización del processor."""

    def test_initialization_with_auto_categorize_true(self) -> None:
        """Test que verifica inicialización con categorización automática."""
        processor = TransactionProcessor(auto_categorize=True, detect_anomalies=False)

        assert processor is not None
        assert processor.auto_categorize is True
        assert processor.categorizer is not None

    def test_initialization_with_auto_categorize_false(self) -> None:
        """Test que verifica inicialización sin categorización automática."""
        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)

        assert processor is not None
        assert processor.auto_categorize is False
        assert processor.categorizer is None


class TestTransactionProcessorIdentifyBank:
    """Tests para identificación de banco desde correos."""

    def test_identify_bank_bac_from_sender(self) -> None:
        """Test identificando BAC desde el sender."""
        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)
        email = {
            "from": {"emailAddress": {"address": "notificaciones@notificacionesbaccr.com"}},
            "subject": "Notificación de transacción",
        }

        banco = processor._identify_bank(email)
        assert banco == "bac"

    def test_identify_bank_popular_from_sender(self) -> None:
        """Test identificando Banco Popular desde el sender."""
        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)
        email = {
            "from": {"emailAddress": {"address": "infopersonal@bancopopular.fi.cr"}},
            "subject": "Notificación de transacción",
        }

        banco = processor._identify_bank(email)
        assert banco == "popular"

    def test_identify_bank_unknown_sender(self) -> None:
        """Test con sender desconocido."""
        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)
        email = {
            "from": {"emailAddress": {"address": "unknown@example.com"}},
            "subject": "Test",
        }

        banco = processor._identify_bank(email)
        assert banco is None


class TestTransactionProcessorCurrencyConversion:
    """Tests para conversión de moneda USD→CRC."""

    @patch("finanzas_tracker.services.transaction_processor.exchange_rate_service")
    def test_apply_currency_conversion_usd(self, mock_exchange_service: MagicMock) -> None:
        """Test aplicando conversión de USD a CRC."""
        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)
        mock_exchange_service.get_rate.return_value = 520.0

        transaction_data = {
            "moneda_original": "USD",
            "monto_original": Decimal("50.00"),
            "fecha_transaccion": datetime(2025, 11, 6, 10, 0),
        }

        processor._apply_currency_conversion(transaction_data)

        assert transaction_data["monto_crc"] == Decimal("26000.00")
        assert transaction_data["tipo_cambio_usado"] == Decimal("520.0")
        mock_exchange_service.get_rate.assert_called_once()

    def test_apply_currency_conversion_crc_no_conversion(self) -> None:
        """Test que verifica que CRC no se convierte."""
        TransactionProcessor(auto_categorize=False, detect_anomalies=False)

        {
            "moneda_original": "CRC",
            "monto_original": Decimal("5000.00"),
            "fecha_transaccion": datetime(2025, 11, 6, 10, 0),
        }

        # No debería haber conversión
        # El método _apply_currency_conversion solo se llama para USD


class TestTransactionProcessorCategorization:
    """Tests para categorización automática con IA."""

    @patch("finanzas_tracker.services.transaction_processor.TransactionCategorizer")
    def test_categorize_transaction_successful(self, mock_categorizer_class: MagicMock) -> None:
        """Test categorizando transacción exitosamente."""
        mock_categorizer = MagicMock()
        mock_categorizer.categorize.return_value = {
            "subcategory_id": "cat-123",
            "categoria_sugerida": "Alimentación/Restaurantes",
            "necesita_revision": False,
            "confianza": 90,
        }
        mock_categorizer_class.return_value = mock_categorizer

        processor = TransactionProcessor(auto_categorize=True, detect_anomalies=False)
        transaction_data = {
            "comercio": "STARBUCKS",
            "monto_crc": Decimal("5000.00"),
            "tipo_transaccion": "compra",
        }
        stats = {
            "categorizadas_automaticamente": 0,
            "necesitan_revision": 0,
        }

        processor._categorize_transaction(transaction_data, stats)

        assert transaction_data["subcategory_id"] == "cat-123"
        assert transaction_data["categoria_sugerida_por_ia"] == "Alimentación/Restaurantes"
        assert transaction_data["necesita_revision"] is False
        assert stats["categorizadas_automaticamente"] == 1
        assert stats["necesitan_revision"] == 0

    @patch("finanzas_tracker.services.transaction_processor.TransactionCategorizer")
    def test_categorize_transaction_needs_review(self, mock_categorizer_class: MagicMock) -> None:
        """Test categorizando transacción que necesita revisión."""
        mock_categorizer = MagicMock()
        mock_categorizer.categorize.return_value = {
            "subcategory_id": None,
            "categoria_sugerida": "Compras/Varios",
            "necesita_revision": True,
            "confianza": 60,
        }
        mock_categorizer_class.return_value = mock_categorizer

        processor = TransactionProcessor(auto_categorize=True, detect_anomalies=False)
        transaction_data = {
            "comercio": "WALMART",
            "monto_crc": Decimal("10000.00"),
            "tipo_transaccion": "compra",
        }
        stats = {
            "categorizadas_automaticamente": 0,
            "necesitan_revision": 0,
        }

        processor._categorize_transaction(transaction_data, stats)

        assert transaction_data["subcategory_id"] is None
        assert transaction_data["necesita_revision"] is True
        assert stats["categorizadas_automaticamente"] == 0
        assert stats["necesitan_revision"] == 1

    @patch("finanzas_tracker.services.transaction_processor.TransactionCategorizer")
    def test_categorize_transaction_error_handling(self, mock_categorizer_class: MagicMock) -> None:
        """Test manejando errores en categorización."""
        mock_categorizer = MagicMock()
        mock_categorizer.categorize.side_effect = Exception("API Error")
        mock_categorizer_class.return_value = mock_categorizer

        processor = TransactionProcessor(auto_categorize=True, detect_anomalies=False)
        transaction_data = {
            "comercio": "TEST",
            "monto_crc": Decimal("1000.00"),
            "tipo_transaccion": "compra",
        }
        stats = {
            "categorizadas_automaticamente": 0,
            "necesitan_revision": 0,
        }

        processor._categorize_transaction(transaction_data, stats)

        # Debe marcar para revisión en caso de error
        assert transaction_data["subcategory_id"] is None
        assert transaction_data["necesita_revision"] is True
        assert stats["necesitan_revision"] == 1


class TestTransactionProcessorSaveTransaction:
    """Tests para guardar transacciones en la base de datos."""

    @patch("finanzas_tracker.services.transaction_processor.get_session")
    @patch("finanzas_tracker.services.transaction_processor.Transaction")
    def test_save_transaction_success(
        self, mock_transaction_class: MagicMock, mock_get_session: MagicMock
    ) -> None:
        """Test guardando transacción exitosamente."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock de Transaction con atributos reales para el logging
        mock_transaction_class.return_value = create_transaction_mock("TEST", Decimal("1000.00"))

        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)
        transaction_data = {
            "email_id": "test-123",
            "banco": "bac",
            "comercio": "TEST",
            "monto_crc": Decimal("1000.00"),
        }

        result = processor._save_transaction(transaction_data)

        assert result is True
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch("finanzas_tracker.services.transaction_processor.get_session")
    @patch("finanzas_tracker.services.transaction_processor.Transaction")
    def test_save_transaction_duplicate(
        self, mock_transaction_class: MagicMock, mock_get_session: MagicMock
    ) -> None:
        """Test manejando transacción duplicada."""
        mock_session = MagicMock()
        mock_session.commit.side_effect = IntegrityError("", "", "")
        mock_get_session.return_value.__enter__.return_value = mock_session

        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)
        transaction_data = {
            "email_id": "duplicate-123",
            "banco": "bac",
            "comercio": "TEST",
            "monto_crc": Decimal("1000.00"),
        }

        result = processor._save_transaction(transaction_data)

        assert result is False


@patch("finanzas_tracker.services.transaction_processor.subscription_detector")
class TestTransactionProcessorProcessEmails:
    """Tests para procesamiento completo de correos."""

    @patch("finanzas_tracker.services.transaction_processor.exchange_rate_service")
    @patch("finanzas_tracker.services.transaction_processor.get_session")
    @patch("finanzas_tracker.services.transaction_processor.Transaction")
    def test_process_emails_bac_success(
        self,
        mock_transaction_class: MagicMock,
        mock_get_session: MagicMock,
        mock_exchange_service: MagicMock,
        mock_subscription_detector: MagicMock,
    ) -> None:
        """Test procesando correos de BAC exitosamente."""
        # Mock de sesión DB
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock de Transaction
        mock_transaction_class.return_value = create_transaction_mock(
            "STARBUCKS", Decimal("5000.00")
        )

        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)

        emails = [
            {
                "id": "email-bac-1",
                "subject": "Notificación de transacción",
                "from": {"emailAddress": {"address": "notificaciones@notificacionesbaccr.com"}},
                "receivedDateTime": "2025-11-06T10:00:00Z",
                "body": {
                    "content": """
                    <html><body><table>
                        <tr><td>Comercio:</td><td>STARBUCKS</td></tr>
                        <tr><td>Monto:</td><td>CRC 5,000.00</td></tr>
                    </table></body></html>
                    """
                },
            }
        ]

        stats = processor.process_emails(emails, profile_id="profile-123")

        assert stats["total"] == 1
        assert stats["procesados"] == 1
        assert stats["bac"] == 1
        assert stats["popular"] == 0
        assert stats["duplicados"] == 0
        assert stats["errores"] == 0

    @patch("finanzas_tracker.services.transaction_processor.exchange_rate_service")
    @patch("finanzas_tracker.services.transaction_processor.get_session")
    @patch("finanzas_tracker.services.transaction_processor.Transaction")
    def test_process_emails_popular_success(
        self,
        mock_transaction_class: MagicMock,
        mock_get_session: MagicMock,
        mock_exchange_service: MagicMock,
        mock_subscription_detector: MagicMock,
    ) -> None:
        """Test procesando correos de Banco Popular exitosamente."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        mock_transaction_class.return_value = create_transaction_mock(
            "SUPERMERCADO", Decimal("15000.00")
        )

        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)

        emails = [
            {
                "id": "email-popular-1",
                "subject": "Notificación",
                "from": {"emailAddress": {"address": "infopersonal@bancopopular.fi.cr"}},
                "receivedDateTime": "2025-11-06T10:00:00Z",
                "body": {
                    "content": """
                    <html><body>
                        <p>Comercio: SUPERMERCADO</p>
                        <p>Monto: CRC 15,000.00</p>
                    </body></html>
                    """
                },
            }
        ]

        stats = processor.process_emails(emails, profile_id="profile-123")

        assert stats["total"] == 1
        assert stats["procesados"] == 1
        assert stats["bac"] == 0
        assert stats["popular"] == 1

    @patch("finanzas_tracker.services.transaction_processor.exchange_rate_service")
    @patch("finanzas_tracker.services.transaction_processor.get_session")
    @patch("finanzas_tracker.services.transaction_processor.Transaction")
    def test_process_emails_with_usd_conversion(
        self,
        mock_transaction_class: MagicMock,
        mock_get_session: MagicMock,
        mock_exchange_service: MagicMock,
        mock_subscription_detector: MagicMock,
    ) -> None:
        """Test procesando correo con conversión USD→CRC."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock query chain for auto-train check (return 0 to skip training)
        mock_session.query.return_value.filter.return_value.count.return_value = 0

        mock_exchange_service.get_rate.return_value = 520.0
        mock_transaction_class.return_value = create_transaction_mock("AMAZON", Decimal("26000.00"))

        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)

        emails = [
            {
                "id": "email-usd-1",
                "subject": "Notificación",
                "from": {"emailAddress": {"address": "notificaciones@notificacionesbaccr.com"}},
                "receivedDateTime": "2025-11-06T10:00:00Z",
                "body": {
                    "content": """
                    <html><body><table>
                        <tr><td>Comercio:</td><td>AMAZON</td></tr>
                        <tr><td>Monto:</td><td>USD 50.00</td></tr>
                    </table></body></html>
                    """
                },
            }
        ]

        stats = processor.process_emails(emails, profile_id="profile-123")

        assert stats["total"] == 1
        assert stats["procesados"] == 1
        assert stats["usd_convertidos"] == 1

    @patch("finanzas_tracker.services.transaction_processor.exchange_rate_service")
    @patch("finanzas_tracker.services.transaction_processor.get_session")
    @patch("finanzas_tracker.services.transaction_processor.Transaction")
    @patch("finanzas_tracker.services.transaction_processor.TransactionCategorizer")
    def test_process_emails_with_auto_categorization(
        self,
        mock_categorizer_class: MagicMock,
        mock_transaction_class: MagicMock,
        mock_get_session: MagicMock,
        mock_exchange_service: MagicMock,
        mock_subscription_detector: MagicMock,
    ) -> None:
        """Test procesando con categorización automática."""
        mock_session = MagicMock()
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock query chain for auto-train check (return 0 to skip training)
        mock_session.query.return_value.filter.return_value.count.return_value = 0

        mock_transaction_class.return_value = create_transaction_mock(
            "STARBUCKS", Decimal("5000.00")
        )

        mock_categorizer = MagicMock()
        mock_categorizer.categorize.return_value = {
            "subcategory_id": "cat-123",
            "categoria_sugerida": "Alimentación/Café",
            "necesita_revision": False,
            "confianza": 95,
        }
        mock_categorizer_class.return_value = mock_categorizer

        processor = TransactionProcessor(auto_categorize=True, detect_anomalies=False)

        emails = [
            {
                "id": "email-cat-1",
                "subject": "Notificación",
                "from": {"emailAddress": {"address": "notificaciones@notificacionesbaccr.com"}},
                "receivedDateTime": "2025-11-06T10:00:00Z",
                "body": {
                    "content": """
                    <html><body><table>
                        <tr><td>Comercio:</td><td>STARBUCKS</td></tr>
                        <tr><td>Monto:</td><td>CRC 5,000.00</td></tr>
                    </table></body></html>
                    """
                },
            }
        ]

        stats = processor.process_emails(emails, profile_id="profile-123")

        assert stats["total"] == 1
        assert stats["procesados"] == 1
        assert stats["categorizadas_automaticamente"] == 1
        assert stats["necesitan_revision"] == 0

    @patch("finanzas_tracker.services.transaction_processor.get_session")
    def test_process_emails_unknown_bank(self, mock_get_session: MagicMock, mock_subscription_detector: MagicMock) -> None:
        """Test procesando correo de banco desconocido."""
        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)

        emails = [
            {
                "id": "email-unknown-1",
                "subject": "Test",
                "from": {"emailAddress": {"address": "unknown@example.com"}},
                "receivedDateTime": "2025-11-06T10:00:00Z",
                "body": {"content": "<html><body></body></html>"},
            }
        ]

        stats = processor.process_emails(emails, profile_id="profile-123")

        assert stats["total"] == 1
        assert stats["procesados"] == 0
        assert stats["errores"] == 1

    @patch("finanzas_tracker.services.transaction_processor.get_session")
    def test_process_emails_parsing_error(self, mock_get_session: MagicMock, mock_subscription_detector: MagicMock) -> None:
        """Test manejando error de parseo."""
        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)

        emails = [
            {
                "id": "email-error-1",
                "subject": "Notificación",
                "from": {"emailAddress": {"address": "notificaciones@notificacionesbaccr.com"}},
                "receivedDateTime": "2025-11-06T10:00:00Z",
                "body": {
                    "content": "<html><body></body></html>"  # HTML sin datos
                },
            }
        ]

        stats = processor.process_emails(emails, profile_id="profile-123")

        assert stats["total"] == 1
        assert stats["procesados"] == 0
        assert stats["errores"] == 1

    @patch("finanzas_tracker.services.transaction_processor.exchange_rate_service")
    @patch("finanzas_tracker.services.transaction_processor.get_session")
    @patch("finanzas_tracker.services.transaction_processor.Transaction")
    def test_process_emails_duplicate_handling(
        self,
        mock_transaction_class: MagicMock,
        mock_get_session: MagicMock,
        mock_exchange_service: MagicMock,
        mock_subscription_detector: MagicMock,
    ) -> None:
        """Test manejando correos duplicados."""
        mock_session = MagicMock()
        # Primera vez: éxito, segunda vez: duplicado
        mock_session.commit.side_effect = [None, IntegrityError("", "", "")]
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock query chain for auto-train check (return 0 to skip training)
        mock_session.query.return_value.filter.return_value.count.return_value = 0

        mock_transaction_class.return_value = create_transaction_mock("TEST", Decimal("1000.00"))

        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)

        emails = [
            {
                "id": "email-dup-1",
                "subject": "Notificación",
                "from": {"emailAddress": {"address": "notificaciones@notificacionesbaccr.com"}},
                "receivedDateTime": "2025-11-06T10:00:00Z",
                "body": {
                    "content": """
                    <html><body><table>
                        <tr><td>Comercio:</td><td>TEST</td></tr>
                        <tr><td>Monto:</td><td>CRC 1,000.00</td></tr>
                    </table></body></html>
                    """
                },
            },
            {
                "id": "email-dup-1",  # Mismo ID (duplicado)
                "subject": "Notificación",
                "from": {"emailAddress": {"address": "notificaciones@notificacionesbaccr.com"}},
                "receivedDateTime": "2025-11-06T10:00:00Z",
                "body": {
                    "content": """
                    <html><body><table>
                        <tr><td>Comercio:</td><td>TEST</td></tr>
                        <tr><td>Monto:</td><td>CRC 1,000.00</td></tr>
                    </table></body></html>
                    """
                },
            },
        ]

        stats = processor.process_emails(emails, profile_id="profile-123")

        assert stats["total"] == 2
        assert stats["procesados"] == 1
        assert stats["duplicados"] == 1

    @patch("finanzas_tracker.services.transaction_processor.exchange_rate_service")
    @patch("finanzas_tracker.services.transaction_processor.get_session")
    @patch("finanzas_tracker.services.transaction_processor.Transaction")
    def test_process_emails_mixed_batch(
        self,
        mock_transaction_class: MagicMock,
        mock_get_session: MagicMock,
        mock_exchange_service: MagicMock,
        mock_subscription_detector: MagicMock,
    ) -> None:
        """Test procesando batch mixto (BAC, Popular, errores)."""
        mock_session = MagicMock()
        # Simular: éxito, éxito, duplicado
        mock_session.commit.side_effect = [None, None, IntegrityError("", "", "")]
        mock_get_session.return_value.__enter__.return_value = mock_session

        # Mock query chain for auto-train check (return 0 to skip training)
        mock_session.query.return_value.filter.return_value.count.return_value = 0

        mock_exchange_service.get_rate.return_value = 520.0
        mock_transaction_class.return_value = create_transaction_mock("VARIOS", Decimal("5000.00"))

        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)

        emails = [
            # Email 1: BAC en CRC - éxito
            {
                "id": "email-1",
                "subject": "Notificación",
                "from": {"emailAddress": {"address": "notificaciones@notificacionesbaccr.com"}},
                "receivedDateTime": "2025-11-06T10:00:00Z",
                "body": {
                    "content": """
                    <html><body><table>
                        <tr><td>Comercio:</td><td>STARBUCKS</td></tr>
                        <tr><td>Monto:</td><td>CRC 5,000.00</td></tr>
                    </table></body></html>
                    """
                },
            },
            # Email 2: Popular en USD - éxito con conversión
            {
                "id": "email-2",
                "subject": "Notificación",
                "from": {"emailAddress": {"address": "infopersonal@bancopopular.fi.cr"}},
                "receivedDateTime": "2025-11-06T11:00:00Z",
                "body": {
                    "content": """
                    <html><body>
                        <p>Comercio: NETFLIX</p>
                        <p>Monto: USD 15.00</p>
                    </body></html>
                    """
                },
            },
            # Email 3: Duplicado
            {
                "id": "email-1",  # Mismo ID que email-1
                "subject": "Notificación",
                "from": {"emailAddress": {"address": "notificaciones@notificacionesbaccr.com"}},
                "receivedDateTime": "2025-11-06T10:00:00Z",
                "body": {
                    "content": """
                    <html><body><table>
                        <tr><td>Comercio:</td><td>STARBUCKS</td></tr>
                        <tr><td>Monto:</td><td>CRC 5,000.00</td></tr>
                    </table></body></html>
                    """
                },
            },
            # Email 4: Banco desconocido - error
            {
                "id": "email-4",
                "subject": "Test",
                "from": {"emailAddress": {"address": "unknown@example.com"}},
                "receivedDateTime": "2025-11-06T12:00:00Z",
                "body": {"content": "<html><body></body></html>"},
            },
        ]

        stats = processor.process_emails(emails, profile_id="profile-123")

        assert stats["total"] == 4
        assert stats["procesados"] == 2
        assert stats["bac"] == 2  # 2 correos de BAC procesados (incluyendo duplicado)
        assert stats["popular"] == 1
        assert stats["usd_convertidos"] == 1
        assert stats["duplicados"] == 1
        assert stats["errores"] == 1

    def test_process_emails_empty_list(self, mock_subscription_detector: MagicMock) -> None:
        """Test procesando lista vacía de correos."""
        processor = TransactionProcessor(auto_categorize=False, detect_anomalies=False)

        stats = processor.process_emails([], profile_id="profile-123")

        assert stats["total"] == 0
        assert stats["procesados"] == 0
        assert stats["errores"] == 0
