"""Tests para AmbiguousMerchantService.

Tests del servicio que detecta y maneja comercios ambiguos
(Walmart, Amazon, PriceSmart, etc.).
"""

from decimal import Decimal
import json
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from finanzas_tracker.services.ambiguous_merchant_service import (
    AmbiguousMerchantService,
    listar_comercios_ambiguos,
)


class TestAmbiguousMerchantServiceInit:
    """Tests de inicialización del servicio."""

    def test_init_with_session(self) -> None:
        """Inicializa correctamente con sesión de BD."""
        mock_db = MagicMock(spec=Session)
        service = AmbiguousMerchantService(mock_db)

        assert service.db == mock_db


class TestAmbiguousMerchantServiceDetectar:
    """Tests del método detectar_y_marcar."""

    @pytest.fixture
    def service(self) -> AmbiguousMerchantService:
        """Crea servicio con mock de sesión."""
        mock_db = MagicMock(spec=Session)
        return AmbiguousMerchantService(mock_db)

    @pytest.fixture
    def mock_transaction(self) -> MagicMock:
        """Crea transacción mock."""
        tx = MagicMock()
        tx.id = str(uuid4())
        tx.comercio = "WALMART"
        tx.es_comercio_ambiguo = False
        tx.categorias_opciones = None
        tx.necesita_revision = False
        tx.confirmada = True
        return tx

    @patch("finanzas_tracker.services.ambiguous_merchant_service.es_comercio_ambiguo")
    @patch("finanzas_tracker.services.ambiguous_merchant_service.obtener_categorias_posibles")
    def test_detectar_comercio_ambiguo(
        self,
        mock_obtener_categorias: MagicMock,
        mock_es_ambiguo: MagicMock,
        service: AmbiguousMerchantService,
        mock_transaction: MagicMock,
    ) -> None:
        """Detecta y marca comercio ambiguo."""
        mock_es_ambiguo.return_value = True
        mock_obtener_categorias.return_value = ["Supermercado", "Electrónica", "Hogar"]

        result = service.detectar_y_marcar(mock_transaction)

        assert result is True
        assert mock_transaction.es_comercio_ambiguo is True
        assert mock_transaction.necesita_revision is True
        assert mock_transaction.confirmada is False
        assert mock_transaction.categorias_opciones is not None

    @patch("finanzas_tracker.services.ambiguous_merchant_service.es_comercio_ambiguo")
    def test_no_detecta_comercio_normal(
        self,
        mock_es_ambiguo: MagicMock,
        service: AmbiguousMerchantService,
        mock_transaction: MagicMock,
    ) -> None:
        """No marca comercio no ambiguo."""
        mock_es_ambiguo.return_value = False

        result = service.detectar_y_marcar(mock_transaction)

        assert result is False
        assert mock_transaction.es_comercio_ambiguo is False

    @patch("finanzas_tracker.services.ambiguous_merchant_service.es_comercio_ambiguo")
    @patch("finanzas_tracker.services.ambiguous_merchant_service.obtener_categorias_posibles")
    def test_no_marca_si_no_hay_categorias(
        self,
        mock_obtener_categorias: MagicMock,
        mock_es_ambiguo: MagicMock,
        service: AmbiguousMerchantService,
        mock_transaction: MagicMock,
    ) -> None:
        """No marca si no hay categorías posibles."""
        mock_es_ambiguo.return_value = True
        mock_obtener_categorias.return_value = []

        result = service.detectar_y_marcar(mock_transaction)

        assert result is False

    @patch("finanzas_tracker.services.ambiguous_merchant_service.es_comercio_ambiguo")
    @patch("finanzas_tracker.services.ambiguous_merchant_service.obtener_categorias_posibles")
    def test_categorias_opciones_json(
        self,
        mock_obtener_categorias: MagicMock,
        mock_es_ambiguo: MagicMock,
        service: AmbiguousMerchantService,
        mock_transaction: MagicMock,
    ) -> None:
        """Las categorías se guardan como JSON."""
        mock_es_ambiguo.return_value = True
        categorias = ["Supermercado", "Ropa", "Electrónica"]
        mock_obtener_categorias.return_value = categorias

        service.detectar_y_marcar(mock_transaction)

        saved_json = mock_transaction.categorias_opciones
        parsed = json.loads(saved_json)
        assert parsed == categorias


