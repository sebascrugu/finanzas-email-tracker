"""Router de Reconciliación - Comparar PDFs con transacciones registradas.

Permite subir un PDF de estado de cuenta y compararlo con las transacciones
ya registradas en el sistema, identificando:
- Transacciones ya registradas (matched)
- Transacciones nuevas (no en el sistema)
- Posibles duplicados

Costa Rica: Soporta BAC y Banco Popular.
"""

from decimal import Decimal
import logging
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from finanzas_tracker.api.schemas.reconciliation import (
    ReconciliationReportResponse,
)
from finanzas_tracker.core.database import get_db
from finanzas_tracker.models.enums import BankName
from finanzas_tracker.services.reconciliation_service import (
    MatchStatus,
    ReconciliationService,
)


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


# ============================================================================
# Schemas
# ============================================================================


class PDFTransactionInfo(BaseModel):
    """Información de transacción del PDF."""

    fecha: str
    comercio: str
    monto: float


class DBTransactionInfo(BaseModel):
    """Información de transacción del sistema."""

    id: int
    fecha: str
    comercio: str
    monto: float


class MatchedTransactionResponse(BaseModel):
    """Transacción del PDF que ya está registrada."""

    model_config = ConfigDict(from_attributes=True)

    status: str
    confidence: float = Field(ge=0, le=1, description="Nivel de confianza del match")
    pdf: PDFTransactionInfo | None = None
    system: DBTransactionInfo | None = None


class ReportSummary(BaseModel):
    """Resumen del reporte de reconciliación."""

    total_pdf: int
    total_sistema: int
    coinciden: int
    diferencia_monto: int
    solo_en_pdf: int
    solo_en_sistema: int
    porcentaje_match: float


class ReconciliationResponse(BaseModel):
    """Resultado completo de la reconciliación."""

    model_config = ConfigDict(from_attributes=True)

    periodo: dict[str, str]
    resumen: ReportSummary
    tiene_problemas: bool
    detalles: dict[str, list[dict[str, Any]]]


class ImportTransactionsRequest(BaseModel):
    """Request para importar transacciones del PDF."""

    profile_id: str
    indices: list[int] = Field(
        default_factory=list,
        description="Índices de transacciones solo_en_pdf a importar",
    )
    default_card_id: str | None = Field(
        default=None,
        description="ID de tarjeta por defecto para transacciones importadas",
    )


class ImportTransactionsResponse(BaseModel):
    """Resultado de importar transacciones."""

    imported_count: int
    transaction_ids: list[int]


class FixAmountRequest(BaseModel):
    """Request para corregir monto de una transacción."""

    transaction_id: str
    new_amount: Decimal
    reason: str = "Corregido según estado de cuenta"


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/upload",
    response_model=ReconciliationResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_and_reconcile(
    pdf_file: UploadFile = File(..., description="PDF del estado de cuenta"),
    profile_id: str = Query(..., description="ID del perfil del usuario"),
    banco: BankName = Query(BankName.BAC, description="Banco del estado de cuenta"),
    db: Session = Depends(get_db),
) -> ReconciliationResponse:
    """Sube un PDF y lo reconcilia con las transacciones existentes.

    El PDF puede ser de:
    - BAC Credomatic (estado de cuenta)
    - Banco Popular (próximamente)

    Retorna un análisis detallado de:
    - Transacciones que ya están registradas (matched)
    - Transacciones nuevas que no están en el sistema (only_in_pdf)
    - Transacciones en sistema que no están en PDF (only_in_system)
    - Diferencias de montos

    Args:
        pdf_file: Archivo PDF del estado de cuenta bancario.
        profile_id: ID del perfil del usuario.
        banco: Banco del estado de cuenta.
        db: Sesión de base de datos.

    Returns:
        ReconciliationResponse con el análisis completo.

    Raises:
        HTTPException: Si el PDF no es válido o no se puede procesar.
    """
    # Validar tipo de archivo
    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "El archivo debe ser un PDF", "code": "INVALID_FILE_TYPE"},
        )

    try:
        # Leer contenido del PDF
        pdf_content = await pdf_file.read()

        if len(pdf_content) < 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "El PDF parece estar vacío", "code": "EMPTY_PDF"},
            )

        # Procesar reconciliación
        service = ReconciliationService(db)
        report = service.reconcile_from_pdf(
            profile_id=profile_id,
            pdf_content=pdf_content,
            banco=banco,
        )

        # Convertir a response usando el método to_dict() del reporte
        report_dict = report.to_dict()

        return ReconciliationResponse(
            periodo=report_dict["periodo"],
            resumen=ReportSummary(**report_dict["resumen"]),
            tiene_problemas=report_dict["tiene_problemas"],
            detalles=report_dict["detalles"],
        )

    except ValueError as e:
        logger.warning(f"Error de validación en reconciliación: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "code": "PDF_PARSE_ERROR"},
        )
    except Exception as e:
        logger.error(f"Error procesando PDF para reconciliación: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Error procesando el PDF", "code": "RECONCILIATION_ERROR"},
        )


