"""
Tests unitarios para TransactionProcessor.

Tests comprehensivos para el servicio que procesa correos bancarios
y los convierte en transacciones, incluyendo:
- Identificación de bancos
- Procesamiento de correos
- Conversión de moneda
- Manejo de errores
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


class TestTransactionProcessorInit:
    """Tests para la inicialización del processor."""

    def test_init_with_auto_categorize_true(self):
        """Debería inicializar con categorizador cuando auto_categorize=True."""
        from finanzas_tracker.services.transaction_processor import TransactionProcessor

        with patch("finanzas_tracker.services.transaction_processor.TransactionCategorizer"):
            processor = TransactionProcessor(auto_categorize=True)

            assert processor.auto_categorize is True
            assert processor.categorizer is not None

    def test_init_with_auto_categorize_false(self):
        """Debería inicializar sin categorizador cuando auto_categorize=False."""
        from finanzas_tracker.services.transaction_processor import TransactionProcessor

        processor = TransactionProcessor(auto_categorize=False)

        assert processor.auto_categorize is False
        assert processor.categorizer is None

    def test_init_creates_parsers(self):
        """Debería crear instancias de BACParser y PopularParser."""
        from finanzas_tracker.parsers.bac_parser import BACParser
        from finanzas_tracker.parsers.popular_parser import PopularParser
        from finanzas_tracker.services.transaction_processor import TransactionProcessor

        processor = TransactionProcessor(auto_categorize=False)

        assert isinstance(processor.bac_parser, BACParser)
        assert isinstance(processor.popular_parser, PopularParser)


class TestIdentifyBank:
    """Tests para _identify_bank."""

    @pytest.fixture
    def processor(self):
        """Fixture para crear processor sin auto-categorize."""
        from finanzas_tracker.services.transaction_processor import TransactionProcessor

        return TransactionProcessor(auto_categorize=False)

    def test_identify_bac_from_notificacion(self, processor):
        """Debería identificar BAC desde correo de notificacion@notificacionesbaccr.com."""
        email = {"from": {"emailAddress": {"address": "notificacion@notificacionesbaccr.com"}}}

        result = processor._identify_bank(email)

        assert result == "bac"

    def test_identify_bac_from_bacnet(self, processor):
        """Debería identificar BAC desde correo de notificaciones@bacnet.net."""
        email = {"from": {"emailAddress": {"address": "notificaciones@bacnet.net"}}}

        result = processor._identify_bank(email)

        assert result == "bac"

    def test_identify_popular_from_infopersonal(self, processor):
        """Debería identificar Popular desde correo de infopersonal@bancopopular.fi.cr."""
        email = {"from": {"emailAddress": {"address": "infopersonal@bancopopular.fi.cr"}}}

        result = processor._identify_bank(email)

        assert result == "popular"

    def test_identify_popular_from_cajero(self, processor):
        """Debería identificar Popular desde correo de cajero@bancopopular.fi.cr."""
        email = {"from": {"emailAddress": {"address": "cajero@bancopopular.fi.cr"}}}

        result = processor._identify_bank(email)

        assert result == "popular"

    def test_identify_bank_unknown_sender(self, processor):
        """Debería retornar None para sender desconocido."""
        email = {"from": {"emailAddress": {"address": "unknown@example.com"}}}

        result = processor._identify_bank(email)

        assert result is None

    def test_identify_bank_empty_email(self, processor):
        """Debería retornar None para email vacío."""
        email = {}

        result = processor._identify_bank(email)

        assert result is None

    def test_identify_bank_case_insensitive(self, processor):
        """Debería identificar banco sin importar mayúsculas/minúsculas."""
        email = {"from": {"emailAddress": {"address": "NOTIFICACION@NOTIFICACIONESBACCR.COM"}}}

        result = processor._identify_bank(email)

        assert result == "bac"


class TestApplyCurrencyConversion:
    """Tests para _apply_currency_conversion."""

    @pytest.fixture
    def processor(self):
        """Fixture para crear processor."""
        from finanzas_tracker.services.transaction_processor import TransactionProcessor

        return TransactionProcessor(auto_categorize=False)

    def test_convert_usd_to_crc(self, processor):
        """Debería convertir USD a CRC usando tipo de cambio."""
        transaction_data = {
            "monto_original": Decimal("100.00"),
            "fecha_transaccion": datetime(2024, 1, 15),
        }

        with patch(
            "finanzas_tracker.services.transaction_processor.exchange_rate_service"
        ) as mock_service:
            mock_service.get_rate.return_value = 520.50

            processor._apply_currency_conversion(transaction_data)

            assert transaction_data["monto_crc"] == Decimal("52050.00")
            assert transaction_data["tipo_cambio_usado"] == Decimal("520.50")

    def test_convert_handles_date_object(self, processor):
        """Debería manejar fecha como date object."""
        from datetime import date

        transaction_data = {
            "monto_original": Decimal("50.00"),
            "fecha_transaccion": date(2024, 1, 15),
        }

        with patch(
            "finanzas_tracker.services.transaction_processor.exchange_rate_service"
        ) as mock_service:
            mock_service.get_rate.return_value = 500.00

            processor._apply_currency_conversion(transaction_data)

            assert transaction_data["monto_crc"] == Decimal("25000.00")

    def test_convert_handles_datetime_object(self, processor):
        """Debería manejar fecha como datetime object."""
        transaction_data = {
            "monto_original": Decimal("25.50"),
            "fecha_transaccion": datetime(2024, 3, 20, 10, 30, 0),
        }

        with patch(
            "finanzas_tracker.services.transaction_processor.exchange_rate_service"
        ) as mock_service:
            mock_service.get_rate.return_value = 510.00

            processor._apply_currency_conversion(transaction_data)

            assert transaction_data["monto_crc"] == Decimal("13005.00")


class TestProcessEmails:
    """Tests para process_emails."""

    @pytest.fixture
    def processor(self):
        """Fixture para crear processor sin categorización."""
        from finanzas_tracker.services.transaction_processor import TransactionProcessor

        return TransactionProcessor(auto_categorize=False)

    def test_process_empty_list(self, processor):
        """Debería retornar stats vacíos para lista vacía."""
        stats = processor.process_emails([], profile_id="test-profile")

        assert stats["total"] == 0
        assert stats["procesados"] == 0
        assert stats["errores"] == 0

    def test_process_bac_email_success(self, processor):
        """Debería procesar correo BAC exitosamente."""
        email = {
            "from": {"emailAddress": {"address": "notificacion@notificacionesbaccr.com"}},
            "subject": "Notificación de transacción",
            "body": {"content": "<html>...</html>"},
        }

        mock_parsed_data = {
            "comercio": "SUPER WALMART",
            "monto_original": Decimal("15000.00"),
            "moneda_original": "CRC",
            "fecha_transaccion": datetime(2024, 1, 15),
            "tipo_transaccion": "COMPRA",
            "email_id": "email-123",
        }

        with patch.object(processor.bac_parser, "parse", return_value=mock_parsed_data):
            with patch.object(processor, "_save_transaction", return_value=(True, MagicMock())):
                stats = processor.process_emails([email], profile_id="test-profile")

        assert stats["total"] == 1
        assert stats["procesados"] == 1
        assert stats["bac"] == 1

    def test_process_popular_email_success(self, processor):
        """Debería procesar correo Popular exitosamente."""
        email = {
            "from": {"emailAddress": {"address": "infopersonal@bancopopular.fi.cr"}},
            "subject": "Notificación de transacción",
            "body": {"content": "Estimado cliente..."},
        }

        mock_parsed_data = {
            "comercio": "WALMART HEREDIA",
            "monto_original": Decimal("25000.00"),
            "moneda_original": "CRC",
            "fecha_transaccion": datetime(2024, 1, 16),
            "tipo_transaccion": "COMPRA",
            "email_id": "email-456",
        }

        with patch.object(processor.popular_parser, "parse", return_value=mock_parsed_data):
            with patch.object(processor, "_save_transaction", return_value=(True, MagicMock())):
                stats = processor.process_emails([email], profile_id="test-profile")

        assert stats["total"] == 1
        assert stats["procesados"] == 1
        assert stats["popular"] == 1

    def test_process_usd_conversion(self, processor):
        """Debería convertir USD a CRC."""
        email = {
            "from": {"emailAddress": {"address": "notificacion@notificacionesbaccr.com"}},
            "subject": "Compra en USD",
            "body": {"content": "<html>...</html>"},
        }

        mock_parsed_data = {
            "comercio": "AMAZON.COM",
            "monto_original": Decimal("50.00"),
            "moneda_original": "USD",
            "fecha_transaccion": datetime(2024, 1, 15),
            "tipo_transaccion": "COMPRA",
            "email_id": "email-789",
        }

        with patch.object(processor.bac_parser, "parse", return_value=mock_parsed_data):
            with patch(
                "finanzas_tracker.services.transaction_processor.exchange_rate_service"
            ) as mock_rate:
                mock_rate.get_rate.return_value = 520.00
                with patch.object(processor, "_save_transaction", return_value=(True, MagicMock())):
                    stats = processor.process_emails([email], profile_id="test-profile")

        assert stats["usd_convertidos"] == 1

    def test_process_unknown_sender_error(self, processor):
        """Debería contar como error cuando sender es desconocido."""
        email = {
            "from": {"emailAddress": {"address": "unknown@example.com"}},
            "subject": "Algo",
        }

        stats = processor.process_emails([email], profile_id="test-profile")

        assert stats["errores"] == 1
        assert stats["procesados"] == 0

    def test_process_parse_failure_error(self, processor):
        """Debería contar como error cuando parser retorna None."""
        email = {
            "from": {"emailAddress": {"address": "notificacion@notificacionesbaccr.com"}},
            "subject": "Correo mal formateado",
        }

        with patch.object(processor.bac_parser, "parse", return_value=None):
            stats = processor.process_emails([email], profile_id="test-profile")

        assert stats["errores"] == 1
        assert stats["procesados"] == 0

    def test_process_duplicate_transaction(self, processor):
        """Debería contar como duplicado cuando save falla."""
        email = {
            "from": {"emailAddress": {"address": "notificacion@notificacionesbaccr.com"}},
            "subject": "Transacción",
        }

        mock_parsed_data = {
            "comercio": "TEST",
            "monto_original": Decimal("1000.00"),
            "moneda_original": "CRC",
            "fecha_transaccion": datetime(2024, 1, 15),
            "tipo_transaccion": "COMPRA",
            "email_id": "duplicate-email",
        }

        with patch.object(processor.bac_parser, "parse", return_value=mock_parsed_data):
            with patch.object(processor, "_save_transaction", return_value=(False, None)):
                stats = processor.process_emails([email], profile_id="test-profile")

        assert stats["duplicados"] == 1
        assert stats["procesados"] == 0

    def test_process_multiple_emails(self, processor):
        """Debería procesar múltiples correos correctamente."""
        emails = [
            {
                "from": {"emailAddress": {"address": "notificacion@notificacionesbaccr.com"}},
                "subject": "1",
            },
            {
                "from": {"emailAddress": {"address": "infopersonal@bancopopular.fi.cr"}},
                "subject": "2",
            },
            {"from": {"emailAddress": {"address": "unknown@example.com"}}, "subject": "3"},
        ]

        mock_parsed = {
            "comercio": "TEST",
            "monto_original": Decimal("1000.00"),
            "moneda_original": "CRC",
            "fecha_transaccion": datetime(2024, 1, 15),
            "tipo_transaccion": "COMPRA",
            "email_id": "test",
        }

        with patch.object(processor.bac_parser, "parse", return_value=mock_parsed):
            with patch.object(processor.popular_parser, "parse", return_value=mock_parsed):
                with patch.object(processor, "_save_transaction", return_value=(True, MagicMock())):
                    stats = processor.process_emails(emails, profile_id="test")

        assert stats["total"] == 3
        assert stats["procesados"] == 2
        assert stats["bac"] == 1
        assert stats["popular"] == 1
        assert stats["errores"] == 1


class TestCategorizeTransaction:
    """Tests para _categorize_transaction."""

    def test_categorize_success(self):
        """Debería categorizar transacción exitosamente."""
        from finanzas_tracker.services.transaction_processor import TransactionProcessor

        with patch(
            "finanzas_tracker.services.transaction_processor.TransactionCategorizer"
        ) as MockCat:
            mock_categorizer = MagicMock()
            mock_categorizer.categorize.return_value = {
                "subcategory_id": 5,
                "categoria_sugerida": "Supermercados",
                "necesita_revision": False,
            }
            MockCat.return_value = mock_categorizer

            processor = TransactionProcessor(auto_categorize=True)

            transaction_data = {
                "comercio": "WALMART",
                "monto_crc": 15000.00,
                "tipo_transaccion": "COMPRA",
                "profile_id": "test-profile",
            }
            stats = {"categorizadas_automaticamente": 0, "necesitan_revision": 0}

            processor._categorize_transaction(transaction_data, stats)

            assert transaction_data["subcategory_id"] == 5
            assert transaction_data["categoria_sugerida_por_ia"] == "Supermercados"
            assert transaction_data["necesita_revision"] is False
            assert stats["categorizadas_automaticamente"] == 1

    def test_categorize_needs_revision(self):
        """Debería marcar para revisión cuando categorizer lo indica."""
        from finanzas_tracker.services.transaction_processor import TransactionProcessor

        with patch(
            "finanzas_tracker.services.transaction_processor.TransactionCategorizer"
        ) as MockCat:
            mock_categorizer = MagicMock()
            mock_categorizer.categorize.return_value = {
                "subcategory_id": None,
                "categoria_sugerida": "Desconocido",
                "necesita_revision": True,
            }
            MockCat.return_value = mock_categorizer

            processor = TransactionProcessor(auto_categorize=True)

            transaction_data = {
                "comercio": "XYZ123",
                "monto_crc": 5000.00,
                "tipo_transaccion": "COMPRA",
            }
            stats = {"categorizadas_automaticamente": 0, "necesitan_revision": 0}

            processor._categorize_transaction(transaction_data, stats)

            assert transaction_data["necesita_revision"] is True
            assert stats["necesitan_revision"] == 1

    def test_categorize_error_marks_for_revision(self):
        """Debería marcar para revisión cuando hay error."""
        from finanzas_tracker.services.transaction_processor import TransactionProcessor

        with patch(
            "finanzas_tracker.services.transaction_processor.TransactionCategorizer"
        ) as MockCat:
            mock_categorizer = MagicMock()
            mock_categorizer.categorize.side_effect = Exception("API Error")
            MockCat.return_value = mock_categorizer

            processor = TransactionProcessor(auto_categorize=True)

            transaction_data = {
                "comercio": "TEST",
                "monto_crc": 1000.00,
                "tipo_transaccion": "COMPRA",
            }
            stats = {"categorizadas_automaticamente": 0, "necesitan_revision": 0}

            processor._categorize_transaction(transaction_data, stats)

            assert transaction_data["subcategory_id"] is None
            assert transaction_data["necesita_revision"] is True
            assert stats["necesitan_revision"] == 1


class TestSenderToBank:
    """Tests para el mapeo SENDER_TO_BANK."""

    def test_all_bac_senders_mapped(self):
        """Todos los senders de BAC deben estar mapeados."""
        from finanzas_tracker.services.transaction_processor import TransactionProcessor

        bac_senders = [
            "notificacion@notificacionesbaccr.com",
            "notificaciones@bacnet.net",
            "notificaciones@notificacionesbaccr.com",
            "alerta@baccredomatic.com",
        ]

        for sender in bac_senders:
            assert sender in TransactionProcessor.SENDER_TO_BANK
            assert TransactionProcessor.SENDER_TO_BANK[sender] == "bac"

    def test_all_popular_senders_mapped(self):
        """Todos los senders de Popular deben estar mapeados."""
        from finanzas_tracker.services.transaction_processor import TransactionProcessor

        popular_senders = [
            "infopersonal@bancopopular.fi.cr",
            "cajero@bancopopular.fi.cr",
        ]

        for sender in popular_senders:
            assert sender in TransactionProcessor.SENDER_TO_BANK
            assert TransactionProcessor.SENDER_TO_BANK[sender] == "popular"
