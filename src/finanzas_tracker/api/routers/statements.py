"""API Router para estados de cuenta por email.

Endpoints para:
- Buscar estados de cuenta en el correo
- Procesar un estado específico
- Procesar todos los pendientes
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from finanzas_tracker.services.statement_email_service import (
    StatementEmailInfo,
    StatementEmailService,
)


router = APIRouter(prefix="/statements", tags=["Statements - Email"])


# ============================================================================
# Schemas
# ============================================================================


class StatementEmailResponse(BaseModel):
    """Respuesta con información de un estado de cuenta por email."""

    email_id: str
    subject: str
    sender: str
    received_date: str
    attachment_name: str
    attachment_size_kb: float

    model_config = {"from_attributes": True}


class ProcessedStatementResponse(BaseModel):
    """Respuesta de un estado de cuenta procesado."""

    email_subject: str
    attachment_name: str
    success: bool
    error: str | None = None

    # Datos del estado si fue exitoso
    titular: str | None = None
    fecha_corte: str | None = None
    total_transacciones: int = 0
    cuentas_encontradas: int = 0


class ProcessAllResponse(BaseModel):
    """Respuesta del procesamiento masivo."""

    total_encontrados: int
    procesados_exitosos: int
    procesados_fallidos: int
    detalles: list[ProcessedStatementResponse]


# ============================================================================
# Endpoints
# ============================================================================


@router.get(
    "/email/search",
    response_model=list[StatementEmailResponse],
    summary="Buscar estados de cuenta en el correo",
)
def search_statement_emails(
    days_back: int = Query(30, ge=1, le=365, description="Días hacia atrás para buscar"),
) -> list[StatementEmailResponse]:
    """
    Busca correos con estados de cuenta PDF adjuntos.

    Busca en los últimos N días correos de BAC Credomatic que contengan
    estados de cuenta en formato PDF.
    """
    service = StatementEmailService()

    try:
        statements = service.fetch_statement_emails(days_back=days_back)

        return [
            StatementEmailResponse(
                email_id=stmt.email_id,
                subject=stmt.subject,
                sender=stmt.sender,
                received_date=stmt.received_date.isoformat(),
                attachment_name=stmt.attachment_name,
                attachment_size_kb=stmt.attachment_size / 1024,
            )
            for stmt in statements
        ]

    except RuntimeError as e:
        raise HTTPException(
            status_code=401,
            detail={"error": str(e), "code": "AUTH_REQUIRED"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": f"Error buscando estados de cuenta: {e}", "code": "SEARCH_ERROR"},
        )


@router.post(
    "/email/process/{email_id}",
    response_model=ProcessedStatementResponse,
    summary="Procesar un estado de cuenta específico",
)
def process_single_statement(
    email_id: str,
    attachment_id: str = Query(..., description="ID del adjunto PDF"),
    save_pdf: bool = Query(True, description="Guardar PDF permanentemente"),
) -> ProcessedStatementResponse:
    """
    Procesa un estado de cuenta específico.

    Descarga el PDF adjunto, lo parsea y extrae las transacciones.
    """
    service = StatementEmailService()

    # Crear StatementEmailInfo mínimo para procesar
    stmt_info = StatementEmailInfo(
        email_id=email_id,
        subject="Manual process",
        sender="",
        received_date=None,  # type: ignore
        attachment_id=attachment_id,
        attachment_name="statement.pdf",
        attachment_size=0,
    )

    try:
        result = service.process_statement(stmt_info, save_pdf=save_pdf)

        if result.error or result.statement_result is None:
            return ProcessedStatementResponse(
                email_subject=stmt_info.subject,
                attachment_name=stmt_info.attachment_name,
                success=False,
                error=result.error or "No statement result",
            )

        # Obtener nombre del titular y cuentas según el tipo de resultado
        metadata = result.statement_result.metadata
        nombre_titular = (
            metadata.nombre_titular
            if hasattr(metadata, "nombre_titular")
            else getattr(metadata, "nombre_cliente", "Unknown")
        )
        cuentas_count = len(metadata.cuentas) if hasattr(metadata, "cuentas") else 0

        return ProcessedStatementResponse(
            email_subject=stmt_info.subject,
            attachment_name=stmt_info.attachment_name,
            success=True,
            titular=nombre_titular,
            fecha_corte=metadata.fecha_corte.isoformat(),
            total_transacciones=len(result.statement_result.transactions),
            cuentas_encontradas=cuentas_count,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "code": "PROCESS_ERROR"},
        )


@router.post(
    "/email/process-all",
    response_model=ProcessAllResponse,
    summary="Procesar todos los estados de cuenta pendientes",
)
def process_all_statements(
    profile_id: str = Query(..., description="ID del perfil del usuario"),
    days_back: int = Query(30, ge=1, le=365, description="Días hacia atrás para buscar"),
    save_pdfs: bool = Query(True, description="Guardar PDFs permanentemente"),
) -> ProcessAllResponse:
    """
    Busca y procesa todos los estados de cuenta de los últimos N días.

    Este endpoint:
    1. Busca correos con estados de cuenta
    2. Descarga cada PDF
    3. Parsea y extrae transacciones
    4. Retorna resumen del procesamiento
    """
    service = StatementEmailService()

    try:
        results = service.process_all_pending(
            profile_id=profile_id,
            days_back=days_back,
            save_pdfs=save_pdfs,
        )

        detalles = []
        for result in results:
            if result.error or result.statement_result is None:
                detalles.append(
                    ProcessedStatementResponse(
                        email_subject=result.email_info.subject,
                        attachment_name=result.email_info.attachment_name,
                        success=False,
                        error=result.error or "No statement result",
                    )
                )
            else:
                # Obtener nombre del titular y cuentas según el tipo de resultado
                metadata = result.statement_result.metadata
                nombre_titular = (
                    metadata.nombre_titular
                    if hasattr(metadata, "nombre_titular")
                    else getattr(metadata, "nombre_cliente", "Unknown")
                )
                cuentas_count = len(metadata.cuentas) if hasattr(metadata, "cuentas") else 0

                detalles.append(
                    ProcessedStatementResponse(
                        email_subject=result.email_info.subject,
                        attachment_name=result.email_info.attachment_name,
                        success=True,
                        titular=nombre_titular,
                        fecha_corte=metadata.fecha_corte.isoformat(),
                        total_transacciones=len(result.statement_result.transactions),
                        cuentas_encontradas=cuentas_count,
                    )
                )

        return ProcessAllResponse(
            total_encontrados=len(results),
            procesados_exitosos=sum(1 for r in results if r.error is None),
            procesados_fallidos=sum(1 for r in results if r.error is not None),
            detalles=detalles,
        )

    except RuntimeError as e:
        raise HTTPException(
            status_code=401,
            detail={"error": str(e), "code": "AUTH_REQUIRED"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "code": "PROCESS_ERROR"},
        )


__all__ = ["router"]
