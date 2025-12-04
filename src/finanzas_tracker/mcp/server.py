"""
MCP Server para Finanzas Tracker CR.

Implementación nivel FAANG con:
- Tools: 10 herramientas en 3 niveles (Consultas, Análisis, Coaching)
- Resources: Contexto automático para el LLM
- Prompts: Plantillas para casos de uso comunes
- Error Handling: Mensajes útiles y logging estructurado
- Profile-aware: Todas las operaciones filtradas por perfil

Uso:
    poetry run python -m finanzas_tracker.mcp
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.category import Category, Subcategory
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction


# =============================================================================
# CONFIGURACIÓN Y TIPOS
# =============================================================================

_logger = get_logger(__name__)
logger: logging.Logger = _logger if _logger else logging.getLogger(__name__)


class ErrorCode(Enum):
    """Códigos de error estándar."""

    PROFILE_NOT_FOUND = "PROFILE_NOT_FOUND"
    NO_DATA = "NO_DATA"
    INVALID_INPUT = "INVALID_INPUT"
    DATABASE_ERROR = "DATABASE_ERROR"


@dataclass
class MCPError:
    """Error estructurado para respuestas MCP."""

    code: ErrorCode
    message: str
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = {"error": True, "code": self.code.value, "message": self.message}
        if self.suggestion:
            result["suggestion"] = self.suggestion
        return result


@dataclass
class MCPState:
    """Estado del servidor MCP."""

    active_profile_id: str | None = None


# Estado singleton
_state = MCPState()


def _get_active_profile_id() -> str | None:
    """Obtiene el profile_id activo."""
    return _state.active_profile_id


def _set_active_profile_id(profile_id: str | None) -> None:
    """Establece el profile_id activo."""
    _state.active_profile_id = profile_id


def _format_currency(amount: Decimal | float) -> str:
    """Formatea un monto en colones."""
    return f"₡{float(amount):,.0f}"


def _safe_divide(numerator: Decimal, denominator: Decimal) -> Decimal:
    """División segura que retorna 0 si el denominador es 0."""
    return numerator / denominator if denominator > 0 else Decimal("0")


# =============================================================================
# SERVIDOR MCP
# =============================================================================

mcp = FastMCP(
    name="finanzas-tracker",
    instructions="""Servidor MCP para finanzas personales de Costa Rica.

IMPORTANTE: Antes de usar cualquier herramienta, usa `set_profile` para establecer
el perfil del usuario. Sin esto, las herramientas no funcionarán correctamente.

HERRAMIENTAS DISPONIBLES:

📋 Nivel 1 - Consultas:
- get_transactions: Buscar transacciones con filtros
- get_spending_summary: Resumen por categoría/comercio
- get_top_merchants: Dónde gasta más

📊 Nivel 2 - Análisis:
- search_transactions: Búsqueda semántica
- get_monthly_comparison: Mes actual vs anterior

🎯 Nivel 3 - Coaching (DIFERENCIADOR):
- budget_coaching: Análisis completo con score de salud
- savings_opportunities: Dónde puede ahorrar
- cashflow_prediction: Predicción de flujo
- spending_alert: Alertas de patrones problemáticos
- goal_advisor: Planificación de metas

⚙️ Configuración:
- set_profile: Establecer perfil activo (REQUERIDO primero)
- list_profiles: Ver perfiles disponibles

MEJORES PRÁCTICAS:
1. Siempre usa set_profile primero
2. Usa budget_coaching para análisis general
3. Usa goal_advisor para metas específicas
4. Los montos están en colones costarricenses (CRC)
""",
)


# =============================================================================
# RECURSOS MCP (Contexto automático para el LLM)
# =============================================================================


@mcp.resource("profile://current")
def get_current_profile_resource() -> str:
    """Información del perfil activo actual."""
    profile_id = _get_active_profile_id()
    if not profile_id:
        return "No hay perfil activo. Usa set_profile primero."

    with get_session() as session:
        profile = session.query(Profile).filter(Profile.id == profile_id).first()
        if not profile:
            return f"Perfil {profile_id} no encontrado."

        return f"""Perfil Activo:
- Nombre: {profile.nombre}
- ID: {profile.id}
- Email: {profile.email_cuenta or 'No configurado'}
- Creado: {profile.created_at.strftime('%Y-%m-%d') if profile.created_at else 'N/A'}
"""


@mcp.resource("finance://summary")
def get_finance_summary_resource() -> str:
    """Resumen financiero rápido del mes actual."""
    profile_id = _get_active_profile_id()
    if not profile_id:
        return "No hay perfil activo."

    with get_session() as session:
        today = date.today()
        first_day = today.replace(day=1)

        # Total del mes
        total = session.query(func.sum(Transaction.monto_crc)).filter(
            Transaction.profile_id == profile_id,
            Transaction.fecha_transaccion >= first_day,
            Transaction.deleted_at.is_(None),
            Transaction.tipo_transaccion == "compra",
        ).scalar() or Decimal("0")

        # Número de transacciones
        count = (
            session.query(func.count(Transaction.id))
            .filter(
                Transaction.profile_id == profile_id,
                Transaction.fecha_transaccion >= first_day,
                Transaction.deleted_at.is_(None),
            )
            .scalar()
            or 0
        )

        days_passed = (today - first_day).days + 1
        daily_avg = total / days_passed if days_passed > 0 else Decimal("0")

        return f"""Resumen Financiero ({today.strftime('%B %Y')}):
