"""
Router de Onboarding.

Endpoints para el flujo de configuración inicial de nuevos usuarios.
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from finanzas_tracker.api.dependencies import get_db
from finanzas_tracker.api.schemas.onboarding import (
    AccountsConfirmedResponse,
    CardsConfirmedResponse,
    ConfirmAccountsRequest,
    ConfirmCardsRequest,
    OnboardingStateResponse,
    OnboardingSummaryResponse,
    PDFProcessedResponse,
    StartOnboardingRequest,
)
from finanzas_tracker.models.enums import BankName
from finanzas_tracker.services.onboarding_service import OnboardingService


router = APIRouter(prefix="/onboarding", tags=["Onboarding"])


def get_onboarding_service(db: Session = Depends(get_db)) -> OnboardingService:
    """Dependency para obtener el servicio de onboarding."""
    return OnboardingService(db)


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/start",
    response_model=OnboardingStateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Iniciar onboarding",
    description="Inicia el proceso de configuración para un usuario recién registrado.",
)
def start_onboarding(
    request: StartOnboardingRequest,
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingStateResponse:
    """Inicia el proceso de onboarding."""
    state = service.start_onboarding(request.user_id)
    return OnboardingStateResponse(**state.to_dict())


@router.get(
    "/{user_id}/status",
    response_model=OnboardingStateResponse,
    summary="Estado del onboarding",
    description="Obtiene el estado actual del proceso de onboarding.",
)
def get_onboarding_status(
    user_id: str,
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingStateResponse:
    """Obtiene el estado actual del onboarding."""
    state = service.get_state(user_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Onboarding no encontrado", "code": "ONBOARDING_NOT_FOUND"},
        )
    return OnboardingStateResponse(**state.to_dict())


@router.post(
    "/{user_id}/upload-pdf",
    response_model=PDFProcessedResponse,
    summary="Subir PDF de estado de cuenta",
    description="Procesa un PDF de estado de cuenta y detecta cuentas/tarjetas automáticamente.",
)
async def upload_pdf(
    user_id: str,
    file: UploadFile = File(..., description="PDF del estado de cuenta"),
    banco: str = Form(default="bac", description="Banco: bac o popular"),
    service: OnboardingService = Depends(get_onboarding_service),
) -> PDFProcessedResponse:
    """Procesa PDF y extrae información."""
    # Validar archivo
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "El archivo debe ser un PDF", "code": "INVALID_FILE_TYPE"},
        )

    # Validar banco
    try:
        bank_enum = BankName(banco.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"Banco no soportado: {banco}", "code": "UNSUPPORTED_BANK"},
        )

    # Leer contenido
    content = await file.read()

    # Procesar
    state = service.process_pdf(user_id, content, bank_enum)

    return PDFProcessedResponse(
        success=state.pdf_processed,
        message="PDF procesado exitosamente" if state.pdf_processed else "Error al procesar PDF",
        detected_accounts=[a.to_dict() for a in state.detected_accounts],
        detected_cards=[c.to_dict() for c in state.detected_cards],
        transactions_count=state.transactions_count,
        next_step="confirm_accounts",
    )


@router.post(
    "/{user_id}/confirm-accounts",
    response_model=AccountsConfirmedResponse,
    summary="Confirmar cuentas detectadas",
    description="Crea las cuentas después de que el usuario las confirme/edite.",
)
def confirm_accounts(
    user_id: str,
    request: ConfirmAccountsRequest,
    service: OnboardingService = Depends(get_onboarding_service),
) -> AccountsConfirmedResponse:
    """Confirma y crea las cuentas."""
    try:
        accounts = service.confirm_accounts(
            user_id=user_id,
            profile_id=request.profile_id,
            confirmed_accounts=[acc.model_dump() for acc in request.accounts],
        )
        return AccountsConfirmedResponse(
            success=True,
            accounts_created=len(accounts),
            next_step="confirm_cards",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "code": "INVALID_REQUEST"},
        )


@router.post(
    "/{user_id}/confirm-cards",
    response_model=CardsConfirmedResponse,
    summary="Confirmar tarjetas detectadas",
    description="Crea las tarjetas después de que el usuario las confirme/edite.",
)
def confirm_cards(
    user_id: str,
    request: ConfirmCardsRequest,
    service: OnboardingService = Depends(get_onboarding_service),
) -> CardsConfirmedResponse:
    """Confirma y crea las tarjetas."""
    try:
        cards = service.confirm_cards(
            user_id=user_id,
            profile_id=request.profile_id,
            confirmed_cards=[card.model_dump() for card in request.cards],
        )

        # Contar ciclos creados (solo tarjetas de crédito con fecha de corte)
        cycles_created = sum(1 for c in cards if c.es_credito and c.fecha_corte)

        return CardsConfirmedResponse(
            success=True,
            cards_created=len(cards),
            billing_cycles_created=cycles_created,
            next_step="complete",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "code": "INVALID_REQUEST"},
        )


@router.post(
    "/{user_id}/complete",
    response_model=OnboardingSummaryResponse,
    summary="Completar onboarding",
    description="Marca el onboarding como completado y retorna un resumen.",
)
def complete_onboarding(
    user_id: str,
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingSummaryResponse:
    """Completa el onboarding y retorna resumen."""
    service.complete_onboarding(user_id)
    summary = service.get_onboarding_summary(user_id)

    if "error" in summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": summary["error"], "code": "ONBOARDING_NOT_FOUND"},
        )

    return OnboardingSummaryResponse(**summary)


@router.get(
    "/{user_id}/summary",
    response_model=OnboardingSummaryResponse,
    summary="Resumen del onboarding",
    description="Obtiene un resumen del onboarding (completado o en progreso).",
)
def get_onboarding_summary(
    user_id: str,
    service: OnboardingService = Depends(get_onboarding_service),
) -> OnboardingSummaryResponse:
    """Obtiene el resumen del onboarding."""
    summary = service.get_onboarding_summary(user_id)

    if "error" in summary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": summary["error"], "code": "ONBOARDING_NOT_FOUND"},
        )

    return OnboardingSummaryResponse(**summary)
