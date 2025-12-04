"""Tests para InternalTransferDetector.

Prueba la detección de pagos de tarjeta y transferencias internas.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from finanzas_tracker.models.enums import CardType, TransactionType, TransactionStatus
from finanzas_tracker.services.internal_transfer_detector import (
    InternalTransferDetector,
    PagoTarjetaDetectado,
    TransferenciaInternaDetectada,
)


@pytest.fixture
def mock_db():
    """Mock de sesión de base de datos."""
    return MagicMock()


@pytest.fixture
def detector(mock_db):
    """Instancia de InternalTransferDetector con mock de DB."""
    return InternalTransferDetector(mock_db)


@pytest.fixture
def sample_transaction():
    """Transacción de ejemplo."""
    tx = MagicMock()
    tx.id = str(uuid4())
    tx.profile_id = str(uuid4())
    tx.comercio = "PAGO TARJETA DE CREDITO ****3640"
    tx.monto_original = Decimal("150000.00")
    tx.monto_crc = Decimal("150000.00")
    tx.moneda = "CRC"
    tx.tipo_transaccion = TransactionType.TRANSFER
    tx.fecha_transaccion = date(2025, 12, 1)
    tx.banco = "BAC"
    tx.estado = TransactionStatus.PENDING
    tx.es_transferencia_interna = False
    tx.tipo_especial = None
    tx.excluir_de_presupuesto = False
    tx.card_id = None
    tx.deleted_at = None
    return tx


@pytest.fixture
def sample_card():
    """Tarjeta de crédito de ejemplo."""
    card = MagicMock()
    card.id = str(uuid4())
    card.profile_id = str(uuid4())
    card.ultimos_4_digitos = "3640"
    card.tipo = CardType.CREDIT
    card.banco = "BAC"
    card.current_balance = Decimal("150000.00")
    card.deleted_at = None
    return card


class TestEsPagoTarjeta:
    """Tests para es_pago_tarjeta()."""

    def test_detecta_pago_tarjeta_basico(self, detector, sample_transaction):
        """Detecta pago de tarjeta con patrón básico."""
        sample_transaction.comercio = "PAGO TARJETA DE CREDITO"
        detector._buscar_tarjeta = MagicMock(return_value=None)
        
        result = detector.es_pago_tarjeta(sample_transaction)
        
        assert result is not None
        assert isinstance(result, PagoTarjetaDetectado)
        assert result.confianza >= 80

    def test_detecta_pago_tc_con_digitos(self, detector, sample_transaction, sample_card):
        """Detecta pago T.C. con últimos 4 dígitos."""
        sample_transaction.comercio = "PAGO T.C. 3640"
        detector._buscar_tarjeta = MagicMock(return_value=sample_card)
        
        result = detector.es_pago_tarjeta(sample_transaction)
        
        assert result is not None
        assert result.ultimos_4_digitos == "3640"
        assert result.tarjeta == sample_card
        assert result.confianza >= 90

    def test_detecta_pago_visa(self, detector, sample_transaction):
        """Detecta pago VISA."""
        sample_transaction.comercio = "PAGO VISA 1234"
        detector._buscar_tarjeta = MagicMock(return_value=None)
        
        result = detector.es_pago_tarjeta(sample_transaction)
        
        assert result is not None
        assert result.ultimos_4_digitos == "1234"

    def test_detecta_pago_mastercard(self, detector, sample_transaction):
        """Detecta pago MASTERCARD."""
        sample_transaction.comercio = "PAGO MASTERCARD"
        detector._buscar_tarjeta = MagicMock(return_value=None)
        
        result = detector.es_pago_tarjeta(sample_transaction)
        
        assert result is not None

    def test_detecta_abono_tarjeta(self, detector, sample_transaction):
        """Detecta abono a tarjeta."""
        sample_transaction.comercio = "ABONO A TARJETA CREDITO"
        detector._buscar_tarjeta = MagicMock(return_value=None)
        
        result = detector.es_pago_tarjeta(sample_transaction)
        
        assert result is not None

    def test_no_detecta_compra_normal(self, detector, sample_transaction):
        """No detecta compra normal como pago."""
        sample_transaction.comercio = "WALMART SUPERCENTER"
        detector._buscar_tarjeta = MagicMock(return_value=None)
        
        result = detector.es_pago_tarjeta(sample_transaction)
        
        assert result is None

    def test_no_detecta_sinpe(self, detector, sample_transaction):
        """No detecta SINPE como pago de tarjeta."""
        sample_transaction.comercio = "SINPE MOVIL JUAN PEREZ"
        detector._buscar_tarjeta = MagicMock(return_value=None)
        
        result = detector.es_pago_tarjeta(sample_transaction)
        
        assert result is None


class TestEsTransferenciaInterna:
    """Tests para es_transferencia_interna()."""

    def test_detecta_pago_tarjeta_como_interna(self, detector, sample_transaction, sample_card):
        """Pago de tarjeta es transferencia interna."""
        sample_transaction.comercio = "PAGO TARJETA DE CREDITO ****3640"
        detector._buscar_tarjeta = MagicMock(return_value=sample_card)
        
        result = detector.es_transferencia_interna(sample_transaction)
        
        assert result is not None
        assert result.tipo == "pago_tarjeta"

    def test_detecta_transferencia_cuenta_propia(self, detector, sample_transaction):
        """Detecta transferencia a cuenta propia."""
        sample_transaction.comercio = "TRANSFERENCIA A CTA PROPIA"
        
        result = detector.es_transferencia_interna(sample_transaction)
        
        assert result is not None
        assert result.tipo in ["entre_cuentas", "ahorro"]

    def test_detecta_ahorro_programado(self, detector, sample_transaction):
        """Detecta ahorro programado."""
        sample_transaction.comercio = "AHORRO PROGRAMADO MENSUAL"
        
        result = detector.es_transferencia_interna(sample_transaction)
        
        assert result is not None

    def test_no_detecta_transferencia_sinpe(self, detector, sample_transaction):
        """SINPE no es transferencia interna."""
        sample_transaction.comercio = "SINPE MOVIL - MARIA GARCIA"
        detector._buscar_tarjeta = MagicMock(return_value=None)
        
        result = detector.es_transferencia_interna(sample_transaction)
        
        assert result is None


class TestExtraerUltimos4:
    """Tests para _extraer_ultimos_4()."""

    def test_extrae_con_asteriscos(self, detector):
        """Extrae dígitos después de asteriscos."""
        result = detector._extraer_ultimos_4("PAGO TC ****3640")
        assert result == "3640"

    def test_extrae_sin_asteriscos(self, detector):
        """Extrae dígitos al final."""
        result = detector._extraer_ultimos_4("PAGO VISA 5678")
        assert result == "5678"

    def test_extrae_con_espacios(self, detector):
        """Extrae dígitos con espacios."""
        result = detector._extraer_ultimos_4("PAGO TARJETA 1234 5678")
        # Debería extraer los últimos 4
        assert result in ["5678", "1234"]

    def test_retorna_none_sin_digitos(self, detector):
        """Retorna None si no hay 4 dígitos."""
        result = detector._extraer_ultimos_4("PAGO TARJETA CREDITO")
        assert result is None


class TestProcesarPagoTarjeta:
    """Tests para procesar_pago_tarjeta()."""

    def test_procesa_pago_y_actualiza_saldo(self, detector, mock_db, sample_transaction, sample_card):
        """Procesa pago actualizando saldo de tarjeta."""
        sample_transaction.comercio = "PAGO TC 3640"
        sample_transaction.monto_original = Decimal("50000.00")
        sample_card.current_balance = Decimal("150000.00")
        detector._buscar_tarjeta = MagicMock(return_value=sample_card)
        
        tx_result, card_result = detector.procesar_pago_tarjeta(
            sample_transaction,
            sample_transaction.profile_id,
        )
        
        assert tx_result.es_transferencia_interna is True
        assert tx_result.tipo_especial == "pago_tarjeta"
        assert tx_result.excluir_de_presupuesto is True
        assert card_result == sample_card
        assert sample_card.current_balance == Decimal("100000.00")
        mock_db.commit.assert_called()

    def test_procesa_pago_sin_tarjeta_encontrada(self, detector, mock_db, sample_transaction):
        """Procesa pago aunque no encuentre la tarjeta."""
        sample_transaction.comercio = "PAGO TC 9999"
        detector._buscar_tarjeta = MagicMock(return_value=None)
        
        tx_result, card_result = detector.procesar_pago_tarjeta(
            sample_transaction,
            sample_transaction.profile_id,
        )
        
        assert tx_result.es_transferencia_interna is True
        assert card_result is None

    def test_no_procesa_transaccion_normal(self, detector, mock_db, sample_transaction):
        """No procesa transacción que no es pago."""
        sample_transaction.comercio = "WALMART SUPERCENTER"
        detector._buscar_tarjeta = MagicMock(return_value=None)
        
        tx_result, card_result = detector.procesar_pago_tarjeta(
            sample_transaction,
            sample_transaction.profile_id,
        )
        
        assert tx_result.es_transferencia_interna is False
        assert card_result is None


class TestVincularPagoConTarjeta:
    """Tests para vincular_pago_con_tarjeta()."""

    def test_vincula_por_ultimos_4(self, detector, sample_transaction):
        """Vincula por últimos 4 dígitos."""
        sample_transaction.comercio = "PAGO TC ****3640"
        
        card1 = MagicMock()
        card1.ultimos_4_digitos = "1234"
        card1.tipo = CardType.CREDIT
        
        card2 = MagicMock()
        card2.ultimos_4_digitos = "3640"
        card2.tipo = CardType.CREDIT
        
        result = detector.vincular_pago_con_tarjeta(
            sample_transaction,
            [card1, card2],
        )
        
        assert result == card2

    def test_vincula_por_monto_similar(self, detector, sample_transaction):
        """Vincula por monto similar cuando no hay dígitos."""
        sample_transaction.comercio = "PAGO TARJETA"
        sample_transaction.monto_original = Decimal("75000.00")
        
        card = MagicMock()
        card.ultimos_4_digitos = "9999"
        card.tipo = CardType.CREDIT
        card.current_balance = Decimal("75500.00")  # Diferencia de 500
        
        result = detector.vincular_pago_con_tarjeta(
            sample_transaction,
            [card],
        )
        
        assert result == card

    def test_no_vincula_sin_coincidencia(self, detector, sample_transaction):
        """No vincula si no hay coincidencia."""
        sample_transaction.comercio = "PAGO TARJETA"
        sample_transaction.monto_original = Decimal("75000.00")
        
        card = MagicMock()
        card.ultimos_4_digitos = "9999"
        card.tipo = CardType.CREDIT
        card.current_balance = Decimal("200000.00")  # Muy diferente
        
        result = detector.vincular_pago_con_tarjeta(
            sample_transaction,
            [card],
        )
        
        assert result is None


class TestDetectarYMarcarTransferencias:
    """Tests para detectar_y_marcar_transferencias()."""

    def test_detecta_multiples_tipos(self, detector, mock_db):
        """Detecta múltiples tipos de transferencias."""
        tx1 = MagicMock()
        tx1.comercio = "PAGO TC 3640"
        tx1.monto_original = Decimal("50000.00")
        tx1.es_transferencia_interna = False
        tx1.profile_id = "profile-123"
        
        tx2 = MagicMock()
        tx2.comercio = "AHORRO PROGRAMADO"
        tx2.monto_original = Decimal("25000.00")
        tx2.es_transferencia_interna = False
        tx2.profile_id = "profile-123"
        
        tx3 = MagicMock()
        tx3.comercio = "WALMART"
        tx3.monto_original = Decimal("10000.00")
        tx3.es_transferencia_interna = False
        tx3.profile_id = "profile-123"
        
        detector._buscar_tarjeta = MagicMock(return_value=None)
        
        result = detector.detectar_y_marcar_transferencias(
            [tx1, tx2, tx3],
            "profile-123",
        )
        
        assert result["total_marcadas"] >= 2  # Al menos tx1 y tx2
        assert tx1.es_transferencia_interna is True
        assert tx2.es_transferencia_interna is True
        assert tx3.es_transferencia_interna is False

    def test_ignora_ya_marcadas(self, detector, mock_db):
        """Ignora transacciones ya marcadas."""
        tx = MagicMock()
        tx.comercio = "PAGO TC 3640"
        tx.es_transferencia_interna = True  # Ya marcada
        
        result = detector.detectar_y_marcar_transferencias(
            [tx],
            "profile-123",
        )
        
        assert result["total_marcadas"] == 0


class TestGetResumenTransferencias:
    """Tests para get_resumen_transferencias()."""

    def test_resumen_con_datos(self, detector, mock_db):
        """Obtiene resumen con datos."""
        tx1 = MagicMock()
        tx1.tipo_especial = "pago_tarjeta"
        tx1.monto_original = Decimal("50000.00")
        
        tx2 = MagicMock()
        tx2.tipo_especial = "pago_tarjeta"
        tx2.monto_original = Decimal("75000.00")
        
        tx3 = MagicMock()
        tx3.tipo_especial = "ahorro"
        tx3.monto_original = Decimal("25000.00")
        
        mock_db.execute.return_value.scalars.return_value.all.return_value = [tx1, tx2, tx3]
        
        result = detector.get_resumen_transferencias("profile-123")
        
        assert result["total"] == 3
        assert result["por_tipo"]["pago_tarjeta"] == 2
        assert result["por_tipo"]["ahorro"] == 1
        assert result["monto_total"] == Decimal("150000.00")

    def test_resumen_vacio(self, detector, mock_db):
        """Obtiene resumen vacío."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        
        result = detector.get_resumen_transferencias("profile-123")
        
        assert result["total"] == 0
        assert result["por_tipo"] == {}
        assert result["monto_total"] == Decimal("0.00")
