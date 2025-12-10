"""Schemas Pydantic para Patrimonio - Accounts, Investments, Goals."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Account Schemas
# =============================================================================


class AccountBase(BaseModel):
    """Campos base para Account."""

    banco: str = Field(..., description="Nombre del banco (bac, popular)")
    tipo: str = Field(..., description="Tipo de cuenta (corriente, ahorro, planilla, dolares)")
    nombre: str = Field(..., max_length=100, description="Nombre descriptivo de la cuenta")
    numero_cuenta: str | None = Field(None, max_length=20, description="Últimos 4 dígitos")
    saldo: Decimal = Field(..., ge=0, description="Saldo actual de la cuenta")
    moneda: str = Field(default="CRC", description="Moneda (CRC o USD)")
    saldo_minimo: Decimal | None = Field(None, ge=0, description="Saldo mínimo requerido")
    es_cuenta_principal: bool = Field(default=False, description="Si es la cuenta principal")
    incluir_en_patrimonio: bool = Field(default=True, description="Incluir en cálculo de net worth")
    notas: str | None = Field(None, max_length=500, description="Notas adicionales")


class AccountCreate(AccountBase):
    """Schema para crear una cuenta."""

    pass


class AccountUpdate(BaseModel):
    """Schema para actualizar una cuenta."""

    nombre: str | None = Field(None, max_length=100)
    saldo: Decimal | None = Field(None, ge=0)
    saldo_minimo: Decimal | None = None
    es_cuenta_principal: bool | None = None
    incluir_en_patrimonio: bool | None = None
    notas: str | None = Field(None, max_length=500)


class AccountResponse(AccountBase):
    """Schema de respuesta para Account."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    created_at: str | None = None


# =============================================================================
# Investment Schemas
# =============================================================================


class InvestmentBase(BaseModel):
    """Campos base para Investment."""

    tipo: str = Field(..., description="Tipo: cdp, ahorro_plazo, fondo_inversion, acciones, cripto")
    institucion: str = Field(..., max_length=100, description="Nombre de la institución")
    nombre: str = Field(..., max_length=100, description="Nombre de la inversión")
    monto_principal: Decimal = Field(..., gt=0, description="Monto invertido inicialmente")
    moneda: str = Field(default="CRC", description="Moneda (CRC o USD)")
    tasa_interes_anual: Decimal = Field(..., ge=0, description="Tasa de interés anual (ej: 0.0373)")
    fecha_inicio: date = Field(..., description="Fecha de inicio de la inversión")
    fecha_vencimiento: date | None = Field(None, description="Fecha de vencimiento")
    notas: str | None = Field(None, max_length=500, description="Notas adicionales")
    activa: bool = Field(default=True, description="Si la inversión está activa")
    incluir_en_patrimonio: bool = Field(
        default=True, description="Incluir en cálculo de patrimonio"
    )


class InvestmentCreate(InvestmentBase):
    """Schema para crear una inversión."""

    pass


class InvestmentUpdate(BaseModel):
    """Schema para actualizar una inversión."""

    nombre: str | None = Field(None, max_length=100)
    tasa_interes_anual: Decimal | None = Field(None, ge=0)
    fecha_vencimiento: date | None = None
    activa: bool | None = None
    incluir_en_patrimonio: bool | None = None
    notas: str | None = Field(None, max_length=500)
    rendimiento_acumulado: Decimal | None = Field(None, ge=0, description="Actualizar rendimiento")


class InvestmentResponse(InvestmentBase):
    """Schema de respuesta para Investment."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    profile_id: int
    rendimiento_acumulado: Decimal = Field(
        default=Decimal("0"), description="Rendimiento acumulado"
    )
    valor_actual: Decimal | None = None
    dias_para_vencimiento: int | None = None
    dias_restantes: int | None = None
    created_at: str | None = None


# =============================================================================
# Goal Schemas
# =============================================================================


class GoalBase(BaseModel):
    """Campos base para Goal."""

    nombre: str = Field(..., max_length=100, description="Nombre de la meta")
    descripcion: str | None = Field(None, max_length=500, description="Descripción detallada")
    monto_objetivo: Decimal = Field(..., gt=0, description="Monto objetivo a alcanzar")
    monto_actual: Decimal = Field(default=Decimal("0"), ge=0, description="Monto ahorrado actual")
    moneda: str = Field(default="CRC", description="Moneda (CRC o USD)")
    fecha_objetivo: date | None = Field(None, description="Fecha límite para alcanzar la meta")
    prioridad: str = Field(default="media", description="Prioridad: alta, media, baja")
    icono: str | None = Field(None, max_length=10, description="Emoji para la meta")


class GoalCreate(GoalBase):
    """Schema para crear una meta."""

    pass


class GoalUpdate(BaseModel):
    """Schema para actualizar una meta."""

    nombre: str | None = Field(None, max_length=100)
    descripcion: str | None = Field(None, max_length=500)
    monto_objetivo: Decimal | None = Field(None, gt=0)
    monto_actual: Decimal | None = Field(None, ge=0)
    fecha_objetivo: date | None = None
    prioridad: str | None = None
    estado: str | None = None
    icono: str | None = None


class GoalContribution(BaseModel):
    """Schema para agregar contribución a una meta."""

    monto: Decimal = Field(..., gt=0, description="Monto a agregar")


class GoalResponse(GoalBase):
    """Schema de respuesta para Goal."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    estado: str
    porcentaje_completado: float = Field(description="Porcentaje completado")
    monto_faltante: Decimal
    dias_restantes: int | None = None
    created_at: str | None = None


# =============================================================================
# Patrimony Summary Schemas
# =============================================================================


class AssetBreakdownResponse(BaseModel):
    """Desglose de activos por tipo y moneda."""

    cuentas_crc: Decimal
    cuentas_usd: Decimal
    inversiones_crc: Decimal
    inversiones_usd: Decimal
    metas_crc: Decimal
    metas_usd: Decimal
    total_crc: Decimal
    total_usd: Decimal


class NetWorthResponse(BaseModel):
    """Resumen de patrimonio neto."""

    total_crc: Decimal = Field(..., description="Total en colones")
    total_usd: Decimal = Field(..., description="Total en dólares")
    total_crc_equivalente: Decimal = Field(..., description="Todo convertido a CRC")
    breakdown: AssetBreakdownResponse
    num_cuentas: int
    num_inversiones: int
    num_metas: int
    fecha_calculo: date


class InvestmentReturnsResponse(BaseModel):
    """Rendimientos de inversiones."""

    crc: Decimal
    usd: Decimal


class GoalsProgressResponse(BaseModel):
    """Progreso general de metas."""

    num_metas: int
    progreso_promedio: Decimal
    monto_objetivo_total: Decimal
    monto_actual_total: Decimal
