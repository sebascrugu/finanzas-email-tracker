"""Router de Categorías - Solo lectura."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from finanzas_tracker.api.dependencies import DBSession
from finanzas_tracker.api.schemas.category import (
    CategoryListResponse,
    CategoryResponse,
    SubcategoryResponse,
)
from finanzas_tracker.models.category import Category, Subcategory


router = APIRouter(prefix="/categories")


@router.get("", response_model=CategoryListResponse)
def list_categories(db: DBSession) -> CategoryListResponse:
    """
    Lista todas las categorías con sus subcategorías.

    Categorías del sistema 50/30/20:
    - **Necesidades** (50%): Gastos esenciales
    - **Gustos** (30%): Gastos discrecionales
    - **Ahorros** (20%): Ahorro e inversiones
    """
    stmt = select(Category).order_by(Category.tipo)
    categories = db.execute(stmt).scalars().all()

    return CategoryListResponse(
        items=[CategoryResponse.model_validate(c) for c in categories],
        total=len(categories),
    )


@router.get("/{category_id}", response_model=CategoryResponse)
def get_category(category_id: str, db: DBSession) -> CategoryResponse:
    """Obtiene una categoría por ID con sus subcategorías."""
    stmt = select(Category).where(Category.id == category_id)
    category = db.execute(stmt).scalar_one_or_none()

    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Categoría no encontrada", "code": "CAT_NOT_FOUND"},
        )

    return CategoryResponse.model_validate(category)


@router.get("/{category_id}/subcategories", response_model=list[SubcategoryResponse])
def list_subcategories(category_id: str, db: DBSession) -> list[SubcategoryResponse]:
    """Lista subcategorías de una categoría específica."""
    stmt = select(Subcategory).where(
        Subcategory.category_id == category_id
    ).order_by(Subcategory.nombre)

    subcategories = db.execute(stmt).scalars().all()

    return [SubcategoryResponse.model_validate(s) for s in subcategories]


@router.get("/subcategories/all", response_model=list[SubcategoryResponse])
def list_all_subcategories(db: DBSession) -> list[SubcategoryResponse]:
    """Lista todas las subcategorías del sistema."""
    stmt = select(Subcategory).order_by(Subcategory.nombre)
    subcategories = db.execute(stmt).scalars().all()

    return [SubcategoryResponse.model_validate(s) for s in subcategories]


@router.get("/subcategories/{subcategory_id}", response_model=SubcategoryResponse)
def get_subcategory(subcategory_id: str, db: DBSession) -> SubcategoryResponse:
    """Obtiene una subcategoría por ID."""
    stmt = select(Subcategory).where(Subcategory.id == subcategory_id)
    subcategory = db.execute(stmt).scalar_one_or_none()

    if not subcategory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "Subcategoría no encontrada", "code": "SUBCAT_NOT_FOUND"},
        )

    return SubcategoryResponse.model_validate(subcategory)
