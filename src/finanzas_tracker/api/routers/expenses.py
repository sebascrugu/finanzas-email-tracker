"""API Router para Gastos Proyectados y Alertas.

Endpoints para predicción de gastos y alertas de vencimiento.
"""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from finanzas_tracker.api.dependencies import get_db
from finanzas_tracker.services.recurring_expense_predictor import (
    AlertLevel,
    ExpenseType,
    RecurringExpensePredictor,
    generar_reporte_gastos_proximos,
)


router = APIRouter(prefix="/expenses", tags=["Gastos Proyectados"])


# =============================================================================
# Schemas
# =============================================================================


class PredictedExpenseResponse(BaseModel):
    """Schema de respuesta para un gasto predecido."""

    comercio: str = Field(..., description="Nombre del comercio")
    monto_estimado: float = Field(..., description="Monto estimado del gasto")
    monto_min: float | None = Field(None, description="Monto mínimo histórico")
    monto_max: float | None = Field(None, description="Monto máximo histórico")
    fecha_estimada: date = Field(..., description="Fecha estimada del gasto")
    tipo: str = Field(..., description="Tipo de gasto (subscription, utility, loan, etc.)")
    confianza: int = Field(..., ge=0, le=100, description="Nivel de confianza (0-100)")
    dias_restantes: int = Field(..., description="Días hasta el gasto")
    nivel_alerta: str = Field(..., description="Nivel de alerta (info, warning, urgent)")
    notas: str = Field("", description="Notas adicionales")

    model_config = ConfigDict(from_attributes=True)


class PredictedExpenseListResponse(BaseModel):
    """Lista de gastos predecidos con resumen."""

    gastos: list[PredictedExpenseResponse]
    total_estimado: float = Field(..., description="Total estimado de gastos")
    cantidad: int = Field(..., description="Cantidad de gastos predecidos")
    alertas_urgentes: int = Field(..., description="Cantidad de alertas urgentes")
    alertas_warning: int = Field(..., description="Cantidad de alertas de advertencia")


class ExpenseSummaryResponse(BaseModel):
    """Resumen mensual de gastos proyectados."""

    periodo_inicio: date
    periodo_fin: date
    total_estimado: float
    cantidad_gastos: int
    alertas_urgentes: int
    por_tipo: dict[str, float] = Field(..., description="Gastos agrupados por tipo")
    gastos: list[PredictedExpenseResponse]


class CashFlowResponse(BaseModel):
    """Proyección de flujo de caja."""

    saldo_inicial: float
    saldo_final: float
    gastos_proyectados: float
    dias_proyectados: int
    flujo_diario: dict[str, float] = Field(..., description="Saldo proyectado por fecha")


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/predicted", response_model=PredictedExpenseListResponse)
def get_predicted_expenses(
    profile_id: str = Query(..., description="ID del perfil"),
    dias: int = Query(30, ge=1, le=90, description="Días hacia adelante"),
    confianza_minima: int = Query(50, ge=0, le=100, description="Confianza mínima"),
    db: Session = Depends(get_db),
) -> PredictedExpenseListResponse:
    """Obtiene los gastos proyectados para los próximos días.

    Predice gastos basándose en historial de transacciones,
    suscripciones detectadas y patrones de pago.
    """
    predictor = RecurringExpensePredictor(db)
    
    predicciones = predictor.predecir_gastos(
        profile_id=profile_id,
        dias_adelante=dias,
        confianza_minima=confianza_minima,
    )
    
    # Convertir a response
    responses = []
    for pred in predicciones:
        responses.append(
            PredictedExpenseResponse(
                comercio=pred.comercio,
                monto_estimado=float(pred.monto_estimado),
                monto_min=float(pred.monto_min) if pred.monto_min else None,
                monto_max=float(pred.monto_max) if pred.monto_max else None,
                fecha_estimada=pred.fecha_estimada,
                tipo=pred.tipo.value,
                confianza=pred.confianza,
                dias_restantes=pred.dias_restantes,
                nivel_alerta=pred.nivel_alerta.value,
                notas=pred.notas,
            )
        )
    
    total = sum(p.monto_estimado for p in predicciones)
    urgentes = sum(1 for p in predicciones if p.nivel_alerta == AlertLevel.URGENT)
    warnings = sum(1 for p in predicciones if p.nivel_alerta == AlertLevel.WARNING)
    
    return PredictedExpenseListResponse(
        gastos=responses,
        total_estimado=float(total),
        cantidad=len(responses),
        alertas_urgentes=urgentes,
        alertas_warning=warnings,
    )