- Total gastado: {_format_currency(total)}
- Transacciones: {count}
- Promedio diario: {_format_currency(daily_avg)}
- Días transcurridos: {days_passed}
"""


@mcp.resource("categories://list")
def get_categories_resource() -> str:
    """Lista de categorías disponibles."""
    with get_session() as session:
        categories = session.query(Category).filter(Category.deleted_at.is_(None)).all()

        lines = ["Categorías disponibles:"]
        for cat in categories:
            lines.append(f"- {cat.nombre}")

        return "\n".join(lines)


# =============================================================================
# PROMPTS MCP (Plantillas predefinidas)
# =============================================================================


@mcp.prompt()
def weekly_review() -> str:
    """Plantilla para revisión semanal de finanzas."""
    return """Haz una revisión semanal de mis finanzas:

1. Primero usa `get_transactions` con days=7 para ver mis gastos de la semana
2. Luego usa `spending_alert` para ver si hay algo preocupante
3. Finalmente dame un resumen con:
   - Total gastado esta semana
   - Top 3 categorías
   - Alguna alerta o recomendación

Responde de forma concisa y amigable."""


@mcp.prompt()
def savings_plan(goal: str = "vacaciones", amount: str = "500000", months: str = "6") -> str:
    """Plantilla para crear un plan de ahorro."""
    return f"""Ayúdame a crear un plan de ahorro:

Meta: {goal}
Monto objetivo: ₡{amount}
Plazo: {months} meses

1. Usa `goal_advisor` con goal_amount={amount}, goal_months={months}, goal_name="{goal}"
2. Usa `savings_opportunities` para ver de dónde puedo sacar el dinero
3. Dame un plan concreto y realista

Sé directo y práctico."""


@mcp.prompt()
def monthly_checkup() -> str:
    """Plantilla para chequeo mensual completo."""
    return """Hazme un chequeo mensual completo de mis finanzas:

1. Usa `budget_coaching` para obtener mi score de salud financiera
2. Usa `get_monthly_comparison` para ver cómo voy vs el mes pasado
3. Usa `get_top_merchants` para ver dónde gasto más

Dame:
- Mi score de salud financiera
- Si estoy gastando más o menos que antes
- Los 3 comercios donde más gasto
- UNA acción concreta para mejorar este mes

Responde de forma clara y motivadora."""


@mcp.prompt()
def quick_question(question: str = "¿cuánto gasté en comida?") -> str:
    """Plantilla para preguntas rápidas."""
    return f"""Responde esta pregunta sobre mis finanzas: {question}

Usa las herramientas necesarias y responde de forma directa y breve."""


# =============================================================================
# HERRAMIENTAS DE CONFIGURACIÓN
# =============================================================================


@mcp.tool()
def set_profile(profile_id: str) -> dict[str, Any]:
    """
    ⚙️ Establece el perfil activo para todas las operaciones.

    IMPORTANTE: Debes llamar esto primero antes de usar otras herramientas.

    Args:
        profile_id: UUID del perfil a usar

    Returns:
        Confirmación con datos del perfil
    """
    with get_session() as session:
        profile = session.query(Profile).filter(Profile.id == profile_id).first()

        if not profile:
            return MCPError(
                code=ErrorCode.PROFILE_NOT_FOUND,
                message=f"No existe un perfil con ID: {profile_id}",
                suggestion="Usa list_profiles para ver los perfiles disponibles",
            ).to_dict()

        _set_active_profile_id(profile_id)
        logger.info(f"Perfil activo establecido: {profile.nombre} ({profile_id})")

        return {
            "success": True,
            "message": f"Perfil '{profile.nombre}' activado",
            "profile": {
                "id": str(profile.id),
                "nombre": profile.nombre,
                "email": profile.email_cuenta,
            },
        }


@mcp.tool()
def list_profiles() -> dict[str, Any]:
    """
    📋 Lista todos los perfiles disponibles.

    Returns:
        Lista de perfiles con sus IDs
    """
    with get_session() as session:
        profiles = session.query(Profile).all()

        if not profiles:
            return MCPError(
                code=ErrorCode.NO_DATA,
                message="No hay perfiles configurados",
                suggestion="Crea un perfil desde el dashboard o la API",
            ).to_dict()

        return {
            "total": len(profiles),
            "perfiles": [
                {
                    "id": str(p.id),
                    "nombre": p.nombre,
                    "email": p.email_cuenta,
                }
                for p in profiles
            ],
            "instruccion": "Usa set_profile con el ID del perfil que quieras usar",
        }


# =============================================================================
# NIVEL 1: CONSULTAS BÁSICAS
# =============================================================================


def _require_profile() -> str | dict[str, Any]:
    """Verifica que hay un perfil activo. Retorna error dict si no hay."""
    profile_id = _get_active_profile_id()
    if not profile_id:
        return MCPError(
            code=ErrorCode.PROFILE_NOT_FOUND,
            message="No hay perfil activo",
            suggestion="Usa set_profile primero para establecer el perfil",
        ).to_dict()
    return profile_id


@mcp.tool()
def get_transactions(
    days: int = 30,
    comercio: str | None = None,
    categoria: str | None = None,
    tipo: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    📋 Obtiene transacciones con filtros opcionales.

    Args:
        days: Días hacia atrás (default: 30)
        comercio: Filtrar por nombre de comercio (búsqueda parcial)
        categoria: Filtrar por categoría
        tipo: Filtrar por tipo (compra, transferencia, etc)
        limit: Máximo de resultados (default: 20, max: 100)

    Returns:
        Lista de transacciones con total y estadísticas
    """
    profile_check = _require_profile()
    if isinstance(profile_check, dict):
        return profile_check
    profile_id = profile_check

    # Validar inputs
    days = max(1, min(365, days))
    limit = max(1, min(100, limit))

    with get_session() as session:
        fecha_inicio = datetime.now() - timedelta(days=days)

        stmt = (
            select(Transaction)
            .where(
                Transaction.profile_id == profile_id,
                Transaction.deleted_at.is_(None),
                Transaction.fecha_transaccion >= fecha_inicio,
            )
            .order_by(Transaction.fecha_transaccion.desc())
            .limit(limit)
        )

        if comercio:
            stmt = stmt.where(Transaction.comercio.ilike(f"%{comercio}%"))
        if categoria:
            stmt = stmt.where(Transaction.categoria_sugerida_por_ia.ilike(f"%{categoria}%"))
        if tipo:
            stmt = stmt.where(Transaction.tipo_transaccion == tipo)

        transactions = session.execute(stmt).scalars().all()

        if not transactions:
            return {
                "total": 0,
                "periodo": f"Últimos {days} días",
                "mensaje": "No se encontraron transacciones con esos filtros",
                "transacciones": [],
            }

        total_monto = sum(t.monto_crc for t in transactions)

        return {
            "total": len(transactions),
            "periodo": f"Últimos {days} días",
            "total_monto": _format_currency(total_monto),
            "transacciones": [
                {
                    "fecha": t.fecha_transaccion.strftime("%Y-%m-%d"),
                    "comercio": t.comercio,
                    "monto": _format_currency(t.monto_crc),
                    "tipo": t.tipo_transaccion,
                    "categoria": t.categoria_sugerida_por_ia or "Sin categoría",
                    "banco": t.banco,
                }
                for t in transactions
            ],
        }


