"""Parser de correos de Banco Popular."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Any

from bs4 import BeautifulSoup

from finanzas_tracker.core.logging import get_logger

logger = get_logger(__name__)


class PopularParser:
    """
    Parser para correos de Banco Popular.

    Extrae información de transacciones desde correos HTML de Banco Popular.
    """

    @staticmethod
    def parse(email_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parsea un correo de Banco Popular.

        Args:
            email_data: Datos del correo de Microsoft Graph

        Returns:
            dict | None: Datos parseados de la transacción o None si falla
        """
        try:
            subject = email_data.get("subject", "")
            body_html = email_data.get("body", {}).get("content", "")

            # Parsear HTML
            soup = BeautifulSoup(body_html, "lxml")

            # Extraer información del correo
            # NOTA: Esta implementación es genérica y debe ajustarse cuando
            # tengamos acceso a correos reales de Banco Popular
            comercio = PopularParser._extract_comercio(soup, subject)
            ubicacion = PopularParser._extract_ubicacion(soup)
            fecha = PopularParser._extract_fecha(soup, email_data)
            tipo_transaccion = PopularParser._extract_tipo_transaccion(soup, subject)
            monto_str = PopularParser._extract_monto(soup)

            if not monto_str:
                logger.warning(f"No se pudo extraer el monto del correo: {subject}")
                return None

            # Detectar moneda y monto
            moneda, monto = PopularParser._parse_monto(monto_str)

            # Parsear ubicación
            ciudad, pais = PopularParser._parse_ubicacion(ubicacion)

            transaction_data = {
                "email_id": email_data.get("id"),
                "banco": "popular",
                "comercio": comercio,
                "monto_original": monto,
                "moneda_original": moneda,
                "tipo_transaccion": tipo_transaccion.lower(),
                "fecha_transaccion": fecha,
                "ciudad": ciudad,
                "pais": pais,
            }

            logger.debug(f"✅ Transacción parseada: {comercio} - {moneda} {monto}")
            return transaction_data

        except Exception as e:
            logger.error(f"Error parseando correo de Banco Popular: {e}")
            return None

    @staticmethod
    def _extract_comercio(soup: BeautifulSoup, subject: str) -> str:
        """
        Extrae el nombre del comercio.

        Esta es una implementación genérica que busca patrones comunes.
        Debe ajustarse según el formato real de los correos.
        """
        # Buscar en el texto del correo
        text = soup.get_text()

        # Buscar patrones comunes
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
            # Intentar extraer comercio del asunto
            words = subject.split()
            for i, word in enumerate(words):
                if word.lower() in ["en", "de", "comercio"]:
                    if i + 1 < len(words):
                        return " ".join(words[i + 1 :]).strip()

        return "Desconocido"

    @staticmethod
    def _extract_ubicacion(soup: BeautifulSoup) -> str:
        """Extrae la ubicación de la transacción."""
        text = soup.get_text()

        # Buscar patrones de ubicación
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

    @staticmethod
    def _extract_fecha(soup: BeautifulSoup, email_data: dict[str, Any]) -> datetime:
        """Extrae la fecha de la transacción."""
        text = soup.get_text()

        # Buscar patrones de fecha
        patterns = [
            r"Fecha[:\s]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"Hora[:\s]+(\d{1,2}:\d{2})",
        ]

        fecha_str = None
        hora_str = None

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                if "Fecha" in pattern:
                    fecha_str = match.group(1)
                elif "Hora" in pattern:
                    hora_str = match.group(1)

        # Intentar parsear fecha
        if fecha_str:
            try:
                # Intentar diferentes formatos
                for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]:
                    try:
                        fecha = datetime.strptime(fecha_str, fmt)
                        if hora_str:
                            hora = datetime.strptime(hora_str, "%H:%M")
                            fecha = fecha.replace(hour=hora.hour, minute=hora.minute)
                        return fecha
                    except ValueError:
                        continue
            except Exception:
                pass

        # Fallback: usar fecha del correo
        received_str = email_data.get("receivedDateTime", "")
        if received_str:
            return datetime.fromisoformat(received_str.replace("Z", "+00:00"))

        return datetime.now()

    @staticmethod
    def _extract_tipo_transaccion(soup: BeautifulSoup, subject: str) -> str:
        """Extrae el tipo de transacción."""
        text = soup.get_text().lower()
        subject_lower = subject.lower()

        # Palabras clave para identificar el tipo
        if any(word in text or word in subject_lower for word in ["compra", "purchase"]):
            return "compra"
        if any(word in text or word in subject_lower for word in ["retiro", "withdrawal"]):
            return "retiro"
        if any(
            word in text or word in subject_lower for word in ["transferencia", "transfer", "sinpe"]
        ):
            return "transferencia"
        if any(
            word in text or word in subject_lower
            for word in ["pago", "payment", "pago de servicio"]
        ):
            return "pago_servicio"

        return "compra"

    @staticmethod
    def _extract_monto(soup: BeautifulSoup) -> str | None:
        """Extrae el monto de la transacción."""
        text = soup.get_text()

        # Buscar patrones de monto
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

    @staticmethod
    def _parse_monto(monto_str: str) -> tuple[str, Decimal]:
        """
        Parsea el string del monto y detecta la moneda.

        Args:
            monto_str: String como "CRC 4,000.00" o "USD 25.00"

        Returns:
            tuple[str, Decimal]: (moneda, monto)
        """
        # Limpiar el string
        monto_str = monto_str.strip()

        # Detectar moneda
        moneda = "CRC"
        if "USD" in monto_str.upper() or "$" in monto_str:
            moneda = "USD"
        elif "CRC" in monto_str.upper() or "₡" in monto_str:
            moneda = "CRC"

        # Extraer números
        monto_clean = re.sub(r"[^\d,.]", "", monto_str)
        monto_clean = monto_clean.replace(",", "")

        # Convertir a Decimal
        try:
            monto = Decimal(monto_clean)
        except Exception:
            monto = Decimal("0")

        return moneda, monto

    @staticmethod
    def _parse_ubicacion(ubicacion_str: str) -> tuple[str | None, str | None]:
        """
        Parsea la string de ubicación.

        Args:
            ubicacion_str: String como "SAN JOSE, Costa Rica"

        Returns:
            tuple[str | None, str | None]: (ciudad, pais)
        """
        if not ubicacion_str:
            return None, None

        parts = [p.strip() for p in ubicacion_str.split(",")]

        if len(parts) >= 2:
            return parts[0], parts[1]
        if len(parts) == 1:
            return parts[0], None

        return None, None