@router.get("/alerts", response_model=PredictedExpenseListResponse)
def get_expense_alerts(
    profile_id: str = Query(..., description="ID del perfil"),
    dias: int = Query(7, ge=1, le=30, description="Días para alertas"),
    db: Session = Depends(get_db),
) -> PredictedExpenseListResponse:
    """Obtiene alertas de gastos próximos a vencer.

    Solo retorna gastos con nivel de alerta WARNING o URGENT.
    """
    predictor = RecurringExpensePredictor(db)
    
    alertas = predictor.get_alertas_vencimiento(
        profile_id=profile_id,
        dias_alerta=dias,
    )
    
    responses = []
    for pred in alertas:
        responses.append(
            PredictedExpenseResponse(
                comercio=pred.comercio,
                monto_estimado=float(pred.monto_estimado),
                monto_min=float(pred.monto_min) if pred.monto_min else None,
                monto_max=float(pred.monto_max) if pred.monto_max else None,
                fecha_estimada=pred.fecha_estimada,
                tipo=pred.tipo.value,
                confianza=pred.confianza,
                dias_restantes=pred.dias_restantes,
                nivel_alerta=pred.nivel_alerta.value,
                notas=pred.notas,
            )
        )
    
    total = sum(p.monto_estimado for p in alertas)
    urgentes = sum(1 for p in alertas if p.nivel_alerta == AlertLevel.URGENT)
    warnings = sum(1 for p in alertas if p.nivel_alerta == AlertLevel.WARNING)
    
    return PredictedExpenseListResponse(
        gastos=responses,
        total_estimado=float(total),
        cantidad=len(responses),
        alertas_urgentes=urgentes,
        alertas_warning=warnings,
    )


@router.get("/summary/monthly", response_model=ExpenseSummaryResponse)
def get_monthly_expense_summary(
    profile_id: str = Query(..., description="ID del perfil"),
    mes: int | None = Query(None, ge=1, le=12, description="Mes (1-12)"),
    anio: int | None = Query(None, ge=2020, le=2030, description="Año"),
    db: Session = Depends(get_db),
) -> ExpenseSummaryResponse:
    """Obtiene resumen de gastos proyectados para un mes.

    Si no se especifica mes/año, usa el mes actual.
    """
    predictor = RecurringExpensePredictor(db)
    
    resumen = predictor.generar_resumen_mensual(
        profile_id=profile_id,
        mes=mes,
        anio=anio,
    )
    
    # Convertir gastos a response
    gastos_response = []
    for pred in resumen.gastos:
        gastos_response.append(
            PredictedExpenseResponse(
                comercio=pred.comercio,
                monto_estimado=float(pred.monto_estimado),
                monto_min=float(pred.monto_min) if pred.monto_min else None,
                monto_max=float(pred.monto_max) if pred.monto_max else None,
                fecha_estimada=pred.fecha_estimada,
                tipo=pred.tipo.value,
                confianza=pred.confianza,
                dias_restantes=pred.dias_restantes,
                nivel_alerta=pred.nivel_alerta.value,
                notas=pred.notas,
            )
        )
    
    # Convertir por_tipo
    por_tipo = {k.value: float(v) for k, v in resumen.por_tipo.items()}
    
    return ExpenseSummaryResponse(
        periodo_inicio=resumen.periodo_inicio,
        periodo_fin=resumen.periodo_fin,
        total_estimado=float(resumen.total_estimado),
        cantidad_gastos=len(resumen.gastos),
        alertas_urgentes=resumen.alertas_urgentes,
        por_tipo=por_tipo,
        gastos=gastos_response,
    )


@router.get("/cash-flow", response_model=CashFlowResponse)
def get_cash_flow_projection(
    profile_id: str = Query(..., description="ID del perfil"),
    saldo_inicial: float = Query(..., description="Saldo inicial de cuenta"),
    dias: int = Query(30, ge=1, le=90, description="Días a proyectar"),
    db: Session = Depends(get_db),
) -> CashFlowResponse:
    """Proyecta el flujo de caja basado en gastos predecidos.

    Calcula cómo afectarán los gastos proyectados al saldo de cuenta.
    """
    predictor = RecurringExpensePredictor(db)
    
    flujo = predictor.estimar_flujo_caja(
        profile_id=profile_id,
        saldo_inicial=Decimal(str(saldo_inicial)),
        dias=dias,
    )
    
    # Convertir a dict con fechas string
    flujo_diario = {
        fecha.isoformat(): float(saldo)
        for fecha, saldo in flujo.items()
    }
    
    # Calcular totales
    saldos = list(flujo.values())
    gastos_proyectados = float(Decimal(str(saldo_inicial)) - saldos[-1]) if saldos else 0
    
    return CashFlowResponse(
        saldo_inicial=saldo_inicial,
        saldo_final=float(saldos[-1]) if saldos else saldo_inicial,
        gastos_proyectados=gastos_proyectados,
        dias_proyectados=dias,
        flujo_diario=flujo_diario,
    )


@router.get("/report")
def get_expense_report(
    profile_id: str = Query(..., description="ID del perfil"),
    dias: int = Query(30, ge=1, le=90, description="Días a proyectar"),
    db: Session = Depends(get_db),
) -> dict:
    """Genera un reporte completo de gastos próximos.

    Incluye gastos, alertas y resumen en un solo endpoint.
    """
    return generar_reporte_gastos_proximos(db, profile_id, dias)
