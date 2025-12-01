"""Schemas para Presupuestos."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class BudgetBase(BaseModel):
    """Campos base de presupuesto."""

    category_id: str = Field(..., description="ID de la subcategoría")
    mes: date = Field(..., description="Primer día del mes (YYYY-MM-01)")
    amount_crc: Decimal = Field(..., gt=0, description="Límite de gasto en colones")


class BudgetCreate(BudgetBase):
    """Schema para crear presupuesto."""

    notas: str | None = Field(None, max_length=500, description="Notas opcionales")


class BudgetUpdate(BaseModel):
    """Schema para actualizar presupuesto (todos opcionales)."""

    amount_crc: Decimal | None = Field(None, gt=0)
    notas: str | None = Field(None, max_length=500)


class BudgetResponse(BaseModel):
    """Schema de respuesta de presupuesto."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    category_id: str
    mes: date
    amount_crc: Decimal
    notas: str | None
    created_at: date


class BudgetListResponse(BaseModel):
    """Schema de respuesta de lista de presupuestos."""

    items: list[BudgetResponse]
    total: int


class CategoryBudgetSummary(BaseModel):
    """Resumen de presupuesto por categoría principal."""

    categoria: str = Field(..., description="necesidades, gustos, o ahorros")
    presupuestado: Decimal = Field(..., description="Total presupuestado en CRC")
    gastado: Decimal = Field(..., description="Total gastado en CRC")
    restante: Decimal = Field(..., description="Diferencia (puede ser negativo)")
    porcentaje_usado: Decimal = Field(..., description="Porcentaje del presupuesto usado")
    status: str = Field(
        ...,
        description="bajo_presupuesto (<80%), en_limite (80-100%), sobre_presupuesto (>100%)"
    )


class BudgetSummaryResponse(BaseModel):
    """Resumen completo del presupuesto 50/30/20."""

    mes: date
    categorias: list[CategoryBudgetSummary]
    total_presupuestado: Decimal
    total_gastado: Decimal
    total_restante: Decimal