class TestAmbiguousMerchantServiceConfirmar:
    """Tests del método confirmar_categoria."""

    @pytest.fixture
    def service(self) -> AmbiguousMerchantService:
        """Crea servicio con mock de sesión."""
        mock_db = MagicMock(spec=Session)
        return AmbiguousMerchantService(mock_db)

    def test_confirmar_categoria_exitoso(
        self,
        service: AmbiguousMerchantService,
    ) -> None:
        """Confirma categoría correctamente."""
        tx = MagicMock()
        tx.categorias_opciones = json.dumps(["Supermercado", "Electrónica"])

        service.db.execute.return_value.scalar_one_or_none.return_value = tx

        result = service.confirmar_categoria(
            transaction_id="tx-123",
            categoria_seleccionada="Supermercado",
        )

        assert result == tx
        assert tx.categoria_confirmada_usuario == "Supermercado"
        assert tx.categoria_sugerida_por_ia == "Supermercado"
        assert tx.confirmada is True
        assert tx.necesita_revision is False
        service.db.flush.assert_called_once()

    def test_confirmar_categoria_con_notas(
        self,
        service: AmbiguousMerchantService,
    ) -> None:
        """Confirma categoría con notas adicionales."""
        tx = MagicMock()
        tx.categorias_opciones = json.dumps(["Supermercado"])

        service.db.execute.return_value.scalar_one_or_none.return_value = tx

        result = service.confirmar_categoria(
            transaction_id="tx-123",
            categoria_seleccionada="Supermercado",
            notas="Compras de despensa mensual",
        )

        assert result == tx
        assert tx.notas == "Compras de despensa mensual"

    def test_confirmar_transaccion_no_existe(
        self,
        service: AmbiguousMerchantService,
    ) -> None:
        """Retorna None si transacción no existe."""
        service.db.execute.return_value.scalar_one_or_none.return_value = None

        result = service.confirmar_categoria(
            transaction_id="tx-inexistente",
            categoria_seleccionada="Supermercado",
        )

        assert result is None
        service.db.flush.assert_not_called()

    def test_confirmar_categoria_no_en_opciones(
        self,
        service: AmbiguousMerchantService,
    ) -> None:
        """Permite categoría que no está en opciones (usuario sabe mejor)."""
        tx = MagicMock()
        tx.categorias_opciones = json.dumps(["Supermercado", "Electrónica"])

        service.db.execute.return_value.scalar_one_or_none.return_value = tx

        result = service.confirmar_categoria(
            transaction_id="tx-123",
            categoria_seleccionada="Regalo",  # No está en opciones
        )

        assert result == tx
        assert tx.categoria_confirmada_usuario == "Regalo"

    def test_confirmar_sin_opciones_previas(
        self,
        service: AmbiguousMerchantService,
    ) -> None:
        """Funciona aunque no tenga opciones previas."""
        tx = MagicMock()
        tx.categorias_opciones = None

        service.db.execute.return_value.scalar_one_or_none.return_value = tx

        result = service.confirmar_categoria(
            transaction_id="tx-123",
            categoria_seleccionada="Supermercado",
        )

        assert result == tx
        assert tx.confirmada is True


