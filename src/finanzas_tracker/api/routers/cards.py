"""
API endpoints para gestión de tarjetas de crédito y ciclos de facturación.

Endpoints:
- GET /cards - Listar tarjetas del perfil
- GET /cards/{id} - Detalle de tarjeta con resumen
- GET /cards/{id}/cycles - Ciclos de facturación
- POST /cards/{id}/cycles - Crear nuevo ciclo
- POST /cards/{id}/cycles/{cycle_id}/close - Cerrar ciclo
- GET /cards/{id}/payments - Historial de pagos
- POST /cards/{id}/payments - Registrar pago
- GET /cards/alerts - Alertas de vencimiento
"""

from datetime import date
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from finanzas_tracker.core.database import get_db
from finanzas_tracker.models.enums import CardPaymentType, CardType
from finanzas_tracker.services.card_service import CardService

router = APIRouter(prefix="/cards", tags=["Tarjetas"])


# =============================================================================
# Schemas
# =============================================================================


class CardResponse(BaseModel):
    """Respuesta con información de tarjeta."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    ultimos_4_digitos: str
    tipo: str
    banco: str
    alias: str | None = None
    limite_credito: float | None = None
    fecha_corte: int | None = None
    fecha_vencimiento: int | None = None
    interest_rate_annual: float | None = None
    activa: bool = True


class CardSummaryResponse(BaseModel):
    """Resumen completo del estado de una tarjeta."""

    tarjeta: dict
    deuda_total: float
    disponible: float | None
    porcentaje_usado: float | None
    ciclo_actual: dict | None
    proximo_pago: dict | None
    ciclos_pendientes: int
    ultimos_pagos: list[dict]


class BillingCycleResponse(BaseModel):
    """Respuesta con información de ciclo de facturación."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    card_id: str
    fecha_inicio: date
    fecha_corte: date
    fecha_pago: date
    total_periodo: float
    saldo_anterior: float
    intereses_periodo: float
    total_a_pagar: float
    pago_minimo: float
    monto_pagado: float
    status: str
    saldo_pendiente: float
    dias_para_pago: int | None
    porcentaje_pagado: float


class BillingCycleCreate(BaseModel):
    """Schema para crear un ciclo de facturación."""

    fecha_inicio: date = Field(..., description="Fecha de inicio del período")
    fecha_corte: date = Field(..., description="Fecha de corte")
    fecha_pago: date = Field(..., description="Fecha límite de pago")
    saldo_anterior: float = Field(
        default=0.0,
        ge=0,
        description="Saldo arrastrado del ciclo anterior",
    )


