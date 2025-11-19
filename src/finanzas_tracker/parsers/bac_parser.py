"""Parser de correos de BAC Credomatic."""

from datetime import datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Any

from bs4 import BeautifulSoup

from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)


class BACParser:
    """
    Parser para correos de BAC Credomatic.

    Extrae información de transacciones desde correos HTML de BAC.
    """

    @staticmethod
    def parse(email_data: dict[str, Any]) -> dict[str, Any] | None:
        """
        Parsea un correo de BAC Credomatic.

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

            # Detectar si es retiro sin tarjeta (formato diferente)
            if "retiro sin tarjeta" in subject.lower():
                return BACParser._parse_retiro_sin_tarjeta(soup, email_data)

            # Formato normal de notificaciones de transacción
            # Extraer información de la tabla
            comercio = BACParser._extract_comercio(soup, subject)
            ciudad_pais = BACParser._extract_ciudad_pais(soup)
            fecha = BACParser._extract_fecha(soup, email_data)
            tipo_transaccion = BACParser._extract_tipo_transaccion(soup)
            monto_str = BACParser._extract_monto(soup)

            if not monto_str:
                logger.warning(f"No se pudo extraer el monto del correo: {subject}")
                return None

            # Detectar moneda y monto
            moneda, monto = BACParser._parse_monto(monto_str)

            # Parsear ubicación
            ciudad, pais = BACParser._parse_ubicacion(ciudad_pais)

            transaction_data = {
                "email_id": email_data.get("id"),
                "banco": "bac",
                "comercio": comercio,
                "monto_original": monto,
                "moneda_original": moneda,
                "tipo_transaccion": tipo_transaccion.lower(),
                "fecha_transaccion": fecha,
                "ciudad": ciudad,
                "pais": pais,
            }

            logger.debug(f" Transacción parseada: {comercio} - {moneda} {monto}")
            return transaction_data

        except Exception as e:
            logger.error(f"Error parseando correo de BAC: {e}")
            return None

    @staticmethod
    def _extract_comercio(soup: BeautifulSoup, subject: str) -> str:
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
        # Ejemplo: "Notificación de transacción WEB CHECKOUT JPS LOT N 09-11-2025 - 10:18"
        match = re.search(r"Notificación de transacción\s+(.+?)\s+\d{2}-\d{2}-\d{4}", subject)
        if match:
            return match.group(1).strip()

        return "Desconocido"

    @staticmethod
    def _extract_ciudad_pais(soup: BeautifulSoup) -> str:
        """Extrae ciudad y país del correo."""
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if "Ciudad y país" in label or "Ciudad y pa" in label:
                    return cells[1].get_text(strip=True)
        return ""

    @staticmethod
    def _extract_fecha(soup: BeautifulSoup, email_data: dict[str, Any]) -> datetime:
        """
        Extrae la fecha de la transacción.

        Intenta primero desde el HTML, luego del asunto, y finalmente
        usa la fecha del correo.
        """
        # Intentar desde la tabla HTML
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if "Fecha:" in label:
                    fecha_str = cells[1].get_text(strip=True)
                    # Ejemplo: "Nov 9, 2025, 10:18"
                    try:
                        return datetime.strptime(fecha_str, "%b %d, %Y, %H:%M")
                    except ValueError:
                        pass

        # Fallback: usar fecha del correo
        received_str = email_data.get("receivedDateTime", "")
        if received_str:
            return datetime.fromisoformat(received_str.replace("Z", "+00:00"))

        return datetime.now()

    @staticmethod
    def _extract_tipo_transaccion(soup: BeautifulSoup) -> str:
        """Extrae el tipo de transacción."""
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if "Tipo de Transacción" in label or "Tipo de Transacci" in label:
                    return cells[1].get_text(strip=True)
        return "compra"

    @staticmethod
    def _extract_monto(soup: BeautifulSoup) -> str | None:
        """Extrae el monto de la transacción."""
        # Buscar todas las filas de tabla
        rows = soup.find_all("tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) >= 2:
                # Obtener texto de la primera celda (etiqueta)
                label_text = cells[0].get_text(strip=True)

                # Si encontramos "Monto", extraer valor de la segunda celda
                if "Monto" in label_text or "monto" in label_text:
                    monto_text = cells[1].get_text(strip=True)
                    if monto_text:  # Verificar que no esté vacío
                        return monto_text

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
        # Remover todo excepto dígitos, comas y puntos
        monto_clean = re.sub(r"[^\d,.]", "", monto_str)

        # Remover comas (separadores de miles)
        monto_clean = monto_clean.replace(",", "")

        # Convertir a Decimal
        try:
            monto = Decimal(monto_clean)
        except (ValueError, InvalidOperation):
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

    @staticmethod
    def _parse_retiro_sin_tarjeta(
        soup: BeautifulSoup,
        email_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Parsea correos de retiro sin tarjeta (formato diferente).

        Args:
            soup: BeautifulSoup del HTML
            email_data: Datos del correo

        Returns:
            dict | None: Datos de la transacción o None
        """
        text = soup.get_text()

        # Extraer monto (formato: "Monto: 50,000.00 CRC")
        monto_match = re.search(r"Monto:\s*([\d,]+\.?\d*)\s*(CRC|USD)", text)
        if not monto_match:
            logger.warning("No se pudo extraer monto de retiro sin tarjeta")
            return None

        monto_str = monto_match.group(0)
        moneda, monto = BACParser._parse_monto(monto_str)

        # Extraer fecha (formato: "31/10/2025 18:10:02")
        fecha_match = re.search(r"(\d{2}/\d{2}/\d{4})\s+(\d{2}:\d{2}:\d{2})", text)
        if fecha_match:
            fecha_str = f"{fecha_match.group(1)} {fecha_match.group(2)}"
            try:
                fecha = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S")
            except ValueError:
                # Fallback a fecha del correo
                fecha_str = email_data.get("receivedDateTime", "")
                if fecha_str:
                    fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
                else:
                    fecha = datetime.now()
        else:
            # Usar fecha del correo
            fecha_str = email_data.get("receivedDateTime", "")
            if fecha_str:
                fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))
            else:
                fecha = datetime.now()

        # Extraer lugar (formato: "Lugar donde se retiró el dinero: CAR-AUTOM TRES RIOS")
        lugar_match = re.search(r"Lugar donde se retir[oó] el dinero:\s*([^\n]+)", text)
        comercio = "RETIRO SIN TARJETA"
        ciudad = None

        if lugar_match:
            lugar = lugar_match.group(1).strip()
            comercio = f"RETIRO SIN TARJETA - {lugar}"
            # Intentar extraer ciudad del lugar
            if "TRES RIOS" in lugar.upper():
                ciudad = "Tres Ríos"
            elif "SAN JOSE" in lugar.upper():
                ciudad = "San José"

        transaction_data = {
            "email_id": email_data.get("id"),
            "banco": "bac",
            "comercio": comercio,
            "monto_original": monto,
            "moneda_original": moneda,
            "tipo_transaccion": "retiro",
            "fecha_transaccion": fecha,
            "ciudad": ciudad,
            "pais": "Costa Rica",
        }

        logger.debug(f" Retiro sin tarjeta parseado: {comercio} - {moneda} {monto}")
        return transaction_data
