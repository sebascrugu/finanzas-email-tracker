"""
Tests unitarios para BACParser.

Tests comprehensivos que cubren todos los casos de parseo de correos de BAC Credomatic:
- Compras en colones (CRC)
- Compras en dólares (USD)
- Retiros sin tarjeta
- Transferencias SINPE
- HTML malformado
- Campos faltantes
- Edge cases
"""

from datetime import datetime
from decimal import Decimal

from bs4 import BeautifulSoup

from finanzas_tracker.parsers.bac_parser import BACParser
from finanzas_tracker.utils.parser_utils import ParserUtils


class TestBACParserComprasCRC:
    """Tests para compras en colones costarricenses."""

    def test_parse_compra_crc_tabla_completa(self) -> None:
        """Test parseando una compra normal en colones con todos los campos."""
        email_data = {
            "id": "email-123",
            "subject": "Notificación de transacción DUNKIN TRES RIOS 06-11-2025 - 10:32",
            "receivedDateTime": "2025-11-06T10:32:00Z",
            "body": {
                "content": """
                <html>
                <body>
                    <table>
                        <tr><td>Comercio:</td><td>DUNKIN TRES RIOS</td></tr>
                        <tr><td>Ciudad y país:</td><td>TRES RIOS, Costa Rica</td></tr>
                        <tr><td>Fecha:</td><td>Nov 6, 2025, 10:32</td></tr>
                        <tr><td>Tarjeta:</td><td>AMEX ***********6380</td></tr>
                        <tr><td>Tipo de Transacción:</td><td>COMPRA</td></tr>
                        <tr><td>Monto:</td><td>CRC 1,290.00</td></tr>
                    </table>
                </body>
                </html>
                """
            },
        }

        result = BACParser().parse(email_data)

        assert result is not None
        assert result["email_id"] == "email-123"
        assert result["banco"] == "bac"
        assert result["comercio"] == "DUNKIN TRES RIOS"
        assert result["monto_original"] == Decimal("1290.00")
        assert result["moneda_original"] == "CRC"
        assert result["tipo_transaccion"] == "compra"
        assert result["ciudad"] == "TRES RIOS"
        assert result["pais"] == "Costa Rica"
        assert isinstance(result["fecha_transaccion"], datetime)

    def test_parse_compra_crc_con_comas(self) -> None:
        """Test parseando monto con separadores de miles."""
        email_data = {
            "id": "email-456",
            "subject": "Notificación de transacción",
            "receivedDateTime": "2025-11-06T15:00:00Z",
            "body": {
                "content": """
                <html>
                <body>
                    <table>
                        <tr><td>Comercio:</td><td>HOSPITAL METROPOLITANO</td></tr>
                        <tr><td>Ciudad y país:</td><td>SAN JOSE, Costa Rica</td></tr>
                        <tr><td>Tipo de Transacción:</td><td>COMPRA</td></tr>
                        <tr><td>Monto:</td><td>CRC 25,991.33</td></tr>
                    </table>
                </body>
                </html>
                """
            },
        }

        result = BACParser().parse(email_data)

        assert result is not None
        assert result["monto_original"] == Decimal("25991.33")
        assert result["moneda_original"] == "CRC"
        assert result["comercio"] == "HOSPITAL METROPOLITANO"

    def test_parse_compra_sin_ciudad(self) -> None:
        """Test parseando transacción sin información de ciudad."""
        email_data = {
            "id": "email-789",
            "subject": "Notificación de transacción",
            "receivedDateTime": "2025-11-06T12:00:00Z",
            "body": {
                "content": """
                <html>
                <body>
                    <table>
                        <tr><td>Comercio:</td><td>AMAZON WEB SERVICES</td></tr>
                        <tr><td>Ciudad y país:</td><td></td></tr>
                        <tr><td>Tipo de Transacción:</td><td>COMPRA</td></tr>
                        <tr><td>Monto:</td><td>CRC 5,200.00</td></tr>
                    </table>
                </body>
                </html>
                """
            },
        }

        result = BACParser().parse(email_data)

        assert result is not None
        assert result["ciudad"] is None
        assert result["pais"] is None
        assert result["comercio"] == "AMAZON WEB SERVICES"