class PaymentResponse(BaseModel):
    """Respuesta con información de pago."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    card_id: str
    billing_cycle_id: str | None
    monto: float
    tipo: str
    fecha_pago: date
    referencia: str | None
    notas: str | None


class PaymentCreate(BaseModel):
    """Schema para registrar un pago."""

    monto: float = Field(..., gt=0, description="Monto del pago")
    fecha_pago: date | None = Field(
        default=None,
        description="Fecha del pago (default: hoy)",
    )
    billing_cycle_id: str | None = Field(
        default=None,
        description="ID del ciclo de facturación (opcional)",
    )
    tipo: CardPaymentType | None = Field(
        default=None,
        description="Tipo de pago (auto-detectado si no se especifica)",
    )
    referencia: str | None = Field(
        default=None,
        description="Referencia bancaria",
    )
    notas: str | None = Field(default=None, description="Notas adicionales")


class AlertResponse(BaseModel):
    """Respuesta de alerta de vencimiento."""

    card_id: str
    card_nombre: str
    cycle_id: str
    fecha_pago: str
    dias_restantes: int
    monto_pendiente: float
    pago_minimo: float
    es_urgente: bool


class InterestProjectionResponse(BaseModel):
    """Proyección de intereses."""

    deuda_inicial: float
    tasa_mensual: float
    meses_proyectados: int
    total_intereses: float
    saldo_final: float
    historial: list[dict]


# =============================================================================
# Endpoints - Tarjetas
# =============================================================================


@router.get("", response_model=list[CardResponse])
def list_cards(
    profile_id: Annotated[str, Query(description="ID del perfil")],
    tipo: Annotated[CardType | None, Query(description="Filtrar por tipo")] = None,
    db: Session = Depends(get_db),
) -> list[CardResponse]:
    """
    Lista las tarjetas de un perfil.

    Retorna todas las tarjetas activas (no eliminadas) del perfil,
    opcionalmente filtradas por tipo (débito/crédito).
    """
    service = CardService(db)
    cards = service.get_cards_by_profile(profile_id, tipo=tipo)
    return [CardResponse.model_validate(card) for card in cards]


@router.get("/{card_id}", response_model=CardSummaryResponse)
def get_card_summary(
    card_id: str,
    db: Session = Depends(get_db),
) -> CardSummaryResponse:
    """
    Obtiene el resumen completo de una tarjeta.

    Incluye:
    - Información de la tarjeta
    - Deuda total y disponible
    - Ciclo actual
    - Próximo pago
    - Últimos pagos realizados
    """
    service = CardService(db)
    summary = service.get_card_summary(card_id)

    if not summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Tarjeta no encontrada", "code": "CARD_NOT_FOUND"},
        )

    return CardSummaryResponse(**summary)


@router.get("/{card_id}/interest-projection", response_model=InterestProjectionResponse)
def get_interest_projection(
    card_id: str,
    meses: Annotated[int, Query(ge=1, le=24, description="Meses a proyectar")] = 6,
    db: Session = Depends(get_db),
) -> InterestProjectionResponse:
    """
    Proyecta intereses si solo se paga el mínimo.

    Calcula cuánto pagarías en intereses si solo pagas el mínimo
    durante los próximos N meses.
    """
    service = CardService(db)
    projection = service.calculate_interest_projection(card_id, meses=meses)

    if "error" in projection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": projection["error"], "code": "CARD_ERROR"},
        )

    return InterestProjectionResponse(**projection)


# =============================================================================
# Endpoints - Ciclos de Facturación
# =============================================================================


@router.get("/{card_id}/cycles", response_model=list[BillingCycleResponse])
def list_billing_cycles(
    card_id: str,
    limit: Annotated[int, Query(ge=1, le=24, description="Límite de ciclos")] = 12,
    db: Session = Depends(get_db),
) -> list[BillingCycleResponse]:
    """
    Lista los ciclos de facturación de una tarjeta.

    Retorna los últimos N ciclos ordenados por fecha de corte
    (más reciente primero).
    """
    service = CardService(db)
    cycles = service.get_cycles_by_card(card_id, limit=limit)

    return [
        BillingCycleResponse(
            id=c.id,
            card_id=c.card_id,
            fecha_inicio=c.fecha_inicio,
            fecha_corte=c.fecha_corte,
            fecha_pago=c.fecha_pago,
            total_periodo=float(c.total_periodo),
            saldo_anterior=float(c.saldo_anterior),
            intereses_periodo=float(c.intereses_periodo),
            total_a_pagar=float(c.total_a_pagar),
            pago_minimo=float(c.pago_minimo),
            monto_pagado=float(c.monto_pagado),
            status=c.status,
            saldo_pendiente=float(c.saldo_pendiente),
            dias_para_pago=c.dias_para_pago,
            porcentaje_pagado=c.porcentaje_pagado,
        )
        for c in cycles
    ]


@router.post("/{card_id}/cycles", response_model=BillingCycleResponse, status_code=201)
def create_billing_cycle(
    card_id: str,
    data: BillingCycleCreate,
    db: Session = Depends(get_db),
) -> BillingCycleResponse:
    """
    Crea un nuevo ciclo de facturación.

    Normalmente los ciclos se crean automáticamente basándose en
    la configuración de la tarjeta (fecha_corte, fecha_vencimiento).
    Este endpoint es para casos especiales o importación de datos.
    """
    service = CardService(db)

    # Verificar que la tarjeta existe
    card = service.get_card(card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Tarjeta no encontrada", "code": "CARD_NOT_FOUND"},
        )

    # Verificar que no haya un ciclo abierto
    current = service.get_current_cycle(card_id)
    if current:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Ya existe un ciclo abierto para esta tarjeta",
                "code": "CYCLE_ALREADY_OPEN",
                "cycle_id": current.id,
            },
        )

    cycle = service.create_cycle(
        card_id=card_id,
        fecha_inicio=data.fecha_inicio,
        fecha_corte=data.fecha_corte,
        fecha_pago=data.fecha_pago,
        saldo_anterior=Decimal(str(data.saldo_anterior)),
    )

    return BillingCycleResponse(
        id=cycle.id,
        card_id=cycle.card_id,
        fecha_inicio=cycle.fecha_inicio,
        fecha_corte=cycle.fecha_corte,
        fecha_pago=cycle.fecha_pago,
        total_periodo=float(cycle.total_periodo),
        saldo_anterior=float(cycle.saldo_anterior),
        intereses_periodo=float(cycle.intereses_periodo),
        total_a_pagar=float(cycle.total_a_pagar),
        pago_minimo=float(cycle.pago_minimo),
        monto_pagado=float(cycle.monto_pagado),
        status=cycle.status,
        saldo_pendiente=float(cycle.saldo_pendiente),
        dias_para_pago=cycle.dias_para_pago,
        porcentaje_pagado=cycle.porcentaje_pagado,
    )


@router.post("/{card_id}/cycles/auto", response_model=BillingCycleResponse, status_code=201)
def create_billing_cycle_auto(
    card_id: str,
    db: Session = Depends(get_db),
) -> BillingCycleResponse:
    """
    Crea automáticamente el próximo ciclo basándose en la configuración de la tarjeta.

    Usa fecha_corte y fecha_vencimiento de la tarjeta para calcular
    las fechas del nuevo ciclo.
    """
    service = CardService(db)

    card = service.get_card(card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Tarjeta no encontrada", "code": "CARD_NOT_FOUND"},
        )

    if not card.es_credito:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Solo las tarjetas de crédito tienen ciclos de facturación",
                "code": "NOT_CREDIT_CARD",
            },
        )

    # Verificar que no haya un ciclo abierto
    current = service.get_current_cycle(card_id)
    if current:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Ya existe un ciclo abierto para esta tarjeta",
                "code": "CYCLE_ALREADY_OPEN",
                "cycle_id": current.id,
            },
        )

    cycle = service.create_next_cycle_for_card(card)
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "No se pudo crear el ciclo. Verifica que la tarjeta tenga fecha_corte configurada.",
                "code": "CYCLE_CREATION_FAILED",
            },
        )

    return BillingCycleResponse(
        id=cycle.id,
        card_id=cycle.card_id,
        fecha_inicio=cycle.fecha_inicio,
        fecha_corte=cycle.fecha_corte,
        fecha_pago=cycle.fecha_pago,
        total_periodo=float(cycle.total_periodo),
        saldo_anterior=float(cycle.saldo_anterior),
        intereses_periodo=float(cycle.intereses_periodo),
        total_a_pagar=float(cycle.total_a_pagar),
        pago_minimo=float(cycle.pago_minimo),
        monto_pagado=float(cycle.monto_pagado),
        status=cycle.status,
        saldo_pendiente=float(cycle.saldo_pendiente),
        dias_para_pago=cycle.dias_para_pago,
        porcentaje_pagado=cycle.porcentaje_pagado,
    )


@router.post("/{card_id}/cycles/{cycle_id}/close", response_model=BillingCycleResponse)
def close_billing_cycle(
    card_id: str,
    cycle_id: str,
    db: Session = Depends(get_db),
) -> BillingCycleResponse:
    """
    Cierra un ciclo de facturación.

    Calcula el total a pagar y el pago mínimo. Normalmente esto
    sucede automáticamente cuando pasa la fecha de corte.
    """
    service = CardService(db)

    cycle = service.close_cycle(cycle_id)
    if not cycle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Ciclo no encontrado", "code": "CYCLE_NOT_FOUND"},
        )

    if cycle.card_id != card_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "El ciclo no pertenece a esta tarjeta", "code": "CYCLE_MISMATCH"},
        )

    return BillingCycleResponse(
        id=cycle.id,
        card_id=cycle.card_id,
        fecha_inicio=cycle.fecha_inicio,
        fecha_corte=cycle.fecha_corte,
        fecha_pago=cycle.fecha_pago,
        total_periodo=float(cycle.total_periodo),
        saldo_anterior=float(cycle.saldo_anterior),
        intereses_periodo=float(cycle.intereses_periodo),
        total_a_pagar=float(cycle.total_a_pagar),
        pago_minimo=float(cycle.pago_minimo),
        monto_pagado=float(cycle.monto_pagado),
        status=cycle.status,
        saldo_pendiente=float(cycle.saldo_pendiente),
        dias_para_pago=cycle.dias_para_pago,
        porcentaje_pagado=cycle.porcentaje_pagado,
    )


# =============================================================================
# Endpoints - Pagos
# =============================================================================


@router.get("/{card_id}/payments", response_model=list[PaymentResponse])
def list_payments(
    card_id: str,
    limit: Annotated[int, Query(ge=1, le=100, description="Límite de pagos")] = 50,
    db: Session = Depends(get_db),
) -> list[PaymentResponse]:
    """
    Lista los pagos realizados a una tarjeta.

    Retorna los últimos N pagos ordenados por fecha (más reciente primero).
    """
    service = CardService(db)
    payments = service.get_payments_by_card(card_id, limit=limit)

    return [
        PaymentResponse(
            id=p.id,
            card_id=p.card_id,
            billing_cycle_id=p.billing_cycle_id,
            monto=float(p.monto),
            tipo=p.tipo.value,
            fecha_pago=p.fecha_pago,
            referencia=p.referencia,
            notas=p.notas,
        )
        for p in payments
    ]


@router.post("/{card_id}/payments", response_model=PaymentResponse, status_code=201)
def register_payment(
    card_id: str,
    data: PaymentCreate,
    db: Session = Depends(get_db),
) -> PaymentResponse:
    """
    Registra un pago a la tarjeta.

    Si se especifica billing_cycle_id, el monto se aplicará al ciclo
    correspondiente y se actualizará su estado.
    """
    service = CardService(db)

    # Verificar que la tarjeta existe
    card = service.get_card(card_id)
    if not card:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Tarjeta no encontrada", "code": "CARD_NOT_FOUND"},
        )

    payment = service.register_payment(
        card_id=card_id,
        monto=Decimal(str(data.monto)),
        fecha_pago=data.fecha_pago,
        billing_cycle_id=data.billing_cycle_id,
        tipo=data.tipo,
        referencia=data.referencia,
        notas=data.notas,
    )

    return PaymentResponse(
        id=payment.id,
        card_id=payment.card_id,
        billing_cycle_id=payment.billing_cycle_id,
        monto=float(payment.monto),
        tipo=payment.tipo.value,
        fecha_pago=payment.fecha_pago,
        referencia=payment.referencia,
        notas=payment.notas,
    )


# =============================================================================
# Endpoints - Alertas
# =============================================================================


@router.get("/alerts/upcoming", response_model=list[AlertResponse])
def get_upcoming_payment_alerts(
    profile_id: Annotated[str, Query(description="ID del perfil")],
    dias: Annotated[int, Query(ge=1, le=30, description="Días a considerar")] = 7,
    db: Session = Depends(get_db),
) -> list[AlertResponse]:
    """
    Obtiene alertas de pagos que vencen próximamente.

    Retorna las tarjetas con pagos que vencen en los próximos N días,
    ordenadas por urgencia (días restantes).
    """
    service = CardService(db)
    alerts = service.get_upcoming_payments(profile_id, dias=dias)
    return [AlertResponse(**alert) for alert in alerts]


@router.get("/alerts/overdue", response_model=list[dict])
def get_overdue_alerts(
    profile_id: Annotated[str, Query(description="ID del perfil")],
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    Obtiene alertas de pagos vencidos.

    Retorna las tarjetas con pagos que ya pasaron su fecha de pago,
    incluyendo los intereses estimados por mora.
    """
    service = CardService(db)
    return service.get_overdue_cycles(profile_id)
