"""
Tests para el parser de transferencias de BAC.

Estos tests usan formatos reales de correos de transferencias de BAC
incluyendo SINPE Móvil y transferencias locales regulares.
"""

from datetime import datetime

import pytest

from finanzas_tracker.parsers.bac_parser import BACParser


class TestBACParserTransferencias:
    """Tests para parsing de correos de transferencia de BAC."""

    @pytest.fixture
    def parser(self) -> BACParser:
        """Fixture del parser BAC."""
        return BACParser()

    @pytest.fixture
    def transferencia_sinpe_email(self) -> dict:
        """Email completo de una transferencia SINPE Móvil."""
        return {
            "id": "test-sinpe-001",
            "subject": "Notificación de Transferencia",
            "receivedDateTime": "2025-11-29T14:06:22Z",
            "body": {
                "content": """
                <html>
                <body>
                <p>Notificación de Transferencia Local</p>
                <p>Estimado(a) LUIS_MENA_MATA :</p>
                <p>BAC Credomatic le comunica que SEBASTIAN ERNESTO CRUZ GUZMAN
                realizó una transferencia electrónica a su cuenta N° *****9659.</p>
                <p>La transferencia se realizó el día 29-11-2025 a las 08:06:22 horas;
                por un monto de 2.500,00 CRC, por concepto de: comprale_un_regalito_a_juli</p>
                <p>El número de referencia es 2025112910284000060544973</p>
                <p>Muchas Gracias.</p>
                </body>
                </html>
                """,
            },
        }

    @pytest.fixture
    def transferencia_regular_email(self) -> dict:
        """Email de una transferencia regular (sin concepto)."""
        return {
            "id": "test-transfer-002",
            "subject": "Notificación de Transferencia",
            "receivedDateTime": "2025-11-30T16:07:00Z",
            "body": {
                "content": """
                <html>
                <body>
                <p>Notificación de Transferencia Local</p>
                <p>Estimado(a) DOUGLAS ANDRES OTAROLA CASCANTE :</p>
                <p>BAC Credomatic le comunica que SEBASTIAN ERNESTO CRUZ GUZMAN
                realizó una transferencia electrónica a su cuenta N° *****7338.</p>
                <p>La transferencia se realizó el día 30-11-2025 a las 10:07:21 horas;
                por un monto de 5.000,00 CRC, por concepto de: Sin Descripcion</p>
                <p>El número de referencia es 2025113010283000278879918</p>
                <p>Muchas Gracias.</p>
                </body>
                </html>
                """,
            },
        }

    @pytest.fixture
    def transferencia_monto_grande_email(self) -> dict:
        """Email de una transferencia con monto grande (700,000 CRC)."""
        return {
            "id": "test-transfer-003",
            "subject": "Notificación de Transferencia",
            "receivedDateTime": "2025-11-28T16:56:00Z",
            "body": {
                "content": """
                <html>
                <body>
                <p>Notificación de Transferencia Local</p>
                <p>Estimado(a) speedy logistics sociedad de :</p>
                <p>BAC Credomatic le comunica que SEBASTIAN ERNESTO CRUZ GUZMAN
                realizó una transferencia electrónica a su cuenta N° *****1339.</p>
                <p>La transferencia se realizó el día 28-11-2025 a las 10:56:38 horas;
                por un monto de 700.000,00 CRC, por concepto de: sebas_cruz_____</p>
                <p>El número de referencia es 2025112810284000058544755</p>
                <p>Muchas Gracias.</p>
                </body>
                </html>
                """,
            },
        }

    def test_parse_transferencia_sinpe(
        self,
        parser: BACParser,
        transferencia_sinpe_email: dict,
    ) -> None:
        """Test parsing de transferencia SINPE con concepto."""
        result = parser.parse(transferencia_sinpe_email)

        assert result is not None
        assert result["banco"] == "bac"
        assert result["tipo_transaccion"] == "transferencia"
        assert result["monto_original"] == 2500.0
        assert result["moneda_original"] == "CRC"
        assert "LUIS MENA MATA" in result["comercio"]
        assert "comprale un regalito a juli" in result["comercio"]
        assert result["email_id"] == "test-sinpe-001"

    def test_parse_transferencia_extrae_fecha_correcta(
        self,
        parser: BACParser,
        transferencia_sinpe_email: dict,
    ) -> None:
        """Test que la fecha se extrae correctamente del contenido."""
        result = parser.parse(transferencia_sinpe_email)

        assert result is not None
        assert result["fecha_transaccion"].year == 2025
        assert result["fecha_transaccion"].month == 11
        assert result["fecha_transaccion"].day == 29
        assert result["fecha_transaccion"].hour == 8
        assert result["fecha_transaccion"].minute == 6

    def test_parse_transferencia_sin_concepto(
        self,
        parser: BACParser,
        transferencia_regular_email: dict,
    ) -> None:
        """Test transferencia con 'Sin Descripcion' como concepto."""
        result = parser.parse(transferencia_regular_email)

        assert result is not None
        assert result["monto_original"] == 5000.0
        assert "DOUGLAS ANDRES OTAROLA CASCANTE" in result["comercio"]
        # No debe incluir "Sin Descripcion" en el comercio
        assert "Sin Descripcion" not in result["comercio"]
        assert "TRANSFERENCIA A" in result["comercio"]

    def test_parse_transferencia_monto_grande(
        self,
        parser: BACParser,
        transferencia_monto_grande_email: dict,
    ) -> None:
        """Test transferencia con monto grande (700,000 CRC)."""
        result = parser.parse(transferencia_monto_grande_email)

        assert result is not None
        assert result["monto_original"] == 700000.0
        assert result["moneda_original"] == "CRC"

    def test_parse_transferencia_extrae_metadata(
        self,
        parser: BACParser,
        transferencia_sinpe_email: dict,
    ) -> None:
        """Test que se extraen los metadatos de la transferencia."""
        result = parser.parse(transferencia_sinpe_email)

        assert result is not None
        assert "metadata" in result
        assert result["metadata"]["destinatario"] == "LUIS MENA MATA"
        assert result["metadata"]["concepto"] == "comprale un regalito a juli"
        assert result["metadata"]["referencia"] == "2025112910284000060544973"

    def test_parse_transferencia_pais_costa_rica(
        self,
        parser: BACParser,
        transferencia_sinpe_email: dict,
    ) -> None:
        """Test que las transferencias se marcan como Costa Rica."""
        result = parser.parse(transferencia_sinpe_email)

        assert result is not None
        assert result["pais"] == "Costa Rica"


