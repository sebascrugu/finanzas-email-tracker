"""Tests para SubscriptionDetector.

Prueba la detección de suscripciones y pagos recurrentes.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from finanzas_tracker.services.subscription_detector import (
    DetectedSubscription,
    SubscriptionDetector,
    SubscriptionFrequency,
)


@pytest.fixture
def mock_db():
    """Mock de sesión de base de datos."""
    return MagicMock()


@pytest.fixture
def detector(mock_db):
    """Instancia de SubscriptionDetector con mock de DB."""
    return SubscriptionDetector(mock_db)


def create_mock_transaction(
    comercio: str,
    monto: Decimal,
    fecha: date,
    profile_id: str = "profile-123",
) -> MagicMock:
    """Crea una transacción mock."""
    tx = MagicMock()
    tx.id = str(uuid4())
    tx.profile_id = profile_id
    tx.comercio = comercio
    tx.monto_original = monto
    tx.fecha_transaccion = fecha
    tx.es_transferencia_interna = False
    tx.deleted_at = None
    return tx


class TestNormalizarComercio:
    """Tests para _normalizar_comercio()."""

    def test_normaliza_mayusculas(self, detector):
        """Convierte a mayúsculas."""
        result = detector._normalizar_comercio("Netflix")
        assert result == "NETFLIX"

    def test_remueve_numeros_largos(self, detector):
        """Remueve números de referencia largos."""
        result = detector._normalizar_comercio("SPOTIFY 123456789")
        assert "123456789" not in result

    def test_remueve_ultimos_digitos(self, detector):
        """Remueve ***1234."""
        result = detector._normalizar_comercio("AMAZON ***1234")
        assert "***1234" not in result
        assert "AMAZON" in result

    def test_remueve_ubicaciones(self, detector):
        """Remueve ubicaciones conocidas."""
        result = detector._normalizar_comercio("WALMART SAN JOSE CR")
        assert "SAN JOSE" not in result
        assert "WALMART" in result

    def test_limpia_espacios(self, detector):
        """Limpia espacios múltiples."""
        result = detector._normalizar_comercio("UBER   EATS")
        assert result == "UBER EATS"


class TestDeterminarFrecuencia:
    """Tests para _determinar_frecuencia()."""

    def test_detecta_semanal(self, detector):
        """Detecta frecuencia semanal."""
        result = detector._determinar_frecuencia(7)
        assert result == SubscriptionFrequency.WEEKLY

    def test_detecta_mensual(self, detector):
        """Detecta frecuencia mensual."""
        result = detector._determinar_frecuencia(30)
        assert result == SubscriptionFrequency.MONTHLY

    def test_detecta_anual(self, detector):
        """Detecta frecuencia anual."""
        result = detector._determinar_frecuencia(365)
        assert result == SubscriptionFrequency.ANNUAL

    def test_no_detecta_irregular(self, detector):
        """No detecta frecuencia irregular."""
        result = detector._determinar_frecuencia(45)  # Entre mensual y bimestral
        assert result is None


class TestCalcularConfianza:
    """Tests para _calcular_confianza()."""

    def test_alta_confianza_muchos_cobros(self, detector):
        """Alta confianza con muchos cobros y monto consistente."""
        score = detector._calcular_confianza(
            cantidad_cobros=6,
            variacion_monto=2.0,
            dias_promedio=30,
            frecuencia=SubscriptionFrequency.MONTHLY,
            es_conocida=False,
        )
        assert score >= 70

    def test_bonus_suscripcion_conocida(self, detector):
        """Bonus por suscripción conocida."""
        score_conocida = detector._calcular_confianza(
            cantidad_cobros=2,
            variacion_monto=5.0,
            dias_promedio=30,
            frecuencia=SubscriptionFrequency.MONTHLY,
            es_conocida=True,
        )
        score_desconocida = detector._calcular_confianza(
            cantidad_cobros=2,
            variacion_monto=5.0,
            dias_promedio=30,
            frecuencia=SubscriptionFrequency.MONTHLY,
            es_conocida=False,
        )
        assert score_conocida > score_desconocida

    def test_penalizacion_variacion_alta(self, detector):
        """Penalización por variación de monto alta."""
        score_estable = detector._calcular_confianza(
            cantidad_cobros=4,
            variacion_monto=1.0,
            dias_promedio=30,
            frecuencia=SubscriptionFrequency.MONTHLY,
            es_conocida=False,
        )
        score_variable = detector._calcular_confianza(
            cantidad_cobros=4,
            variacion_monto=25.0,
            dias_promedio=30,
            frecuencia=SubscriptionFrequency.MONTHLY,
            es_conocida=False,
        )
        assert score_estable > score_variable


class TestAnalizarGrupo:
    """Tests para _analizar_grupo()."""

    def test_detecta_suscripcion_mensual(self, detector):
        """Detecta suscripción mensual."""
        hoy = date.today()
        txs = [
            create_mock_transaction("NETFLIX", Decimal("10.99"), hoy - timedelta(days=60)),
            create_mock_transaction("NETFLIX", Decimal("10.99"), hoy - timedelta(days=30)),
            create_mock_transaction("NETFLIX", Decimal("10.99"), hoy),
        ]

        result = detector._analizar_grupo("NETFLIX", txs)

        assert result is not None
        assert result.frecuencia == SubscriptionFrequency.MONTHLY
        assert result.cantidad_cobros == 3
        assert result.monto_promedio == Decimal("10.99")

    def test_detecta_con_variacion_monto_pequena(self, detector):
        """Detecta con pequeña variación de monto."""
        hoy = date.today()
        txs = [
            create_mock_transaction("SPOTIFY", Decimal("5.99"), hoy - timedelta(days=60)),
            create_mock_transaction("SPOTIFY", Decimal("6.49"), hoy - timedelta(days=30)),
            create_mock_transaction("SPOTIFY", Decimal("6.49"), hoy),
        ]

        result = detector._analizar_grupo("SPOTIFY", txs)

        assert result is not None
        assert result.variacion_monto < 10

    def test_no_detecta_con_pocas_transacciones(self, detector):
        """No detecta con menos de 2 transacciones."""
        txs = [create_mock_transaction("RANDOM", Decimal("50"), date.today())]

        result = detector._analizar_grupo("RANDOM", txs)

        assert result is None

    def test_detecta_conocida_con_una_transaccion(self, detector):
        """Detecta suscripción conocida con solo 1 transacción."""
        txs = [create_mock_transaction("NETFLIX", Decimal("10.99"), date.today())]

        result = detector._analizar_grupo("NETFLIX", txs, es_conocida=True)

        assert result is not None


class TestDetectarSuscripciones:
    """Tests para detectar_suscripciones()."""

    def test_detecta_suscripciones_en_historial(self, detector, mock_db):
        """Detecta suscripciones en historial de transacciones."""
        hoy = date.today()

        # Netflix mensual
        tx_netflix = [
            create_mock_transaction("NETFLIX COM", Decimal("10.99"), hoy - timedelta(days=90)),
            create_mock_transaction("NETFLIX COM", Decimal("10.99"), hoy - timedelta(days=60)),
            create_mock_transaction("NETFLIX COM", Decimal("10.99"), hoy - timedelta(days=30)),
            create_mock_transaction("NETFLIX COM", Decimal("10.99"), hoy),
        ]

        # Spotify mensual
        tx_spotify = [
            create_mock_transaction("SPOTIFY AB", Decimal("5.99"), hoy - timedelta(days=65)),
            create_mock_transaction("SPOTIFY AB", Decimal("5.99"), hoy - timedelta(days=35)),
            create_mock_transaction("SPOTIFY AB", Decimal("5.99"), hoy - timedelta(days=5)),
        ]

        # Compra aleatoria (no suscripción)
        tx_random = [
            create_mock_transaction("WALMART", Decimal("150.00"), hoy - timedelta(days=45)),
        ]

        mock_db.execute.return_value.scalars.return_value.all.return_value = (
            tx_netflix + tx_spotify + tx_random
        )

        result = detector.detectar_suscripciones("profile-123")

        assert len(result) >= 2
        comercios = [s.comercio_normalizado for s in result]
        assert any("NETFLIX" in c for c in comercios)
        assert any("SPOTIFY" in c for c in comercios)

    def test_ordena_por_confianza(self, detector, mock_db):
        """Ordena resultados por confianza descendente."""
        hoy = date.today()

        # Suscripción con alta confianza (6 cobros)
        tx_alta = [
            create_mock_transaction("SERVICIO_A", Decimal("10"), hoy - timedelta(days=i * 30))
            for i in range(6)
        ]

        # Suscripción con baja confianza (2 cobros)
        tx_baja = [
            create_mock_transaction("SERVICIO_B", Decimal("20"), hoy - timedelta(days=30)),
            create_mock_transaction("SERVICIO_B", Decimal("20"), hoy),
        ]

        mock_db.execute.return_value.scalars.return_value.all.return_value = tx_alta + tx_baja

        result = detector.detectar_suscripciones("profile-123")

        if len(result) >= 2:
            assert result[0].confianza >= result[-1].confianza


class TestDetectarConocidas:
    """Tests para detectar_conocidas()."""

    def test_detecta_netflix(self, detector, mock_db):
        """Detecta Netflix por patrón."""
        txs = [
            create_mock_transaction("NETFLIX.COM", Decimal("15.99"), date.today()),
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = txs

        result = detector.detectar_conocidas("profile-123")

        assert len(result) == 1
        assert result[0].comercio_normalizado == "Netflix"

    def test_detecta_spotify(self, detector, mock_db):
        """Detecta Spotify por patrón."""
        txs = [
            create_mock_transaction("SPOTIFY AB SWEDEN", Decimal("5.99"), date.today()),
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = txs

        result = detector.detectar_conocidas("profile-123")

        assert len(result) == 1
        assert result[0].comercio_normalizado == "Spotify"

    def test_detecta_amazon_prime(self, detector, mock_db):
        """Detecta Amazon Prime por patrón."""
        txs = [
            create_mock_transaction("AMAZON PRIME VIDEO", Decimal("8.99"), date.today()),
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = txs

        result = detector.detectar_conocidas("profile-123")

        assert len(result) == 1
        assert result[0].comercio_normalizado == "Amazon Prime"


class TestGetProximoCobro:
    """Tests para get_proximo_cobro()."""

    def test_calcula_proximo_cobro_mensual(self, detector):
        """Calcula próximo cobro mensual."""
        sub = DetectedSubscription(
            comercio="Netflix",
            comercio_normalizado="NETFLIX",
            monto_promedio=Decimal("10.99"),
            monto_min=Decimal("10.99"),
            monto_max=Decimal("10.99"),
            frecuencia=SubscriptionFrequency.MONTHLY,
            dias_promedio_entre_cobros=30.0,
            ultimo_cobro=date(2025, 11, 15),
            primer_cobro=date(2025, 8, 15),
            cantidad_cobros=4,
            confianza=85,
        )

        proximo = detector.get_proximo_cobro(sub)

        assert proximo == date(2025, 12, 15)


class TestGetGastoMensualSuscripciones:
    """Tests para get_gasto_mensual_suscripciones()."""

    def test_suma_suscripciones_mensuales(self, detector):
        """Suma correctamente suscripciones mensuales."""
        subs = [
            DetectedSubscription(
                comercio="Netflix",
                comercio_normalizado="NETFLIX",
                monto_promedio=Decimal("10.99"),
                monto_min=Decimal("10.99"),
                monto_max=Decimal("10.99"),
                frecuencia=SubscriptionFrequency.MONTHLY,
                dias_promedio_entre_cobros=30.0,
                ultimo_cobro=date.today(),
                primer_cobro=date.today(),
                cantidad_cobros=1,
                confianza=80,
            ),
            DetectedSubscription(
                comercio="Spotify",
                comercio_normalizado="SPOTIFY",
                monto_promedio=Decimal("5.99"),
                monto_min=Decimal("5.99"),
                monto_max=Decimal("5.99"),
                frecuencia=SubscriptionFrequency.MONTHLY,
                dias_promedio_entre_cobros=30.0,
                ultimo_cobro=date.today(),
                primer_cobro=date.today(),
                cantidad_cobros=1,
                confianza=80,
            ),
        ]

        total = detector.get_gasto_mensual_suscripciones(subs)

        assert total == Decimal("16.98")

    def test_convierte_anual_a_mensual(self, detector):
        """Convierte suscripción anual a mensual."""
        subs = [
            DetectedSubscription(
                comercio="Dominio",
                comercio_normalizado="DOMINIO",
                monto_promedio=Decimal("120.00"),
                monto_min=Decimal("120.00"),
                monto_max=Decimal("120.00"),
                frecuencia=SubscriptionFrequency.ANNUAL,
                dias_promedio_entre_cobros=365.0,
                ultimo_cobro=date.today(),
                primer_cobro=date.today(),
                cantidad_cobros=1,
                confianza=70,
            ),
        ]

        total = detector.get_gasto_mensual_suscripciones(subs)

        assert total == Decimal("10.00")  # 120/12

    def test_convierte_semanal_a_mensual(self, detector):
        """Convierte suscripción semanal a mensual."""
        subs = [
            DetectedSubscription(
                comercio="Servicio Semanal",
                comercio_normalizado="SERVICIO",
                monto_promedio=Decimal("10.00"),
                monto_min=Decimal("10.00"),
                monto_max=Decimal("10.00"),
                frecuencia=SubscriptionFrequency.WEEKLY,
                dias_promedio_entre_cobros=7.0,
                ultimo_cobro=date.today(),
                primer_cobro=date.today(),
                cantidad_cobros=4,
                confianza=75,
            ),
        ]

        total = detector.get_gasto_mensual_suscripciones(subs)

        # 10 * 4.33 = 43.30
        assert total == Decimal("43.30")


class TestDetectedSubscriptionToDict:
    """Tests para DetectedSubscription.to_dict()."""

    def test_convierte_a_dict(self):
        """Convierte suscripción a diccionario."""
        sub = DetectedSubscription(
            comercio="Netflix",
            comercio_normalizado="NETFLIX",
            monto_promedio=Decimal("10.99"),
            monto_min=Decimal("10.99"),
            monto_max=Decimal("10.99"),
            frecuencia=SubscriptionFrequency.MONTHLY,
            dias_promedio_entre_cobros=30.0,
            ultimo_cobro=date(2025, 12, 1),
            primer_cobro=date(2025, 9, 1),
            cantidad_cobros=4,
            confianza=85,
            variacion_monto=1.5,
        )

        result = sub.to_dict()

        assert result["comercio"] == "Netflix"
        assert result["monto_promedio"] == 10.99
        assert result["frecuencia"] == "mensual"
        assert result["confianza"] == 85
        assert result["ultimo_cobro"] == "2025-12-01"
