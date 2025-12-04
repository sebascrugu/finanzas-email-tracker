"""Tests para TransactionService.

Prueba la gestión de ciclo de vida y estados de transacciones.
"""

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from finanzas_tracker.models.enums import TransactionStatus, TransactionType
from finanzas_tracker.services.transaction_service import TransactionService


@pytest.fixture
def mock_db():
    """Mock de sesión de base de datos."""
    return MagicMock()


@pytest.fixture
def service(mock_db):
    """Instancia de TransactionService con mock de DB."""
    return TransactionService(mock_db)


@pytest.fixture
def sample_transaction():
    """Transacción de ejemplo usando MagicMock."""
    txn = MagicMock()
    txn.id = str(uuid4())
    txn.profile_id = str(uuid4())
    txn.comercio = "Supermercado La Esquina"
    txn.monto_original = Decimal("15000.00")
    txn.monto_crc = Decimal("15000.00")
    txn.moneda = "CRC"
    txn.tipo_transaccion = TransactionType.PURCHASE
    txn.fecha_transaccion = date(2025, 12, 1)
    txn.banco = "BAC"
    txn.estado = TransactionStatus.PENDING
    txn.es_historica = False
    txn.deleted_at = None
    txn.razon_ajuste = None
    txn.reconciliada_en = None
    txn.monto_original_estimado = None
    txn.monto_ajustado = None
    txn.es_transferencia_interna = False
    txn.cuenta_origen_id = None
    txn.cuenta_destino_id = None
    return txn


class TestTransactionServiceInit:
    """Tests de inicialización."""

    def test_init_stores_db_session(self, mock_db):
        """Verifica que guarda la sesión de DB."""
        service = TransactionService(mock_db)
        assert service.db == mock_db


class TestGet:
    """Tests para get()."""

    def test_get_existing_transaction(self, service, mock_db, sample_transaction):
        """Obtiene transacción existente."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_transaction
        
        result = service.get(1)
        
        assert result == sample_transaction
        mock_db.execute.assert_called_once()

    def test_get_nonexistent_returns_none(self, service, mock_db):
        """Retorna None si no existe."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        
        result = service.get(999)
        
        assert result is None


class TestGetByProfile:
    """Tests para get_by_profile()."""

    def test_get_by_profile_basic(self, service, mock_db, sample_transaction):
        """Lista transacciones de un perfil."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_transaction]
        
        result = service.get_by_profile("profile-123")
        
        assert len(result) == 1
        assert result[0] == sample_transaction

    def test_get_by_profile_with_fecha_range(self, service, mock_db):
        """Lista transacciones filtradas por fecha."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        
        result = service.get_by_profile(
            "profile-123",
            fecha_inicio=date(2025, 12, 1),
            fecha_fin=date(2025, 12, 31),
        )
        
        assert isinstance(result, list)
        mock_db.execute.assert_called_once()

    def test_get_by_profile_with_estado_filter(self, service, mock_db):
        """Lista transacciones filtradas por estado."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        
        result = service.get_by_profile(
            "profile-123",
            estado=TransactionStatus.PENDING,
        )
        
        assert isinstance(result, list)

    def test_get_by_profile_solo_historicas_true(self, service, mock_db):
        """Lista solo transacciones históricas."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        
        result = service.get_by_profile(
            "profile-123",
            solo_historicas=True,
        )
        
        assert isinstance(result, list)

    def test_get_by_profile_solo_historicas_false(self, service, mock_db):
        """Lista solo transacciones activas."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        
        result = service.get_by_profile(
            "profile-123",
            solo_historicas=False,
        )
        
        assert isinstance(result, list)

    def test_get_by_profile_with_pagination(self, service, mock_db):
        """Lista transacciones con paginación."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        
        result = service.get_by_profile(
            "profile-123",
            skip=10,
            limit=20,
        )
        
        assert isinstance(result, list)


class TestCambiarEstado:
    """Tests para cambiar_estado()."""

    def test_cambiar_estado_success(self, service, mock_db, sample_transaction):
        """Cambia estado correctamente."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_transaction
        
        result = service.cambiar_estado(1, TransactionStatus.CONFIRMED)
        
        assert result.estado == TransactionStatus.CONFIRMED
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

    def test_cambiar_estado_to_cancelled_with_razon(self, service, mock_db, sample_transaction):
        """Cambia a cancelado guardando razón."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_transaction
        
        result = service.cambiar_estado(
            1,
            TransactionStatus.CANCELLED,
            razon="Transacción duplicada",
        )
        
        assert result.estado == TransactionStatus.CANCELLED
        assert result.razon_ajuste == "Transacción duplicada"

    def test_cambiar_estado_to_reconciled_sets_timestamp(self, service, mock_db, sample_transaction):
        """Cambia a reconciliada estableciendo timestamp."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_transaction
        
        result = service.cambiar_estado(1, TransactionStatus.RECONCILED)
        
        assert result.estado == TransactionStatus.RECONCILED
        assert result.reconciliada_en is not None

    def test_cambiar_estado_transaction_not_found(self, service, mock_db):
        """Error si transacción no existe."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        
        with pytest.raises(ValueError, match="no encontrada"):
            service.cambiar_estado(999, TransactionStatus.CONFIRMED)


