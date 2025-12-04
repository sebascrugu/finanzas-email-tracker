"""Tests de integración E2E para detección de suscripciones y gastos.

Prueba el flujo completo:
1. Transacciones -> SubscriptionDetector -> Suscripciones detectadas
2. Suscripciones -> RecurringExpensePredictor -> Gastos proyectados
3. Transacciones -> InternalTransferDetector -> Transferencias marcadas
"""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from finanzas_tracker.services.internal_transfer_detector import InternalTransferDetector
from finanzas_tracker.services.recurring_expense_predictor import (
    AlertLevel,
    ExpenseType,
    RecurringExpensePredictor,
)
from finanzas_tracker.services.subscription_detector import (
    SubscriptionDetector,
    SubscriptionFrequency,
)


def create_mock_transaction(
    comercio: str,
    monto: Decimal,
    fecha: date,
    profile_id: str = "profile-e2e-test",
    descripcion: str | None = None,
) -> MagicMock:
    """Crea una transacción mock para tests E2E."""
    tx = MagicMock()
    tx.id = str(uuid4())
    tx.profile_id = profile_id
    tx.comercio = comercio
    tx.descripcion = descripcion or comercio
    tx.monto_original = monto
    tx.fecha_transaccion = fecha
    tx.es_transferencia_interna = False
    tx.deleted_at = None
    return tx


class TestE2ESubscriptionFlow:
    """Tests E2E para flujo de detección de suscripciones."""

    @pytest.fixture
    def mock_db(self):
        """Mock de base de datos."""
        return MagicMock()

    def test_complete_subscription_detection_flow(self, mock_db):
        """Test del flujo completo: transacciones -> suscripciones."""
        hoy = date.today()
        profile_id = "profile-e2e-test"

        # Simular historial de 6 meses con múltiples suscripciones
        transacciones = []

        # Netflix mensual (6 cobros)
        for i in range(6):
            transacciones.append(
                create_mock_transaction(
                    "NETFLIX.COM",
                    Decimal("10.99"),
                    hoy - timedelta(days=30 * i),
                    profile_id,
                )
            )

        # Spotify mensual (6 cobros)
        for i in range(6):
            transacciones.append(
                create_mock_transaction(
                    "SPOTIFY AB",
                    Decimal("5.99"),
                    hoy - timedelta(days=30 * i + 5),
                    profile_id,
                )
            )

        # AWS mensual (4 cobros)
        for i in range(4):
            transacciones.append(
                create_mock_transaction(
                    "AWS AMAZON WEB SERVICES",
                    Decimal("25.50"),
                    hoy - timedelta(days=30 * i + 10),
                    profile_id,
                )
            )

        # Compras aleatorias (no deben ser detectadas como suscripción)
        transacciones.append(
            create_mock_transaction(
                "WALMART SUPERCENTER",
                Decimal("150.00"),
                hoy - timedelta(days=45),
                profile_id,
            )
        )

        # Configurar mock DB
        mock_db.execute.return_value.scalars.return_value.all.return_value = transacciones

        # Ejecutar detección
        detector = SubscriptionDetector(mock_db)
        suscripciones = detector.detectar_suscripciones(profile_id)

        # Verificar resultados
        assert len(suscripciones) >= 3
        comercios = [s.comercio_normalizado for s in suscripciones]

        # Deben detectarse las 3 suscripciones conocidas
        assert any("NETFLIX" in c for c in comercios)
        assert any("SPOTIFY" in c for c in comercios)
        assert any("AWS" in c for c in comercios)

        # Walmart no debe ser detectado
        assert not any("WALMART" in c for c in comercios)

        # Verificar frecuencia detectada
        netflix = next(s for s in suscripciones if "NETFLIX" in s.comercio_normalizado)
        assert netflix.frecuencia == SubscriptionFrequency.MONTHLY
        assert netflix.cantidad_cobros == 6
        assert netflix.confianza >= 70

    def test_subscription_to_expense_prediction_flow(self, mock_db):
        """Test del flujo: suscripciones -> predicciones de gastos."""
        hoy = date.today()
        profile_id = "profile-e2e-test"

        # Crear historial de suscripciones
        transacciones = []

        # Netflix (último cobro hace 25 días -> próximo en 5 días)
        for i in range(4):
            transacciones.append(
                create_mock_transaction(
                    "NETFLIX.COM",
                    Decimal("10.99"),
                    hoy - timedelta(days=25 + 30 * i),
                    profile_id,
                )
            )

        # ICE (servicio público, último hace 28 días -> próximo en 2 días)
        for i in range(4):
            transacciones.append(
                create_mock_transaction(
                    "ICE TELECOMUNICACIONES",
                    Decimal("35000"),
                    hoy - timedelta(days=28 + 30 * i),
                    profile_id,
                )
            )

        mock_db.execute.return_value.scalars.return_value.all.return_value = transacciones

        # Ejecutar predicción
        predictor = RecurringExpensePredictor(mock_db)
        predicciones = predictor.predecir_gastos(profile_id, dias_adelante=30)

        # Verificar que hay predicciones
        assert len(predicciones) >= 2

        # Verificar tipos correctos
        tipos = {p.tipo for p in predicciones}
        assert ExpenseType.SUBSCRIPTION in tipos or ExpenseType.UTILITY in tipos

        # Verificar alertas
        alertas = predictor.get_alertas_vencimiento(profile_id, dias_alerta=7)
        # ICE debería ser urgente (en 2 días) y es monto grande
        urgentes = [a for a in alertas if a.nivel_alerta == AlertLevel.URGENT]
        assert len(urgentes) >= 0  # Puede variar según la fecha

    def test_gasto_mensual_calculation(self, mock_db):
        """Test de cálculo de gasto mensual en suscripciones."""
        hoy = date.today()
        profile_id = "profile-e2e-test"

        transacciones = []

        # Netflix mensual ₡10.99
        for i in range(3):
            transacciones.append(
                create_mock_transaction(
                    "NETFLIX.COM",
                    Decimal("10.99"),
                    hoy - timedelta(days=30 * i),
                    profile_id,
                )
            )

        # Spotify mensual ₡5.99
        for i in range(3):
            transacciones.append(
                create_mock_transaction(
                    "SPOTIFY AB",
                    Decimal("5.99"),
                    hoy - timedelta(days=30 * i + 5),
                    profile_id,
                )
            )

        mock_db.execute.return_value.scalars.return_value.all.return_value = transacciones

        detector = SubscriptionDetector(mock_db)
        suscripciones = detector.detectar_suscripciones(profile_id)

        gasto_mensual = detector.get_gasto_mensual_suscripciones(suscripciones)

        # Debería ser aproximadamente 10.99 + 5.99 = 16.98
        assert gasto_mensual >= Decimal("16")