@mcp.tool()
def get_spending_summary(
    days: int = 30,
    group_by: str = "categoria",
) -> dict[str, Any]:
    """
    📊 Resumen de gastos agrupado.

    Args:
        days: Días hacia atrás (default: 30)
        group_by: Agrupar por "categoria", "comercio" o "banco"

    Returns:
        Totales por grupo con porcentajes
    """
    profile_check = _require_profile()
    if isinstance(profile_check, dict):
        return profile_check
    profile_id = profile_check

    days = max(1, min(365, days))

    with get_session() as session:
        fecha_inicio = datetime.now() - timedelta(days=days)

        # Mapeo de campos
        field_map = {
            "categoria": Transaction.categoria_sugerida_por_ia,
            "comercio": Transaction.comercio,
            "banco": Transaction.banco,
        }
        group_field = field_map.get(group_by, Transaction.categoria_sugerida_por_ia)

        stmt = (
            select(
                group_field.label("grupo"),
                func.sum(Transaction.monto_crc).label("total"),
                func.count(Transaction.id).label("cantidad"),
            )
            .where(
                Transaction.profile_id == profile_id,
                Transaction.deleted_at.is_(None),
                Transaction.fecha_transaccion >= fecha_inicio,
                Transaction.tipo_transaccion == "compra",
            )
            .group_by(group_field)
            .order_by(func.sum(Transaction.monto_crc).desc())
        )

        results = session.execute(stmt).all()

        if not results:
            return {
                "periodo": f"Últimos {days} días",
                "agrupado_por": group_by,
                "mensaje": "No hay gastos en este período",
                "grupos": [],
            }

        total_general: Decimal = sum((r.total or Decimal("0") for r in results), Decimal("0"))
        if total_general == Decimal("0"):
            total_general = Decimal("1")  # Avoid division by zero

        return {
            "periodo": f"Últimos {days} días",
            "agrupado_por": group_by,
            "total": _format_currency(total_general),
            "grupos": [
                {
                    "nombre": r.grupo or "Sin categoría",
                    "total": _format_currency(r.total or 0),
                    "cantidad": r.cantidad,
                    "porcentaje": round(
                        float(_safe_divide(r.total or Decimal("0"), total_general) * 100), 1
                    ),
                }
                for r in results[:10]  # Top 10
            ],
        }