class TestBACParserTransferenciaEdgeCases:
    """Tests de edge cases para transferencias."""

    @pytest.fixture
    def parser(self) -> BACParser:
        """Fixture del parser BAC."""
        return BACParser()

    def test_transferencia_con_underscores_en_nombre(self, parser: BACParser) -> None:
        """Test que los underscores en nombres se convierten a espacios."""
        email_data = {
            "id": "test-edge-001",
            "subject": "Notificación de Transferencia",
            "receivedDateTime": "2025-12-01T10:00:00Z",
            "body": {
                "content": """
                <p>Estimado(a) JUAN_PEREZ_GARCIA :</p>
                <p>BAC Credomatic le comunica que TEST USER
                realizó una transferencia electrónica a su cuenta N° *****1234.</p>
                <p>La transferencia se realizó el día 01-12-2025 a las 10:00:00 horas;
                por un monto de 1.000,00 CRC, por concepto de: test_concepto_largo</p>
                <p>El número de referencia es 123456789</p>
                """,
            },
        }

        result = parser.parse(email_data)

        assert result is not None
        assert "JUAN PEREZ GARCIA" in result["comercio"]
        assert "test concepto largo" in result["comercio"]
        assert "_" not in result["comercio"]

    def test_transferencia_sin_numero_referencia(self, parser: BACParser) -> None:
        """Test transferencia sin número de referencia visible."""
        email_data = {
            "id": "test-edge-002",
            "subject": "Notificación de Transferencia",
            "receivedDateTime": "2025-12-01T10:00:00Z",
            "body": {
                "content": """
                <p>Estimado(a) DESTINATARIO TEST :</p>
                <p>BAC Credomatic le comunica que REMITENTE TEST
                realizó una transferencia electrónica a su cuenta N° *****1234.</p>
                <p>La transferencia se realizó el día 01-12-2025 a las 10:00:00 horas;
                por un monto de 500,00 CRC, por concepto de: prueba</p>
                """,
            },
        }

        result = parser.parse(email_data)

        assert result is not None
        assert result["metadata"]["referencia"] == ""

    def test_transferencia_monto_pequeno(self, parser: BACParser) -> None:
        """Test transferencia con monto pequeño (100 CRC)."""
        email_data = {
            "id": "test-edge-003",
            "subject": "Notificación de Transferencia",
            "receivedDateTime": "2025-12-01T10:00:00Z",
            "body": {
                "content": """
                <p>Estimado(a) DESTINATARIO :</p>
                <p>BAC Credomatic le comunica que REMITENTE
                realizó una transferencia electrónica a su cuenta N° *****1234.</p>
                <p>La transferencia se realizó el día 01-12-2025 a las 10:00:00 horas;
                por un monto de 100,00 CRC, por concepto de: minimo</p>
                <p>El número de referencia es 123</p>
                """,
            },
        }

        result = parser.parse(email_data)

        assert result is not None
        assert result["monto_original"] == 100.0

    def test_no_detecta_transferencia_sin_keyword_en_subject(
        self, parser: BACParser
    ) -> None:
        """Test que no se detecta transferencia si el subject no lo indica."""
        email_data = {
            "id": "test-edge-004",
            "subject": "Notificación de transacción",  # Sin "transferencia"
            "receivedDateTime": "2025-12-01T10:00:00Z",
            "body": {
                "content": """
                <p>BAC Credomatic le comunica que realizó una transferencia...</p>
                <p>por un monto de 1.000,00 CRC</p>
                """,
            },
        }

        # Debe intentar parsear como compra normal, no como transferencia
        result = parser.parse(email_data)
        # Este caso probablemente retorne None o un resultado diferente
        # porque no tiene el formato de compra esperado
        # El punto es que no se procese como transferencia
        if result is not None:
            assert result.get("tipo_transaccion") != "transferencia"


