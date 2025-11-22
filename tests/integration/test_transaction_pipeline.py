"""
Tests de integracion para el pipeline de transacciones.

Prueba el flujo de parseo: Email -> Parser -> Datos estructurados
"""

from decimal import Decimal

from finanzas_tracker.parsers import BACParser, PopularParser


class TestBACParserIntegration:
    """Tests de integracion para BACParser."""

    def test_parse_email_to_transaction_data(self) -> None:
        """Test del flujo completo: email BAC -> datos de transaccion."""
        email_data = {
            "id": "integration-test-001",
            "subject": "Notificacion de transaccion STARBUCKS COSTA RICA 15-11-2025 - 14:30",
            "receivedDateTime": "2025-11-15T14:30:00Z",
            "body": {
                "content": """
                <html><body>
                    <table>
                        <tr><td>Comercio:</td><td>STARBUCKS COSTA RICA</td></tr>
                        <tr><td>Ciudad y pais:</td><td>SAN JOSE, Costa Rica</td></tr>
                        <tr><td>Fecha:</td><td>Nov 15, 2025, 14:30</td></tr>
                        <tr><td>Tarjeta:</td><td>VISA ***********1234</td></tr>
                        <tr><td>Tipo de Transaccion:</td><td>COMPRA</td></tr>
                        <tr><td>Monto:</td><td>CRC 4,500.00</td></tr>
                    </table>
                </body></html>
                """
            },
        }

        parser = BACParser()
        result = parser.parse(email_data)

        assert result is not None
        assert result["email_id"] == "integration-test-001"
        assert result["banco"] == "bac"
        assert result["comercio"] == "STARBUCKS COSTA RICA"
        assert result["monto_original"] == Decimal("4500.00")
        assert result["moneda_original"] == "CRC"
        assert result["tipo_transaccion"] == "compra"
        assert result["ciudad"] == "SAN JOSE"
        assert result["pais"] == "Costa Rica"

    def test_parse_usd_transaction(self) -> None:
        """Test parsing transaccion en USD."""
        email_data = {
            "id": "integration-test-002",
            "subject": "Notificacion de transaccion AMAZON.COM 15-11-2025 - 09:00",
            "receivedDateTime": "2025-11-15T09:00:00Z",
            "body": {
                "content": """
                <html><body>
                    <table>
                        <tr><td>Comercio:</td><td>AMAZON.COM</td></tr>
                        <tr><td>Ciudad y pais:</td><td>SEATTLE, United States</td></tr>
                        <tr><td>Fecha:</td><td>Nov 15, 2025, 09:00</td></tr>
                        <tr><td>Tipo de Transaccion:</td><td>COMPRA</td></tr>
                        <tr><td>Monto:</td><td>USD 29.99</td></tr>
                    </table>
                </body></html>
                """
            },
        }

        parser = BACParser()
        result = parser.parse(email_data)

        assert result is not None
        assert result["monto_original"] == Decimal("29.99")
        assert result["moneda_original"] == "USD"
        assert result["comercio"] == "AMAZON.COM"

    def test_parse_retiro_sin_tarjeta(self) -> None:
        """Test parsing retiro sin tarjeta."""
        email_data = {
            "id": "integration-test-003",
            "subject": "Notificacion de retiro sin tarjeta",
            "receivedDateTime": "2025-11-15T12:00:00Z",
            "body": {
                "content": """
                <html><body>
                    <p>Se realizo un retiro sin tarjeta</p>
                    <p>Monto: 50,000.00 CRC</p>
                    <p>Fecha: 15/11/2025 12:00:00</p>
                    <p>Lugar donde se retiro el dinero: CAR-AUTOM TRES RIOS</p>
                </body></html>
                """
            },
        }

        parser = BACParser()
        result = parser.parse(email_data)

        assert result is not None
        assert result["tipo_transaccion"] == "retiro"
        assert result["monto_original"] == Decimal("50000.00")
        assert "RETIRO SIN TARJETA" in result["comercio"]

    def test_parse_multiple_emails_batch(self) -> None:
        """Test procesando multiples emails en batch."""
        emails = [
            {
                "id": f"batch-{i}",
                "subject": f"Notificacion {i}",
                "receivedDateTime": "2025-11-15T10:00:00Z",
                "body": {
                    "content": f"""
                    <html><body>
                        <table>
                            <tr><td>Comercio:</td><td>STORE {i}</td></tr>
                            <tr><td>Monto:</td><td>CRC {i * 1000}.00</td></tr>
                            <tr><td>Tipo de Transaccion:</td><td>COMPRA</td></tr>
                        </table>
                    </body></html>
                    """
                },
            }
            for i in range(1, 6)
        ]

        parser = BACParser()
        results = [parser.parse(email) for email in emails]

        # Todos deberían parsearse exitosamente
        assert all(r is not None for r in results)
        assert len(results) == 5

        # Verificar montos correctos
        for i, result in enumerate(results, 1):
            assert result["comercio"] == f"STORE {i}"
            assert result["monto_original"] == Decimal(f"{i * 1000}.00")


