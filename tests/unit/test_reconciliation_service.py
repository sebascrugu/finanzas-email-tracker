"""Tests para ReconciliationService.

Tests del servicio de reconciliación de estados de cuenta.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from finanzas_tracker.services.reconciliation_service import (
    MatchStatus,
    ReconciliationMatch,
    ReconciliationResult,
    ReconciliationService,
)


class TestMatchStatus:
    """Tests para el enum MatchStatus."""

    def test_all_statuses_defined(self) -> None:
        """Todos los estados de match están definidos."""
        assert MatchStatus.MATCHED.value == "matched"
        assert MatchStatus.AMOUNT_MISMATCH.value == "amount_mismatch"
        assert MatchStatus.ONLY_IN_PDF.value == "only_in_pdf"
        assert MatchStatus.ONLY_IN_SYSTEM.value == "only_in_system"

    def test_is_string_enum(self) -> None:
        """MatchStatus es un string enum."""
        assert isinstance(MatchStatus.MATCHED.value, str)


class TestReconciliationMatch:
    """Tests para el dataclass ReconciliationMatch."""

    def test_create_matched(self) -> None:
        """Crea match exitoso."""
        match = ReconciliationMatch(
            status=MatchStatus.MATCHED,
            pdf_transaction={"fecha": "2024-11-15", "comercio": "STARBUCKS", "monto": 5000},
            system_transaction=MagicMock(),
            confidence=0.95,
        )

        assert match.status == MatchStatus.MATCHED
        assert match.confidence == 0.95
        assert match.amount_difference is None

    def test_create_amount_mismatch(self) -> None:
        """Crea match con diferencia de monto."""
        match = ReconciliationMatch(
            status=MatchStatus.AMOUNT_MISMATCH,
            pdf_transaction={"fecha": "2024-11-15", "comercio": "UBER", "monto": 5500},
            system_transaction=MagicMock(),
            amount_difference=Decimal("500.00"),
            confidence=0.8,
        )

        assert match.status == MatchStatus.AMOUNT_MISMATCH
        assert match.amount_difference == Decimal("500.00")

    def test_create_only_in_pdf(self) -> None:
        """Crea transacción solo en PDF."""
        match = ReconciliationMatch(
            status=MatchStatus.ONLY_IN_PDF,
            pdf_transaction={"fecha": "2024-11-20", "comercio": "EFECTIVO", "monto": 10000},
        )

        assert match.status == MatchStatus.ONLY_IN_PDF
        assert match.system_transaction is None

    def test_create_only_in_system(self) -> None:
        """Crea transacción solo en sistema."""
        match = ReconciliationMatch(
            status=MatchStatus.ONLY_IN_SYSTEM,
            system_transaction=MagicMock(),
        )

        assert match.status == MatchStatus.ONLY_IN_SYSTEM
        assert match.pdf_transaction is None

    def test_to_dict_matched(self) -> None:
        """to_dict para match exitoso."""
        sys_tx = MagicMock()
        sys_tx.id = "tx-123"
        sys_tx.fecha_transaccion = date(2024, 11, 15)
        sys_tx.comercio_original = "STARBUCKS"
        sys_tx.monto_original = Decimal("5000.00")

        match = ReconciliationMatch(
            status=MatchStatus.MATCHED,
            pdf_transaction={"fecha": "2024-11-15", "comercio": "STARBUCKS", "monto": 5000},
            system_transaction=sys_tx,
            confidence=0.95,
        )

        result = match.to_dict()

        assert result["status"] == "matched"
        assert result["confidence"] == 0.95
        assert result["pdf"]["comercio"] == "STARBUCKS"
        assert result["system"]["id"] == "tx-123"

    def test_to_dict_with_amount_difference(self) -> None:
        """to_dict incluye diferencia de monto."""
        match = ReconciliationMatch(
            status=MatchStatus.AMOUNT_MISMATCH,
            pdf_transaction={"fecha": "2024-11-15", "comercio": "UBER", "monto": 5500},
            system_transaction=MagicMock(
                id="tx-1",
                fecha_transaccion=date(2024, 11, 15),
                comercio_original="UBER",
                monto_original=Decimal("5000.00"),
            ),
            amount_difference=Decimal("500.00"),
        )

        result = match.to_dict()

        assert result["amount_difference"] == 500.00

    def test_to_dict_only_pdf(self) -> None:
        """to_dict para solo en PDF."""
        match = ReconciliationMatch(
            status=MatchStatus.ONLY_IN_PDF,
            pdf_transaction={"fecha": "2024-11-20", "comercio": "EFECTIVO", "monto": 10000},
        )

        result = match.to_dict()

        assert result["status"] == "only_in_pdf"
        assert "pdf" in result
        assert "system" not in result


class TestReconciliationResult:
    """Tests para el dataclass ReconciliationResult."""

    def test_create_empty_result(self) -> None:
        """Crea resultado vacío."""
        result = ReconciliationResult(
            periodo_inicio=date(2024, 11, 1),
            periodo_fin=date(2024, 11, 30),
        )

        assert result.total_pdf == 0
        assert result.total_system == 0
        assert result.matched == []
        assert result.amount_mismatches == []
        assert result.only_in_pdf == []
        assert result.only_in_system == []

    def test_match_rate_zero(self) -> None:
        """match_rate es 0 cuando total_pdf es 0."""
        result = ReconciliationResult(
            periodo_inicio=date(2024, 11, 1),
            periodo_fin=date(2024, 11, 30),
            total_pdf=0,
        )

        assert result.match_rate == 0.0

    def test_match_rate_calculation(self) -> None:
        """match_rate se calcula correctamente."""
        matched = [ReconciliationMatch(status=MatchStatus.MATCHED) for _ in range(8)]

        result = ReconciliationResult(
            periodo_inicio=date(2024, 11, 1),
            periodo_fin=date(2024, 11, 30),
            total_pdf=10,
            matched=matched,
        )

        assert result.match_rate == 80.0

    def test_has_issues_false(self) -> None:
        """has_issues es False cuando todo coincide."""
        result = ReconciliationResult(
            periodo_inicio=date(2024, 11, 1),
            periodo_fin=date(2024, 11, 30),
            matched=[ReconciliationMatch(status=MatchStatus.MATCHED)],
        )

        assert result.has_issues is False

    def test_has_issues_true_amount_mismatch(self) -> None:
        """has_issues es True cuando hay diferencias de monto."""
        result = ReconciliationResult(
            periodo_inicio=date(2024, 11, 1),
            periodo_fin=date(2024, 11, 30),
            amount_mismatches=[ReconciliationMatch(status=MatchStatus.AMOUNT_MISMATCH)],
        )

        assert result.has_issues is True

    def test_has_issues_true_only_in_pdf(self) -> None:
        """has_issues es True cuando hay transacciones solo en PDF."""
        result = ReconciliationResult(
            periodo_inicio=date(2024, 11, 1),
            periodo_fin=date(2024, 11, 30),
            only_in_pdf=[ReconciliationMatch(status=MatchStatus.ONLY_IN_PDF)],
        )

        assert result.has_issues is True

    def test_has_issues_true_only_in_system(self) -> None:
        """has_issues es True cuando hay transacciones solo en sistema."""
        result = ReconciliationResult(
            periodo_inicio=date(2024, 11, 1),
            periodo_fin=date(2024, 11, 30),
            only_in_system=[ReconciliationMatch(status=MatchStatus.ONLY_IN_SYSTEM)],
        )

        assert result.has_issues is True

    def test_to_dict_structure(self) -> None:
        """to_dict retorna estructura correcta."""
        result = ReconciliationResult(
            periodo_inicio=date(2024, 11, 1),
            periodo_fin=date(2024, 11, 30),
            total_pdf=10,
            total_system=8,
        )

        data = result.to_dict()

        assert "periodo" in data
        assert data["periodo"]["inicio"] == "2024-11-01"
        assert data["periodo"]["fin"] == "2024-11-30"
        assert "resumen" in data
        assert data["resumen"]["total_pdf"] == 10
        assert data["resumen"]["total_sistema"] == 8
        assert "tiene_problemas" in data
        assert "detalles" in data


class TestReconciliationServiceInit:
    """Tests de inicialización del servicio."""

    def test_init_with_session(self) -> None:
        """Inicializa correctamente con sesión de BD."""
        mock_db = MagicMock(spec=Session)
        service = ReconciliationService(mock_db)

        assert service.db == mock_db


class TestReconciliationServiceReconcile:
    """Tests del método reconcile."""

    @pytest.fixture
    def service(self) -> ReconciliationService:
        """Crea servicio con mock de sesión."""
        mock_db = MagicMock(spec=Session)
        return ReconciliationService(mock_db)

    @pytest.fixture
    def pdf_transactions(self) -> list[dict]:
        """Transacciones de ejemplo del PDF."""
        return [
            {"fecha": "2024-11-05", "comercio": "STARBUCKS", "monto": 5000},
            {"fecha": "2024-11-10", "comercio": "UBER EATS", "monto": 12500},
            {"fecha": "2024-11-15", "comercio": "WALMART", "monto": 45000},
        ]

    def test_reconcile_empty_pdf(
        self,
        service: ReconciliationService,
    ) -> None:
        """Reconcilia PDF vacío."""
        with patch.object(service, "_get_system_transactions", return_value=[]):
            result = service.reconcile(
                profile_id="profile-123",
                pdf_transactions=[],
                periodo_inicio=date(2024, 11, 1),
                periodo_fin=date(2024, 11, 30),
            )

        assert result.total_pdf == 0
        assert result.total_system == 0
        assert len(result.matched) == 0

    def test_reconcile_empty_system(
        self,
        service: ReconciliationService,
        pdf_transactions: list[dict],
    ) -> None:
        """Reconcilia cuando no hay transacciones en sistema."""
        with patch.object(service, "_get_system_transactions", return_value=[]):
            result = service.reconcile(
                profile_id="profile-123",
                pdf_transactions=pdf_transactions,
                periodo_inicio=date(2024, 11, 1),
                periodo_fin=date(2024, 11, 30),
            )

        assert result.total_pdf == 3
        assert result.total_system == 0
        assert len(result.only_in_pdf) == 3

    def test_reconcile_perfect_match(
        self,
        service: ReconciliationService,
    ) -> None:
        """Reconcilia con coincidencias perfectas."""
        pdf_tx = [
            {"fecha": date(2024, 11, 5), "comercio": "STARBUCKS", "monto": 5000},
        ]

        sys_tx = MagicMock()
        sys_tx.id = "tx-1"
        sys_tx.fecha_transaccion = date(2024, 11, 5)
        sys_tx.comercio_original = "STARBUCKS"
        sys_tx.monto_original = Decimal("5000.00")

        with patch.object(service, "_get_system_transactions", return_value=[sys_tx]):
            with patch.object(service, "_find_best_match", return_value=(sys_tx, 0.95, None)):
                result = service.reconcile(
                    profile_id="profile-123",
                    pdf_transactions=pdf_tx,
                    periodo_inicio=date(2024, 11, 1),
                    periodo_fin=date(2024, 11, 30),
                )

        assert len(result.matched) == 1
        assert len(result.only_in_pdf) == 0

    def test_reconcile_amount_mismatch(
        self,
        service: ReconciliationService,
    ) -> None:
        """Detecta diferencias de monto."""
        pdf_tx = [
            {"fecha": date(2024, 11, 10), "comercio": "UBER", "monto": 5500},
        ]

        sys_tx = MagicMock()
        sys_tx.id = "tx-1"
        sys_tx.fecha_transaccion = date(2024, 11, 10)
        sys_tx.comercio_original = "UBER"
        sys_tx.monto_original = Decimal("5000.00")

        with patch.object(service, "_get_system_transactions", return_value=[sys_tx]):
            with patch.object(
                service, "_find_best_match", return_value=(sys_tx, 0.8, Decimal("500.00"))
            ):
                result = service.reconcile(
                    profile_id="profile-123",
                    pdf_transactions=pdf_tx,
                    periodo_inicio=date(2024, 11, 1),
                    periodo_fin=date(2024, 11, 30),
                )

        assert len(result.amount_mismatches) == 1
        assert result.amount_mismatches[0].amount_difference == Decimal("500.00")

    def test_reconcile_only_in_system(
        self,
        service: ReconciliationService,
    ) -> None:
        """Detecta transacciones solo en sistema."""
        sys_tx = MagicMock()
        sys_tx.id = "tx-orphan"
        sys_tx.fecha_transaccion = date(2024, 11, 20)
        sys_tx.comercio_original = "SPOTIFY"
        sys_tx.monto_original = Decimal("5000.00")

        with patch.object(service, "_get_system_transactions", return_value=[sys_tx]):
            result = service.reconcile(
                profile_id="profile-123",
                pdf_transactions=[],
                periodo_inicio=date(2024, 11, 1),
                periodo_fin=date(2024, 11, 30),
            )

        assert len(result.only_in_system) == 1
        assert result.only_in_system[0].system_transaction.id == "tx-orphan"

    def test_reconcile_mixed_results(
        self,
        service: ReconciliationService,
    ) -> None:
        """Reconcilia con resultados mixtos."""
        pdf_txs = [
            {"fecha": date(2024, 11, 5), "comercio": "STARBUCKS", "monto": 5000},
            {"fecha": date(2024, 11, 15), "comercio": "EFECTIVO", "monto": 10000},
        ]

        sys_tx1 = MagicMock()
        sys_tx1.id = "tx-1"
        sys_tx1.fecha_transaccion = date(2024, 11, 5)
        sys_tx1.comercio_original = "STARBUCKS"
        sys_tx1.monto_original = Decimal("5000.00")

        sys_tx2 = MagicMock()
        sys_tx2.id = "tx-2"
        sys_tx2.fecha_transaccion = date(2024, 11, 20)
        sys_tx2.comercio_original = "NETFLIX"
        sys_tx2.monto_original = Decimal("8000.00")

        def mock_find_match(pdf_tx, sys_txns, matched, tol_days, tol_amount):
            if pdf_tx.get("comercio") == "STARBUCKS":
                return (sys_tx1, 0.95, None)
            return None

        with patch.object(service, "_get_system_transactions", return_value=[sys_tx1, sys_tx2]):
            with patch.object(service, "_find_best_match", side_effect=mock_find_match):
                result = service.reconcile(
                    profile_id="profile-123",
                    pdf_transactions=pdf_txs,
                    periodo_inicio=date(2024, 11, 1),
                    periodo_fin=date(2024, 11, 30),
                )

        assert len(result.matched) == 1  # STARBUCKS
        assert len(result.only_in_pdf) == 1  # EFECTIVO
        assert len(result.only_in_system) == 1  # NETFLIX


class TestReconciliationServiceGetSystemTransactions:
    """Tests del método _get_system_transactions."""

    @pytest.fixture
    def service(self) -> ReconciliationService:
        """Crea servicio con mock de sesión."""
        mock_db = MagicMock(spec=Session)
        return ReconciliationService(mock_db)

    def test_get_system_transactions_empty(
        self,
        service: ReconciliationService,
    ) -> None:
        """Retorna lista vacía cuando no hay transacciones."""
        service.db.execute.return_value.scalars.return_value.all.return_value = []

        result = service._get_system_transactions(
            profile_id="profile-123",
            fecha_inicio=date(2024, 11, 1),
            fecha_fin=date(2024, 11, 30),
        )

        assert result == []

    def test_get_system_transactions_filters_correctly(
        self,
        service: ReconciliationService,
    ) -> None:
        """Filtra transacciones correctamente."""
        mock_txs = [MagicMock(), MagicMock()]
        service.db.execute.return_value.scalars.return_value.all.return_value = mock_txs

        result = service._get_system_transactions(
            profile_id="profile-123",
            fecha_inicio=date(2024, 11, 1),
            fecha_fin=date(2024, 11, 30),
        )

        assert len(result) == 2
        service.db.execute.assert_called_once()


class TestReconciliationServiceFindBestMatch:
    """Tests del método _find_best_match."""

    @pytest.fixture
    def service(self) -> ReconciliationService:
        """Crea servicio con mock de sesión."""
        mock_db = MagicMock(spec=Session)
        return ReconciliationService(mock_db)

    @pytest.fixture
    def system_transaction(self) -> MagicMock:
        """Crea transacción del sistema mock."""
        tx = MagicMock()
        tx.id = "tx-1"
        tx.fecha_transaccion = date(2024, 11, 15)
        tx.comercio_original = "STARBUCKS"
        tx.monto_original = Decimal("5000.00")
        return tx

    def test_find_best_match_no_candidates(
        self,
        service: ReconciliationService,
    ) -> None:
        """Retorna None cuando no hay candidatos."""
        pdf_tx = {"fecha": "2024-11-15", "comercio": "STARBUCKS", "monto": 5000}

        result = service._find_best_match(
            pdf_tx=pdf_tx,
            system_txns=[],
            already_matched=set(),
            tolerance_days=2,
            tolerance_amount=Decimal("100"),
        )

        assert result is None

    def test_find_best_match_skips_already_matched(
        self,
        service: ReconciliationService,
        system_transaction: MagicMock,
    ) -> None:
        """Omite transacciones ya matcheadas."""
        pdf_tx = {"fecha": "2024-11-15", "comercio": "STARBUCKS", "monto": 5000}

        result = service._find_best_match(
            pdf_tx=pdf_tx,
            system_txns=[system_transaction],
            already_matched={"tx-1"},  # Ya matcheada
            tolerance_days=2,
            tolerance_amount=Decimal("100"),
        )

        assert result is None

    def test_find_best_match_no_fecha(
        self,
        service: ReconciliationService,
        system_transaction: MagicMock,
    ) -> None:
        """Retorna None si PDF no tiene fecha."""
        pdf_tx = {"comercio": "STARBUCKS", "monto": 5000}  # Sin fecha

        result = service._find_best_match(
            pdf_tx=pdf_tx,
            system_txns=[system_transaction],
            already_matched=set(),
            tolerance_days=2,
            tolerance_amount=Decimal("100"),
        )

        assert result is None


class TestReconciliationResultToDict:
    """Tests adicionales para to_dict de ReconciliationResult."""

    def test_to_dict_limits_matched_details(self) -> None:
        """to_dict limita detalles de matched a 10."""
        matched = [
            ReconciliationMatch(
                status=MatchStatus.MATCHED,
                pdf_transaction={"fecha": "2024-11-15", "comercio": f"TIENDA-{i}", "monto": 1000},
            )
            for i in range(15)
        ]

        result = ReconciliationResult(
            periodo_inicio=date(2024, 11, 1),
            periodo_fin=date(2024, 11, 30),
            matched=matched,
        )

        data = result.to_dict()

        # Solo primeros 10 en detalles
        assert len(data["detalles"]["matched"]) == 10

    def test_to_dict_includes_all_problems(self) -> None:
        """to_dict incluye todos los problemas sin límite."""
        mismatches = [
            ReconciliationMatch(
                status=MatchStatus.AMOUNT_MISMATCH,
                pdf_transaction={"fecha": "2024-11-15", "comercio": f"TIENDA-{i}", "monto": 1000},
                amount_difference=Decimal("100"),
            )
            for i in range(15)
        ]

        result = ReconciliationResult(
            periodo_inicio=date(2024, 11, 1),
            periodo_fin=date(2024, 11, 30),
            amount_mismatches=mismatches,
        )

        data = result.to_dict()

        # Todos los problemas se incluyen
        assert len(data["detalles"]["amount_mismatches"]) == 15

    def test_to_dict_resumen_completeness(self) -> None:
        """to_dict incluye resumen completo."""
        result = ReconciliationResult(
            periodo_inicio=date(2024, 11, 1),
            periodo_fin=date(2024, 11, 30),
            total_pdf=100,
            total_system=95,
            matched=[ReconciliationMatch(status=MatchStatus.MATCHED) for _ in range(80)],
            amount_mismatches=[
                ReconciliationMatch(status=MatchStatus.AMOUNT_MISMATCH) for _ in range(5)
            ],
            only_in_pdf=[ReconciliationMatch(status=MatchStatus.ONLY_IN_PDF) for _ in range(15)],
            only_in_system=[
                ReconciliationMatch(status=MatchStatus.ONLY_IN_SYSTEM) for _ in range(10)
            ],
        )

        data = result.to_dict()
        resumen = data["resumen"]

        assert resumen["total_pdf"] == 100
        assert resumen["total_sistema"] == 95
        assert resumen["coinciden"] == 80
        assert resumen["diferencia_monto"] == 5
        assert resumen["solo_en_pdf"] == 15
        assert resumen["solo_en_sistema"] == 10
        assert resumen["porcentaje_match"] == 80.0
