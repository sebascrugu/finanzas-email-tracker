"""Parsers de correos y estados de cuenta bancarios."""

from finanzas_tracker.parsers.bac_credit_card_parser import (
    BACCreditCardParser,
    CreditCardMetadata,
    CreditCardStatementResult,
    CreditCardTransaction,
)
from finanzas_tracker.parsers.bac_parser import BACParser
from finanzas_tracker.parsers.bac_pdf_parser import (
    BACPDFParser,
    BACStatementMetadata,
    BACStatementResult,
    BACTransaction,
)
from finanzas_tracker.parsers.base_parser import BaseParser, EmailParseError, ParsedTransaction
from finanzas_tracker.parsers.popular_parser import PopularParser


__all__ = [
    "BaseParser",
    "BACParser",
    "BACCreditCardParser",
    "BACPDFParser",
    "BACTransaction",
    "BACStatementResult",
    "BACStatementMetadata",
    "CreditCardMetadata",
    "CreditCardStatementResult",
    "CreditCardTransaction",
    "PopularParser",
    "EmailParseError",
    "ParsedTransaction",
]