@mcp.tool()
def get_top_merchants(days: int = 30, limit: int = 10) -> dict[str, Any]:
    """
    🏪 Comercios donde más gastas.

    Args:
        days: Días hacia atrás (default: 30)
        limit: Número de comercios (default: 10)

    Returns:
        Top comercios por gasto total
    """
    profile_check = _require_profile()
    if isinstance(profile_check, dict):
        return profile_check
    profile_id = profile_check

    with get_session() as session:
        fecha_inicio = datetime.now() - timedelta(days=days)

        stmt = (
            select(
                Transaction.comercio,
                func.sum(Transaction.monto_crc).label("total"),
                func.count(Transaction.id).label("visitas"),
            )
            .where(
                Transaction.profile_id == profile_id,
                Transaction.deleted_at.is_(None),
                Transaction.fecha_transaccion >= fecha_inicio,
                Transaction.tipo_transaccion == "compra",
            )
            .group_by(Transaction.comercio)
            .order_by(func.sum(Transaction.monto_crc).desc())
            .limit(limit)
        )

        results = session.execute(stmt).all()

        return {
            "periodo": f"Últimos {days} días",
            "top_comercios": [
                {
                    "posicion": i + 1,
                    "comercio": r.comercio,
                    "total": _format_currency(r.total),
                    "visitas": r.visitas,
                    "promedio_visita": _format_currency(
                        _safe_divide(r.total, Decimal(str(r.visitas)))
                    ),
                }
                for i, r in enumerate(results)
            ],
        }


# =============================================================================
# NIVEL 2: ANÁLISIS
# =============================================================================


@mcp.tool()
def search_transactions(query: str, limit: int = 10) -> dict[str, Any]:
    """
    🔍 Búsqueda semántica de transacciones.

    Busca transacciones usando lenguaje natural.
    Ejemplos: "comida rápida", "uber", "supermercado"

    Args:
        query: Texto de búsqueda
        limit: Máximo de resultados

    Returns:
        Transacciones que coinciden con la búsqueda
    """
    profile_check = _require_profile()
    if isinstance(profile_check, dict):
        return profile_check
    profile_id = profile_check

    if not query or len(query.strip()) < 2:
        return MCPError(
            code=ErrorCode.INVALID_INPUT,
            message="La búsqueda debe tener al menos 2 caracteres",
        ).to_dict()

    with get_session() as session:
        # Intentar búsqueda semántica primero
        try:
            from finanzas_tracker.services.embedding_service import EmbeddingService

            service = EmbeddingService(session)
            results = service.search_similar(query, profile_id=profile_id, limit=limit)

            if results:
                return {
                    "query": query,
                    "tipo_busqueda": "semántica",
                    "total": len(results),
                    "resultados": [
                        {
                            "comercio": txn.comercio,
                            "monto": _format_currency(txn.monto_crc),
                            "fecha": txn.fecha_transaccion.strftime("%Y-%m-%d"),
                            "categoria": txn.categoria_sugerida_por_ia,
                            "relevancia": f"{similarity * 100:.0f}%",
                        }
                        for txn, similarity in results
                    ],
                }
        except Exception as e:
            logger.warning(f"Búsqueda semántica falló, usando fallback: {e}")

        # Fallback a búsqueda simple
        stmt = (
            select(Transaction)
            .where(
                Transaction.profile_id == profile_id,
                Transaction.deleted_at.is_(None),
                Transaction.comercio.ilike(f"%{query}%"),
            )
            .order_by(Transaction.fecha_transaccion.desc())
            .limit(limit)
        )
        transactions = session.execute(stmt).scalars().all()

        return {
            "query": query,
            "tipo_busqueda": "texto",
            "total": len(transactions),
            "resultados": [
                {
                    "comercio": t.comercio,
                    "monto": _format_currency(t.monto_crc),
                    "fecha": t.fecha_transaccion.strftime("%Y-%m-%d"),
                    "categoria": t.categoria_sugerida_por_ia,
                }
                for t in transactions
            ],
        }


@mcp.tool()
def get_monthly_comparison() -> dict[str, Any]:
    """
    📈 Compara gastos del mes actual vs el anterior.

    Returns:
        Comparación con diferencia y tendencia
    """
    profile_check = _require_profile()
    if isinstance(profile_check, dict):
        return profile_check
    profile_id = profile_check

    with get_session() as session:
        now = datetime.now()
        inicio_mes_actual = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        if now.month == 1:
            inicio_mes_anterior = now.replace(year=now.year - 1, month=12, day=1)
        else:
            inicio_mes_anterior = now.replace(month=now.month - 1, day=1)

        fin_mes_anterior = inicio_mes_actual - timedelta(seconds=1)

        # Total mes actual
        total_actual = session.query(func.sum(Transaction.monto_crc)).filter(
            Transaction.profile_id == profile_id,
            Transaction.deleted_at.is_(None),
            Transaction.fecha_transaccion >= inicio_mes_actual,
            Transaction.tipo_transaccion == "compra",
        ).scalar() or Decimal("0")

        # Total mes anterior
        total_anterior = session.query(func.sum(Transaction.monto_crc)).filter(
            Transaction.profile_id == profile_id,
            Transaction.deleted_at.is_(None),
            Transaction.fecha_transaccion >= inicio_mes_anterior,
            Transaction.fecha_transaccion <= fin_mes_anterior,
            Transaction.tipo_transaccion == "compra",
        ).scalar() or Decimal("0")

        diferencia = total_actual - total_anterior
        if total_anterior > 0:
            porcentaje = float((diferencia / total_anterior) * 100)
        else:
            porcentaje = 100.0 if total_actual > 0 else 0.0

        if porcentaje > 10:
            tendencia = "📈 Aumentando"
            emoji = "⚠️"
        elif porcentaje < -10:
            tendencia = "📉 Disminuyendo"
            emoji = "✅"
        else:
            tendencia = "➡️ Estable"
            emoji = "👍"

        return {
            "mes_actual": {
                "nombre": now.strftime("%B %Y"),
                "total": _format_currency(total_actual),
            },
            "mes_anterior": {
                "nombre": inicio_mes_anterior.strftime("%B %Y"),
                "total": _format_currency(total_anterior),
            },
            "comparacion": {
                "diferencia": _format_currency(abs(diferencia)),
                "porcentaje": f"{'+' if porcentaje > 0 else ''}{porcentaje:.1f}%",
                "tendencia": tendencia,
                "emoji": emoji,
            },
        }


