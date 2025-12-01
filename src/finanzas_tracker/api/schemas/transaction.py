"""Schemas para Transacciones."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TransactionBase(BaseModel):
    """Campos base de transacción."""

    comercio: str = Field(..., min_length=1, max_length=255, description="Nombre del comercio")
    monto_original: Decimal = Field(..., gt=0, description="Monto en moneda original")
    moneda_original: str = Field(default="CRC", pattern="^(CRC|USD)$", description="Moneda: CRC o USD")
    fecha_transaccion: datetime = Field(..., description="Fecha y hora de la transacción")
    tipo_transaccion: str = Field(
        default="compra",
        description="Tipo: compra, transferencia, retiro, pago_servicio",
    )
    banco: str = Field(default="bac", description="Banco: bac o popular")


class TransactionCreate(TransactionBase):
    """Schema para crear transacción."""

    email_id: str | None = Field(None, description="ID del email origen (opcional para manuales)")
    monto_crc: Decimal | None = Field(None, gt=0, description="Monto en colones (calculado si es USD)")
    subcategory_id: str | None = Field(None, description="ID de subcategoría")
    notas: str | None = Field(None, max_length=1000, description="Notas adicionales")
    tipo_especial: str | None = Field(None, description="dinero_ajeno, intermediaria, etc.")
    excluir_de_presupuesto: bool | None = Field(False, description="Excluir del cálculo 50/30/20")


class TransactionUpdate(BaseModel):
    """Schema para actualizar transacción (todos opcionales)."""

    comercio: str | None = Field(None, min_length=1, max_length=255)
    subcategory_id: str | None = None
    notas: str | None = Field(None, max_length=1000)
    tipo_especial: str | None = None
    excluir_de_presupuesto: bool | None = None
    confirmada: bool | None = None
    contexto: str | None = Field(None, description="Contexto del gasto en lenguaje natural")
    necesita_revision: bool | None = None


class TransactionResponse(BaseModel):
    """Schema de respuesta de transacción."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email_id: str
    profile_id: str
    banco: str
    tipo_transaccion: str
    comercio: str
    monto_original: Decimal
    moneda_original: str
    monto_crc: Decimal
    tipo_cambio_usado: Decimal | None
    fecha_transaccion: datetime
    ciudad: str | None
    pais: str | None
    subcategory_id: str | None
    categoria_sugerida_por_ia: str | None
    confirmada: bool
    necesita_revision: bool
    notas: str | None
    contexto: str | None
    tipo_especial: str | None
    excluir_de_presupuesto: bool
    created_at: datetime
    updated_at: datetime


class TransactionListResponse(BaseModel):
    """Schema de respuesta de lista de transacciones."""

    items: list[TransactionResponse]
    total: int = Field(..., description="Total de registros (sin paginación)")
    skip: int = Field(..., description="Registros saltados")
    limit: int = Field(..., description="Límite de registros por página")
    total_crc: Decimal = Field(..., description="Suma total en colones de los items retornados")
