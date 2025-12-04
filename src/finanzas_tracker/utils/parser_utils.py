"""Utilidades compartidas para parsers de correos bancarios."""

from decimal import Decimal, InvalidOperation
import re


class ParserUtils:
    """
    Clase con métodos de utilidad compartidos por todos los parsers.

    Contiene funciones comunes para parsear montos, ubicaciones,
    y otros datos extraídos de correos bancarios.
    """

    @staticmethod
    def parse_monto(monto_str: str) -> tuple[str, Decimal]:
        """
        Parsea el string del monto y detecta la moneda.

        Args:
            monto_str: String como "CRC 4,000.00" o "USD 25.00"

        Returns:
            tuple[str, Decimal]: (moneda, monto)

        Examples:
            >>> ParserUtils.parse_monto("CRC 1,290.00")
            ('CRC', Decimal('1290.00'))
            >>> ParserUtils.parse_monto("USD 25.99")
            ('USD', Decimal('25.99'))
            >>> ParserUtils.parse_monto("$100.50")
            ('USD', Decimal('100.50'))
        """
        # Limpiar el string
        monto_str = monto_str.strip()

        # Detectar moneda
        moneda = "CRC"
        if "USD" in monto_str.upper() or "$" in monto_str:
            moneda = "USD"
        elif "CAD" in monto_str.upper():
            moneda = "CAD"
        elif "EUR" in monto_str.upper() or "€" in monto_str:
            moneda = "EUR"
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
    def parse_ubicacion(ubicacion_str: str) -> tuple[str | None, str | None]:
        """
        Parsea la string de ubicación.

        Args:
            ubicacion_str: String como "SAN JOSE, Costa Rica"

        Returns:
            tuple[str | None, str | None]: (ciudad, pais)

        Examples:
            >>> ParserUtils.parse_ubicacion("SAN JOSE, Costa Rica")
            ('SAN JOSE', 'Costa Rica')
            >>> ParserUtils.parse_ubicacion("TRES RIOS")
            ('TRES RIOS', None)
            >>> ParserUtils.parse_ubicacion("")
            (None, None)
        """
        if not ubicacion_str:
            return None, None

        parts = [p.strip() for p in ubicacion_str.split(",")]

        if len(parts) >= 2:
            return parts[0], parts[1]
        if len(parts) == 1:
            return parts[0], None

        return None, None