# =============================================================================
# NIVEL 3: COACHING (EL DIFERENCIADOR)
# =============================================================================


def _get_analysis_data(session: Session, profile_id: str, days: int) -> dict[str, Any]:
    """Obtiene datos para análisis de coaching."""
    today = date.today()
    start_date = today - timedelta(days=days)
    first_day_month = today.replace(day=1)
    last_month_start = (first_day_month - timedelta(days=1)).replace(day=1)

    # Transacciones del período
    transactions = (
        session.query(Transaction)
        .options(joinedload(Transaction.subcategory).joinedload(Subcategory.category))
        .filter(
            Transaction.profile_id == profile_id,
            Transaction.fecha_transaccion >= start_date,
            Transaction.deleted_at.is_(None),
        )
        .order_by(Transaction.fecha_transaccion.desc())
        .all()
    )

    current_month_txns = [t for t in transactions if t.fecha_transaccion.date() >= first_day_month]

    # Mes anterior
    last_month_txns = (
        session.query(Transaction)
        .filter(
            Transaction.profile_id == profile_id,
            Transaction.fecha_transaccion >= last_month_start,
            Transaction.fecha_transaccion < first_day_month,
            Transaction.deleted_at.is_(None),
        )
        .all()
    )

    total_current = sum(t.monto_crc for t in current_month_txns)
    total_last = sum(t.monto_crc for t in last_month_txns)

    # Por categoría
    by_category_current: dict[str, Decimal] = defaultdict(Decimal)
    by_category_last: dict[str, Decimal] = defaultdict(Decimal)

    for t in current_month_txns:
        cat = _get_category_name(t)
        by_category_current[cat] += t.monto_crc

    for t in last_month_txns:
        cat = _get_category_name(t)
        by_category_last[cat] += t.monto_crc

    # Por comercio
    by_merchant: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "total": Decimal("0")}
    )
    for t in current_month_txns:
        by_merchant[t.comercio]["count"] += 1
        by_merchant[t.comercio]["total"] += t.monto_crc

    return {
        "transactions": transactions,
        "current_month_txns": current_month_txns,
        "total_current": total_current,
        "total_last": total_last,
        "by_category_current": dict(by_category_current),
        "by_category_last": dict(by_category_last),
        "by_merchant": dict(by_merchant),
        "transaction_count": len(current_month_txns),
        "days": days,
    }


def _get_category_name(t: Transaction) -> str:
    """Obtiene el nombre de la categoría de una transacción."""
    if t.subcategory and t.subcategory.category:
        return str(t.subcategory.category.nombre)
    return str(t.categoria_sugerida_por_ia) if t.categoria_sugerida_por_ia else "Sin categoría"