class TestBACParserTransferenciaVsCompra:
    """Tests para verificar que se distingue correctamente entre transferencias y compras."""

    @pytest.fixture
    def parser(self) -> BACParser:
        """Fixture del parser BAC."""
        return BACParser()

    def test_compra_no_se_detecta_como_transferencia(self, parser: BACParser) -> None:
        """Test que una compra normal no se procesa como transferencia."""
        email_data = {
            "id": "test-compra-001",
            "subject": "Notificación de transacción AMAZON 30-11-2025 - 10:00",
            "receivedDateTime": "2025-11-30T10:00:00Z",
            "body": {
                "content": """
                <table>
                    <tr><td>Comercio:</td><td>AMAZON</td></tr>
                    <tr><td>Ciudad y país:</td><td>SAN JOSE, Costa Rica</td></tr>
                    <tr><td>Fecha:</td><td>Nov 30, 2025, 10:00</td></tr>
                    <tr><td>Tipo de Transacción:</td><td>COMPRA</td></tr>
                    <tr><td>Monto:</td><td>CRC 15,000.00</td></tr>
                </table>
                """,
            },
        }

        result = parser.parse(email_data)

        assert result is not None
        # No debe ser transferencia
        assert result.get("tipo_transaccion") != "transferencia"

    def test_subject_transferencia_activa_parser_correcto(
        self, parser: BACParser
    ) -> None:
        """Test que el subject con 'Transferencia' activa el parser correcto."""
        # Con subject de transferencia
        email_transfer = {
            "id": "test-001",
            "subject": "Notificación de Transferencia",
            "receivedDateTime": "2025-12-01T10:00:00Z",
            "body": {
                "content": """
                <p>Estimado(a) DESTINATARIO :</p>
                <p>BAC Credomatic le comunica que REMITENTE
                realizó una transferencia electrónica a su cuenta N° *****1234.</p>
                <p>La transferencia se realizó el día 01-12-2025 a las 10:00:00 horas;
                por un monto de 5.000,00 CRC, por concepto de: test</p>
                <p>El número de referencia es 123456</p>
                """,
            },
        }
        result = parser.parse(email_transfer)
        assert result is not None
        assert result["tipo_transaccion"] == "transferencia"

        # Con subject de transacción (compra) - mismo HTML pero subject diferente
        email_compra = {
            "id": "test-002",
            "subject": "Notificación de transacción",  # Sin "transferencia"
            "receivedDateTime": "2025-12-01T10:00:00Z",
            "body": {
                "content": """
                <p>Estimado(a) DESTINATARIO :</p>
                <p>BAC Credomatic le comunica que REMITENTE
                realizó una transferencia electrónica a su cuenta N° *****1234.</p>
                <p>La transferencia se realizó el día 01-12-2025 a las 10:00:00 horas;
                por un monto de 5.000,00 CRC, por concepto de: test</p>
                <p>El número de referencia es 123456</p>
                """,
            },
        }
        result_compra = parser.parse(email_compra)
        # Este no debería procesarse como transferencia
        if result_compra is not None:
            assert result_compra.get("tipo_transaccion") != "transferencia"