class TestBACParserComprasUSD:
    """Tests para compras en dólares."""

    def test_parse_compra_usd_con_simbolo_dolar(self) -> None:
        """Test parseando compra en dólares con símbolo $."""
        email_data = {
            "id": "email-usd-1",
            "subject": "Notificación de transacción",
            "receivedDateTime": "2025-11-06T14:00:00Z",
            "body": {
                "content": """
                <html>
                <body>
                    <table>
                        <tr><td>Comercio:</td><td>AMAZON.COM</td></tr>
                        <tr><td>Ciudad y país:</td><td>SEATTLE, United States</td></tr>
                        <tr><td>Tipo de Transacción:</td><td>COMPRA</td></tr>
                        <tr><td>Monto:</td><td>USD 49.99</td></tr>
                    </table>
                </body>
                </html>
                """
            },
        }

        result = BACParser().parse(email_data)

        assert result is not None
        assert result["monto_original"] == Decimal("49.99")
        assert result["moneda_original"] == "USD"
        assert result["comercio"] == "AMAZON.COM"
        assert result["ciudad"] == "SEATTLE"
        assert result["pais"] == "United States"

    def test_parse_compra_usd_sin_decimales(self) -> None:
        """Test parseando compra en dólares sin decimales."""
        email_data = {
            "id": "email-usd-2",
            "subject": "Notificación de transacción",
            "receivedDateTime": "2025-11-06T16:00:00Z",
            "body": {
                "content": """
                <html>
                <body>
                    <table>
                        <tr><td>Comercio:</td><td>NETFLIX</td></tr>
                        <tr><td>Tipo de Transacción:</td><td>COMPRA</td></tr>
                        <tr><td>Monto:</td><td>USD 15</td></tr>
                    </table>
                </body>
                </html>
                """
            },
        }

        result = BACParser().parse(email_data)

        assert result is not None
        assert result["monto_original"] == Decimal("15")
        assert result["moneda_original"] == "USD"


class TestBACParserRetiroSinTarjeta:
    """Tests para retiros sin tarjeta."""

    def test_parse_retiro_sin_tarjeta_completo(self) -> None:
        """Test parseando retiro sin tarjeta con toda la información."""
        email_data = {
            "id": "email-retiro-1",
            "subject": "Retiro sin tarjeta",
            "receivedDateTime": "2025-11-06T18:00:00Z",
            "body": {
                "content": """
                <html>
                <body>
                    <p>Se ha realizado un retiro sin tarjeta</p>
                    <p>Monto: 50,000.00 CRC</p>
                    <p>Fecha: 06/11/2025 18:10:02</p>
                    <p>Lugar donde se retiró el dinero: CAR-AUTOM TRES RIOS</p>
                </body>
                </html>
                """
            },
        }

        result = BACParser().parse(email_data)

        assert result is not None
        assert result["banco"] == "bac"
        assert result["monto_original"] == Decimal("50000.00")
        assert result["moneda_original"] == "CRC"
        assert result["tipo_transaccion"] == "retiro"
        assert "RETIRO SIN TARJETA" in result["comercio"]
        assert "CAR-AUTOM TRES RIOS" in result["comercio"]
        assert result["pais"] == "Costa Rica"

    def test_parse_retiro_sin_tarjeta_sin_lugar(self) -> None:
        """Test parseando retiro sin tarjeta sin información de lugar."""
        email_data = {
            "id": "email-retiro-2",
            "subject": "Retiro sin tarjeta",
            "receivedDateTime": "2025-11-06T20:00:00Z",
            "body": {
                "content": """
                <html>
                <body>
                    <p>Se ha realizado un retiro sin tarjeta</p>
                    <p>Monto: 20,000.00 CRC</p>
                    <p>Fecha: 06/11/2025 20:15:30</p>
                </body>
                </html>
                """
            },
        }

        result = BACParser().parse(email_data)

        assert result is not None
        assert result["comercio"] == "RETIRO SIN TARJETA"
        assert result["tipo_transaccion"] == "retiro"
        assert result["monto_original"] == Decimal("20000.00")


