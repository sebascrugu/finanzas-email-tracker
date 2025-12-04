"""Servicio de Patrimonio - Consolida net worth total.

Calcula el patrimonio neto combinando:
- Cuentas bancarias (Account)
- Inversiones (Investment)
- Metas de ahorro (Goal)

También gestiona snapshots de patrimonio para tracking histórico.
"""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import logging

from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from finanzas_tracker.models.account import Account
from finanzas_tracker.models.enums import (
    AccountType,
    Currency,
    GoalStatus,
)
from finanzas_tracker.models.goal import Goal
from finanzas_tracker.models.investment import Investment
from finanzas_tracker.models.patrimonio_snapshot import PatrimonioSnapshot


logger = logging.getLogger(__name__)


@dataclass
class AssetBreakdown:
    """Desglose de activos por tipo."""

    cuentas_crc: Decimal
    cuentas_usd: Decimal
    inversiones_crc: Decimal
    inversiones_usd: Decimal
    metas_crc: Decimal
    metas_usd: Decimal

    @property
    def total_crc(self) -> Decimal:
        """Total en colones."""
        return self.cuentas_crc + self.inversiones_crc + self.metas_crc

    @property
    def total_usd(self) -> Decimal:
        """Total en dólares."""
        return self.cuentas_usd + self.inversiones_usd + self.metas_usd


@dataclass
class NetWorthSummary:
    """Resumen de patrimonio neto."""

    total_crc: Decimal
    total_usd: Decimal
    total_crc_equivalente: Decimal  # USD convertido a CRC
    breakdown: AssetBreakdown
    num_cuentas: int
    num_inversiones: int
    num_metas: int
    fecha_calculo: date