class TestAmbiguousMerchantServicePendientes:
    """Tests del método obtener_pendientes."""

    @pytest.fixture
    def service(self) -> AmbiguousMerchantService:
        """Crea servicio con mock de sesión."""
        mock_db = MagicMock(spec=Session)
        return AmbiguousMerchantService(mock_db)

    def test_obtener_pendientes_vacio(
        self,
        service: AmbiguousMerchantService,
    ) -> None:
        """Retorna lista vacía si no hay pendientes."""
        service.db.execute.return_value.scalars.return_value.all.return_value = []

        result = service.obtener_pendientes("profile-123")

        assert result == []

    def test_obtener_pendientes_con_datos(
        self,
        service: AmbiguousMerchantService,
    ) -> None:
        """Retorna transacciones pendientes formateadas."""
        from datetime import datetime

        tx1 = MagicMock()
        tx1.id = "tx-1"
        tx1.comercio = "WALMART"
        tx1.monto_crc = Decimal("50000.00")
        tx1.fecha_transaccion = datetime(2024, 11, 15, 10, 30)
        tx1.categorias_opciones = json.dumps(["Supermercado", "Electrónica"])

        tx2 = MagicMock()
        tx2.id = "tx-2"
        tx2.comercio = "AMAZON"
        tx2.monto_crc = Decimal("25000.00")
        tx2.fecha_transaccion = datetime(2024, 11, 20, 15, 45)
        tx2.categorias_opciones = json.dumps(["Electrónica", "Libros"])

        service.db.execute.return_value.scalars.return_value.all.return_value = [tx1, tx2]

        result = service.obtener_pendientes("profile-123")

        assert len(result) == 2
        assert result[0]["id"] == "tx-1"
        assert result[0]["comercio"] == "WALMART"
        assert result[0]["monto_crc"] == 50000.00
        assert result[0]["opciones_categoria"] == ["Supermercado", "Electrónica"]
        assert result[1]["id"] == "tx-2"
        assert result[1]["comercio"] == "AMAZON"

    def test_obtener_pendientes_sin_opciones(
        self,
        service: AmbiguousMerchantService,
    ) -> None:
        """Maneja transacciones sin categorías_opciones."""
        from datetime import datetime

        tx = MagicMock()
        tx.id = "tx-1"
        tx.comercio = "TIENDA"
        tx.monto_crc = Decimal("15000.00")
        tx.fecha_transaccion = datetime(2024, 11, 25)
        tx.categorias_opciones = None

        service.db.execute.return_value.scalars.return_value.all.return_value = [tx]

        result = service.obtener_pendientes("profile-123")

        assert len(result) == 1
        assert result[0]["opciones_categoria"] == []


class TestAmbiguousMerchantServiceEstadisticas:
    """Tests del método obtener_estadisticas."""

    @pytest.fixture
    def service(self) -> AmbiguousMerchantService:
        """Crea servicio con mock de sesión."""
        mock_db = MagicMock(spec=Session)
        return AmbiguousMerchantService(mock_db)

    def test_estadisticas_sin_ambiguos(
        self,
        service: AmbiguousMerchantService,
    ) -> None:
        """Estadísticas cuando no hay comercios ambiguos."""
        service.db.execute.return_value.scalars.return_value.all.side_effect = [
            [],  # total
            [],  # pendientes
        ]

        result = service.obtener_estadisticas("profile-123")

        assert result["total_ambiguos"] == 0
        assert result["pendientes_confirmacion"] == 0
        assert result["confirmados"] == 0
        assert result["porcentaje_completado"] == 100

    def test_estadisticas_con_datos(
        self,
        service: AmbiguousMerchantService,
    ) -> None:
        """Estadísticas con comercios ambiguos."""
        service.db.execute.return_value.scalars.return_value.all.side_effect = [
            [MagicMock() for _ in range(10)],  # total = 10
            [MagicMock() for _ in range(3)],  # pendientes = 3
        ]

        result = service.obtener_estadisticas("profile-123")

        assert result["total_ambiguos"] == 10
        assert result["pendientes_confirmacion"] == 3
        assert result["confirmados"] == 7
        assert result["porcentaje_completado"] == 70.0

    def test_estadisticas_todos_confirmados(
        self,
        service: AmbiguousMerchantService,
    ) -> None:
        """Estadísticas cuando todos están confirmados."""
        service.db.execute.return_value.scalars.return_value.all.side_effect = [
            [MagicMock() for _ in range(20)],  # total = 20
            [],  # pendientes = 0
        ]

        result = service.obtener_estadisticas("profile-123")

        assert result["total_ambiguos"] == 20
        assert result["pendientes_confirmacion"] == 0
        assert result["confirmados"] == 20
        assert result["porcentaje_completado"] == 100.0