@mcp.tool()
def budget_coaching(days: int = 30) -> dict[str, Any]:
    """
    🎯 Coaching financiero completo.

    Analiza tus finanzas y te da:
    - Score de salud financiera (0-100)
    - Tendencias de gasto
    - Patrones de comportamiento
    - Recomendaciones priorizadas

    Args:
        days: Período de análisis (default: 30)

    Returns:
        Análisis completo con score y recomendaciones
    """
    profile_check = _require_profile()
    if isinstance(profile_check, dict):
        return profile_check
    profile_id = profile_check

    with get_session() as session:
        data = _get_analysis_data(session, profile_id, days)

        if data["transaction_count"] == 0:
            return {
                "periodo": f"Últimos {days} días",
                "mensaje": "No hay suficientes datos para el análisis",
                "sugerencia": "Necesitas al menos algunas transacciones para el coaching",
            }

        # Análisis
        coaching_points = []

        # 1. Tendencia de gasto
        if data["total_last"] > 0:
            change_pct = ((data["total_current"] - data["total_last"]) / data["total_last"]) * 100
            if change_pct > 20:
                coaching_points.append(
                    {
                        "tipo": "tendencia",
                        "prioridad": "alta",
                        "emoji": "📈",
                        "titulo": "Gasto aumentando",
                        "detalle": f"Llevas {change_pct:.0f}% más que el mes pasado",
                        "accion": "Revisa las categorías que más aumentaron",
                    }
                )
            elif change_pct < -20:
                coaching_points.append(
                    {
                        "tipo": "tendencia",
                        "prioridad": "baja",
                        "emoji": "✅",
                        "titulo": "¡Excelente control!",
                        "detalle": f"Llevas {abs(change_pct):.0f}% menos que el mes pasado",
                        "accion": "Sigue así y considera invertir el ahorro",
                    }
                )

        # 2. Patrón de fin de semana
        weekend_total = sum(
            t.monto_crc for t in data["current_month_txns"] if t.fecha_transaccion.weekday() >= 5
        )
        weekday_total = sum(
            t.monto_crc for t in data["current_month_txns"] if t.fecha_transaccion.weekday() < 5
        )

        if weekend_total > 0 and weekday_total > 0:
            weekend_avg = weekend_total / 8  # ~8 días de fin de semana al mes
            weekday_avg = weekday_total / 22  # ~22 días entre semana
            if weekend_avg > weekday_avg * Decimal("1.5"):
                coaching_points.append(
                    {
                        "tipo": "patron",
                        "prioridad": "media",
                        "emoji": "🎉",
                        "titulo": "Gastas más en fines de semana",
                        "detalle": f"Promedio fin de semana: {_format_currency(weekend_avg)} vs {_format_currency(weekday_avg)} entre semana",
                        "accion": "Planifica actividades más económicas para el fin de semana",
                    }
                )

        # 3. Gastos pequeños
        small_txns = [t for t in data["current_month_txns"] if t.monto_crc < 5000]
        if len(small_txns) > 15:
            small_total = sum(t.monto_crc for t in small_txns)
            coaching_points.append(
                {
                    "tipo": "patron",
                    "prioridad": "media",
                    "emoji": "🪙",
                    "titulo": "Muchos gastos pequeños",
                    "detalle": f"{len(small_txns)} compras menores a ₡5,000 suman {_format_currency(small_total)}",
                    "accion": "Usa efectivo para gastos pequeños y establece un límite diario",
                }
            )

        # 4. Categorías que aumentaron
        for cat, amount in data["by_category_current"].items():
            last_amount = data["by_category_last"].get(cat, Decimal("0"))
            if last_amount > 0:
                increase_pct = ((amount - last_amount) / last_amount) * 100
                if increase_pct > 50 and amount > 15000:
                    coaching_points.append(
                        {
                            "tipo": "categoria",
                            "prioridad": "alta",
                            "emoji": "⚠️",
                            "titulo": f"{cat} aumentó {increase_pct:.0f}%",
                            "detalle": f"De {_format_currency(last_amount)} a {_format_currency(amount)}",
                            "accion": f"Revisa qué pasó en {cat} este mes",
                        }
                    )

        # Calcular score de salud
        score = 100
        high_priority = len([c for c in coaching_points if c["prioridad"] == "alta"])
        medium_priority = len([c for c in coaching_points if c["prioridad"] == "media"])
        score -= high_priority * 15
        score -= medium_priority * 5
        score = max(0, min(100, score))

        if score >= 80:
            nivel, emoji_score = "Excelente", "🌟"
        elif score >= 60:
            nivel, emoji_score = "Bueno", "👍"
        elif score >= 40:
            nivel, emoji_score = "Regular", "⚠️"
        else:
            nivel, emoji_score = "Necesita atención", "🔴"

        # Ordenar por prioridad
        priority_order = {"alta": 0, "media": 1, "baja": 2}
        coaching_points.sort(key=lambda x: priority_order.get(x["prioridad"], 1))

        return {
            "periodo": f"Últimos {days} días",
            "salud_financiera": {
                "score": score,
                "nivel": nivel,
                "emoji": emoji_score,
            },
            "resumen": {
                "total_gastado": _format_currency(data["total_current"]),
                "transacciones": data["transaction_count"],
                "promedio_diario": _format_currency(
                    _safe_divide(data["total_current"], Decimal(str(days)))
                ),
            },
            "coaching": coaching_points[:5],
            "accion_principal": coaching_points[0]
            if coaching_points
            else {
                "emoji": "✅",
                "titulo": "Todo bien",
                "detalle": "No hay alertas importantes",
                "accion": "Sigue así",
            },
        }


@mcp.tool()
def savings_opportunities() -> dict[str, Any]:
    """
    💰 Encuentra oportunidades de ahorro.

    Analiza dónde puedes ahorrar dinero:
    - Categorías que aumentaron vs mes pasado
    - Comercios con muchas visitas
    - Gastos que podrías reducir

    Returns:
        Lista de oportunidades con ahorro potencial
    """
    profile_check = _require_profile()
    if isinstance(profile_check, dict):
        return profile_check
    profile_id = profile_check

    with get_session() as session:
        data = _get_analysis_data(session, profile_id, 30)

        opportunities = []
        total_potential = Decimal("0")

        # 1. Categorías que aumentaron
        for cat, amount in data["by_category_current"].items():
            last = data["by_category_last"].get(cat, Decimal("0"))
            if last > 0:
                increase = amount - last
                if increase > 10000:
                    opportunities.append(
                        {
                            "tipo": "categoria",
                            "descripcion": f"{cat}: aumentó {_format_currency(increase)}",
                            "ahorro_potencial": _format_currency(increase),
                            "accion": f"Volver al nivel anterior ahorraría {_format_currency(increase)}",
                        }
                    )
                    total_potential += increase

        # 2. Comercios frecuentes
        for merchant, info in data["by_merchant"].items():
            if info["count"] >= 8:
                potential = info["total"] * Decimal("0.3")
                opportunities.append(
                    {
                        "tipo": "frecuencia",
                        "descripcion": f"{merchant}: {info['count']} visitas",
                        "ahorro_potencial": _format_currency(potential),
                        "accion": f"Reducir 30% de visitas ahorraría {_format_currency(potential)}",
                    }
                )
                total_potential += potential

        # Ordenar por potencial
        def get_potential(x: dict[str, Any]) -> float:
            s = x.get("ahorro_potencial", "₡0")
            return float(s.replace("₡", "").replace(",", "")) if isinstance(s, str) else 0

        opportunities.sort(key=get_potential, reverse=True)

        return {
            "periodo": "Últimos 30 días",
            "ahorro_potencial_total": _format_currency(total_potential),
            "oportunidades": opportunities[:5],
            "mensaje": f"Identificamos {_format_currency(total_potential)} en posibles ahorros",
        }


