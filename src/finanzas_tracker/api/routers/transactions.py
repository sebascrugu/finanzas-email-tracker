"""Router de Transacciones - CRUD completo."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from finanzas_tracker.api.dependencies import ActiveProfile, DBSession
from finanzas_tracker.api.errors import NotFoundError
from finanzas_tracker.api.schemas.transaction import (
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.repositories import TransactionRepository
from finanzas_tracker.services.ambiguous_merchant_service import (
    AmbiguousMerchantService,
    listar_comercios_ambiguos,
)


router = APIRouter(prefix="/transactions")


# Schemas para comercios ambiguos
class ConfirmCategoryRequest(BaseModel):
    """Request para confirmar categoría de comercio ambiguo."""

    categoria: str = Field(..., description="Categoría seleccionada por el usuario")
    notas: str | None = Field(None, description="Notas adicionales")


class AmbiguousTransactionResponse(BaseModel):
    """Transacción pendiente de confirmación."""

    id: str
    comercio: str
    monto_crc: float
    fecha: str
    opciones_categoria: list[str]


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    db: DBSession,
    profile: ActiveProfile,
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(50, ge=1, le=200, description="Límite de registros"),
    mes: date | None = Query(None, description="Filtrar por mes (YYYY-MM-01)"),
    categoria_id: str | None = Query(None, description="Filtrar por subcategoría"),
    tipo: str | None = Query(None, description="Filtrar por tipo de transacción"),
    banco: str | None = Query(None, description="Filtrar por banco"),
    desde: date | None = Query(None, description="Fecha desde"),
    hasta: date | None = Query(None, description="Fecha hasta"),
) -> TransactionListResponse:
    """
    Lista transacciones del perfil activo con filtros opcionales.

    Ordenadas por fecha descendente (más recientes primero).
    """
    repo = TransactionRepository(db)

    # Usar repository para obtener transacciones
    transactions = repo.get_by_profile(
        profile_id=profile.id,
        skip=skip,
        limit=limit,
        mes=mes,
        categoria_id=categoria_id,
        tipo=tipo,
        banco=banco,
        desde=desde,
        hasta=hasta,
    )

    # Contar total con los mismos filtros
    total = repo.count_by_profile(
        profile_id=profile.id,
        mes=mes,
        categoria_id=categoria_id,
        tipo=tipo,
        banco=banco,
        desde=desde,
        hasta=hasta,
    )

    # Calcular total gastado
    total_crc = sum(t.monto_crc for t in transactions)

    return TransactionListResponse(
        items=[TransactionResponse.model_validate(t) for t in transactions],
        total=total,
        skip=skip,
        limit=limit,
        total_crc=total_crc,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: str,
    db: DBSession,
    profile: ActiveProfile,
) -> TransactionResponse:
    """Obtiene una transacción por ID."""
    repo = TransactionRepository(db)
    transaction = repo.get(transaction_id)

    if not transaction or transaction.profile_id != profile.id:
        raise NotFoundError("Transacción", transaction_id)

    return TransactionResponse.model_validate(transaction)


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    data: TransactionCreate,
    db: DBSession,
    profile: ActiveProfile,
) -> TransactionResponse:
    """
    Crea una nueva transacción manualmente.

    Útil para agregar transacciones que no vinieron de email/PDF.
    """
    transaction = Transaction(
        profile_id=profile.id,
        email_id=data.email_id or f"manual_{datetime.now().timestamp()}",
        banco=data.banco,
        tipo_transaccion=data.tipo_transaccion,
        comercio=data.comercio,
        monto_original=data.monto_original,
        moneda_original=data.moneda_original,
        monto_crc=data.monto_crc or data.monto_original,  # Si es CRC, mismo monto
        fecha_transaccion=data.fecha_transaccion,
        subcategory_id=data.subcategory_id,
        notas=data.notas,
        tipo_especial=data.tipo_especial,
        excluir_de_presupuesto=data.excluir_de_presupuesto or False,
        confirmada=True,
    )

    db.add(transaction)
    db.commit()
    db.refresh(transaction)

    return TransactionResponse.model_validate(transaction)


@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: str,
    data: TransactionUpdate,
    db: DBSession,
    profile: ActiveProfile,
) -> TransactionResponse:
    """
    Actualiza una transacción existente.

    Solo actualiza los campos proporcionados.
    """
    stmt = select(Transaction).where(
        Transaction.id == transaction_id,
        Transaction.profile_id == profile.id,
        Transaction.deleted_at.is_(None),
    )
    transaction = db.execute(stmt).scalar_one_or_none()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Transacción no encontrada", "code": "TXN_NOT_FOUND"},
        )

    # Actualizar solo campos proporcionados
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(transaction, field, value)

    db.commit()
    db.refresh(transaction)

    return TransactionResponse.model_validate(transaction)


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: str,
    db: DBSession,
    profile: ActiveProfile,
) -> None:
    """
    Elimina una transacción (soft delete).

    La transacción no se borra físicamente, solo se marca como eliminada.
    """
    stmt = select(Transaction).where(
        Transaction.id == transaction_id,
        Transaction.profile_id == profile.id,
        Transaction.deleted_at.is_(None),
    )
    transaction = db.execute(stmt).scalar_one_or_none()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Transacción no encontrada", "code": "TXN_NOT_FOUND"},
        )

    # Soft delete
    transaction.deleted_at = datetime.now()
    db.commit()


@router.get("/stats/monthly", response_model=dict)
def get_monthly_stats(
    db: DBSession,
    profile: ActiveProfile,
    mes: date = Query(..., description="Mes a consultar (YYYY-MM-01)"),
) -> dict:
    """
    Obtiene estadísticas del mes: total gastado, por categoría, etc.
    """
    year = mes.year
    month = mes.month

    stmt = select(Transaction).where(
        Transaction.profile_id == profile.id,
        Transaction.deleted_at.is_(None),
        Transaction.excluir_de_presupuesto == False,
        func.extract("year", Transaction.fecha_transaccion) == year,
        func.extract("month", Transaction.fecha_transaccion) == month,
    )

    transactions = db.execute(stmt).scalars().all()

    total_crc = sum(t.monto_crc for t in transactions)
    count = len(transactions)

    # Agrupar por categoría
    by_category: dict[str, Decimal] = {}
    for t in transactions:
        cat_id = t.subcategory_id or "sin_categoria"
        by_category[cat_id] = by_category.get(cat_id, Decimal("0")) + t.monto_crc

    return {
        "mes": mes.isoformat(),
        "total_crc": float(total_crc),
        "transacciones": count,
        "promedio_por_transaccion": float(total_crc / count) if count > 0 else 0,
        "por_categoria": {k: float(v) for k, v in by_category.items()},
    }


# ============ Endpoints para Comercios Ambiguos ============


@router.get("/ambiguous/pending", response_model=list[AmbiguousTransactionResponse])
def get_pending_ambiguous(
    db: DBSession,
    profile: ActiveProfile,
) -> list[AmbiguousTransactionResponse]:
    """
    Lista transacciones de comercios ambiguos pendientes de confirmación.

    Comercios como Walmart, Amazon, PriceSmart pueden ser varias categorías.
    El usuario debe confirmar qué compró.
    """
    service = AmbiguousMerchantService(db)
    pendientes = service.obtener_pendientes(profile.id)

    return [AmbiguousTransactionResponse(**p) for p in pendientes]


@router.post("/ambiguous/{transaction_id}/confirm", response_model=TransactionResponse)
def confirm_category(
    transaction_id: str,
    request: ConfirmCategoryRequest,
    db: DBSession,
    profile: ActiveProfile,
) -> TransactionResponse:
    """
    Confirma la categoría de una transacción de comercio ambiguo.

    El usuario selecciona una de las opciones disponibles (ej: Supermercado, Electrónica).
    """
    # Verificar que la transacción pertenece al perfil
    stmt = select(Transaction).where(
        Transaction.id == transaction_id,
        Transaction.profile_id == profile.id,
        Transaction.deleted_at.is_(None),
    )
    transaction = db.execute(stmt).scalar_one_or_none()

    if not transaction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Transacción no encontrada", "code": "TXN_NOT_FOUND"},
        )

    if not transaction.es_comercio_ambiguo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Esta transacción no es de un comercio ambiguo",
                "code": "NOT_AMBIGUOUS",
            },
        )

    service = AmbiguousMerchantService(db)
    updated = service.confirmar_categoria(
        transaction_id=transaction_id,
        categoria_seleccionada=request.categoria,
        notas=request.notas,
    )

    # Commit explícito
    db.commit()

    return TransactionResponse.model_validate(updated)


@router.get("/ambiguous/stats", response_model=dict)
def get_ambiguous_stats(
    db: DBSession,
    profile: ActiveProfile,
) -> dict[str, Any]:
    """Estadísticas de comercios ambiguos."""
    service = AmbiguousMerchantService(db)
    return service.obtener_estadisticas(profile.id)


@router.post("/ambiguous/scan", response_model=dict)
def scan_existing_transactions(
    db: DBSession,
    profile: ActiveProfile,
) -> dict[str, Any]:
    """
    Escanea transacciones existentes y marca las de comercios ambiguos.

    Útil para aplicar la detección a datos históricos.
    """
    service = AmbiguousMerchantService(db)
    count = service.marcar_transacciones_existentes(profile.id)

    # Commit explícito
    db.commit()

    return {
        "message": "Escaneadas transacciones exitosamente",
        "transacciones_marcadas": count,
    }


@router.get("/ambiguous/merchants", response_model=dict)
def get_known_ambiguous_merchants() -> dict[str, list[str]]:
    """
    Lista de comercios conocidos como ambiguos y sus posibles categorías.

    Útil para que el frontend muestre las opciones disponibles.
    """
    return listar_comercios_ambiguos()
