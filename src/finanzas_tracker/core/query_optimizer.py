"""
Query optimization helpers y best practices.

Proporciona:
- Preloading strategies para evitar N+1
- Query batching
- Índices sugeridos
- Cached queries para datos estáticos
"""

from functools import lru_cache
from typing import Any

from sqlalchemy import Index
from sqlalchemy.orm import Session, joinedload, selectinload

from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)


class QueryOptimizer:
    """
    Helper para optimizar queries comunes.

    Best Practices:
    - Usa joinedload() para relaciones 1-to-1 y few-to-many
    - Usa selectinload() para relaciones many-to-many
    - Usa subqueryload() para relaciones large many-to-many
    - Evita lazy loading en loops
    """

    @staticmethod
    def suggest_indexes() -> list[dict[str, Any]]:
        """
        Sugiere índices faltantes basados en queries comunes.

        Returns:
            Lista de sugerencias de índices
        """
        suggestions = []

        # Transactions - queries más comunes
        suggestions.append({
            "table": "transactions",
            "columns": ["profile_id", "fecha_transaccion"],
            "reason": "WHERE profile_id = ? AND fecha_transaccion BETWEEN",
            "priority": "HIGH",
            "existing": True,  # Ya existe ix_transactions_profile_id_fecha
        })

        suggestions.append({
            "table": "transactions",
            "columns": ["profile_id", "necesita_revision"],
            "reason": "WHERE profile_id = ? AND necesita_revision = TRUE",
            "priority": "MEDIUM",
            "existing": False,
        })

        suggestions.append({
            "table": "transactions",
            "columns": ["comercio", "profile_id"],
            "reason": "Búsqueda de duplicados y aprendizaje histórico",
            "priority": "MEDIUM",
            "existing": False,
        })

        suggestions.append({
            "table": "transactions",
            "columns": ["account_id"],
            "reason": "JOIN transactions.account_id = accounts.id",
            "priority": "MEDIUM",
            "existing": False,
        })

        # Accounts
        suggestions.append({
            "table": "accounts",
            "columns": ["profile_id", "activa"],
            "reason": "WHERE profile_id = ? AND activa = TRUE",
            "priority": "MEDIUM",
            "existing": False,
        })

        # Income
        suggestions.append({
            "table": "incomes",
            "columns": ["profile_id", "fecha"],
            "reason": "WHERE profile_id = ? AND fecha BETWEEN",
            "priority": "MEDIUM",
            "existing": False,
        })

        # Savings Goals
        suggestions.append({
            "table": "savings_goals",
            "columns": ["profile_id", "archived"],
            "reason": "WHERE profile_id = ? AND archived = FALSE",
            "priority": "LOW",
            "existing": False,
        })

        return suggestions

    @staticmethod
    def get_optimization_tips() -> list[str]:
        """Retorna tips de optimización para el equipo."""
        return [
            "✅ Usa joinedload() para cargar relaciones en queries que las necesiten",
            "✅ Evita acceder a relaciones dentro de loops (N+1 queries)",
            "✅ Usa selectinload() para colecciones grandes (>100 items)",
            "✅ Considera pagination para queries que retornan muchos resultados",
            "✅ Usa índices compuestos para filtros frecuentes (profile_id + fecha)",
            "⚠️  Evita SELECT * cuando solo necesitas algunas columnas",
            "⚠️  No uses lazy loading por defecto, especifica strategy explícitamente",
            "💡 Profile queries en desarrollo con profile_queries() context manager",
        ]


# Cached query helpers para datos que no cambian frecuentemente
@lru_cache(maxsize=32)
def get_all_categories_cached(session_id: int) -> list:
    """
    Obtiene todas las categorías (cached).

    NOTA: Este es un ejemplo. En producción usarías Redis o similar.
    Por ahora, LRU cache es suficiente para categorías que no cambian.

    Args:
        session_id: ID único de la sesión (para invalidar cache)

    Returns:
        Lista de categorías
    """
    # Este sería implementado en el servicio correspondiente
    logger.debug("Cache MISS - Cargando categorías...")
    # return session.query(Category).all()
    return []