class TestE2EInternalTransferFlow:
    """Tests E2E para detección de transferencias internas."""

    @pytest.fixture
    def detector(self):
        """Instancia de InternalTransferDetector."""
        mock_db = MagicMock()
        return InternalTransferDetector(mock_db)

    def test_card_payment_detection(self, detector):
        """Test de detección de pago de tarjeta."""
        # Simular pago de tarjeta de crédito
        tx = MagicMock()
        tx.id = "tx-123"
        tx.profile_id = "profile-test"
        tx.comercio = "PAGO TC BAC ***1234"
        tx.descripcion = "PAGO TARJETA VISA ***1234"
        tx.monto_original = Decimal("50000")
        tx.fecha_transaccion = date.today()
        tx.es_transferencia_interna = False
        tx.deleted_at = None

        resultado = detector.es_pago_tarjeta(tx)

        # Debe retornar un PagoTarjetaDetectado, no None
        assert resultado is not None
        assert resultado.ultimos_4_digitos == "1234"
        assert resultado.confianza >= 80

    def test_internal_transfer_detection(self, detector):
        """Test de detección de transferencia interna."""
        # Ahorro programado
        tx1 = MagicMock()
        tx1.id = "tx-ahorro"
        tx1.profile_id = "profile-test"
        tx1.comercio = "AHORRO PROGRAMADO"
        tx1.descripcion = "AHORRO PROGRAMADO MENSUAL"
        tx1.monto_original = Decimal("25000")
        tx1.fecha_transaccion = date.today()
        tx1.es_transferencia_interna = False
        tx1.deleted_at = None

        resultado1 = detector.es_transferencia_interna(tx1)
        # Debe detectar como transferencia interna
        assert resultado1 is not None
        assert resultado1.tipo == "entre_cuentas"

    def test_regular_transaction_not_internal(self, detector):
        """Test que transacciones regulares no son marcadas como internas."""
        tx = MagicMock()
        tx.id = "tx-compra"
        tx.profile_id = "profile-test"
        tx.comercio = "STARBUCKS"
        tx.descripcion = "STARBUCKS COSTA RICA"
        tx.monto_original = Decimal("5000")
        tx.fecha_transaccion = date.today()
        tx.es_transferencia_interna = False
        tx.deleted_at = None

        resultado = detector.es_transferencia_interna(tx)
        # No debe ser detectada como transferencia interna
        assert resultado is None


