"""Queries optimizadas con caching para el dashboard.

Este módulo contiene todas las consultas costosas del dashboard con caching integrado.
Las funciones están diseñadas para ser reutilizables en diferentes páginas.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import joinedload

from finanzas_tracker.core.cache import cached_query
from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.account import Account
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.transaction import Transaction


@cached_query(ttl_seconds=300, profile_aware=True)
def get_patrimonio_total(profile_id: str) -> dict[str, Decimal]:
    """
    Calcula el patrimonio total del perfil.

    Args:
        profile_id: ID del perfil

    Returns:
        dict con: patrimonio_cuentas, patrimonio_ingresos, patrimonio_gastos,
        movimientos_netos, patrimonio_total
    """
    with get_session() as session:
        # 1. Saldo en cuentas
        patrimonio_cuentas = Account.calcular_patrimonio_total(session, profile_id)

        # 2. Movimientos históricos
        ingresos_historicos = (
            session.query(Income)
            .filter(
                Income.profile_id == profile_id,
                Income.deleted_at.is_(None),
            )
            .all()
        )
        patrimonio_ingresos = sum(i.calcular_monto_patrimonio() for i in ingresos_historicos)

        gastos_historicos = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == profile_id,
                Transaction.deleted_at.is_(None),
            )
            .all()
        )
        patrimonio_gastos = sum(g.calcular_monto_patrimonio() for g in gastos_historicos)
        movimientos_netos = patrimonio_ingresos - patrimonio_gastos

        # Patrimonio total
        patrimonio_total = patrimonio_cuentas + movimientos_netos

        return {
            "patrimonio_cuentas": patrimonio_cuentas,
            "patrimonio_ingresos": patrimonio_ingresos,
            "patrimonio_gastos": patrimonio_gastos,
            "movimientos_netos": movimientos_netos,
            "patrimonio_total": patrimonio_total,
        }


@cached_query(ttl_seconds=180, profile_aware=True)
def get_monthly_data(profile_id: str, year: int, month: int) -> dict[str, any]:
    """
    Obtiene datos del mes para el dashboard.

    Args:
        profile_id: ID del perfil
        year: Año
        month: Mes (1-12)

    Returns:
        dict con ingresos, gastos, totales y agregaciones
    """
    with get_session() as session:
        # Calcular rango del mes
        primer_dia = date(year, month, 1)
        proximo_mes = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)

        # Ingresos del mes
        ingresos_mes = (
            session.query(Income)
            .filter(
                Income.profile_id == profile_id,
                Income.fecha >= primer_dia,
                Income.fecha < proximo_mes,
                Income.deleted_at.is_(None),
            )
            .all()
        )
        total_ingresos_mes = sum(i.monto_crc for i in ingresos_mes)

        # Gastos del mes
        gastos_mes = (
            session.query(Transaction)
            .options(joinedload(Transaction.subcategory).joinedload("category"))
            .filter(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion >= primer_dia,
                Transaction.fecha_transaccion < proximo_mes,
                Transaction.deleted_at.is_(None),
                Transaction.excluir_de_presupuesto == False,  # noqa: E712
            )
            .all()
        )
        total_gastos_mes = sum(g.monto_crc for g in gastos_mes)
        balance_mes = total_ingresos_mes - total_gastos_mes

        # Transacciones sin revisar
        sin_revisar = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == profile_id,
                Transaction.necesita_revision == True,  # noqa: E712
                Transaction.deleted_at.is_(None),
            )
            .count()
        )

        # Gastos por día
        gastos_por_dia = defaultdict(float)
        for gasto in gastos_mes:
            dia = gasto.fecha_transaccion.day
            gastos_por_dia[dia] += gasto.monto_crc

        # Gastos por categoría
        gastos_por_categoria = defaultdict(float)
        for gasto in gastos_mes:
            if gasto.categoria:
                gastos_por_categoria[gasto.categoria.nombre] += gasto.monto_crc

        # Gastos por merchant
        gastos_por_merchant = defaultdict(float)
        for gasto in gastos_mes:
            if gasto.merchant:
                gastos_por_merchant[gasto.merchant.nombre_normalizado] += gasto.monto_crc

        return {
            "ingresos": ingresos_mes,
            "gastos": gastos_mes,
            "total_ingresos": total_ingresos_mes,
            "total_gastos": total_gastos_mes,
            "balance": balance_mes,
            "sin_revisar": sin_revisar,
            "gastos_por_dia": dict(gastos_por_dia),
            "gastos_por_categoria": dict(gastos_por_categoria),
            "gastos_por_merchant": dict(gastos_por_merchant),
            "count_ingresos": len(ingresos_mes),
            "count_gastos": len(gastos_mes),
        }


@cached_query(ttl_seconds=300, profile_aware=True)
def get_accounts_breakdown(profile_id: str) -> dict[str, any]:
    """
    Obtiene breakdown de cuentas por tipo.

    Args:
        profile_id: ID del perfil

    Returns:
        dict con cuentas activas, breakdown por tipo, y totales
    """
    with get_session() as session:
        cuentas_activas = (
            session.query(Account)
            .filter(
                Account.profile_id == profile_id,
                Account.activa == True,  # noqa: E712
                Account.deleted_at.is_(None),
            )
            .all()
        )

        # Breakdown por tipo
        cuentas_por_tipo = defaultdict(float)
        for cuenta in cuentas_activas:
            cuentas_por_tipo[cuenta.tipo] += cuenta.saldo_crc

        # Intereses mensuales
        intereses_mensuales = Account.calcular_intereses_mensuales_totales(session, profile_id)

        return {
            "cuentas": cuentas_activas,
            "cuentas_por_tipo": dict(cuentas_por_tipo),
            "intereses_mensuales": intereses_mensuales,
            "count_cuentas": len(cuentas_activas),
        }


__all__ = [
    "get_patrimonio_total",
    "get_monthly_data",
    "get_accounts_breakdown",
]