class TestPopularParserIntegration:
    """Tests de integracion para PopularParser."""

    def test_parse_compra_popular(self) -> None:
        """Test parsing compra de Banco Popular."""
        email_data = {
            "id": "integration-test-010",
            "subject": "Notificacion de compra en AUTOMERCADO",
            "receivedDateTime": "2025-11-15T16:00:00Z",
            "body": {
                "content": """
                <html><body>
                    <p>Comercio: AUTOMERCADO CURRIDABAT</p>
                    <p>Monto: CRC 35,000.00</p>
                    <p>Fecha: 15/11/2025</p>
                    <p>Hora: 16:00</p>
                    <p>Ciudad: San Jose, Costa Rica</p>
                </body></html>
                """
            },
        }

        parser = PopularParser()
        result = parser.parse(email_data)

        assert result is not None
        assert result["banco"] == "popular"
        assert result["monto_original"] == Decimal("35000.00")

    def test_parse_transferencia_sinpe(self) -> None:
        """Test parsing transferencia SINPE."""
        email_data = {
            "id": "integration-test-011",
            "subject": "Transferencia SINPE realizada",
            "receivedDateTime": "2025-11-15T17:00:00Z",
            "body": {
                "content": """
                <html><body>
                    <p>Transferencia SINPE</p>
                    <p>Monto: CRC 100,000.00</p>
                    <p>Fecha: 15/11/2025</p>
                </body></html>
                """
            },
        }

        parser = PopularParser()
        result = parser.parse(email_data)

        assert result is not None
        assert result["tipo_transaccion"] == "transferencia"


class TestParserEdgeCases:
    """Tests de casos edge para ambos parsers."""

    def test_bac_empty_html_returns_none(self) -> None:
        """Test que HTML vacio retorna None."""
        email_data = {
            "id": "edge-001",
            "subject": "Test",
            "receivedDateTime": "2025-11-15T10:00:00Z",
            "body": {"content": "<html><body></body></html>"},
        }

        parser = BACParser()
        result = parser.parse(email_data)
        assert result is None

    def test_popular_malformed_monto_returns_none(self) -> None:
        """Test que monto malformado retorna None."""
        email_data = {
            "id": "edge-002",
            "subject": "Test",
            "receivedDateTime": "2025-11-15T10:00:00Z",
            "body": {
                "content": """
                <html><body>
                    <p>Comercio: TEST</p>
                    <p>Monto: INVALID</p>
                </body></html>
                """
            },
        }

        parser = PopularParser()
        result = parser.parse(email_data)
        assert result is None

    def test_bac_large_amount_parsing(self) -> None:
        """Test parsing de montos grandes."""
        email_data = {
            "id": "edge-003",
            "subject": "Notificacion grande",
            "receivedDateTime": "2025-11-15T10:00:00Z",
            "body": {
                "content": """
                <html><body>
                    <table>
                        <tr><td>Comercio:</td><td>CONCESIONARIO AUTOS</td></tr>
                        <tr><td>Monto:</td><td>CRC 15,000,000.00</td></tr>
                        <tr><td>Tipo de Transaccion:</td><td>COMPRA</td></tr>
                    </table>
                </body></html>
                """
            },
        }

        parser = BACParser()
        result = parser.parse(email_data)

        assert result is not None
        assert result["monto_original"] == Decimal("15000000.00")

    def test_parser_date_fallback_to_received(self) -> None:
        """Test que usa fecha del correo si no encuentra en HTML."""
        email_data = {
            "id": "edge-004",
            "subject": "Notificacion sin fecha",
            "receivedDateTime": "2025-11-15T14:30:00Z",
            "body": {
                "content": """
                <html><body>
                    <table>
                        <tr><td>Comercio:</td><td>TEST STORE</td></tr>
                        <tr><td>Monto:</td><td>CRC 5,000.00</td></tr>
                        <tr><td>Tipo de Transaccion:</td><td>COMPRA</td></tr>
                    </table>
                </body></html>
                """
            },
        }

        parser = BACParser()
        result = parser.parse(email_data)

        assert result is not None
        assert result["fecha_transaccion"].year == 2025
        assert result["fecha_transaccion"].month == 11
        assert result["fecha_transaccion"].day == 15
