"""
Schemas Pydantic para Onboarding.

Define los modelos de request/response para el flujo de onboarding.
"""

from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field

from finanzas_tracker.models.enums import AccountType, BankName, CardType, Currency


# =============================================================================
# Detecciones (lo que el sistema detecta del PDF)
# =============================================================================


class DetectedAccountResponse(BaseModel):
    """Cuenta detectada automáticamente del PDF."""

    numero_cuenta: str = Field(..., description="Últimos 4 dígitos de la cuenta")
    tipo: str = Field(..., description="Tipo de cuenta (corriente, ahorro, planilla)")
    banco: str = Field(..., description="Banco (bac, popular)")
    saldo: float = Field(..., description="Saldo detectado")
    moneda: str = Field(default="CRC", description="Moneda (CRC, USD)")
    nombre_sugerido: str = Field(..., description="Nombre sugerido para la cuenta")


class DetectedCardResponse(BaseModel):
    """Tarjeta detectada automáticamente del PDF."""

    ultimos_4_digitos: str = Field(..., description="Últimos 4 dígitos")
    marca: str | None = Field(None, description="VISA, Mastercard, etc.")
    banco: str = Field(..., description="Banco emisor")
    tipo_sugerido: str | None = Field(None, description="Tipo sugerido (credito, debito)")
    limite_credito: float | None = Field(None, description="Límite de crédito detectado")
    saldo_actual: float | None = Field(None, description="Saldo actual detectado")
    fecha_corte: int | None = Field(None, description="Día de corte detectado")
    fecha_pago: int | None = Field(None, description="Día de pago detectado")


# =============================================================================
# Estado del Onboarding
# =============================================================================


class OnboardingStateResponse(BaseModel):
    """Estado actual del proceso de onboarding."""

    user_id: str
    profile_id: str | None = None
    current_step: str = Field(..., description="Paso actual: registered, pdf_uploaded, accounts_confirmed, cards_confirmed, budget_set, completed")
    detected_accounts: list[DetectedAccountResponse] = Field(default_factory=list)
    detected_cards: list[DetectedCardResponse] = Field(default_factory=list)
    pdf_processed: bool = False
    email_connected: bool = False
    transactions_count: int = 0
    progress_percent: int = Field(..., description="Porcentaje de progreso (0-100)")

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# Requests
# =============================================================================


class StartOnboardingRequest(BaseModel):
    """Iniciar onboarding (después del registro)."""

    user_id: str = Field(..., description="ID del usuario registrado")


class UploadPDFRequest(BaseModel):
    """Subir PDF de estado de cuenta."""

    banco: str = Field(default="bac", description="Banco del estado de cuenta")
    # El archivo PDF se envía como multipart/form-data


class ConfirmAccountRequest(BaseModel):
    """Datos de una cuenta confirmada/editada por el usuario."""

    numero_cuenta: str = Field(..., min_length=4, max_length=4, description="Últimos 4 dígitos")
    nombre: str = Field(..., min_length=1, max_length=100, description="Nombre de la cuenta")
    tipo: str = Field(..., description="corriente, ahorro, planilla")
    banco: str = Field(..., description="bac, popular")
    saldo: float = Field(..., ge=0, description="Saldo actual")
    moneda: str = Field(default="CRC", description="CRC o USD")
    es_principal: bool = Field(default=False, description="Si es la cuenta principal")


class ConfirmAccountsRequest(BaseModel):
    """Lista de cuentas confirmadas."""

    profile_id: str = Field(..., description="ID del perfil")
    accounts: list[ConfirmAccountRequest] = Field(..., min_length=1)


class ConfirmCardRequest(BaseModel):
    """Datos de una tarjeta confirmada/editada por el usuario."""

    ultimos_4_digitos: str = Field(..., min_length=4, max_length=4)
    tipo: str = Field(..., description="credito o debito")
    banco: str = Field(..., description="bac, popular")
    marca: str | None = Field(None, description="VISA, Mastercard, etc.")
    limite_credito: float | None = Field(None, ge=0, description="Límite (solo crédito)")
    saldo_actual: float = Field(default=0, ge=0, description="Saldo actual")
    fecha_corte: int | None = Field(None, ge=1, le=31, description="Día de corte (1-31)")
    fecha_pago: int | None = Field(None, ge=1, le=31, description="Día de pago (1-31)")
    tasa_interes: float = Field(default=52.0, ge=0, le=100, description="Tasa anual %")


class ConfirmCardsRequest(BaseModel):
    """Lista de tarjetas confirmadas."""

    profile_id: str = Field(..., description="ID del perfil")
    cards: list[ConfirmCardRequest] = Field(..., min_length=1)


# =============================================================================
# Responses
# =============================================================================


class PDFProcessedResponse(BaseModel):
    """Respuesta después de procesar PDF."""

    success: bool
    message: str
    detected_accounts: list[DetectedAccountResponse]
    detected_cards: list[DetectedCardResponse]
    transactions_count: int
    next_step: str = Field(..., description="Siguiente paso sugerido")


class AccountsConfirmedResponse(BaseModel):
    """Respuesta después de confirmar cuentas."""

    success: bool
    accounts_created: int
    next_step: str


class CardsConfirmedResponse(BaseModel):
    """Respuesta después de confirmar tarjetas."""

    success: bool
    cards_created: int
    billing_cycles_created: int
    next_step: str


class OnboardingSummaryResponse(BaseModel):
    """Resumen final del onboarding."""

    status: str = Field(..., description="completed o in_progress")
    progress_percent: int
    summary: dict = Field(..., description="Cuentas, tarjetas, transacciones creadas")
    next_steps: list[str] = Field(..., description="Próximos pasos sugeridos")
