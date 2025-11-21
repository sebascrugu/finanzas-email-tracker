"""Tests for BAC parser."""

from datetime import datetime

import pytest

from finanzas_tracker.parsers.bac_parser import BACParser


class TestBACParser:
    """Tests for BACParser class."""

    @pytest.fixture
    def parser(self) -> BACParser:
        """Create a BAC parser instance."""
        return BACParser()

    @pytest.fixture
    def sample_bac_html(self) -> str:
        """Sample BAC email HTML."""
        return """
        <html>
        <body>
            <table>
                <tr><td>Comercio:</td><td>DUNKIN TRES RIOS</td></tr>
                <tr><td>Ciudad y país:</td><td>San Jose, Costa Rica</td></tr>
                <tr><td>Fecha:</td><td>Nov 6, 2025, 10:32</td></tr>
                <tr><td>Tarjeta:</td><td>AMEX ***********6380</td></tr>
                <tr><td>Autorización:</td><td>937009</td></tr>
                <tr><td>Tipo de Transacción:</td><td>COMPRA</td></tr>
                <tr><td>Monto:</td><td>CRC 1,290.00</td></tr>
            </table>
        </body>
        </html>
        """

    @pytest.fixture
    def sample_email_data(self) -> dict:
        """Sample email metadata."""
        return {
            "subject": "Notificación de transacción DUNKIN TRES RIOS 06-11-2025",
            "date": datetime(2025, 11, 6, 10, 32),
            "from": "notificaciones@bac.net",
        }

    def test_bank_name(self, parser: BACParser) -> None:
        """Bank name should be 'bac'."""
        assert parser.bank_name == "bac"

    def test_extract_comercio_from_table(self, parser: BACParser, sample_bac_html: str) -> None:
        """Should extract merchant from HTML table."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(sample_bac_html, "html.parser")
        comercio = parser._extract_comercio(soup, "")
        assert comercio == "DUNKIN TRES RIOS"

    def test_extract_comercio_fallback_subject(self, parser: BACParser) -> None:
        """Should extract merchant from subject when table fails."""
        from bs4 import BeautifulSoup

        empty_html = "<html><body></body></html>"
        soup = BeautifulSoup(empty_html, "html.parser")
        subject = "Notificación de transacción WALMART 06-11-2025"
        comercio = parser._extract_comercio(soup, subject)
        assert comercio == "WALMART"

    def test_extract_comercio_unknown(self, parser: BACParser) -> None:
        """Should return 'Desconocido' when merchant not found."""
        from bs4 import BeautifulSoup

        empty_html = "<html><body></body></html>"
        soup = BeautifulSoup(empty_html, "html.parser")
        comercio = parser._extract_comercio(soup, "Some other subject")
        assert comercio == "Desconocido"

    def test_extract_ubicacion(self, parser: BACParser, sample_bac_html: str) -> None:
        """Should extract location from HTML table."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(sample_bac_html, "html.parser")
        ubicacion = parser._extract_ubicacion(soup)
        assert ubicacion == "San Jose, Costa Rica"

    def test_extract_ubicacion_empty(self, parser: BACParser) -> None:
        """Should return empty string when location not found."""
        from bs4 import BeautifulSoup

        empty_html = "<html><body></body></html>"
        soup = BeautifulSoup(empty_html, "html.parser")
        ubicacion = parser._extract_ubicacion(soup)
        assert ubicacion == ""

    def test_handle_special_format_returns_none_for_normal(
        self, parser: BACParser, sample_bac_html: str, sample_email_data: dict
    ) -> None:
        """Should return None for normal transactions."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(sample_bac_html, "html.parser")
        result = parser._handle_special_format(soup, sample_email_data)
        assert result is None

    def test_parser_inherits_from_base(self, parser: BACParser) -> None:
        """Parser should inherit from BaseParser."""
        from finanzas_tracker.parsers.base_parser import BaseParser

        assert isinstance(parser, BaseParser)