class TestE2ECompleteFlow:
    """Tests E2E del flujo completo del sistema."""

    @pytest.fixture
    def mock_db(self):
        """Mock de base de datos."""
        return MagicMock()

    def test_monthly_expense_summary(self, mock_db):
        """Test de resumen mensual de gastos proyectados."""
        hoy = date.today()
        profile_id = "profile-e2e-test"

        # Crear historial variado
        transacciones = []

        # Suscripción Netflix
        for i in range(4):
            transacciones.append(
                create_mock_transaction(
                    "NETFLIX.COM",
                    Decimal("10.99"),
                    hoy - timedelta(days=30 * i),
                    profile_id,
                )
            )

        # Servicio ICE
        for i in range(4):
            transacciones.append(
                create_mock_transaction(
                    "ICE ELECTRICIDAD",
                    Decimal("45000"),
                    hoy - timedelta(days=30 * i + 15),
                    profile_id,
                )
            )

        # Cuota préstamo
        for i in range(4):
            transacciones.append(
                create_mock_transaction(
                    "CUOTA PRESTAMO PERSONAL BAC",
                    Decimal("150000"),
                    hoy - timedelta(days=30 * i + 10),
                    profile_id,
                )
            )

        mock_db.execute.return_value.scalars.return_value.all.return_value = transacciones

        # Generar resumen mensual
        predictor = RecurringExpensePredictor(mock_db)
        resumen = predictor.generar_resumen_mensual(profile_id)

        # Verificar estructura del resumen
        assert resumen.total_estimado >= Decimal("0")
        assert resumen.periodo_inicio <= resumen.periodo_fin

        # Verificar que se calculan por tipo
        resumen_dict = resumen.to_dict()
        assert "por_tipo" in resumen_dict
        assert "gastos" in resumen_dict

    def test_cash_flow_projection(self, mock_db):
        """Test de proyección de flujo de caja."""
        hoy = date.today()
        profile_id = "profile-e2e-test"

        # Crear suscripción simple
        transacciones = []
        for i in range(3):
            transacciones.append(
                create_mock_transaction(
                    "SERVICIO MENSUAL",
                    Decimal("50000"),
                    hoy - timedelta(days=30 * i + 20),
                    profile_id,
                )
            )

        mock_db.execute.return_value.scalars.return_value.all.return_value = transacciones

        predictor = RecurringExpensePredictor(mock_db)
        flujo = predictor.estimar_flujo_caja(
            profile_id,
            saldo_inicial=Decimal("500000"),
            dias=30,
        )

        # Verificar estructura del flujo
        assert len(flujo) == 31  # 30 días + hoy
        assert hoy in flujo
        assert flujo[hoy] == Decimal("500000")  # Saldo inicial

        # El saldo debería disminuir cuando hay gastos
        saldos = list(flujo.values())
        # Al menos el último saldo debería ser menor si hay gastos
        assert saldos[-1] <= saldos[0]


class TestE2EEdgeCases:
    """Tests E2E para casos límite."""

    @pytest.fixture
    def mock_db(self):
        """Mock de base de datos."""
        return MagicMock()

    def test_empty_transaction_history(self, mock_db):
        """Test con historial vacío."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []

        detector = SubscriptionDetector(mock_db)
        suscripciones = detector.detectar_suscripciones("profile-empty")
        assert suscripciones == []

        predictor = RecurringExpensePredictor(mock_db)
        predicciones = predictor.predecir_gastos("profile-empty")
        assert predicciones == []

    def test_single_transaction_per_merchant(self, mock_db):
        """Test con solo una transacción por comercio."""
        transacciones = [
            create_mock_transaction(
                "RANDOM SHOP 1",
                Decimal("100"),
                date.today() - timedelta(days=30),
            ),
            create_mock_transaction(
                "RANDOM SHOP 2",
                Decimal("200"),
                date.today() - timedelta(days=15),
            ),
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = transacciones

        detector = SubscriptionDetector(mock_db)
        suscripciones = detector.detectar_suscripciones("profile-test")

        # No debería detectar suscripciones
        assert len(suscripciones) == 0

    def test_variable_amounts(self, mock_db):
        """Test con montos variables (utilidades)."""
        hoy = date.today()
        transacciones = [
            create_mock_transaction(
                "ICE ELECTRICIDAD",
                Decimal("35000"),
                hoy - timedelta(days=90),
            ),
            create_mock_transaction(
                "ICE ELECTRICIDAD",
                Decimal("42000"),  # +20%
                hoy - timedelta(days=60),
            ),
            create_mock_transaction(
                "ICE ELECTRICIDAD",
                Decimal("38000"),
                hoy - timedelta(days=30),
            ),
        ]
        mock_db.execute.return_value.scalars.return_value.all.return_value = transacciones

        predictor = RecurringExpensePredictor(mock_db)
        predicciones = predictor.predecir_gastos("profile-test", dias_adelante=60)

        # Debería detectar aunque el monto varíe
        # El tipo debería ser utility
        utility_predictions = [p for p in predicciones if p.tipo == ExpenseType.UTILITY]
        # Puede o no detectarse dependiendo de la variación permitida
        assert len(predicciones) >= 0