class TestConfirmarTransaccion:
    """Tests para confirmar_transaccion()."""

    def test_confirmar_transaccion_success(self, service, mock_db, sample_transaction):
        """Confirma transacción pendiente."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_transaction
        
        result = service.confirmar_transaccion(1)
        
        assert result.estado == TransactionStatus.CONFIRMED


class TestCancelarTransaccion:
    """Tests para cancelar_transaccion()."""

    def test_cancelar_transaccion_with_default_razon(self, service, mock_db, sample_transaction):
        """Cancela con razón por defecto."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_transaction
        
        result = service.cancelar_transaccion(1)
        
        assert result.estado == TransactionStatus.CANCELLED
        assert result.razon_ajuste == "Cancelada por usuario"

    def test_cancelar_transaccion_with_custom_razon(self, service, mock_db, sample_transaction):
        """Cancela con razón personalizada."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_transaction
        
        result = service.cancelar_transaccion(1, razon="Error de banco")
        
        assert result.estado == TransactionStatus.CANCELLED
        assert result.razon_ajuste == "Error de banco"


class TestMarcarComoHistoricas:
    """Tests para marcar_como_historicas()."""

    def test_marcar_como_historicas_success(self, service, mock_db):
        """Marca transacciones como históricas."""
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_db.execute.return_value = mock_result
        
        count = service.marcar_como_historicas("profile-123", date(2025, 12, 1))
        
        assert count == 5
        mock_db.commit.assert_called_once()

    def test_marcar_como_historicas_no_transactions(self, service, mock_db):
        """Retorna 0 si no hay transacciones para marcar."""
        mock_result = MagicMock()
        mock_result.rowcount = 0
        mock_db.execute.return_value = mock_result
        
        count = service.marcar_como_historicas("profile-123", date(2025, 12, 1))
        
        assert count == 0


class TestGetPendientes:
    """Tests para get_pendientes()."""

    def test_get_pendientes_calls_get_by_profile(self, service, mock_db, sample_transaction):
        """Obtiene transacciones pendientes."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = [sample_transaction]
        
        result = service.get_pendientes("profile-123")
        
        assert len(result) == 1

    def test_get_pendientes_with_limite(self, service, mock_db):
        """Obtiene pendientes con límite personalizado."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        
        result = service.get_pendientes("profile-123", limite=10)
        
        assert isinstance(result, list)


class TestGetHuerfanas:
    """Tests para get_huerfanas()."""

    def test_get_huerfanas_returns_orphan_transactions(self, service, mock_db):
        """Obtiene transacciones huérfanas."""
        mock_db.execute.return_value.scalars.return_value.all.return_value = []
        
        result = service.get_huerfanas("profile-123")
        
        assert isinstance(result, list)


class TestConfirmarBatch:
    """Tests para confirmar_batch()."""

    def test_confirmar_batch_success(self, service, mock_db):
        """Confirma múltiples transacciones."""
        mock_result = MagicMock()
        mock_result.rowcount = 3
        mock_db.execute.return_value = mock_result
        
        count = service.confirmar_batch([1, 2, 3])
        
        assert count == 3
        mock_db.commit.assert_called_once()

    def test_confirmar_batch_empty_list(self, service, mock_db):
        """Retorna 0 con lista vacía."""
        count = service.confirmar_batch([])
        
        assert count == 0
        mock_db.execute.assert_not_called()


class TestGetResumenEstados:
    """Tests para get_resumen_estados()."""

    def test_get_resumen_estados_with_data(self, service, mock_db):
        """Obtiene resumen con datos."""
        mock_db.execute.return_value.all.return_value = [
            (TransactionStatus.PENDING, 10),
            (TransactionStatus.CONFIRMED, 25),
            (TransactionStatus.RECONCILED, 5),
        ]
        
        result = service.get_resumen_estados("profile-123")
        
        assert result["pendiente"] == 10
        assert result["confirmada"] == 25
        assert result["reconciliada"] == 5
        assert result["cancelada"] == 0
        assert result["huerfana"] == 0

    def test_get_resumen_estados_empty(self, service, mock_db):
        """Obtiene resumen vacío."""
        mock_db.execute.return_value.all.return_value = []
        
        result = service.get_resumen_estados("profile-123")
        
        assert result["pendiente"] == 0
        assert result["confirmada"] == 0
        assert result["reconciliada"] == 0
        assert result["cancelada"] == 0
        assert result["huerfana"] == 0


class TestMarcarTransferenciaInterna:
    """Tests para marcar_transferencia_interna()."""

    def test_marcar_transferencia_interna_success(self, service, mock_db):
        """Marca par de transacciones como transferencia interna."""
        origen = MagicMock()
        origen.id = str(uuid4())
        origen.profile_id = str(uuid4())
        origen.comercio = "Transferencia a cuenta USD"
        origen.monto_original = Decimal("500.00")
        origen.monto_crc = Decimal("500.00")
        origen.moneda = "USD"
        origen.tipo_transaccion = TransactionType.TRANSFER
        origen.fecha_transaccion = date(2025, 12, 1)
        origen.banco = "BAC"
        origen.estado = TransactionStatus.PENDING
        origen.cuenta_origen_id = "CTA-001"
        origen.cuenta_destino_id = None
        origen.es_transferencia_interna = False
        origen.deleted_at = None
        
        destino = MagicMock()
        destino.id = str(uuid4())
        destino.profile_id = str(uuid4())
        destino.comercio = "Depósito desde CRC"
        destino.monto_original = Decimal("500.00")
        destino.monto_crc = Decimal("500.00")
        destino.moneda = "USD"
        destino.tipo_transaccion = TransactionType.DEPOSIT
        destino.fecha_transaccion = date(2025, 12, 1)
        destino.banco = "BAC"
        destino.estado = TransactionStatus.PENDING
        destino.cuenta_destino_id = "CTA-002"
        destino.cuenta_origen_id = None
        destino.es_transferencia_interna = False
        destino.deleted_at = None
        
        def side_effect(stmt):
            mock_result = MagicMock()
            # Simple mock that returns origen for first call, destino for second
            return mock_result
        
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [origen, destino]
        
        result_origen, result_destino = service.marcar_transferencia_interna(1, 2)
        
        assert result_origen.es_transferencia_interna is True
        assert result_destino.es_transferencia_interna is True
        mock_db.commit.assert_called_once()

    def test_marcar_transferencia_interna_origen_not_found(self, service, mock_db):
        """Error si transacción origen no existe."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        
        with pytest.raises(ValueError, match="origen.*no encontrada"):
            service.marcar_transferencia_interna(999, 2)

    def test_marcar_transferencia_interna_destino_not_found(self, service, mock_db, sample_transaction):
        """Error si transacción destino no existe."""
        mock_db.execute.return_value.scalar_one_or_none.side_effect = [sample_transaction, None]
        
        with pytest.raises(ValueError, match="destino.*no encontrada"):
            service.marcar_transferencia_interna(1, 999)