class TestBACParserSINPERecibido:
    """Tests para parsing de SINPE recibido (ingresos)."""

    @pytest.fixture
    def parser(self) -> BACParser:
        """Fixture del parser BAC."""
        return BACParser()

    @pytest.fixture
    def sinpe_recibido_email(self) -> dict:
        """Email real de SINPE recibido."""
        return {
            "id": "test-sinpe-recibido-001",
            "subject": "Notificación Transferencia SINPE Tiempo Real BAC SAN JOSE S.A2025111475422010033613481",
            "receivedDateTime": "2025-11-14T18:30:00Z",
            "body": {
                "content": """
                <html>
                <body>
                <p>Notificación de Transferencia SINPE</p>
                <p>Hola Estimado Cliente SEBASTIAN ERNESTO CRUZ GU :</p>
                <p>BAC Credomatic le comunica que recibió una transferencia SINPE 
                con el número de referencia 2025111475422010033613481 
                a su cuenta IBAN CR8401XXXXXXXXXXXX6111 
                por un monto de 4,000.00 Colones 
                por concepto JPS PP WEB: 01-1803-0569 :LN S:4875, 
                la cual se aplicó correctamente el día 14/11/2025 a las 12:29 PM.</p>
                <p>Muchas gracias.</p>
                </body>
                </html>
                """,
            },
        }

    def test_parse_sinpe_recibido_basico(
        self,
        parser: BACParser,
        sinpe_recibido_email: dict,
    ) -> None:
        """Test parsing básico de SINPE recibido."""
        result = parser.parse(sinpe_recibido_email)

        assert result is not None
        assert result["banco"] == "bac"
        assert result["tipo_transaccion"] == "ingreso"
        assert result["monto_original"] == 4000.0
        assert result["moneda_original"] == "CRC"

    def test_parse_sinpe_recibido_extrae_concepto(
        self,
        parser: BACParser,
        sinpe_recibido_email: dict,
    ) -> None:
        """Test que el concepto se extrae correctamente."""
        result = parser.parse(sinpe_recibido_email)

        assert result is not None
        assert "JPS PP WEB" in result["comercio"]
        assert result["metadata"]["concepto"] == "JPS PP WEB: 01-1803-0569 :LN S:4875"

    def test_parse_sinpe_recibido_extrae_referencia(
        self,
        parser: BACParser,
        sinpe_recibido_email: dict,
    ) -> None:
        """Test que la referencia se extrae correctamente."""
        result = parser.parse(sinpe_recibido_email)

        assert result is not None
        assert result["metadata"]["referencia"] == "2025111475422010033613481"

    def test_parse_sinpe_recibido_extrae_fecha(
        self,
        parser: BACParser,
        sinpe_recibido_email: dict,
    ) -> None:
        """Test que la fecha se extrae correctamente."""
        result = parser.parse(sinpe_recibido_email)

        assert result is not None
        assert result["fecha_transaccion"].year == 2025
        assert result["fecha_transaccion"].month == 11
        assert result["fecha_transaccion"].day == 14
        assert result["fecha_transaccion"].hour == 12
        assert result["fecha_transaccion"].minute == 29

    def test_parse_sinpe_recibido_es_ingreso(
        self,
        parser: BACParser,
        sinpe_recibido_email: dict,
    ) -> None:
        """Test que SINPE recibido se marca como ingreso, no como gasto."""
        result = parser.parse(sinpe_recibido_email)

        assert result is not None
        # CRÍTICO: Este debe ser un ingreso, no un gasto
        assert result["tipo_transaccion"] == "ingreso"
        assert result["metadata"]["tipo"] == "sinpe_recibido"


class TestBACParserAvisosNoTransacciones:
    """Tests para verificar que los avisos de configuración no se procesan como transacciones."""

    @pytest.fixture
    def parser(self) -> BACParser:
        """Fixture del parser BAC."""
        return BACParser()

    def test_aviso_activacion_no_es_transaccion(self, parser: BACParser) -> None:
        """Test que avisos de activación no se procesan como transacciones."""
        email_data = {
            "id": "test-aviso-001",
            "subject": "Aviso BAC Credomatic - Activación de Transferencias Internacionales",
            "receivedDateTime": "2025-11-15T16:46:00Z",
            "body": {
                "content": """
                <p>Estimado cliente:</p>
                <p>Le informamos que se ha activado el servicio de transferencias internacionales.</p>
                """,
            },
        }

        result = parser.parse(email_data)

        # Este correo NO debe procesarse como transacción
        assert result is None

    def test_aviso_afiliacion_no_es_transaccion(self, parser: BACParser) -> None:
        """Test que avisos de afiliación no se procesan como transacciones."""
        email_data = {
            "id": "test-aviso-002",
            "subject": "Notificación de afiliación SINPE Móvil",
            "receivedDateTime": "2025-11-04T12:38:00Z",
            "body": {
                "content": """
                <p>Estimado cliente:</p>
                <p>BAC Credomatic le comunica la afiliación del servicio SINPE Móvil.</p>
                """,
            },
        }

        result = parser.parse(email_data)

        # Este correo NO debe procesarse como transacción
        assert result is None