@mcp.tool()
def cashflow_prediction(days_ahead: int = 15) -> dict[str, Any]:
    """
    🔮 Predice tu flujo de efectivo.

    Basado en patrones históricos:
    - Gasto estimado próximos días
    - Días de "riesgo" (fines de semana)
    - Si el ritmo actual es sostenible

    Args:
        days_ahead: Días a predecir (default: 15)

    Returns:
        Predicción con alertas
    """
    profile_check = _require_profile()
    if isinstance(profile_check, dict):
        return profile_check
    profile_id = profile_check

    with get_session() as session:
        data = _get_analysis_data(session, profile_id, 60)

        # Calcular promedio por día de la semana
        by_weekday: dict[int, list[Decimal]] = defaultdict(list)
        for t in data["transactions"]:
            weekday = t.fecha_transaccion.weekday()
            by_weekday[weekday].append(t.monto_crc)

        avg_by_weekday: dict[int, Decimal] = {}
        for weekday, amounts in by_weekday.items():
            if amounts:
                avg_by_weekday[weekday] = Decimal(str(sum(amounts) / len(amounts)))
            else:
                avg_by_weekday[weekday] = Decimal("0")

        # Predecir próximos días
        predictions = []
        total_predicted = Decimal("0")
        today = date.today()
        weekday_names = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]

        for i in range(1, min(days_ahead + 1, 8)):  # Max 7 días en detalle
            future_date = today + timedelta(days=i)
            weekday = future_date.weekday()
            predicted = avg_by_weekday.get(weekday, Decimal("0"))

            predictions.append(
                {
                    "fecha": future_date.strftime("%Y-%m-%d"),
                    "dia": weekday_names[weekday],
                    "estimado": _format_currency(predicted),
                    "riesgo": "alto" if weekday >= 5 else "normal",
                }
            )
            total_predicted += predicted

        # Proyección mensual
        daily_avg = _safe_divide(data["total_current"], Decimal("30"))
        monthly_projection = daily_avg * 30

        # Sostenibilidad
        if data["total_last"] > 0:
            ratio = monthly_projection / data["total_last"]
            if ratio <= 1:
                sostenible = {"nivel": "bueno", "emoji": "✅", "mensaje": "Ritmo sostenible"}
            elif ratio <= 1.2:
                sostenible = {"nivel": "aceptable", "emoji": "👍", "mensaje": "Ritmo aceptable"}
            else:
                sostenible = {
                    "nivel": "alto",
                    "emoji": "⚠️",
                    "mensaje": f"Proyectas {(ratio - 1) * 100:.0f}% más que el mes pasado",
                }
        else:
            sostenible = {
                "nivel": "desconocido",
                "emoji": "❓",
                "mensaje": "Sin datos del mes anterior",
            }

        return {
            "prediccion_7_dias": {
                "total": _format_currency(total_predicted),
                "detalle": predictions,
            },
            "proyeccion_mensual": _format_currency(monthly_projection),
            "sostenibilidad": sostenible,
            "dias_riesgo": [p["fecha"] for p in predictions if p["riesgo"] == "alto"],
        }


@mcp.tool()
def spending_alert() -> dict[str, Any]:
    """
    🚨 Detecta alertas y patrones problemáticos.

    Identifica:
    - Transacciones inusuales (muy grandes)
    - Categorías fuera de control
    - Ritmo de gasto insostenible

    Returns:
        Alertas ordenadas por severidad
    """
    profile_check = _require_profile()
    if isinstance(profile_check, dict):
        return profile_check
    profile_id = profile_check

    with get_session() as session:
        data = _get_analysis_data(session, profile_id, 30)

        alerts = []

        # 1. Transacciones inusuales
        if data["transaction_count"] > 0:
            avg_txn = _safe_divide(data["total_current"], Decimal(str(data["transaction_count"])))

            for t in data["current_month_txns"][:20]:  # Últimas 20
                if t.monto_crc > avg_txn * 3 and t.monto_crc > 15000:
                    alerts.append(
                        {
                            "severidad": "alta",
                            "emoji": "⚠️",
                            "titulo": f"Gasto inusual: {t.comercio}",
                            "detalle": f"{_format_currency(t.monto_crc)} es {t.monto_crc / avg_txn:.1f}x tu promedio",
                            "fecha": t.fecha_transaccion.strftime("%Y-%m-%d"),
                        }
                    )

        # 2. Categorías descontroladas
        for cat, amount in data["by_category_current"].items():
            last = data["by_category_last"].get(cat, Decimal("0"))
            if last > 0:
                increase_pct = ((amount - last) / last) * 100
                if increase_pct > 50 and amount > 20000:
                    alerts.append(
                        {
                            "severidad": "media",
                            "emoji": "📈",
                            "titulo": f"{cat} +{increase_pct:.0f}%",
                            "detalle": f"De {_format_currency(last)} a {_format_currency(amount)}",
                            "fecha": "Este mes",
                        }
                    )

        # 3. Ritmo insostenible
        if data["total_last"] > 0:
            ratio = data["total_current"] / data["total_last"]
            if ratio > 1.3:
                alerts.append(
                    {
                        "severidad": "alta",
                        "emoji": "🔥",
                        "titulo": "Ritmo de gasto alto",
                        "detalle": f"Llevas {(ratio - 1) * 100:.0f}% más que el mes pasado",
                        "fecha": "Tendencia actual",
                    }
                )

        # Ordenar por severidad
        severity_order = {"alta": 0, "media": 1, "baja": 2}
        alerts.sort(key=lambda x: severity_order.get(x["severidad"], 1))

        high_count = len([a for a in alerts if a["severidad"] == "alta"])

        if high_count > 0:
            estado = "🔴 Requiere atención"
        elif alerts:
            estado = "🟡 Algunas alertas"
        else:
            estado = "🟢 Todo en orden"

        return {
            "estado": estado,
            "total_alertas": len(alerts),
            "alertas_altas": high_count,
            "alertas": alerts[:5],
            "mensaje": f"{high_count} alerta(s) importantes"
            if high_count
            else "Sin alertas importantes",
        }


