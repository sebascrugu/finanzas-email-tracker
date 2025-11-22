"""Parser de correos de Banco Popular."""

from datetime import datetime
import re
from typing import Any

from bs4 import BeautifulSoup

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.parsers.base_parser import BaseParser


logger = get_logger(__name__)


class PopularParser(BaseParser):
    """
    Parser para correos de Banco Popular.

    Extrae información de transacciones desde correos HTML de Banco Popular.
    """

    @property
    def bank_name(self) -> str:
        return "popular"

    def _extract_comercio(self, soup: BeautifulSoup, subject: str) -> str:
        """
        Extrae el nombre del comercio.

        Busca patrones comunes en el texto del correo.
        """
        text = soup.get_text()

        patterns = [
            r"Comercio[:\s]+([A-Z][A-Za-z0-9\s]+)",
            r"Establecimiento[:\s]+([A-Z][A-Za-z0-9\s]+)",
            r"Lugar[:\s]+([A-Z][A-Za-z0-9\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        # Fallback: buscar en el asunto
        if "transacción" in subject.lower() or "compra" in subject.lower():
            words = subject.split()
            for i, word in enumerate(words):
                if word.lower() in ["en", "de", "comercio"] and i + 1 < len(words):
                    return " ".join(words[i + 1 :]).strip()

        return "Desconocido"

    def _extract_ubicacion(self, soup: BeautifulSoup) -> str:
        """Extrae la ubicación de la transacción."""
        text = soup.get_text()

        patterns = [
            r"Ciudad[:\s]+([A-Z][A-Za-z\s]+,\s*[A-Za-z\s]+)",
            r"Ubicación[:\s]+([A-Z][A-Za-z\s]+,\s*[A-Za-z\s]+)",
            r"Pa[ií]s[:\s]+([A-Za-z\s]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return ""

    def _extract_fecha(self, soup: BeautifulSoup, email_data: dict[str, Any]) -> datetime:
        """Extrae la fecha de la transacción."""
        text = soup.get_text()

        fecha_str = None
        hora_str = None

        # Buscar fecha
        fecha_match = re.search(r"Fecha[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})", text)
        if fecha_match:
            fecha_str = fecha_match.group(1)

        # Buscar hora
        hora_match = re.search(r"Hora[:\s]+(\d{1,2}:\d{2})", text)
        if hora_match:
            hora_str = hora_match.group(1)

        # Intentar parsear fecha
        if fecha_str:
            for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]:
                try:
                    fecha = datetime.strptime(fecha_str, fmt)
                    if hora_str:
                        hora = datetime.strptime(hora_str, "%H:%M")
                        fecha = fecha.replace(hour=hora.hour, minute=hora.minute)
                    return fecha
                except ValueError:
                    continue

        return self._get_email_date_fallback(email_data)

    def _extract_tipo_transaccion(self, soup: BeautifulSoup, subject: str) -> str:
        """Extrae el tipo de transacción."""
        text = soup.get_text().lower()
        subject_lower = subject.lower()

        # Mapeo de keywords a tipos
        type_keywords = {
            "compra": ["compra", "purchase"],
            "retiro": ["retiro", "withdrawal"],
            "transferencia": ["transferencia", "transfer", "sinpe"],
            "pago_servicio": ["pago", "payment", "pago de servicio"],
        }

        for trans_type, keywords in type_keywords.items():
            if any(kw in text or kw in subject_lower for kw in keywords):
                return trans_type

        return "compra"

    def _extract_monto(self, soup: BeautifulSoup) -> str | None:
        """Extrae el monto de la transacción."""
        text = soup.get_text()

        patterns = [
            r"Monto[:\s]+((?:USD|CRC|[$₡])\s*[\d,]+\.?\d*)",
            r"Total[:\s]+((?:USD|CRC|[$₡])\s*[\d,]+\.?\d*)",
            r"Importe[:\s]+((?:USD|CRC|[$₡])\s*[\d,]+\.?\d*)",
            r"((?:USD|CRC)\s+[\d,]+\.?\d*)",
            r"([$₡]\s*[\d,]+\.?\d*)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return None
