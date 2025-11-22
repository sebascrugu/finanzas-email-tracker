"""Parser de correos de BAC Credomatic."""

from datetime import datetime
import re
from typing import Any

from bs4 import BeautifulSoup

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.parsers.base_parser import BaseParser, ParsedTransaction
from finanzas_tracker.utils.parser_utils import ParserUtils


logger = get_logger(__name__)


class BACParser(BaseParser):
    """
    Parser para correos de BAC Credomatic.

    Extrae información de transacciones desde correos HTML de BAC.
    """

    @property
    def bank_name(self) -> str:
        return "bac"

    def _handle_special_format(
        self, soup: BeautifulSoup, email_data: dict[str, Any]
    ) -> ParsedTransaction | None:
        """Maneja formato especial de retiro sin tarjeta."""
        subject = email_data.get("subject", "")
        if "retiro sin tarjeta" in subject.lower():
            return self._parse_retiro_sin_tarjeta(soup, email_data)
        return None

    def _extract_comercio(self, soup: BeautifulSoup, subject: str) -> str:
        """Extrae el nombre del comercio del correo."""
        # Intentar desde la tabla HTML
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if "Comercio" in label:
                    return cells[1].get_text(strip=True)

        # Fallback: extraer del asunto
        match = re.search(r"Notificación de transacción\s+(.+?)\s+\d{2}-\d{2}-\d{4}", subject)
        if match:
            return match.group(1).strip()

        return "Desconocido"

    def _extract_ubicacion(self, soup: BeautifulSoup) -> str:
        """Extrae ciudad y país del correo."""
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if "Ciudad y país" in label or "Ciudad y pa" in label:
                    return cells[1].get_text(strip=True)
        return ""

    def _extract_fecha(
        self, soup: BeautifulSoup, email_data: dict[str, Any]
    ) -> datetime:
        """
        Extrae la fecha de la transacción.

        Intenta primero desde el HTML, luego usa la fecha del correo.
        """
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if "Fecha:" in label:
                    fecha_str = cells[1].get_text(strip=True)
                    try:
                        return datetime.strptime(fecha_str, "%b %d, %Y, %H:%M")
                    except ValueError:
                        pass

        return self._get_email_date_fallback(email_data)

    def _extract_tipo_transaccion(self, soup: BeautifulSoup, subject: str) -> str:
        """Extrae el tipo de transacción."""
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if "Tipo de Transacción" in label or "Tipo de Transacci" in label:
                    return cells[1].get_text(strip=True)
        return "compra"

    def _extract_monto(self, soup: BeautifulSoup) -> str | None:
        """Extrae el monto de la transacción."""
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label_text = cells[0].get_text(strip=True)
                if "Monto" in label_text or "monto" in label_text:
                    monto_text = cells[1].get_text(strip=True)
                    if monto_text:
                        return monto_text
        return None

    def _parse_retiro_sin_tarjeta(
        self,
        soup: BeautifulSoup,
        email_data: dict[str, Any],
    ) -> ParsedTransaction | None:
        """
        Parsea correos de retiro sin tarjeta (formato diferente).

        Args:
            soup: BeautifulSoup del HTML
            email_data: Datos del correo

        Returns:
            ParsedTransaction | None: Datos de la transacción o None
        """
        text = soup.get_text()

        # Extraer monto (formato: "Monto: 50,000.00 CRC")
        monto_match = re.search(r"Monto:\s*([\d,]+\.?\d*)\s*(CRC|USD)", text)
        if not monto_match:
            logger.warning("No se pudo extraer monto de retiro sin tarjeta")
            return None

        monto_str = monto_match.group(0)
        moneda, monto = ParserUtils.parse_monto(monto_str)

        # Validar
        validation_error = self._validate_transaction(
            monto, moneda, "retiro sin tarjeta"
        )
        if validation_error:
            logger.warning(validation_error)
            return None

        # Extraer fecha
        fecha = self._extract_fecha_retiro(text, email_data)

        # Extraer lugar
        comercio, ciudad = self._extract_lugar_retiro(text)

        return {
            "email_id": email_data.get("id", ""),
            "banco": self.bank_name,
            "comercio": comercio,
            "monto_original": monto,
            "moneda_original": moneda,
            "tipo_transaccion": "retiro",
            "fecha_transaccion": fecha,
            "ciudad": ciudad,
            "pais": "Costa Rica",
        }

    def _extract_fecha_retiro(
        self, text: str, email_data: dict[str, Any]
    ) -> datetime:
        """Extrae fecha de un correo de retiro sin tarjeta."""
        fecha_match = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})", text)
        if fecha_match:
            fecha_str = f"{fecha_match.group(1)} {fecha_match.group(2)}"
            try:
                return datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                pass
        return self._get_email_date_fallback(email_data)

    def _extract_lugar_retiro(self, text: str) -> tuple[str, str | None]:
        """
        Extrae lugar de retiro sin tarjeta.

        Returns:
            Tuple de (comercio, ciudad)
        """
        lugar_match = re.search(r"Lugar donde se retir[oó] el dinero:\s*([^\n]+)", text)
        comercio = "RETIRO SIN TARJETA"
        ciudad = None

        if lugar_match:
            lugar = lugar_match.group(1).strip()
            comercio = f"RETIRO SIN TARJETA - {lugar}"

            # Mapeo de lugares conocidos a ciudades
            city_mappings = {
                "TRES RIOS": "Tres Rios",
                "SAN JOSE": "San Jose",
                "HEREDIA": "Heredia",
                "CARTAGO": "Cartago",
                "ALAJUELA": "Alajuela",
            }
            lugar_upper = lugar.upper()
            for key, city in city_mappings.items():
                if key in lugar_upper:
                    ciudad = city
                    break

        return comercio, ciudad