@mcp.tool()
def goal_advisor(
    goal_amount: float,
    goal_months: int = 6,
    goal_name: str = "mi meta",
) -> dict[str, Any]:
    """
    🎯 Asesor de metas de ahorro.

    Analiza si tu meta es alcanzable y te da un plan:
    - Cuánto necesitas ahorrar por mes
    - De dónde puedes sacar ese dinero
    - Si es realista o necesitas ajustar

    Args:
        goal_amount: Monto de la meta en colones
        goal_months: Meses para alcanzarla
        goal_name: Nombre de la meta

    Returns:
        Plan de ahorro con acciones concretas
    """
    profile_check = _require_profile()
    if isinstance(profile_check, dict):
        return profile_check
    profile_id = profile_check

    # Validar inputs
    if goal_amount <= 0:
        return MCPError(
            code=ErrorCode.INVALID_INPUT, message="El monto debe ser mayor a 0"
        ).to_dict()
    if goal_months <= 0:
        return MCPError(
            code=ErrorCode.INVALID_INPUT, message="Los meses deben ser mayor a 0"
        ).to_dict()

    with get_session() as session:
        data = _get_analysis_data(session, profile_id, 30)

        goal = Decimal(str(goal_amount))
        monthly_needed = goal / goal_months

        # Identificar categorías reducibles
        reducible_cats = ["Entretenimiento", "Restaurantes", "Compras", "Comida"]
        reducible_total = Decimal("0")
        plan = []

        for cat, amount in data["by_category_current"].items():
            if any(r.lower() in cat.lower() for r in reducible_cats):
                reduction = amount * Decimal("0.3")  # 30% reducible
                reducible_total += reduction
                plan.append(
                    {
                        "categoria": cat,
                        "actual": _format_currency(amount),
                        "reduccion": _format_currency(reduction),
                        "nuevo": _format_currency(amount - reduction),
                    }
                )

        # Evaluar viabilidad
        is_achievable = reducible_total >= monthly_needed

        if reducible_total <= 0:
            difficulty = "imposible"
            mensaje = "No encontramos categorías para reducir. Considera aumentar ingresos."
        elif monthly_needed / reducible_total <= Decimal("0.5"):
            difficulty = "fácil"
            mensaje = f"¡{goal_name} es muy alcanzable! Solo necesitas pequeños ajustes."
        elif monthly_needed / reducible_total <= Decimal("0.8"):
            difficulty = "moderado"
            mensaje = f"{goal_name} es alcanzable con disciplina. ¡Tú puedes!"
        elif monthly_needed / reducible_total <= 1:
            difficulty = "desafiante"
            mensaje = f"{goal_name} requiere compromiso, pero es posible."
        else:
            difficulty = "muy difícil"
            mensaje = f"{goal_name} es ambicioso. Considera extender el plazo a {int(goal_months * 1.5)} meses."

        return {
            "meta": {
                "nombre": goal_name,
                "monto": _format_currency(goal),
                "plazo": f"{goal_months} meses",
            },
            "necesitas": {
                "mensual": _format_currency(monthly_needed),
                "semanal": _format_currency(monthly_needed / 4),
            },
            "capacidad": {
                "ahorro_posible": _format_currency(reducible_total),
            },
            "viabilidad": {
                "es_alcanzable": is_achievable,
                "dificultad": difficulty,
                "mensaje": mensaje,
            },
            "plan": plan[:4],
            "primer_paso": plan[0] if plan else {"mensaje": "Revisa tus gastos fijos"},
        }


# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================


async def run_server() -> None:
    """Ejecuta el servidor MCP vía stdio."""
    logger.info("🚀 MCP Server iniciando...")
    logger.info("📊 10 herramientas + 4 resources + 4 prompts disponibles")
    await mcp.run_stdio_async()


def main() -> None:
    """Entry point CLI."""
    import asyncio

    asyncio.run(run_server())


if __name__ == "__main__":
    main()
