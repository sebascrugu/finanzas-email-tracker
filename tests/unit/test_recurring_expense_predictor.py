"""Tests para RecurringExpensePredictor.

Prueba la predicción de gastos recurrentes y alertas de vencimiento.
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from finanzas_tracker.services.recurring_expense_predictor import (
    AlertLevel,
    ExpenseType,
    PredictedExpense,
    RecurringExpensePredictor,
    generar_reporte_gastos_proximos,
)
from finanzas_tracker.services.subscription_detector import (
    DetectedSubscription,
    SubscriptionFrequency,
)


@pytest.fixture
def mock_db():
    """Mock de sesión de base de datos."""
    return MagicMock()


@pytest.fixture
def predictor(mock_db):
    """Instancia de RecurringExpensePredictor con mock de DB."""
    return RecurringExpensePredictor(mock_db)


def create_mock_subscription(
    comercio: str,
    monto: Decimal,
    ultimo_cobro: date,
    frecuencia: SubscriptionFrequency = SubscriptionFrequency.MONTHLY,
    confianza: int = 80,
) -> DetectedSubscription:
    """Crea una suscripción mock."""
    dias = {
        SubscriptionFrequency.WEEKLY: 7,
        SubscriptionFrequency.BIWEEKLY: 14,
        SubscriptionFrequency.MONTHLY: 30,
        SubscriptionFrequency.ANNUAL: 365,
    }.get(frecuencia, 30)
    
    return DetectedSubscription(
        comercio=comercio,
        comercio_normalizado=comercio.upper(),
        monto_promedio=monto,
        monto_min=monto,
        monto_max=monto,
        frecuencia=frecuencia,
        dias_promedio_entre_cobros=float(dias),
        ultimo_cobro=ultimo_cobro,
        primer_cobro=ultimo_cobro - timedelta(days=dias * 3),
        cantidad_cobros=4,
        confianza=confianza,
    )


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


class TestClasificarTipo:
    """Tests para _clasificar_tipo()."""

    def test_detecta_utility_ice(self, predictor):
        """Detecta ICE como utility."""
        result = predictor._clasificar_tipo("ICE TELECOMUNICACIONES")
        assert result == ExpenseType.UTILITY

    def test_detecta_utility_cnfl(self, predictor):
        """Detecta CNFL como utility."""
        result = predictor._clasificar_tipo("CNFL PAGO")
        assert result == ExpenseType.UTILITY

    def test_detecta_loan_cuota(self, predictor):
        """Detecta cuota como préstamo."""
        result = predictor._clasificar_tipo("CUOTA PRESTAMO BAC")
        assert result == ExpenseType.LOAN

    def test_detecta_insurance_ins(self, predictor):
        """Detecta INS como seguro."""
        result = predictor._clasificar_tipo("INS POLIZA AUTO")
        assert result == ExpenseType.INSURANCE

    def test_detecta_rent(self, predictor):
        """Detecta alquiler."""
        result = predictor._clasificar_tipo("ALQUILER MENSUAL")
        assert result == ExpenseType.RENT

    def test_default_subscription(self, predictor):
        """Default es suscripción."""
        result = predictor._clasificar_tipo("NETFLIX")
        assert result == ExpenseType.SUBSCRIPTION


class TestDeterminarAlerta:
    """Tests para _determinar_alerta()."""

    def test_urgent_menos_2_dias(self, predictor):
        """Alerta urgente si quedan 2 días o menos."""
        result = predictor._determinar_alerta(1, Decimal("10000"))
        assert result == AlertLevel.URGENT

    def test_urgent_2_dias(self, predictor):
        """Alerta urgente en 2 días."""
        result = predictor._determinar_alerta(2, Decimal("10000"))
        assert result == AlertLevel.URGENT

    def test_warning_monto_grande_5_dias(self, predictor):
        """Warning si monto grande y 5 días."""
        result = predictor._determinar_alerta(5, Decimal("100000"))
        assert result == AlertLevel.WARNING

    def test_info_monto_pequeno_5_dias(self, predictor):
        """Info si monto pequeño y 5 días."""
        result = predictor._determinar_alerta(5, Decimal("10000"))
        assert result == AlertLevel.INFO

    def test_warning_monto_grande_7_dias(self, predictor):
        """Warning si monto grande y 7 días."""
        result = predictor._determinar_alerta(7, Decimal("80000"))
        assert result == AlertLevel.WARNING

    def test_info_10_dias(self, predictor):
        """Info si quedan 10 días."""
        result = predictor._determinar_alerta(10, Decimal("100000"))
        assert result == AlertLevel.INFO


class TestCalcularProximoCobro:
    """Tests para _calcular_proximo_cobro()."""

    def test_calcula_proximo_mensual(self, predictor):
        """Calcula próximo cobro mensual."""
        hoy = date.today()
        sub = create_mock_subscription(
            "Netflix",
            Decimal("10.99"),
            hoy - timedelta(days=25),  # Hace 25 días
        )
        
        proximo = predictor._calcular_proximo_cobro(sub, hoy)
        
        assert proximo is not None
        assert proximo >= hoy
        # Debería ser en ~5 días (30 - 25)
        assert (proximo - hoy).days <= 10

    def test_avanza_periodos_si_ya_paso(self, predictor):
        """Avanza períodos si ya pasó la fecha."""
        hoy = date.today()
        sub = create_mock_subscription(
            "Spotify",
            Decimal("5.99"),
            hoy - timedelta(days=45),  # Hace 45 días
        )
        
        proximo = predictor._calcular_proximo_cobro(sub, hoy)
        
        assert proximo is not None
        assert proximo >= hoy


class TestPredecirGastos:
    """Tests para predecir_gastos()."""

    def test_predice_suscripciones(self, predictor, mock_db):
        """Predice gastos de suscripciones."""
        hoy = date.today()
        
        # Mock de suscripciones detectadas
        with patch.object(
            predictor.subscription_detector,
            'detectar_suscripciones',
        ) as mock_detect:
            mock_detect.return_value = [
                create_mock_subscription(
                    "Netflix",
                    Decimal("10.99"),
                    hoy - timedelta(days=5),
                ),
                create_mock_subscription(
                    "Spotify",
                    Decimal("5.99"),
                    hoy - timedelta(days=20),
                ),
            ]
            
            # Mock de transacciones para gastos periódicos
            mock_db.execute.return_value.scalars.return_value.all.return_value = []
            
            result = predictor.predecir_gastos("profile-123", dias_adelante=30)
        
        assert len(result) == 2
        comercios = [r.comercio for r in result]
        assert "Netflix" in comercios
        assert "Spotify" in comercios

    def test_ordena_por_fecha(self, predictor, mock_db):
        """Ordena predicciones por fecha."""
        hoy = date.today()
        
        with patch.object(
            predictor.subscription_detector,
            'detectar_suscripciones',
        ) as mock_detect:
            # Crear suscripciones con fechas diferentes
            mock_detect.return_value = [
                create_mock_subscription(
                    "Servicio A",
                    Decimal("50"),
                    hoy - timedelta(days=5),  # Próximo en ~25 días
                ),
                create_mock_subscription(
                    "Servicio B",
                    Decimal("30"),
                    hoy - timedelta(days=25),  # Próximo en ~5 días
                ),
            ]
            mock_db.execute.return_value.scalars.return_value.all.return_value = []
            
            result = predictor.predecir_gastos("profile-123")
        
        if len(result) >= 2:
            assert result[0].fecha_estimada <= result[1].fecha_estimada


class TestGetAlertasVencimiento:
    """Tests para get_alertas_vencimiento()."""

    def test_filtra_solo_warning_y_urgent(self, predictor, mock_db):
        """Solo retorna alertas de warning y urgent."""
        hoy = date.today()
        
        with patch.object(predictor, 'predecir_gastos') as mock_predecir:
            mock_predecir.return_value = [
                PredictedExpense(
                    comercio="Urgente",
                    monto_estimado=Decimal("10000"),
                    fecha_estimada=hoy + timedelta(days=1),
                    tipo=ExpenseType.SUBSCRIPTION,
                    confianza=80,
                    dias_restantes=1,
                    nivel_alerta=AlertLevel.URGENT,
                ),
                PredictedExpense(
                    comercio="Warning",
                    monto_estimado=Decimal("50000"),
                    fecha_estimada=hoy + timedelta(days=5),
                    tipo=ExpenseType.UTILITY,
                    confianza=75,
                    dias_restantes=5,
                    nivel_alerta=AlertLevel.WARNING,
                ),
                PredictedExpense(
                    comercio="Info",
                    monto_estimado=Decimal("5000"),
                    fecha_estimada=hoy + timedelta(days=7),
                    tipo=ExpenseType.SUBSCRIPTION,
                    confianza=70,
                    dias_restantes=7,
                    nivel_alerta=AlertLevel.INFO,
                ),
            ]
            
            result = predictor.get_alertas_vencimiento("profile-123")
        
        assert len(result) == 2
        niveles = [r.nivel_alerta for r in result]
        assert AlertLevel.INFO not in niveles


class TestGenerarResumenMensual:
    """Tests para generar_resumen_mensual()."""

    def test_genera_resumen(self, predictor, mock_db):
        """Genera resumen mensual correctamente."""
        hoy = date.today()
        
        with patch.object(predictor, 'predecir_gastos') as mock_predecir:
            mock_predecir.return_value = [
                PredictedExpense(
                    comercio="Netflix",
                    monto_estimado=Decimal("10.99"),
                    fecha_estimada=hoy + timedelta(days=5),
                    tipo=ExpenseType.SUBSCRIPTION,
                    confianza=80,
                    dias_restantes=5,
                    nivel_alerta=AlertLevel.INFO,
                ),
                PredictedExpense(
                    comercio="ICE",
                    monto_estimado=Decimal("25000"),
                    fecha_estimada=hoy + timedelta(days=10),
                    tipo=ExpenseType.UTILITY,
                    confianza=85,
                    dias_restantes=10,
                    nivel_alerta=AlertLevel.INFO,
                ),
            ]
            
            result = predictor.generar_resumen_mensual("profile-123")
        
        assert result.total_estimado > Decimal("0")
        assert ExpenseType.SUBSCRIPTION in result.por_tipo
        assert ExpenseType.UTILITY in result.por_tipo

    def test_cuenta_alertas_urgentes(self, predictor, mock_db):
        """Cuenta alertas urgentes."""
        hoy = date.today()
        
        with patch.object(predictor, 'predecir_gastos') as mock_predecir:
            mock_predecir.return_value = [
                PredictedExpense(
                    comercio="Urgente 1",
                    monto_estimado=Decimal("10000"),
                    fecha_estimada=hoy + timedelta(days=1),
                    tipo=ExpenseType.SUBSCRIPTION,
                    confianza=80,
                    dias_restantes=1,
                    nivel_alerta=AlertLevel.URGENT,
                ),
                PredictedExpense(
                    comercio="Urgente 2",
                    monto_estimado=Decimal("20000"),
                    fecha_estimada=hoy + timedelta(days=2),
                    tipo=ExpenseType.UTILITY,
                    confianza=85,
                    dias_restantes=2,
                    nivel_alerta=AlertLevel.URGENT,
                ),
            ]
            
            result = predictor.generar_resumen_mensual("profile-123")
        
        assert result.alertas_urgentes == 2


class TestEstimarFlujoCaja:
    """Tests para estimar_flujo_caja()."""

    def test_calcula_flujo_correcto(self, predictor, mock_db):
        """Calcula flujo de caja correctamente."""
        hoy = date.today()
        saldo_inicial = Decimal("100000")
        
        with patch.object(predictor, 'predecir_gastos') as mock_predecir:
            mock_predecir.return_value = [
                PredictedExpense(
                    comercio="Gasto 1",
                    monto_estimado=Decimal("10000"),
                    fecha_estimada=hoy + timedelta(days=5),
                    tipo=ExpenseType.SUBSCRIPTION,
                    confianza=80,
                    dias_restantes=5,
                    nivel_alerta=AlertLevel.INFO,
                ),
                PredictedExpense(
                    comercio="Gasto 2",
                    monto_estimado=Decimal("25000"),
                    fecha_estimada=hoy + timedelta(days=10),
                    tipo=ExpenseType.UTILITY,
                    confianza=85,
                    dias_restantes=10,
                    nivel_alerta=AlertLevel.INFO,
                ),
            ]
            
            result = predictor.estimar_flujo_caja(
                "profile-123",
                saldo_inicial,
                dias=15,
            )
        
        # El día 5 debería tener saldo - 10000
        fecha_dia_5 = hoy + timedelta(days=5)
        assert result[fecha_dia_5] == saldo_inicial - Decimal("10000")
        
        # El día 10 debería tener saldo - 10000 - 25000
        fecha_dia_10 = hoy + timedelta(days=10)
        assert result[fecha_dia_10] == saldo_inicial - Decimal("35000")


class TestDetectarGastosPeriodicos:
    """Tests para _detectar_gastos_periodicos()."""

    def test_detecta_pagos_utility_mensual(self, predictor, mock_db):
        """Detecta pagos de servicios mensuales."""
        hoy = date.today()
        
        # Pagos de ICE mensuales
        txs = [
            create_mock_transaction(
                "ICE TELECOMUNICACIONES",
                Decimal("35000"),
                hoy - timedelta(days=90),
            ),
            create_mock_transaction(
                "ICE TELECOMUNICACIONES",
                Decimal("34500"),
                hoy - timedelta(days=60),
            ),
            create_mock_transaction(
                "ICE TELECOMUNICACIONES",
                Decimal("36000"),
                hoy - timedelta(days=30),
            ),
        ]
        
        mock_db.execute.return_value.scalars.return_value.all.return_value = txs
        
        result = predictor._detectar_gastos_periodicos("profile-123", 30, 50)
        
        assert len(result) >= 1
        assert any("ICE" in r.comercio.upper() for r in result)

    def test_ignora_transacciones_unicas(self, predictor, mock_db):
        """Ignora transacciones únicas."""
        hoy = date.today()
        
        txs = [
            create_mock_transaction(
                "COMPRA UNICA",
                Decimal("50000"),
                hoy - timedelta(days=30),
            ),
        ]
        
        mock_db.execute.return_value.scalars.return_value.all.return_value = txs
        
        result = predictor._detectar_gastos_periodicos("profile-123", 30, 50)
        
        assert len(result) == 0


class TestPredictedExpenseToDict:
    """Tests para PredictedExpense.to_dict()."""

    def test_convierte_a_dict(self):
        """Convierte predicción a diccionario."""
        expense = PredictedExpense(
            comercio="Netflix",
            monto_estimado=Decimal("10.99"),
            fecha_estimada=date(2025, 12, 15),
            tipo=ExpenseType.SUBSCRIPTION,
            confianza=80,
            dias_restantes=5,
            nivel_alerta=AlertLevel.INFO,
            monto_min=Decimal("10.99"),
            monto_max=Decimal("10.99"),
        )
        
        result = expense.to_dict()
        
        assert result["comercio"] == "Netflix"
        assert result["monto_estimado"] == 10.99
        assert result["fecha_estimada"] == "2025-12-15"
        assert result["tipo"] == "subscription"
        assert result["nivel_alerta"] == "info"


class TestGenerarReporteGastosProximos:
    """Tests para función generar_reporte_gastos_proximos()."""

    def test_genera_reporte_completo(self, mock_db):
        """Genera reporte con estructura correcta."""
        with patch.object(
            RecurringExpensePredictor,
            'predecir_gastos',
        ) as mock_predecir, patch.object(
            RecurringExpensePredictor,
            'get_alertas_vencimiento',
        ) as mock_alertas:
            mock_predecir.return_value = []
            mock_alertas.return_value = []
            
            result = generar_reporte_gastos_proximos(mock_db, "profile-123")
        
        assert "generado_en" in result
        assert "dias_proyectados" in result
        assert "total_gastos" in result
        assert "total_estimado" in result
        assert "alertas_urgentes" in result
        assert "gastos" in result
        assert "alertas" in result


class TestExpenseSummaryToDict:
    """Tests para ExpenseSummary.to_dict()."""

    def test_convierte_summary_a_dict(self):
        """Convierte resumen a diccionario."""
        from finanzas_tracker.services.recurring_expense_predictor import ExpenseSummary
        
        summary = ExpenseSummary(
            periodo_inicio=date(2025, 12, 1),
            periodo_fin=date(2025, 12, 31),
            total_estimado=Decimal("50000"),
            gastos=[],
            por_tipo={ExpenseType.SUBSCRIPTION: Decimal("10000")},
            alertas_urgentes=1,
        )
        
        result = summary.to_dict()
        
        assert result["periodo_inicio"] == "2025-12-01"
        assert result["periodo_fin"] == "2025-12-31"
        assert result["total_estimado"] == 50000.0
        assert result["alertas_urgentes"] == 1
        assert "subscription" in result["por_tipo"]