@router.post(
    "/import-new",
    response_model=ImportTransactionsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_new_transactions(
    request: ImportTransactionsRequest,
    pdf_file: UploadFile = File(..., description="PDF del estado de cuenta"),
    banco: BankName = Query(BankName.BAC, description="Banco del estado de cuenta"),
    db: Session = Depends(get_db),
) -> ImportTransactionsResponse:
    """Importa transacciones que solo están en el PDF.

    Después de revisar los resultados del endpoint /upload, el usuario puede
    seleccionar qué transacciones solo_en_pdf desea importar al sistema.

    Args:
        request: Configuración de qué importar.
        pdf_file: PDF original (se re-procesa para obtener datos).
        banco: Banco del estado de cuenta.
        db: Sesión de base de datos.

    Returns:
        Resumen de transacciones importadas.
    """
    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "El archivo debe ser un PDF", "code": "INVALID_FILE_TYPE"},
        )

    try:
        pdf_content = await pdf_file.read()

        service = ReconciliationService(db)

        # Re-procesar para obtener resultado fresco
        report = service.reconcile_from_pdf(
            profile_id=request.profile_id,
            pdf_content=pdf_content,
            banco=banco,
        )

        # Filtrar solo los índices solicitados
        if request.indices:
            transactions_to_import = [
                report.only_in_pdf[i] for i in request.indices if i < len(report.only_in_pdf)
            ]
        else:
            # Importar todas las transacciones solo_en_pdf
            transactions_to_import = report.only_in_pdf

        # Importar
        created = service.import_pdf_only_transactions(
            profile_id=request.profile_id,
            transactions=transactions_to_import,
            default_card_id=request.default_card_id,
        )

        return ImportTransactionsResponse(
            imported_count=len(created),
            transaction_ids=[tx.id for tx in created],
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "code": "IMPORT_ERROR"},
        )
    except Exception as e:
        logger.error(f"Error importando transacciones: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Error importando transacciones", "code": "IMPORT_ERROR"},
        )