class TestAjustarMonto:
    """Tests para ajustar_monto()."""

    def test_ajustar_monto_success(self, service, mock_db, sample_transaction):
        """Ajusta monto correctamente."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_transaction
        
        result = service.ajustar_monto(1, Decimal("16000.00"), "Corrección de recibo")
        
        assert result.monto_ajustado == Decimal("16000.00")
        assert result.monto_original == Decimal("16000.00")
        assert result.monto_crc == Decimal("16000.00")
        assert result.razon_ajuste == "Corrección de recibo"
        mock_db.commit.assert_called_once()

    def test_ajustar_monto_preserves_original(self, service, mock_db, sample_transaction):
        """Preserva monto original estimado."""
        sample_transaction.monto_original_estimado = None
        original_monto = sample_transaction.monto_original
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_transaction
        
        result = service.ajustar_monto(1, Decimal("16000.00"))
        
        assert result.monto_original_estimado == original_monto

    def test_ajustar_monto_transaction_not_found(self, service, mock_db):
        """Error si transacción no existe."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        
        with pytest.raises(ValueError, match="no encontrada"):
            service.ajustar_monto(999, Decimal("16000.00"))

    def test_ajustar_monto_with_default_razon(self, service, mock_db, sample_transaction):
        """Ajusta con razón por defecto."""
        mock_db.execute.return_value.scalar_one_or_none.return_value = sample_transaction
        
        result = service.ajustar_monto(1, Decimal("16000.00"))
        
        assert result.razon_ajuste == "Ajuste manual"
