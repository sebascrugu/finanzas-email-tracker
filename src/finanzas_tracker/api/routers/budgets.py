"""Router de Presupuestos - CRUD + resumen."""

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from finanzas_tracker.api.dependencies import ActiveProfile, DBSession
from finanzas_tracker.api.schemas.budget import (
    BudgetCreate,
    BudgetListResponse,
    BudgetResponse,
    BudgetSummaryResponse,
    BudgetUpdate,
    CategoryBudgetSummary,
)
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.transaction import Transaction


router = APIRouter(prefix="/budgets")


@router.get("", response_model=BudgetListResponse)
def list_budgets(
    db: DBSession,
    profile: ActiveProfile,
    mes: date | None = Query(None, description="Filtrar por mes (YYYY-MM-01)"),
) -> BudgetListResponse:
    """Lista presupuestos del perfil activo."""
    stmt = select(Budget).where(Budget.profile_id == profile.id)

    if mes:
        stmt = stmt.where(Budget.mes == mes)

    stmt = stmt.order_by(Budget.mes.desc())
    budgets = db.execute(stmt).scalars().all()

    return BudgetListResponse(
        items=[BudgetResponse.model_validate(b) for b in budgets],
        total=len(budgets),
    )


@router.post("", response_model=BudgetResponse, status_code=status.HTTP_201_CREATED)
def create_budget(
    data: BudgetCreate,
    db: DBSession,
    profile: ActiveProfile,
) -> BudgetResponse:
    """
    Crea un nuevo presupuesto para una categoría en un mes.

    Solo puede haber un presupuesto por categoría por mes.
    """
    # Verificar que no exista ya
    stmt = select(Budget).where(
        Budget.profile_id == profile.id,
        Budget.category_id == data.category_id,
        Budget.mes == data.mes,
    )
    existing = db.execute(stmt).scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "Ya existe un presupuesto para esta categoría en este mes",
                "code": "BUDGET_EXISTS",
                "budget_id": existing.id,
            },
        )

    budget = Budget(
        profile_id=profile.id,
        category_id=data.category_id,
        mes=data.mes,
        amount_crc=data.amount_crc,
        monto_limite=data.amount_crc,  # Alias
        notas=data.notas,
    )

    db.add(budget)
    db.commit()
    db.refresh(budget)

    return BudgetResponse.model_validate(budget)


@router.patch("/{budget_id}", response_model=BudgetResponse)
def update_budget(
    budget_id: str,
    data: BudgetUpdate,
    db: DBSession,
    profile: ActiveProfile,
) -> BudgetResponse:
    """Actualiza un presupuesto existente."""
    stmt = select(Budget).where(
        Budget.id == budget_id,
        Budget.profile_id == profile.id,
    )
    budget = db.execute(stmt).scalar_one_or_none()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Presupuesto no encontrado", "code": "BUDGET_NOT_FOUND"},
        )

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "amount_crc" and value is not None:
            budget.monto_limite = value  # Actualizar alias también
        setattr(budget, field, value)

    db.commit()
    db.refresh(budget)

    return BudgetResponse.model_validate(budget)


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: str,
    db: DBSession,
    profile: ActiveProfile,
) -> None:
    """Elimina un presupuesto."""
    stmt = select(Budget).where(
        Budget.id == budget_id,
        Budget.profile_id == profile.id,
    )
    budget = db.execute(stmt).scalar_one_or_none()

    if not budget:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Presupuesto no encontrado", "code": "BUDGET_NOT_FOUND"},
        )

    db.delete(budget)
    db.commit()


@router.get("/summary", response_model=BudgetSummaryResponse)
def get_budget_summary(
    db: DBSession,
    profile: ActiveProfile,
    mes: date = Query(..., description="Mes a consultar (YYYY-MM-01)"),
) -> BudgetSummaryResponse:
    """
    Obtiene resumen del presupuesto 50/30/20 para un mes.

    Incluye:
    - Total presupuestado vs gastado por categoría principal
    - Porcentaje de uso de cada categoría
    - Estado: bajo_presupuesto, en_limite, sobre_presupuesto
    """
    year = mes.year
    month = mes.month

    # Obtener categorías principales
    categories_stmt = select(Category)
    categories = {c.tipo: c for c in db.execute(categories_stmt).scalars().all()}

    # Obtener subcategorías agrupadas por categoría principal
    subcats_stmt = select(Subcategory)
    subcategories = db.execute(subcats_stmt).scalars().all()
    subcat_to_cat = {s.id: s.category_id for s in subcategories}
    cat_id_to_tipo = {c.id: c.tipo for c in categories.values()}

    # Obtener presupuestos del mes
    budgets_stmt = select(Budget).where(
        Budget.profile_id == profile.id,
        Budget.mes == mes,
    )
    budgets = db.execute(budgets_stmt).scalars().all()

    # Sumar presupuestos por categoría principal
    budget_by_tipo: dict[str, Decimal] = {"necesidades": Decimal("0"), "gustos": Decimal("0"), "ahorros": Decimal("0")}
    for b in budgets:
        cat_id = subcat_to_cat.get(b.category_id)
        if cat_id:
            tipo = cat_id_to_tipo.get(cat_id)
            if tipo:
                budget_by_tipo[tipo] += b.amount_crc

    # Obtener gastos del mes (excluyendo los excluidos de presupuesto)
    gastos_stmt = select(Transaction).where(
        Transaction.profile_id == profile.id,
        Transaction.deleted_at.is_(None),
        Transaction.excluir_de_presupuesto == False,
        func.extract("year", Transaction.fecha_transaccion) == year,
        func.extract("month", Transaction.fecha_transaccion) == month,
    )
    transactions = db.execute(gastos_stmt).scalars().all()

    # Sumar gastos por categoría principal
    spent_by_tipo: dict[str, Decimal] = {"necesidades": Decimal("0"), "gustos": Decimal("0"), "ahorros": Decimal("0")}
    for t in transactions:
        if t.subcategory_id:
            cat_id = subcat_to_cat.get(t.subcategory_id)
            if cat_id:
                tipo = cat_id_to_tipo.get(cat_id)
                if tipo:
                    spent_by_tipo[tipo] += t.monto_crc

    # Construir resumen por categoría
    summaries = []
    for tipo in ["necesidades", "gustos", "ahorros"]:
        budgeted = budget_by_tipo[tipo]
        spent = spent_by_tipo[tipo]
        remaining = budgeted - spent
        percentage = (spent / budgeted * 100) if budgeted > 0 else Decimal("0")

        if percentage < 80:
            status = "bajo_presupuesto"
        elif percentage <= 100:
            status = "en_limite"
        else:
            status = "sobre_presupuesto"

        summaries.append(CategoryBudgetSummary(
            categoria=tipo,
            presupuestado=budgeted,
            gastado=spent,
            restante=remaining,
            porcentaje_usado=percentage,
            status=status,
        ))

    total_presupuestado = sum(s.presupuestado for s in summaries)
    total_gastado = sum(s.gastado for s in summaries)

    return BudgetSummaryResponse(
        mes=mes,
        categorias=summaries,
        total_presupuestado=total_presupuestado,
        total_gastado=total_gastado,
        total_restante=total_presupuestado - total_gastado,
    )