class PatrimonyService:
    """Servicio para calcular y consolidar patrimonio."""

    # Tipo de cambio por defecto (debería venir de ExchangeRateService)
    DEFAULT_EXCHANGE_RATE = Decimal("515.00")

    def __init__(self, db: Session) -> None:
        """Inicializa el servicio.

        Args:
            db: Sesión de base de datos.
        """
        self.db = db

    def get_accounts(self, profile_id: str) -> list[Account]:
        """Obtiene todas las cuentas activas de un perfil.

        Args:
            profile_id: ID del perfil.

        Returns:
            Lista de cuentas activas.
        """
        stmt = select(Account).where(
            Account.profile_id == profile_id,
            Account.deleted_at.is_(None),
            Account.incluir_en_patrimonio.is_(True),
        )
        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def get_investments(
        self,
        profile_id: str,
        include_inactive: bool = False,
    ) -> list[Investment]:
        """Obtiene todas las inversiones de un perfil.

        Args:
            profile_id: ID del perfil.
            include_inactive: Si incluir inversiones inactivas.

        Returns:
            Lista de inversiones.
        """
        stmt = select(Investment).where(
            Investment.profile_id == profile_id,
            Investment.deleted_at.is_(None),
        )

        if not include_inactive:
            stmt = stmt.where(Investment.activa.is_(True))

        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def get_goals(
        self,
        profile_id: str,
        only_active: bool = True,
    ) -> list[Goal]:
        """Obtiene todas las metas de un perfil.

        Args:
            profile_id: ID del perfil.
            only_active: Si solo incluir metas activas.

        Returns:
            Lista de metas.
        """
        stmt = select(Goal).where(
            Goal.profile_id == profile_id,
            Goal.deleted_at.is_(None),
        )

        if only_active:
            stmt = stmt.where(Goal.estado == GoalStatus.ACTIVA)

        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def calculate_net_worth(
        self,
        profile_id: str,
        exchange_rate: Decimal | None = None,
    ) -> NetWorthSummary:
        """Calcula el patrimonio neto total.

        Args:
            profile_id: ID del perfil.
            exchange_rate: Tipo de cambio USD/CRC. Si no se provee, usa default.

        Returns:
            Resumen de patrimonio neto.
        """
        rate = exchange_rate or self.DEFAULT_EXCHANGE_RATE

        accounts = self.get_accounts(profile_id)
        investments = self.get_investments(profile_id)
        goals = self.get_goals(profile_id)

        # Calcular totales por tipo y moneda
        cuentas_crc = Decimal("0")
        cuentas_usd = Decimal("0")
        inversiones_crc = Decimal("0")
        inversiones_usd = Decimal("0")
        metas_crc = Decimal("0")
        metas_usd = Decimal("0")

        # Cuentas
        for account in accounts:
            saldo = account.saldo or Decimal("0")
            if account.moneda == Currency.CRC:
                cuentas_crc += saldo
            else:
                cuentas_usd += saldo

        # Inversiones (usar valor_actual si existe, sino monto_principal)
        for investment in investments:
            valor = investment.valor_actual or investment.monto_principal
            if investment.moneda == Currency.CRC:
                inversiones_crc += valor
            else:
                inversiones_usd += valor

        # Metas (monto actual ahorrado)
        for goal in goals:
            monto = goal.monto_actual or Decimal("0")
            if goal.moneda == Currency.CRC:
                metas_crc += monto
            else:
                metas_usd += monto

        breakdown = AssetBreakdown(
            cuentas_crc=cuentas_crc,
            cuentas_usd=cuentas_usd,
            inversiones_crc=inversiones_crc,
            inversiones_usd=inversiones_usd,
            metas_crc=metas_crc,
            metas_usd=metas_usd,
        )

        total_crc = breakdown.total_crc
        total_usd = breakdown.total_usd
        total_crc_equivalente = total_crc + (total_usd * rate)

        logger.info(
            "Net worth calculado para profile %d: ₡%s + $%s = ₡%s equivalente",
            profile_id,
            total_crc,
            total_usd,
            total_crc_equivalente,
        )

        return NetWorthSummary(
            total_crc=total_crc,
            total_usd=total_usd,
            total_crc_equivalente=total_crc_equivalente,
            breakdown=breakdown,
            num_cuentas=len(accounts),
            num_inversiones=len(investments),
            num_metas=len(goals),
            fecha_calculo=date.today(),
        )

    def get_investment_returns(
        self,
        profile_id: str,
    ) -> dict[str, Decimal]:
        """Calcula rendimientos totales de inversiones.

        Args:
            profile_id: ID del perfil.

        Returns:
            Diccionario con rendimientos por moneda.
        """
        investments = self.get_investments(profile_id)

        returns_crc = Decimal("0")
        returns_usd = Decimal("0")

        for inv in investments:
            rendimiento = inv.rendimiento_acumulado
            if inv.moneda == Currency.CRC:
                returns_crc += rendimiento
            else:
                returns_usd += rendimiento

        return {
            "crc": returns_crc,
            "usd": returns_usd,
        }

    def get_goals_progress(
        self,
        profile_id: str,
    ) -> dict[str, Decimal | int]:
        """Resumen de progreso de metas.

        Args:
            profile_id: ID del perfil.

        Returns:
            Diccionario con progreso general de metas.
        """
        goals = self.get_goals(profile_id, only_active=True)

        if not goals:
            return {
                "num_metas": 0,
                "progreso_promedio": Decimal("0"),
                "monto_objetivo_total": Decimal("0"),
                "monto_actual_total": Decimal("0"),
            }

        total_objetivo = Decimal("0")
        total_actual = Decimal("0")
        sum_progreso = Decimal("0")

        for goal in goals:
            total_objetivo += goal.monto_objetivo
            total_actual += goal.monto_actual or Decimal("0")
            sum_progreso += goal.progreso_porcentaje

        progreso_promedio = sum_progreso / len(goals)

        return {
            "num_metas": len(goals),
            "progreso_promedio": progreso_promedio.quantize(Decimal("0.01")),
            "monto_objetivo_total": total_objetivo,
            "monto_actual_total": total_actual,
        }

    def get_accounts_by_type(
        self,
        profile_id: str,
    ) -> dict[AccountType, list[Account]]:
        """Agrupa cuentas por tipo.

        Args:
            profile_id: ID del perfil.

        Returns:
            Diccionario de cuentas agrupadas por tipo.
        """
        accounts = self.get_accounts(profile_id)
        result: dict[AccountType, list[Account]] = {}

        for account in accounts:
            if account.tipo not in result:
                result[account.tipo] = []
            result[account.tipo].append(account)

        return result

    # ========================================================================
    # MÉTODOS PARA PATRIMONIO SNAPSHOTS
    # ========================================================================

    def crear_snapshot(
        self,
        profile_id: str,
        fecha: date | None = None,
        exchange_rate: Decimal | None = None,
        es_fecha_base: bool = False,
        notas: str | None = None,
    ) -> PatrimonioSnapshot:
        """Crea un snapshot del patrimonio actual.

        Args:
            profile_id: ID del perfil.
            fecha: Fecha del snapshot. Usa hoy si no se provee.
            exchange_rate: Tipo de cambio USD/CRC para conversión.
            es_fecha_base: Si es el snapshot inicial de onboarding.
            notas: Notas opcionales del snapshot.

        Returns:
            PatrimonioSnapshot creado y guardado en DB.
        """
        rate = exchange_rate or self.DEFAULT_EXCHANGE_RATE
        fecha_snapshot_date = fecha or date.today()
        # Convertir date a datetime (inicio del día en UTC)
        fecha_snapshot_dt = datetime.combine(fecha_snapshot_date, datetime.min.time())

        # Obtener datos actuales
        accounts = self.get_accounts(profile_id)
        investments = self.get_investments(profile_id)

        # Calcular saldos por tipo de cuenta y moneda
        saldo_cuentas_crc = Decimal("0")
        saldo_cuentas_usd = Decimal("0")
        saldo_tarjetas_crc = Decimal("0")
        saldo_tarjetas_usd = Decimal("0")
        saldo_prestamos_crc = Decimal("0")
        saldo_prestamos_usd = Decimal("0")

        for account in accounts:
            saldo = account.saldo or Decimal("0")
            is_crc = account.moneda == Currency.CRC

            if account.tipo == AccountType.CUENTA_CORRIENTE or account.tipo == AccountType.CUENTA_AHORRO:
                if is_crc:
                    saldo_cuentas_crc += saldo
                else:
                    saldo_cuentas_usd += saldo
            elif account.tipo == AccountType.TARJETA_CREDITO:
                # Tarjetas tienen saldo negativo (deuda)
                if is_crc:
                    saldo_tarjetas_crc += saldo
                else:
                    saldo_tarjetas_usd += saldo
            elif account.tipo == AccountType.PRESTAMO:
                if is_crc:
                    saldo_prestamos_crc += saldo
                else:
                    saldo_prestamos_usd += saldo

        # Calcular inversiones
        saldo_inversiones_crc = Decimal("0")
        saldo_inversiones_usd = Decimal("0")

        for inv in investments:
            valor = inv.valor_actual or inv.monto_principal
            if inv.moneda == Currency.CRC:
                saldo_inversiones_crc += valor
            else:
                saldo_inversiones_usd += valor

        # Crear snapshot
        snapshot = PatrimonioSnapshot(
            profile_id=profile_id,
            fecha_snapshot=fecha_snapshot_dt,
            es_fecha_base=es_fecha_base,
            saldo_cuentas_crc=saldo_cuentas_crc,
            saldo_cuentas_usd=saldo_cuentas_usd,
            deuda_tarjetas_crc=saldo_tarjetas_crc,
            deuda_tarjetas_usd=saldo_tarjetas_usd,
            saldo_inversiones_crc=saldo_inversiones_crc,
            saldo_inversiones_usd=saldo_inversiones_usd,
            deuda_prestamos_crc=saldo_prestamos_crc,
            deuda_prestamos_usd=saldo_prestamos_usd,
            tipo_cambio_usd=rate,
            notas=notas,
        )

        self.db.add(snapshot)
        self.db.commit()
        self.db.refresh(snapshot)

        logger.info(
            "Snapshot creado para profile %s fecha %s: activos=₡%s, deudas=₡%s, patrimonio=₡%s",
            profile_id,
            fecha_snapshot_date,
            snapshot.total_activos_crc,
            snapshot.total_deudas_crc,
            snapshot.patrimonio_neto_crc,
        )

        return snapshot

    def establecer_patrimonio_inicial(
        self,
        profile_id: str,
        fecha_base: date,
        exchange_rate: Decimal | None = None,
        notas: str | None = None,
    ) -> PatrimonioSnapshot:
        """Establece el patrimonio inicial (FECHA_BASE) para un perfil.

        Este es el punto de partida para el tracking de patrimonio.
        Todas las transacciones antes de esta fecha se consideran históricas.

        Args:
            profile_id: ID del perfil.
            fecha_base: Fecha de inicio del tracking.
            exchange_rate: Tipo de cambio USD/CRC.
            notas: Notas opcionales.

        Returns:
            PatrimonioSnapshot marcado como fecha_base.

        Raises:
            ValueError: Si ya existe un snapshot de fecha base.
        """
        # Verificar que no exista ya una fecha base
        existing = self.get_snapshot_fecha_base(profile_id)
        if existing:
            raise ValueError(
                f"Ya existe un patrimonio inicial para profile {profile_id} "
                f"en fecha {existing.fecha_snapshot}"
            )

        return self.crear_snapshot(
            profile_id=profile_id,
            fecha=fecha_base,
            exchange_rate=exchange_rate,
            es_fecha_base=True,
            notas=notas or "Patrimonio inicial - Inicio de tracking",
        )

    def get_snapshot_fecha_base(
        self,
        profile_id: str,
    ) -> PatrimonioSnapshot | None:
        """Obtiene el snapshot de fecha base (patrimonio inicial).

        Args:
            profile_id: ID del perfil.

        Returns:
            PatrimonioSnapshot de fecha base o None si no existe.
        """
        stmt = select(PatrimonioSnapshot).where(
            PatrimonioSnapshot.profile_id == profile_id,
            PatrimonioSnapshot.es_fecha_base.is_(True),
            PatrimonioSnapshot.deleted_at.is_(None),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def obtener_historial(
        self,
        profile_id: str,
        fecha_inicio: date | None = None,
        fecha_fin: date | None = None,
        limite: int | None = None,
    ) -> list[PatrimonioSnapshot]:
        """Obtiene historial de snapshots de patrimonio.

        Args:
            profile_id: ID del perfil.
            fecha_inicio: Fecha inicio del rango (inclusive).
            fecha_fin: Fecha fin del rango (inclusive).
            limite: Máximo de snapshots a retornar.

        Returns:
            Lista de snapshots ordenados por fecha descendente.
        """
        stmt = select(PatrimonioSnapshot).where(
            PatrimonioSnapshot.profile_id == profile_id,
            PatrimonioSnapshot.deleted_at.is_(None),
        )

        if fecha_inicio:
            stmt = stmt.where(PatrimonioSnapshot.fecha_snapshot >= fecha_inicio)

        if fecha_fin:
            stmt = stmt.where(PatrimonioSnapshot.fecha_snapshot <= fecha_fin)

        stmt = stmt.order_by(desc(PatrimonioSnapshot.fecha_snapshot))

        if limite:
            stmt = stmt.limit(limite)

        result = self.db.execute(stmt)
        return list(result.scalars().all())

    def get_ultimo_snapshot(
        self,
        profile_id: str,
    ) -> PatrimonioSnapshot | None:
        """Obtiene el snapshot más reciente.

        Args:
            profile_id: ID del perfil.

        Returns:
            PatrimonioSnapshot más reciente o None.
        """
        snapshots = self.obtener_historial(profile_id, limite=1)
        return snapshots[0] if snapshots else None

    def calcular_cambio_periodo(
        self,
        profile_id: str,
        fecha_inicio: date,
        fecha_fin: date,
    ) -> dict[str, Decimal]:
        """Calcula el cambio de patrimonio entre dos fechas.

        Busca los snapshots más cercanos a las fechas dadas.

        Args:
            profile_id: ID del perfil.
            fecha_inicio: Fecha de inicio del periodo.
            fecha_fin: Fecha de fin del periodo.

        Returns:
            Diccionario con cambios absolutos y porcentuales.

        Raises:
            ValueError: Si no hay snapshots suficientes.
        """
        # Buscar snapshot más cercano a fecha_inicio
        stmt_inicio = (
            select(PatrimonioSnapshot)
            .where(
                PatrimonioSnapshot.profile_id == profile_id,
                PatrimonioSnapshot.fecha_snapshot <= fecha_inicio,
                PatrimonioSnapshot.deleted_at.is_(None),
            )
            .order_by(desc(PatrimonioSnapshot.fecha_snapshot))
            .limit(1)
        )
        snapshot_inicio = self.db.execute(stmt_inicio).scalar_one_or_none()

        # Buscar snapshot más cercano a fecha_fin
        stmt_fin = (
            select(PatrimonioSnapshot)
            .where(
                PatrimonioSnapshot.profile_id == profile_id,
                PatrimonioSnapshot.fecha_snapshot <= fecha_fin,
                PatrimonioSnapshot.deleted_at.is_(None),
            )
            .order_by(desc(PatrimonioSnapshot.fecha_snapshot))
            .limit(1)
        )
        snapshot_fin = self.db.execute(stmt_fin).scalar_one_or_none()

        if not snapshot_inicio:
            raise ValueError(
                f"No hay snapshots antes de {fecha_inicio} para profile {profile_id}"
            )

        if not snapshot_fin:
            raise ValueError(
                f"No hay snapshots antes de {fecha_fin} para profile {profile_id}"
            )

        # Calcular cambios
        patrimonio_inicio = snapshot_inicio.patrimonio_neto_crc
        patrimonio_fin = snapshot_fin.patrimonio_neto_crc

        cambio_absoluto = patrimonio_fin - patrimonio_inicio

        if patrimonio_inicio != Decimal("0"):
            cambio_porcentual = (cambio_absoluto / patrimonio_inicio) * 100
        else:
            cambio_porcentual = Decimal("0")

        logger.info(
            "Cambio patrimonio profile %s [%s - %s]: ₡%s → ₡%s (%.2f%%)",
            profile_id,
            snapshot_inicio.fecha_snapshot,
            snapshot_fin.fecha_snapshot,
            patrimonio_inicio,
            patrimonio_fin,
            cambio_porcentual,
        )

        return {
            "fecha_inicio_real": snapshot_inicio.fecha_snapshot,
            "fecha_fin_real": snapshot_fin.fecha_snapshot,
            "patrimonio_inicio_crc": patrimonio_inicio,
            "patrimonio_fin_crc": patrimonio_fin,
            "cambio_absoluto_crc": cambio_absoluto,
            "cambio_porcentual": cambio_porcentual.quantize(Decimal("0.01")),
            "activos_inicio_crc": snapshot_inicio.total_activos_crc,
            "activos_fin_crc": snapshot_fin.total_activos_crc,
            "deudas_inicio_crc": snapshot_inicio.total_deudas_crc,
            "deudas_fin_crc": snapshot_fin.total_deudas_crc,
        }

    def generar_snapshot_mensual(
        self,
        profile_id: str,
        exchange_rate: Decimal | None = None,
    ) -> PatrimonioSnapshot | None:
        """Genera un snapshot si no existe uno para el mes actual.

        Útil para automatizar snapshots mensuales.

        Args:
            profile_id: ID del perfil.
            exchange_rate: Tipo de cambio USD/CRC.

        Returns:
            PatrimonioSnapshot creado o None si ya existe uno este mes.
        """
        today = date.today()
        mes_inicio = date(today.year, today.month, 1)

        # Verificar si ya existe snapshot este mes
        stmt = select(PatrimonioSnapshot).where(
            PatrimonioSnapshot.profile_id == profile_id,
            PatrimonioSnapshot.fecha_snapshot >= mes_inicio,
            PatrimonioSnapshot.deleted_at.is_(None),
        ).limit(1)
        existing = self.db.execute(stmt).scalar_one_or_none()

        if existing:
            logger.info(
                "Ya existe snapshot para %s en mes %s-%s",
                profile_id,
                today.year,
                today.month,
            )
            return None

        return self.crear_snapshot(
            profile_id=profile_id,
            fecha=today,
            exchange_rate=exchange_rate,
            notas=f"Snapshot mensual automático - {today.strftime('%B %Y')}",
        )
