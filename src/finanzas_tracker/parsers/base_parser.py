"""Parser base abstracto para correos bancarios."""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, TypedDict

from bs4 import BeautifulSoup

from finanzas_tracker.core.constants import MIN_TRANSACTION_AMOUNT, SUPPORTED_CURRENCIES
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.utils.parser_utils import ParserUtils


logger = get_logger(__name__)

# Tipo especial para indicar que un correo debe ser ignorado (config, marketing, etc)
SkipEmail = Literal["SKIP"]


class ParsedTransaction(TypedDict):
    """Estructura tipada para transacciones parseadas."""

    email_id: str
    banco: str
    comercio: str
    monto_original: Decimal
    moneda_original: str
    tipo_transaccion: str
    fecha_transaccion: datetime
    ciudad: str | None
    pais: str | None


class EmailParseError(Exception):
    """Error específico para fallos de parsing de email."""

    def __init__(self, message: str, email_subject: str | None = None) -> None:
        self.email_subject = email_subject
        super().__init__(message)


class BaseParser(ABC):
    """
    Parser base abstracto para correos bancarios.

    Define la interfaz común y lógica compartida para todos los parsers.
    Implementa el patrón Template Method para el flujo de parsing.
    """

    @property
    @abstractmethod
    def bank_name(self) -> str:
        """Nombre del banco que este parser maneja."""
        ...

    def parse(self, email_data: dict[str, Any]) -> ParsedTransaction | None:
        """
        Parsea un correo bancario.

        Template Method que define el flujo de parsing.
        Las subclases implementan los métodos de extracción específicos.

        Args:
            email_data: Datos del correo de Microsoft Graph

        Returns:
            ParsedTransaction | None: Datos parseados o None si falla
        """
        subject = email_data.get("subject", "")

        try:
            body_html = email_data.get("body", {}).get("content", "")
            soup = BeautifulSoup(body_html, "lxml")

            # Hook para manejar formatos especiales (ej: retiro sin tarjeta)
            special_result = self._handle_special_format(soup, email_data)
            if special_result == "SKIP":
                # Email de configuración o marketing que debe ignorarse silenciosamente
                return None
            if special_result is not None:
                return special_result

            # Flujo normal de extracción
            comercio = self._extract_comercio(soup, subject)
            ubicacion_raw = self._extract_ubicacion(soup)
            fecha = self._extract_fecha(soup, email_data)
            tipo_transaccion = self._extract_tipo_transaccion(soup, subject)
            monto_str = self._extract_monto(soup)

            if not monto_str:
                logger.warning(
                    f"No se pudo extraer monto del correo de {self.bank_name}: {subject}"
                )
                return None

            # Validar y convertir monto
            moneda, monto = ParserUtils.parse_monto(monto_str)

            validation_error = self._validate_transaction(monto, moneda, subject)
            if validation_error:
                # "SKIP" = pre-autorización, ignorar silenciosamente (ya se loggeó como INFO)
                if validation_error != "SKIP":
                    logger.warning(validation_error)
                return None

            # Parsear ubicación
            ciudad, pais = ParserUtils.parse_ubicacion(ubicacion_raw)

            transaction: ParsedTransaction = {
                "email_id": email_data.get("id", ""),
                "banco": self.bank_name,
                "comercio": comercio,
                "monto_original": monto,
                "moneda_original": moneda,
                "tipo_transaccion": tipo_transaccion.lower(),
                "fecha_transaccion": fecha,
                "ciudad": ciudad,
                "pais": pais,
            }

            logger.debug(f"Transaccion parseada [{self.bank_name}]: {comercio} - {moneda} {monto}")
            return transaction

        except EmailParseError as e:
            logger.error(f"Error de parsing [{self.bank_name}]: {e}")
            return None
        except ValueError as e:
            logger.error(f"Error de valor [{self.bank_name}] en '{subject}': {e}")
            return None
        except Exception as e:
            logger.error(
                f"Error inesperado parseando correo de {self.bank_name} '{subject}': {type(e).__name__}: {e}"
            )
            return None

    def _validate_transaction(self, monto: Decimal, moneda: str, subject: str) -> str | None:
        """
        Valida monto y moneda de la transacción.

        Returns:
            Mensaje de error si hay validación fallida, None si es válido.
        """
        # Pre-autorizaciones ($0.00) son verificaciones de tarjeta, no transacciones reales
        if monto == Decimal("0.00") or monto == Decimal("0"):
            logger.info(f"Pre-autorización ignorada (monto $0): {subject}")
            return "SKIP"  # Return especial para indicar que debe ignorarse silenciosamente
        
        if monto < MIN_TRANSACTION_AMOUNT:
            return f"Monto invalido (<{MIN_TRANSACTION_AMOUNT}): {monto} en correo: {subject}"
        if moneda not in SUPPORTED_CURRENCIES:
            return f"Moneda invalida: {moneda} en correo: {subject}"
        return None

    def _handle_special_format(
        self, soup: BeautifulSoup, email_data: dict[str, Any]
    ) -> ParsedTransaction | SkipEmail | None:
        """
        Hook para manejar formatos especiales de correo.

        Las subclases pueden sobrescribir para manejar casos especiales
        como retiros sin tarjeta, etc.

        Returns:
            ParsedTransaction si se manejó un formato especial,
            "SKIP" si el correo debe ignorarse silenciosamente,
            None para continuar con el flujo normal.
        """
        return None

    @abstractmethod
    def _extract_comercio(self, soup: BeautifulSoup, subject: str) -> str:
        """Extrae el nombre del comercio del correo."""
        ...

    @abstractmethod
    def _extract_ubicacion(self, soup: BeautifulSoup) -> str:
        """Extrae la ubicación (ciudad/país) del correo."""
        ...

    @abstractmethod
    def _extract_fecha(self, soup: BeautifulSoup, email_data: dict[str, Any]) -> datetime:
        """Extrae la fecha de la transacción."""
        ...

    @abstractmethod
    def _extract_tipo_transaccion(self, soup: BeautifulSoup, subject: str) -> str:
        """Extrae el tipo de transacción."""
        ...

    @abstractmethod
    def _extract_monto(self, soup: BeautifulSoup) -> str | None:
        """Extrae el monto de la transacción como string."""
        ...

    def _get_email_date_fallback(self, email_data: dict[str, Any]) -> datetime:
        """Obtiene la fecha del correo como fallback."""
        received_str = email_data.get("receivedDateTime", "")
        if received_str:
            return datetime.fromisoformat(received_str.replace("Z", "+00:00"))
        return datetime.now()
