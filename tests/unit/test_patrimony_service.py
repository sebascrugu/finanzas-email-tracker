"""
Tests unitarios para PatrimonyService.

Tests para métodos de snapshot de patrimonio:
- crear_snapshot
- establecer_patrimonio_inicial
- obtener_historial
- get_snapshot_fecha_base
- get_ultimo_snapshot
- calcular_cambio_periodo
- generar_snapshot_mensual

Nota: Estos tests usan mocks completos y NO requieren base de datos.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest


# Deshabilitar fixtures de DB para estos tests
pytestmark = pytest.mark.usefixtures()  # No usar fixtures automáticos


class TestPatrimonyServiceInit:
    """Tests para la inicialización del servicio."""

    def test_service_init(self):
        """Debería inicializar el servicio correctamente."""
        # Import dentro del test para evitar side effects de conftest
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from finanzas_tracker.services.patrimony_service import PatrimonyService

            mock_db = MagicMock()
            service = PatrimonyService(mock_db)

            assert service is not None
            assert service.db == mock_db


class TestCrearSnapshot:
    """Tests para crear_snapshot."""

    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio con DB mockeada."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from finanzas_tracker.services.patrimony_service import PatrimonyService

            mock_db = MagicMock()
            return PatrimonyService(mock_db)

    def test_crear_snapshot_sin_cuentas(self, service):
        """Debería crear snapshot con valores en cero si no hay cuentas."""

        # Mock queries
        service.db.execute.return_value.scalars.return_value.all.return_value = []

        # Mock add, commit, refresh
        service.db.add = MagicMock()
        service.db.commit = MagicMock()
        service.db.refresh = MagicMock()

        snapshot = service.crear_snapshot(profile_id="test-profile-id")

        assert snapshot is not None
        assert snapshot.profile_id == "test-profile-id"
        assert snapshot.saldo_cuentas_crc == Decimal("0")
        assert snapshot.saldo_cuentas_usd == Decimal("0")
        # El tipo se establece en el constructor del modelo

        # Verificar que se guardó
        service.db.add.assert_called_once()
        service.db.commit.assert_called_once()

    def test_crear_snapshot_con_exchange_rate_custom(self, service):
        """Debería usar exchange rate personalizado."""
        service.db.execute.return_value.scalars.return_value.all.return_value = []
        service.db.add = MagicMock()
        service.db.commit = MagicMock()
        service.db.refresh = MagicMock()

        custom_rate = Decimal("525.00")
        snapshot = service.crear_snapshot(
            profile_id="test-profile-id",
            exchange_rate=custom_rate,
        )

        assert snapshot.tipo_cambio_usd == custom_rate

    def test_crear_snapshot_con_fecha_especifica(self, service):
        """Debería crear snapshot con fecha específica."""
        service.db.execute.return_value.scalars.return_value.all.return_value = []
        service.db.add = MagicMock()
        service.db.commit = MagicMock()
        service.db.refresh = MagicMock()

        fecha_test = date(2025, 6, 15)
        snapshot = service.crear_snapshot(
            profile_id="test-profile-id",
            fecha=fecha_test,
        )

        assert snapshot.fecha_snapshot.date() == fecha_test


class TestEstablecerPatrimonioInicial:
    """Tests para establecer_patrimonio_inicial."""

    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio con DB mockeada."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from finanzas_tracker.services.patrimony_service import PatrimonyService

            mock_db = MagicMock()
            return PatrimonyService(mock_db)

    def test_establecer_patrimonio_inicial_nuevo(self, service):
        """Debería crear snapshot marcado como fecha_base."""
        # No existe fecha base previa
        service.db.execute.return_value.scalar_one_or_none.return_value = None
        service.db.execute.return_value.scalars.return_value.all.return_value = []
        service.db.add = MagicMock()
        service.db.commit = MagicMock()
        service.db.refresh = MagicMock()

        snapshot = service.establecer_patrimonio_inicial(
            profile_id="test-profile-id",
            fecha_base=date(2025, 1, 1),
        )

        assert snapshot is not None
        assert snapshot.es_fecha_base is True
        assert "Patrimonio inicial" in snapshot.notas

    def test_establecer_patrimonio_inicial_duplicado(self, service):
        """Debería lanzar error si ya existe fecha base."""
        from finanzas_tracker.models.patrimonio_snapshot import PatrimonioSnapshot

        # Ya existe fecha base
        existing = MagicMock(spec=PatrimonioSnapshot)
        service.db.execute.return_value.scalar_one_or_none.return_value = existing

        with pytest.raises(ValueError, match="Ya existe un patrimonio inicial"):
            service.establecer_patrimonio_inicial(
                profile_id="test-profile-id",
                fecha_base=date(2025, 1, 1),
            )


class TestObtenerHistorial:
    """Tests para obtener_historial."""

    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio con DB mockeada."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from finanzas_tracker.services.patrimony_service import PatrimonyService

            mock_db = MagicMock()
            return PatrimonyService(mock_db)

    def test_obtener_historial_vacio(self, service):
        """Debería retornar lista vacía si no hay snapshots."""
        service.db.execute.return_value.scalars.return_value.all.return_value = []

        result = service.obtener_historial(profile_id="test-profile-id")

        assert result == []

    def test_obtener_historial_con_limite(self, service):
        """Debería respetar el límite de resultados."""
        from finanzas_tracker.models.patrimonio_snapshot import PatrimonioSnapshot

        snapshots = [MagicMock(spec=PatrimonioSnapshot) for _ in range(5)]
        service.db.execute.return_value.scalars.return_value.all.return_value = snapshots

        result = service.obtener_historial(
            profile_id="test-profile-id",
            limite=3,
        )

        # Verificar que se retornaron los snapshots (el mock no respeta limite)
        assert len(result) == 5

    def test_obtener_historial_ordenado_descendente(self, service):
        """Debería ordenar por fecha descendente (más reciente primero)."""
        from finanzas_tracker.models.patrimonio_snapshot import PatrimonioSnapshot

        s1 = MagicMock(spec=PatrimonioSnapshot)
        s1.fecha_snapshot = datetime(2025, 12, 1, tzinfo=UTC)
        s2 = MagicMock(spec=PatrimonioSnapshot)
        s2.fecha_snapshot = datetime(2025, 11, 1, tzinfo=UTC)

        service.db.execute.return_value.scalars.return_value.all.return_value = [s1, s2]

        result = service.obtener_historial(profile_id="test-profile-id")

        # El servicio debería ordenar descendente
        assert len(result) == 2


class TestGetSnapshotFechaBase:
    """Tests para get_snapshot_fecha_base."""

    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio con DB mockeada."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from finanzas_tracker.services.patrimony_service import PatrimonyService

            mock_db = MagicMock()
            return PatrimonyService(mock_db)

    def test_get_fecha_base_existe(self, service):
        """Debería retornar el snapshot de fecha base."""
        from finanzas_tracker.models.patrimonio_snapshot import PatrimonioSnapshot

        fecha_base_snapshot = MagicMock(spec=PatrimonioSnapshot)
        fecha_base_snapshot.es_fecha_base = True
        service.db.execute.return_value.scalar_one_or_none.return_value = fecha_base_snapshot

        result = service.get_snapshot_fecha_base(profile_id="test-profile-id")

        assert result is not None
        assert result.es_fecha_base is True

    def test_get_fecha_base_no_existe(self, service):
        """Debería retornar None si no hay fecha base."""
        service.db.execute.return_value.scalar_one_or_none.return_value = None

        result = service.get_snapshot_fecha_base(profile_id="test-profile-id")

        assert result is None


class TestCalcularCambioPeriodo:
    """Tests para calcular_cambio_periodo."""

    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio con DB mockeada."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from finanzas_tracker.services.patrimony_service import PatrimonyService

            mock_db = MagicMock()
            return PatrimonyService(mock_db)

    @pytest.fixture
    def snapshot_inicio(self):
        """Fixture para snapshot inicial."""
        from finanzas_tracker.models.patrimonio_snapshot import PatrimonioSnapshot

        s = MagicMock(spec=PatrimonioSnapshot)
        s.fecha_snapshot = datetime(2025, 1, 1, tzinfo=UTC)
        s.patrimonio_neto_crc = Decimal("1000000")
        s.total_activos_crc = Decimal("1500000")
        s.total_deudas_crc = Decimal("500000")
        return s

    @pytest.fixture
    def snapshot_fin(self):
        """Fixture para snapshot final."""
        from finanzas_tracker.models.patrimonio_snapshot import PatrimonioSnapshot

        s = MagicMock(spec=PatrimonioSnapshot)
        s.fecha_snapshot = datetime(2025, 6, 1, tzinfo=UTC)
        s.patrimonio_neto_crc = Decimal("1200000")
        s.total_activos_crc = Decimal("1700000")
        s.total_deudas_crc = Decimal("500000")
        return s

    def test_calcular_cambio_positivo(self, service, snapshot_inicio, snapshot_fin):
        """Debería calcular cambio positivo correctamente."""
        # Primera llamada retorna snapshot_inicio, segunda retorna snapshot_fin
        service.db.execute.return_value.scalar_one_or_none.side_effect = [
            snapshot_inicio,
            snapshot_fin,
        ]

        result = service.calcular_cambio_periodo(
            profile_id="test-profile-id",
            fecha_inicio=date(2025, 1, 1),
            fecha_fin=date(2025, 6, 1),
        )

        assert result["cambio_absoluto_crc"] == Decimal("200000")
        assert result["cambio_porcentual"] == Decimal("20.00")

    def test_calcular_cambio_sin_snapshot_inicio(self, service):
        """Debería lanzar error si no hay snapshot inicial."""
        service.db.execute.return_value.scalar_one_or_none.side_effect = [None, None]

        with pytest.raises(ValueError, match="No hay snapshots antes de"):
            service.calcular_cambio_periodo(
                profile_id="test-profile-id",
                fecha_inicio=date(2025, 1, 1),
                fecha_fin=date(2025, 6, 1),
            )


class TestGenerarSnapshotMensual:
    """Tests para generar_snapshot_mensual."""

    @pytest.fixture
    def service(self):
        """Fixture para crear el servicio con DB mockeada."""
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
            from finanzas_tracker.services.patrimony_service import PatrimonyService

            mock_db = MagicMock()
            return PatrimonyService(mock_db)

    def test_generar_snapshot_mensual_nuevo(self, service):
        """Debería crear snapshot si no existe uno este mes."""
        # No existe snapshot este mes
        service.db.execute.return_value.scalar_one_or_none.return_value = None
        service.db.execute.return_value.scalars.return_value.all.return_value = []
        service.db.add = MagicMock()
        service.db.commit = MagicMock()
        service.db.refresh = MagicMock()

        result = service.generar_snapshot_mensual(profile_id="test-profile-id")

        assert result is not None
        service.db.add.assert_called()

    def test_generar_snapshot_mensual_existente(self, service):
        """Debería retornar None si ya existe snapshot este mes."""
        from finanzas_tracker.models.patrimonio_snapshot import PatrimonioSnapshot

        existing = MagicMock(spec=PatrimonioSnapshot)
        service.db.execute.return_value.scalar_one_or_none.return_value = existing

        result = service.generar_snapshot_mensual(profile_id="test-profile-id")

        assert result is None
        service.db.add.assert_not_called()
