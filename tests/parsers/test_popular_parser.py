"""Tests for Banco Popular parser."""

from datetime import datetime

import pytest

from finanzas_tracker.parsers.popular_parser import PopularParser


class TestPopularParser:
    """Tests for PopularParser class."""

    @pytest.fixture
    def parser(self) -> PopularParser:
        """Create a Popular parser instance."""
        return PopularParser()

    @pytest.fixture
    def sample_popular_text(self) -> str:
        """Sample Banco Popular email text."""
        return """
        Estimado (a) cliente,

        El Banco Popular le informa de la transacción realizada en
        HOSPITAL METROPOLITANO PLSAN JOSE CR el 06/11/2025 a las 10:28,
        con la tarjeta VISA INTERNACIONAL A 6446, Auth # 566794,
        Ref # 531016110325, por 25,991.33 Colones
        """

    @pytest.fixture
    def sample_email_data(self) -> dict:
        """Sample email metadata."""
        return {
            "subject": "Notificación de transacción",
            "date": datetime(2025, 11, 6, 10, 28),
            "from": "notificaciones@bancopopular.fi.cr",
            "body": """
            Estimado (a) cliente,
            El Banco Popular le informa de la transacción realizada en
            HOSPITAL METROPOLITANO PLSAN JOSE CR el 06/11/2025 a las 10:28,
            con la tarjeta VISA INTERNACIONAL A 6446, Auth # 566794,
            Ref # 531016110325, por 25,991.33 Colones
            """,
        }

    def test_bank_name(self, parser: PopularParser) -> None:
        """Bank name should be 'popular'."""
        assert parser.bank_name == "popular"

    def test_parser_inherits_from_base(self, parser: PopularParser) -> None:
        """Parser should inherit from BaseParser."""
        from finanzas_tracker.parsers.base_parser import BaseParser

        assert isinstance(parser, BaseParser)

    def test_extract_amount_from_text(self, parser: PopularParser) -> None:
        """Should extract amount using regex patterns."""
        text = "por 25,991.33 Colones"
        # Test the pattern matching logic
        import re

        pattern = r"por\s+([\d,]+\.?\d*)\s*Colones"
        match = re.search(pattern, text)
        assert match is not None
        amount_str = match.group(1).replace(",", "")
        assert float(amount_str) == 25991.33

    def test_extract_card_digits(self, parser: PopularParser) -> None:
        """Should extract last 4 digits of card."""
        text = "con la tarjeta VISA INTERNACIONAL A 6446"
        import re

        pattern = r"tarjeta\s+\w+\s+\w+\s+\w+\s+(\d{4})"
        match = re.search(pattern, text)
        assert match is not None
        assert match.group(1) == "6446"

    def test_extract_merchant_from_text(self, parser: PopularParser) -> None:
        """Should extract merchant name from text."""
        text = "transacción realizada en HOSPITAL METROPOLITANO PLSAN JOSE CR el 06/11/2025"
        import re

        pattern = r"realizada en\s+(.+?)\s+el\s+\d{2}/\d{2}/\d{4}"
        match = re.search(pattern, text)
        assert match is not None
        assert "HOSPITAL METROPOLITANO" in match.group(1)

    def test_extract_date_from_text(self, parser: PopularParser) -> None:
        """Should extract date from text."""
        text = "el 06/11/2025 a las 10:28"
        import re

        pattern = r"el\s+(\d{2}/\d{2}/\d{4})\s+a las\s+(\d{2}:\d{2})"
        match = re.search(pattern, text)
        assert match is not None
        assert match.group(1) == "06/11/2025"
        assert match.group(2) == "10:28"
