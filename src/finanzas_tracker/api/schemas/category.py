"""Schemas para Categorías."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SubcategoryResponse(BaseModel):
    """Schema de respuesta de subcategoría."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    category_id: str
    nombre: str
    descripcion: str | None
    icono: str
    keywords: str | None = Field(None, description="Palabras clave para matching")


class CategoryResponse(BaseModel):
    """Schema de respuesta de categoría."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    tipo: str = Field(..., description="necesidades, gustos, o ahorros")
    nombre: str
    descripcion: str | None
    icono: str
    created_at: datetime
    subcategories: list[SubcategoryResponse] = Field(default_factory=list)


class CategoryListResponse(BaseModel):
    """Schema de respuesta de lista de categorías."""

    items: list[CategoryResponse]
    total: int