# Preloading strategies para queries comunes
def get_transactions_with_relations(
    session: Session,
    profile_id: str,
    eager_load: bool = True,
) -> Any:
    """
    Obtiene transacciones con relaciones precargadas.

    OPTIMIZADO: Usa joinedload para evitar N+1 queries.

    Args:
        session: SQLAlchemy session
        profile_id: ID del perfil
        eager_load: Si precargar relaciones (default: True)

    Returns:
        Query de transacciones
    """
    from finanzas_tracker.models.transaction import Transaction

    query = session.query(Transaction).filter(Transaction.profile_id == profile_id)

    if eager_load:
        # Precarga todas las relaciones necesarias en UNA query
        query = query.options(
            joinedload(Transaction.account),  # 1-to-1: joinedload
            joinedload(Transaction.subcategory).joinedload("category"),  # nested joinedload
            joinedload(Transaction.merchant),  # 1-to-1: joinedload
        )

    return query


def get_profile_with_full_context(session: Session, profile_id: str) -> Any:
    """
    Obtiene perfil con TODAS sus relaciones precargadas.

    OPTIMIZADO: Una sola query carga todo lo necesario.

    Args:
        session: SQLAlchemy session
        profile_id: ID del perfil

    Returns:
        Profile con relaciones cargadas
    """
    from finanzas_tracker.models.profile import Profile

    return (
        session.query(Profile)
        .options(
            # Relaciones directas
            joinedload(Profile.cards),
            joinedload(Profile.budgets),
            # Relaciones anidadas
            selectinload(Profile.accounts),  # Puede haber muchas cuentas
            selectinload(Profile.savings_goals),  # Puede haber muchas metas
        )
        .filter(Profile.id == profile_id)
        .one()
    )


# Batch loading para reducir queries
def batch_load_subcategories(session: Session, subcategory_ids: list[str]) -> dict[str, Any]:
    """
    Carga múltiples subcategorías en una sola query.

    En lugar de:
        for id in ids:
            session.query(Subcategory).get(id)  # N queries

    Usa:
        batch_load_subcategories(session, ids)  # 1 query

    Args:
        session: SQLAlchemy session
        subcategory_ids: Lista de IDs

    Returns:
        Dict {id: subcategory}
    """
    from finanzas_tracker.models.category import Subcategory

    if not subcategory_ids:
        return {}

    subcategories = (
        session.query(Subcategory)
        .filter(Subcategory.id.in_(subcategory_ids))
        .all()
    )

    return {subcat.id: subcat for subcat in subcategories}


def create_missing_indexes_migration() -> str:
    """
    Genera código Alembic para crear índices faltantes.

    Returns:
        Código Python para migration
    """
    optimizer = QueryOptimizer()
    suggestions = [s for s in optimizer.suggest_indexes() if not s["existing"]]

    if not suggestions:
        return "# No hay índices faltantes"

    lines = [
        '"""Add performance indexes"""',
        "",
        "from alembic import op",
        "",
        "",
        "def upgrade():",
    ]

    for sug in suggestions:
        table = sug["table"]
        columns = sug["columns"]
        index_name = f"ix_{table}_{'_'.join(columns)}"

        lines.append(
            f"    # {sug['reason']} (Priority: {sug['priority']})"
        )
        lines.append(
            f"    op.create_index('{index_name}', '{table}', {columns})"
        )
        lines.append("")

    lines.extend([
        "",
        "def downgrade():",
    ])

    for sug in suggestions:
        table = sug["table"]
        columns = sug["columns"]
        index_name = f"ix_{table}_{'_'.join(columns)}"

        lines.append(f"    op.drop_index('{index_name}', '{table}')")

    return "\n".join(lines)


# Singleton
query_optimizer = QueryOptimizer()
