"""Schemas para Reconciliación y Patrimonio."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


# =====================================================
# ReconciliationReport Schemas
# =====================================================


class ReconciliationReportBase(BaseModel):
    """Campos base de reporte de reconciliación."""

    banco: str = Field(..., description="Banco del estado de cuenta: bac o popular")
    periodo_inicio: datetime = Field(..., description="Fecha de inicio del período")
    periodo_fin: datetime = Field(..., description="Fecha de fin del período")
    es_tarjeta_credito: bool = Field(default=False, description="True si es estado de tarjeta de crédito")
    card_id: str | None = Field(None, description="ID de la tarjeta de crédito (si aplica)")
    account_id: str | None = Field(None, description="ID de la cuenta bancaria (si aplica)")


class ReconciliationReportCreate(ReconciliationReportBase):
    """Schema para crear reporte de reconciliación."""

    total_estado_cuenta: Decimal = Field(..., description="Total según el PDF del banco")
    transacciones_estado_cuenta: int = Field(..., description="Número de transacciones en el PDF")
    pdf_email_id: str | None = Field(None, description="ID del email del cual se extrajo el PDF")
    pdf_filename: str | None = Field(None, description="Nombre del archivo PDF procesado")


class ReconciliationReportUpdate(BaseModel):
    """Schema para actualizar reporte de reconciliación."""

    estado: str | None = Field(None, description="Estado: pendiente, en_proceso, completada, fallida")
    notas: str | None = Field(None, max_length=2000, description="Notas del usuario")
    transacciones_matched: int | None = None
    transacciones_discrepantes: int | None = None
    transacciones_faltantes: int | None = None
    transacciones_huerfanas: int | None = None


class ReconciliationReportResponse(BaseModel):
    """Schema de respuesta de reporte de reconciliación."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    banco: str
    periodo_inicio: datetime
    periodo_fin: datetime
    es_tarjeta_credito: bool
    card_id: str | None
    account_id: str | None

    # Totales
    total_estado_cuenta: Decimal
    total_importado: Decimal
    diferencia: Decimal

    # Contadores
    transacciones_estado_cuenta: int
    transacciones_importadas: int
    transacciones_matched: int
    transacciones_discrepantes: int
    transacciones_faltantes: int
    transacciones_huerfanas: int

    # Estado
    estado: str
    notas: str | None
    pdf_email_id: str | None
    pdf_filename: str | None

    # Propiedades calculadas
    tiene_discrepancias: bool = Field(..., description="True si hay diferencias que revisar")
    porcentaje_match: float = Field(..., description="Porcentaje de transacciones que matchearon")

    # Timestamps
    created_at: datetime
    updated_at: datetime
    completado_at: datetime | None


# =====================================================
# PatrimonioSnapshot Schemas
# =====================================================


class PatrimonioSnapshotBase(BaseModel):
    """Campos base de snapshot de patrimonio."""

    fecha_snapshot: datetime = Field(..., description="Fecha y hora del snapshot")
    tipo: str = Field(default="automatico", description="Tipo: manual, automatico, onboarding, reconciliacion")
    notas: str | None = Field(None, max_length=2000, description="Notas opcionales")


class PatrimonioSnapshotCreate(PatrimonioSnapshotBase):
    """Schema para crear snapshot de patrimonio."""

    # Cuentas bancarias
    saldo_cuentas_crc: Decimal = Field(default=Decimal("0.00"), description="Total en cuentas bancarias (colones)")
    saldo_cuentas_usd: Decimal = Field(default=Decimal("0.00"), description="Total en cuentas bancarias (dólares)")

    # Inversiones
    saldo_inversiones_crc: Decimal = Field(default=Decimal("0.00"), description="Total en inversiones (colones)")
    saldo_inversiones_usd: Decimal = Field(default=Decimal("0.00"), description="Total en inversiones (dólares)")

    # Deudas
    deuda_tarjetas_crc: Decimal = Field(default=Decimal("0.00"), description="Deuda en tarjetas (colones)")
    deuda_tarjetas_usd: Decimal = Field(default=Decimal("0.00"), description="Deuda en tarjetas (dólares)")
    deuda_prestamos_crc: Decimal = Field(default=Decimal("0.00"), description="Deuda en préstamos (colones)")
    deuda_prestamos_usd: Decimal = Field(default=Decimal("0.00"), description="Deuda en préstamos (dólares)")

    # Tipo de cambio
    tipo_cambio_usd: Decimal = Field(default=Decimal("510.00"), description="Tipo de cambio USD/CRC")

    # Flags
    es_fecha_base: bool = Field(default=False, description="True si es el snapshot de FECHA_BASE")


class PatrimonioSnapshotUpdate(BaseModel):
    """Schema para actualizar snapshot de patrimonio."""

    notas: str | None = Field(None, max_length=2000)
    saldo_cuentas_crc: Decimal | None = None
    saldo_cuentas_usd: Decimal | None = None
    saldo_inversiones_crc: Decimal | None = None
    saldo_inversiones_usd: Decimal | None = None
    deuda_tarjetas_crc: Decimal | None = None
    deuda_tarjetas_usd: Decimal | None = None
    deuda_prestamos_crc: Decimal | None = None
    deuda_prestamos_usd: Decimal | None = None
    tipo_cambio_usd: Decimal | None = None


class PatrimonioSnapshotResponse(BaseModel):
    """Schema de respuesta de snapshot de patrimonio."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    profile_id: str
    fecha_snapshot: datetime
    tipo: str

    # Desglose de activos
    saldo_cuentas_crc: Decimal
    saldo_cuentas_usd: Decimal
    saldo_inversiones_crc: Decimal
    saldo_inversiones_usd: Decimal

    # Desglose de deudas
    deuda_tarjetas_crc: Decimal
    deuda_tarjetas_usd: Decimal
    deuda_prestamos_crc: Decimal
    deuda_prestamos_usd: Decimal

    # Tipo de cambio
    tipo_cambio_usd: Decimal

    # Totales calculados
    total_activos_crc: Decimal
    total_deudas_crc: Decimal
    patrimonio_neto_crc: Decimal

    # Cambio vs anterior
    cambio_vs_anterior: Decimal | None
    cambio_porcentual: Decimal | None

    # Propiedades
    patrimonio_display: str = Field(..., description="Patrimonio formateado: ₡X,XXX.XX")
    cambio_display: str | None = Field(None, description="Cambio formateado: +₡X,XXX.XX")

    # Flags
    es_fecha_base: bool
    notas: str | None

    # Timestamps
    created_at: datetime
    updated_at: datetime