@router.post(
    "/fix-amount",
    status_code=status.HTTP_200_OK,
)
async def fix_transaction_amount(
    request: FixAmountRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Corrige el monto de una transacción con discrepancia.

    Cuando la reconciliación detecta una diferencia de monto entre el PDF
    y el sistema, el usuario puede corregir el monto en el sistema.

    Args:
        request: Datos de la corrección.
        db: Sesión de base de datos.

    Returns:
        Transacción corregida.
    """
    service = ReconciliationService(db)

    tx = service.fix_amount_mismatch(
        transaction_id=request.transaction_id,
        new_amount=request.new_amount,
        reason=request.reason,
    )

    if not tx:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Transacción no encontrada", "code": "TXN_NOT_FOUND"},
        )

    return {
        "id": tx.id,
        "monto_original": float(tx.monto_original),
        "monto_crc": float(tx.monto_crc),
        "notas": tx.notas,
        "mensaje": "Monto corregido exitosamente",
    }


@router.get(
    "/match-statuses",
    response_model=list[dict[str, str]],
)
async def get_match_statuses() -> list[dict[str, str]]:
    """Obtiene los estados de match disponibles.

    Útil para UI que necesita mostrar las opciones de matching.
    """
    return [
        {
            "value": MatchStatus.MATCHED.value,
            "label": "Coincide",
            "description": "Transacción encontrada en ambos (PDF y sistema)",
        },
        {
            "value": MatchStatus.AMOUNT_MISMATCH.value,
            "label": "Diferencia de monto",
            "description": "Misma transacción pero con monto diferente",
        },
        {
            "value": MatchStatus.ONLY_IN_PDF.value,
            "label": "Solo en PDF",
            "description": "Transacción nueva que no está en el sistema",
        },
        {
            "value": MatchStatus.ONLY_IN_SYSTEM.value,
            "label": "Solo en sistema",
            "description": "Transacción del sistema que no está en el PDF",
        },
    ]


@router.get(
    "/bancos",
    response_model=list[dict[str, str]],
)
async def get_supported_banks() -> list[dict[str, str]]:
    """Obtiene los bancos soportados para reconciliación."""
    return [
        {
            "value": BankName.BAC.value,
            "label": "BAC Credomatic",
            "supported": "true",
        },
        {
            "value": BankName.POPULAR.value,
            "label": "Banco Popular",
            "supported": "false",  # Próximamente
        },
    ]


# =============================================================================
# Reportes de Reconciliación Persistidos
# =============================================================================


@router.post(
    "/upload-and-save",
    response_model=ReconciliationReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_reconcile_and_save(
    pdf_file: UploadFile = File(..., description="PDF del estado de cuenta"),
    profile_id: str = Query(..., description="ID del perfil del usuario"),
    banco: BankName = Query(BankName.BAC, description="Banco del estado de cuenta"),
    db: Session = Depends(get_db),
) -> ReconciliationReportResponse:
    """Sube un PDF, lo reconcilia y guarda el reporte en la base de datos.

    Similar a /upload pero persiste el resultado para historial.
    """
    if not pdf_file.filename or not pdf_file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "El archivo debe ser un PDF", "code": "INVALID_FILE_TYPE"},
        )

    try:
        pdf_content = await pdf_file.read()

        if len(pdf_content) < 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "El PDF parece estar vacío", "code": "EMPTY_PDF"},
            )

        service = ReconciliationService(db)

        # Reconciliar
        result = service.reconcile_from_pdf(
            profile_id=profile_id,
            pdf_content=pdf_content,
            banco=banco,
        )

        # Guardar reporte
        reporte = service.guardar_reporte(
            profile_id=profile_id,
            result=result,
            banco=banco.value.upper(),
        )

        return ReconciliationReportResponse.model_validate(reporte)

    except ValueError as e:
        logger.warning(f"Error de validación en reconciliación: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "code": "PDF_PARSE_ERROR"},
        )


@router.get("/reportes", response_model=list[ReconciliationReportResponse])
def listar_reportes(
    profile_id: str = Query(..., description="ID del perfil"),
    limite: int = Query(10, ge=1, le=50, description="Máximo de reportes"),
    db: Session = Depends(get_db),
) -> list[ReconciliationReportResponse]:
    """Lista reportes de reconciliación de un perfil."""
    service = ReconciliationService(db)
    reportes = service.get_reportes(profile_id, limite=limite)
    return [ReconciliationReportResponse.model_validate(r) for r in reportes]


@router.get("/reportes/{reporte_id}", response_model=ReconciliationReportResponse)
def obtener_reporte(
    reporte_id: int,
    db: Session = Depends(get_db),
) -> ReconciliationReportResponse:
    """Obtiene un reporte específico por ID."""
    service = ReconciliationService(db)
    reporte = service.get_reporte(reporte_id)

    if not reporte:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Reporte no encontrado", "code": "REPORT_NOT_FOUND"},
        )

    return ReconciliationReportResponse.model_validate(reporte)


@router.post("/reportes/{reporte_id}/aceptar")
def aceptar_reconciliacion(
    reporte_id: int,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Acepta una reconciliación y marca transacciones como reconciliadas.

    Marca todas las transacciones coincidentes del reporte como RECONCILED.
    """
    service = ReconciliationService(db)
    reporte = service.get_reporte(reporte_id)

    if not reporte:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Reporte no encontrado", "code": "REPORT_NOT_FOUND"},
        )

    # Marcar transacciones coincidentes como reconciliadas
    transaction_ids = reporte.ids_coincidentes or []
    count = service.marcar_transacciones_reconciliadas(reporte_id, transaction_ids)

    return {
        "mensaje": f"Reconciliación aceptada. {count} transacciones marcadas como reconciliadas.",
        "transacciones_reconciliadas": count,
        "reporte_id": reporte_id,
    }


class ResolverDiscrepanciaRequest(BaseModel):
    """Request para resolver una discrepancia."""

    accion: str = Field(..., description="ajustar_monto, confirmar, cancelar")
    monto_ajustado: Decimal | None = Field(None, description="Nuevo monto si acción es ajustar")
    razon: str | None = Field(None, description="Razón del ajuste")


@router.post("/reportes/{reporte_id}/resolver/{transaction_id}")
def resolver_discrepancia(
    reporte_id: int,
    transaction_id: int,
    request: ResolverDiscrepanciaRequest,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Resuelve una discrepancia de una transacción.

    Acciones posibles:
    - ajustar_monto: Cambia el monto de la transacción
    - confirmar: Marca como correcta (confirma)
    - cancelar: Marca como cancelada

    Args:
        reporte_id: ID del reporte de reconciliación.
        transaction_id: ID de la transacción con discrepancia.
        request: Datos de la resolución.
    """
    service = ReconciliationService(db)

    try:
        txn = service.resolver_discrepancia(
            reporte_id=reporte_id,
            transaction_id=transaction_id,
            accion=request.accion,
            monto_ajustado=request.monto_ajustado,
            razon=request.razon,
        )

        return {
            "mensaje": f"Discrepancia resuelta: {request.accion}",
            "transaction_id": txn.id,
            "estado": txn.estado.value if txn.estado else None,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": str(e), "code": "INVALID_ACTION"},
        )
