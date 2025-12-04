"""API Router para Suscripciones detectadas.

Endpoints para detectar y listar suscripciones recurrentes.
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from finanzas_tracker.api.dependencies import get_db
from finanzas_tracker.services.subscription_detector import (
    SubscriptionDetector,
)


router = APIRouter(prefix="/subscriptions", tags=["Suscripciones"])


# =============================================================================
# Schemas
# =============================================================================


class SubscriptionResponse(BaseModel):
    """Schema de respuesta para una suscripción detectada."""

    comercio: str = Field(..., description="Nombre del comercio")
    comercio_normalizado: str = Field(..., description="Nombre normalizado")
    monto_promedio: float = Field(..., description="Monto promedio de cobro")
    monto_min: float = Field(..., description="Monto mínimo histórico")
    monto_max: float = Field(..., description="Monto máximo histórico")
    frecuencia: str = Field(..., description="Frecuencia de cobro (semanal, mensual, etc.)")
    dias_promedio_entre_cobros: float = Field(..., description="Días promedio entre cobros")
    ultimo_cobro: date = Field(..., description="Fecha del último cobro")
    primer_cobro: date = Field(..., description="Fecha del primer cobro detectado")
    cantidad_cobros: int = Field(..., description="Cantidad de cobros detectados")
    confianza: int = Field(..., ge=0, le=100, description="Nivel de confianza (0-100)")
    proximo_cobro: date | None = Field(None, description="Fecha estimada del próximo cobro")

    model_config = ConfigDict(from_attributes=True)


class SubscriptionListResponse(BaseModel):
    """Lista de suscripciones con resumen."""

    suscripciones: list[SubscriptionResponse]
    total: int = Field(..., description="Total de suscripciones detectadas")
    gasto_mensual_estimado: float = Field(
        ..., description="Gasto mensual estimado en suscripciones"
    )


class SubscriptionDetectRequest(BaseModel):
    """Request para detectar suscripciones."""

    meses_atras: int = Field(6, ge=1, le=24, description="Meses de historial a analizar")
    min_ocurrencias: int = Field(
        2, ge=2, le=12, description="Mínimo de cobros para considerar suscripción"
    )
    confianza_minima: int = Field(50, ge=0, le=100, description="Confianza mínima requerida")


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_model=SubscriptionListResponse)
def list_subscriptions(
    profile_id: str = Query(..., description="ID del perfil"),
    meses_atras: int = Query(6, ge=1, le=24, description="Meses de historial"),
    confianza_minima: int = Query(50, ge=0, le=100, description="Confianza mínima"),
    db: Session = Depends(get_db),
) -> SubscriptionListResponse:
    """Lista las suscripciones detectadas para un perfil.

    Analiza el historial de transacciones para identificar pagos recurrentes
    como Netflix, Spotify, servicios, etc.
    """
    detector = SubscriptionDetector(db)

    suscripciones = detector.detectar_suscripciones(
        profile_id=profile_id,
        meses_atras=meses_atras,
        confianza_minima=confianza_minima,
    )

    # Calcular gasto mensual
    gasto_mensual = detector.get_gasto_mensual_suscripciones(suscripciones)

    # Convertir a response
    responses = []
    for sub in suscripciones:
        proximo = detector.get_proximo_cobro(sub)
        responses.append(
            SubscriptionResponse(
                comercio=sub.comercio,
                comercio_normalizado=sub.comercio_normalizado,
                monto_promedio=float(sub.monto_promedio),
                monto_min=float(sub.monto_min),
                monto_max=float(sub.monto_max),
                frecuencia=sub.frecuencia.value,
                dias_promedio_entre_cobros=sub.dias_promedio_entre_cobros,
                ultimo_cobro=sub.ultimo_cobro,
                primer_cobro=sub.primer_cobro,
                cantidad_cobros=sub.cantidad_cobros,
                confianza=sub.confianza,
                proximo_cobro=proximo,
            )
        )

    return SubscriptionListResponse(
        suscripciones=responses,
        total=len(responses),
        gasto_mensual_estimado=float(gasto_mensual),
    )


@router.post("/detect", response_model=SubscriptionListResponse)
def detect_subscriptions(
    profile_id: str = Query(..., description="ID del perfil"),
    request: SubscriptionDetectRequest | None = None,
    db: Session = Depends(get_db),
) -> SubscriptionListResponse:
    """Detecta suscripciones en el historial de transacciones.

    Ejecuta el algoritmo de detección con los parámetros especificados.
    """
    if request is None:
        request = SubscriptionDetectRequest()

    detector = SubscriptionDetector(db)

    suscripciones = detector.detectar_suscripciones(
        profile_id=profile_id,
        meses_atras=request.meses_atras,
        min_ocurrencias=request.min_ocurrencias,
        confianza_minima=request.confianza_minima,
    )

    gasto_mensual = detector.get_gasto_mensual_suscripciones(suscripciones)

    responses = []
    for sub in suscripciones:
        proximo = detector.get_proximo_cobro(sub)
        responses.append(
            SubscriptionResponse(
                comercio=sub.comercio,
                comercio_normalizado=sub.comercio_normalizado,
                monto_promedio=float(sub.monto_promedio),
                monto_min=float(sub.monto_min),
                monto_max=float(sub.monto_max),
                frecuencia=sub.frecuencia.value,
                dias_promedio_entre_cobros=sub.dias_promedio_entre_cobros,
                ultimo_cobro=sub.ultimo_cobro,
                primer_cobro=sub.primer_cobro,
                cantidad_cobros=sub.cantidad_cobros,
                confianza=sub.confianza,
                proximo_cobro=proximo,
            )
        )

    return SubscriptionListResponse(
        suscripciones=responses,
        total=len(responses),
        gasto_mensual_estimado=float(gasto_mensual),
    )


@router.get("/known", response_model=SubscriptionListResponse)
def list_known_subscriptions(
    profile_id: str = Query(..., description="ID del perfil"),
    meses_atras: int = Query(3, ge=1, le=12, description="Meses de historial"),
    db: Session = Depends(get_db),
) -> SubscriptionListResponse:
    """Lista solo suscripciones de servicios conocidos.

    Detecta únicamente servicios conocidos como Netflix, Spotify, AWS, GitHub, etc.
    con alta precisión usando patrones específicos.
    """
    detector = SubscriptionDetector(db)

    suscripciones = detector.detectar_conocidas(
        profile_id=profile_id,
        meses_atras=meses_atras,
    )

    gasto_mensual = detector.get_gasto_mensual_suscripciones(suscripciones)

    responses = []
    for sub in suscripciones:
        proximo = detector.get_proximo_cobro(sub)
        responses.append(
            SubscriptionResponse(
                comercio=sub.comercio,
                comercio_normalizado=sub.comercio_normalizado,
                monto_promedio=float(sub.monto_promedio),
                monto_min=float(sub.monto_min),
                monto_max=float(sub.monto_max),
                frecuencia=sub.frecuencia.value,
                dias_promedio_entre_cobros=sub.dias_promedio_entre_cobros,
                ultimo_cobro=sub.ultimo_cobro,
                primer_cobro=sub.primer_cobro,
                cantidad_cobros=sub.cantidad_cobros,
                confianza=sub.confianza,
                proximo_cobro=proximo,
            )
        )

    return SubscriptionListResponse(
        suscripciones=responses,
        total=len(responses),
        gasto_mensual_estimado=float(gasto_mensual),
    )


@router.get("/monthly-total")
def get_monthly_subscription_total(
    profile_id: str = Query(..., description="ID del perfil"),
    db: Session = Depends(get_db),
) -> dict:
    """Obtiene el gasto mensual total en suscripciones.

    Retorna un resumen rápido del gasto mensual estimado.
    """
    detector = SubscriptionDetector(db)

    suscripciones = detector.detectar_suscripciones(
        profile_id=profile_id,
        confianza_minima=60,
    )

    gasto_mensual = detector.get_gasto_mensual_suscripciones(suscripciones)

    return {
        "profile_id": profile_id,
        "gasto_mensual_estimado": float(gasto_mensual),
        "cantidad_suscripciones": len(suscripciones),
        "moneda": "CRC",
    }