class TestBACParserFechas:
    """Tests para extracción y parseo de fechas."""

    def test_parse_fecha_formato_tabla(self) -> None:
        """Test parseando fecha en formato 'Nov 6, 2025, 10:32'."""
        email_data = {
            "id": "email-fecha-1",
            "subject": "Notificación de transacción",
            "receivedDateTime": "2025-11-06T10:32:00Z",
            "body": {
                "content": """
                <html>
                <body>
                    <table>
                        <tr><td>Comercio:</td><td>TEST COMERCIO</td></tr>
                        <tr><td>Fecha:</td><td>Nov 6, 2025, 10:32</td></tr>
                        <tr><td>Monto:</td><td>CRC 1,000.00</td></tr>
                    </table>
                </body>
                </html>
                """
            },
        }

        result = BACParser().parse(email_data)

        assert result is not None
        fecha = result["fecha_transaccion"]
        assert fecha.year == 2025
        assert fecha.month == 11
        assert fecha.day == 6
        assert fecha.hour == 10
        assert fecha.minute == 32

    def test_parse_fecha_fallback_receivedDateTime(self) -> None:
        """Test usando fecha del correo cuando no se encuentra en HTML."""
        email_data = {
            "id": "email-fecha-2",
            "subject": "Notificación de transacción",
            "receivedDateTime": "2025-11-10T15:45:00Z",
            "body": {
                "content": """
                <html>
                <body>
                    <table>
                        <tr><td>Comercio:</td><td>TEST COMERCIO</td></tr>
                        <tr><td>Monto:</td><td>CRC 1,000.00</td></tr>
                    </table>
                </body>
                </html>
                """
            },
        }

        result = BACParser().parse(email_data)

        assert result is not None
        fecha = result["fecha_transaccion"]
        assert fecha.year == 2025
        assert fecha.month == 11
        assert fecha.day == 10


class TestBACParserTiposTransaccion:
    """Tests para diferentes tipos de transacciones."""

    def test_parse_tipo_compra(self) -> None:
        """Test identificando tipo de transacción: COMPRA."""
        email_data = {
            "id": "email-tipo-1",
            "subject": "Notificación de transacción",
            "receivedDateTime": "2025-11-06T10:00:00Z",
            "body": {
                "content": """
                <html><body><table>
                    <tr><td>Comercio:</td><td>SUPERMERCADO</td></tr>
                    <tr><td>Tipo de Transacción:</td><td>COMPRA</td></tr>
                    <tr><td>Monto:</td><td>CRC 5,000.00</td></tr>
                </table></body></html>
                """
            },
        }

        result = BACParser().parse(email_data)
        assert result is not None
        assert result["tipo_transaccion"] == "compra"

    def test_parse_tipo_transferencia(self) -> None:
        """Test identificando tipo de transacción: TRANSFERENCIA."""
        email_data = {
            "id": "email-tipo-2",
            "subject": "Notificación de transacción",
            "receivedDateTime": "2025-11-06T10:00:00Z",
            "body": {
                "content": """
                <html><body><table>
                    <tr><td>Comercio:</td><td>SINPE MOVIL</td></tr>
                    <tr><td>Tipo de Transacción:</td><td>TRANSFERENCIA</td></tr>
                    <tr><td>Monto:</td><td>CRC 10,000.00</td></tr>
                </table></body></html>
                """
            },
        }

        result = BACParser().parse(email_data)
        assert result is not None
        assert result["tipo_transaccion"] == "transferencia"