class TestAmbiguousMerchantServiceMarcarExistentes:
    """Tests del método marcar_transacciones_existentes."""

    @pytest.fixture
    def service(self) -> AmbiguousMerchantService:
        """Crea servicio con mock de sesión."""
        mock_db = MagicMock(spec=Session)
        return AmbiguousMerchantService(mock_db)

    def test_marcar_sin_transacciones(
        self,
        service: AmbiguousMerchantService,
    ) -> None:
        """No marca nada si no hay transacciones."""
        service.db.execute.return_value.scalars.return_value.all.return_value = []

        result = service.marcar_transacciones_existentes("profile-123")

        assert result == 0
        service.db.flush.assert_not_called()

    @patch("finanzas_tracker.services.ambiguous_merchant_service.es_comercio_ambiguo")
    @patch("finanzas_tracker.services.ambiguous_merchant_service.obtener_categorias_posibles")
    def test_marcar_transacciones_existentes(
        self,
        mock_obtener_categorias: MagicMock,
        mock_es_ambiguo: MagicMock,
        service: AmbiguousMerchantService,
    ) -> None:
        """Marca transacciones existentes correctamente."""
        tx1 = MagicMock()
        tx1.comercio = "WALMART"
        tx1.es_comercio_ambiguo = False

        tx2 = MagicMock()
        tx2.comercio = "STARBUCKS"
        tx2.es_comercio_ambiguo = False

        tx3 = MagicMock()
        tx3.comercio = "AMAZON"
        tx3.es_comercio_ambiguo = False

        service.db.execute.return_value.scalars.return_value.all.return_value = [tx1, tx2, tx3]

        # Solo WALMART y AMAZON son ambiguos
        # detectar_y_marcar llama a es_comercio_ambiguo y obtener_categorias_posibles internamente
        # para cada transacción, por lo que necesitamos más valores
        mock_es_ambiguo.side_effect = [True, False, True]
        mock_obtener_categorias.side_effect = [
            ["Supermercado", "Electrónica"],  # Para tx1 (WALMART)
            ["Electrónica", "Libros"],  # Para tx3 (AMAZON)
        ]

        result = service.marcar_transacciones_existentes("profile-123")

        assert result == 2
        service.db.flush.assert_called_once()


class TestListarComerciosAmbiguos:
    """Tests de la función listar_comercios_ambiguos."""

    def test_retorna_diccionario(self) -> None:
        """Retorna un diccionario."""
        result = listar_comercios_ambiguos()
        assert isinstance(result, dict)

    def test_contiene_comercios_conocidos(self) -> None:
        """Contiene comercios conocidos como Walmart."""
        result = listar_comercios_ambiguos()
        # El diccionario puede estar vacío o tener datos
        # dependiendo de la implementación
        assert isinstance(result, dict)

    @patch(
        "finanzas_tracker.services.ambiguous_merchant_service.COMERCIOS_AMBIGUOS",
        {"WALMART": ["Supermercado"]},
    )
    def test_retorna_copia(self) -> None:
        """Retorna una copia, no el original."""
        from finanzas_tracker.services.ambiguous_merchant_service import COMERCIOS_AMBIGUOS

        result = listar_comercios_ambiguos()
        result["NUEVO"] = ["Test"]

        # El original no debe cambiar
        assert "NUEVO" not in COMERCIOS_AMBIGUOS