class TestBACParserEdgeCases:
    """Tests para casos edge y manejo de errores."""

    def test_parse_html_vacio(self) -> None:
        """Test parseando correo con HTML vacío."""
        email_data = {
            "id": "email-edge-1",
            "subject": "Notificación de transacción",
            "receivedDateTime": "2025-11-06T10:00:00Z",
            "body": {"content": "<html><body></body></html>"},
        }

        result = BACParser().parse(email_data)
        assert result is None

    def test_parse_sin_monto(self) -> None:
        """Test parseando correo sin información de monto."""
        email_data = {
            "id": "email-edge-2",
            "subject": "Notificación de transacción",
            "receivedDateTime": "2025-11-06T10:00:00Z",
            "body": {
                "content": """
                <html><body><table>
                    <tr><td>Comercio:</td><td>TEST</td></tr>
                    <tr><td>Tipo de Transacción:</td><td>COMPRA</td></tr>
                </table></body></html>
                """
            },
        }

        result = BACParser().parse(email_data)
        assert result is None

    def test_parse_monto_invalido(self) -> None:
        """Test parseando monto en formato inválido retorna None."""
        email_data = {
            "id": "email-edge-3",
            "subject": "Notificación de transacción",
            "receivedDateTime": "2025-11-06T10:00:00Z",
            "body": {
                "content": """
                <html><body><table>
                    <tr><td>Comercio:</td><td>TEST</td></tr>
                    <tr><td>Monto:</td><td>INVALID AMOUNT</td></tr>
                </table></body></html>
                """
            },
        }

        result = BACParser().parse(email_data)
        # Monto inválido debe retornar None
        assert result is None

    def test_parse_html_malformado(self) -> None:
        """Test parseando HTML malformado."""
        email_data = {
            "id": "email-edge-4",
            "subject": "Notificación de transacción TEST COMERCIO 06-11-2025 - 10:00",
            "receivedDateTime": "2025-11-06T10:00:00Z",
            "body": {
                "content": """
                <html><body>
                    <p>Comercio: TEST COMERCIO</p>
                    <p>Monto: CRC 5,000.00</p>
                </body></html>
                """
            },
        }

        # Debería intentar extraer del subject como fallback
        result = BACParser().parse(email_data)
        # Este caso puede fallar o parsear parcialmente
        # Lo importante es que no explote
        assert result is None or isinstance(result, dict)


class TestBACParserMetodosPrivados:
    """Tests para métodos privados y utilidades."""

    def test_parse_monto_crc(self) -> None:
        """Test del método parse_monto con colones."""
        moneda, monto = ParserUtils.parse_monto("CRC 1,290.00")
        assert moneda == "CRC"
        assert monto == Decimal("1290.00")

    def test_parse_monto_usd(self) -> None:
        """Test del método parse_monto con dólares."""
        moneda, monto = ParserUtils.parse_monto("USD 49.99")
        assert moneda == "USD"
        assert monto == Decimal("49.99")

    def test_parse_monto_solo_numeros(self) -> None:
        """Test del método parse_monto con solo números."""
        moneda, monto = ParserUtils.parse_monto("5000.50")
        assert moneda == "CRC"  # Default
        assert monto == Decimal("5000.50")

    def test_parse_ubicacion_completa(self) -> None:
        """Test del método parse_ubicacion con ciudad y país."""
        ciudad, pais = ParserUtils.parse_ubicacion("SAN JOSE, Costa Rica")
        assert ciudad == "SAN JOSE"
        assert pais == "Costa Rica"

    def test_parse_ubicacion_solo_ciudad(self) -> None:
        """Test del método parse_ubicacion con solo ciudad."""
        ciudad, pais = ParserUtils.parse_ubicacion("SAN JOSE")
        assert ciudad == "SAN JOSE"
        assert pais is None

    def test_parse_ubicacion_vacia(self) -> None:
        """Test del método parse_ubicacion con string vacío."""
        ciudad, pais = ParserUtils.parse_ubicacion("")
        assert ciudad is None
        assert pais is None

    def test_extract_comercio_desde_tabla(self) -> None:
        """Test de _extract_comercio desde HTML."""
        html = """
        <html><body><table>
            <tr><td>Comercio:</td><td>DUNKIN TRES RIOS</td></tr>
        </table></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        comercio = BACParser()._extract_comercio(soup, "Notificación de transacción")
        assert comercio == "DUNKIN TRES RIOS"

    def test_extract_comercio_desde_subject_fallback(self) -> None:
        """Test de _extract_comercio usando subject como fallback."""
        html = "<html><body></body></html>"
        soup = BeautifulSoup(html, "lxml")
        subject = "Notificación de transacción WEB CHECKOUT JPS 09-11-2025 - 10:18"
        comercio = BACParser()._extract_comercio(soup, subject)
        assert comercio == "WEB CHECKOUT JPS"


class TestBACParserIntegracion:
    """Tests de integración que simulan casos reales."""

    def test_flujo_completo_compra_normal(self) -> None:
        """Test de flujo completo con correo real de compra."""
        email_data = {
            "id": "real-email-1",
            "subject": "Notificación de transacción STARBUCKS SAN JOSE 10-11-2025 - 08:30",
            "from": {"emailAddress": {"address": "notificaciones@baccredomatic.com"}},
            "receivedDateTime": "2025-11-10T08:30:00Z",
            "body": {
                "content": """
                <html>
                <body>
                    <p>Hola SEBASTIAN ERNESTO CRUZ GUZMAN</p>
                    <p>A continuación le detallamos la transacción realizada:</p>
                    <table>
                        <tr><td>Comercio:</td><td>STARBUCKS SAN JOSE</td></tr>
                        <tr><td>Ciudad y país:</td><td>SAN JOSE, Costa Rica</td></tr>
                        <tr><td>Fecha:</td><td>Nov 10, 2025, 08:30</td></tr>
                        <tr><td>VISA ***********1234</td><td></td></tr>
                        <tr><td>Autorización:</td><td>123456</td></tr>
                        <tr><td>Tipo de Transacción:</td><td>COMPRA</td></tr>
                        <tr><td>Monto:</td><td>CRC 4,500.00</td></tr>
                    </table>
                    <p>Gracias por usar su tarjeta BAC</p>
                </body>
                </html>
                """
            },
        }

        result = BACParser().parse(email_data)

        # Validar todos los campos
        assert result is not None
        assert result["email_id"] == "real-email-1"
        assert result["banco"] == "bac"
        assert result["comercio"] == "STARBUCKS SAN JOSE"
        assert result["monto_original"] == Decimal("4500.00")
        assert result["moneda_original"] == "CRC"
        assert result["tipo_transaccion"] == "compra"
        assert result["ciudad"] == "SAN JOSE"
        assert result["pais"] == "Costa Rica"

        # Validar fecha
        fecha = result["fecha_transaccion"]
        assert fecha.year == 2025
        assert fecha.month == 11
        assert fecha.day == 10
        assert fecha.hour == 8
        assert fecha.minute == 30

    def test_flujo_completo_compra_internacional_usd(self) -> None:
        """Test de flujo completo con compra internacional en USD."""
        email_data = {
            "id": "real-email-2",
            "subject": "Notificación de transacción STEAM GAMES 10-11-2025 - 14:00",
            "receivedDateTime": "2025-11-10T14:00:00Z",
            "body": {
                "content": """
                <html>
                <body>
                    <table>
                        <tr><td>Comercio:</td><td>STEAM GAMES</td></tr>
                        <tr><td>Ciudad y país:</td><td>BELLEVUE, United States</td></tr>
                        <tr><td>Fecha:</td><td>Nov 10, 2025, 14:00</td></tr>
                        <tr><td>Tipo de Transacción:</td><td>COMPRA</td></tr>
                        <tr><td>Monto:</td><td>USD 59.99</td></tr>
                    </table>
                </body>
                </html>
                """
            },
        }

        result = BACParser().parse(email_data)

        assert result is not None
        assert result["comercio"] == "STEAM GAMES"
        assert result["monto_original"] == Decimal("59.99")
        assert result["moneda_original"] == "USD"
        assert result["ciudad"] == "BELLEVUE"
        assert result["pais"] == "United States"
