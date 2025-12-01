"""
MCP Server Implementation para Finanzas Tracker CR.

Implementa el protocolo MCP usando FastMCP para integración con Claude Desktop.
Incluye herramientas de Nivel 1-3:
- Nivel 1: Consultas básicas (transacciones, resúmenes)
- Nivel 2: Análisis (búsqueda semántica, comparaciones)
- Nivel 3: Coaching (presupuesto, predicciones, alertas) ← DIFERENCIADOR
"""

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.category import Subcategory
from finanzas_tracker.models.transaction import Transaction


_logger = get_logger(__name__)
logger: logging.Logger = _logger if _logger else logging.getLogger(__name__)

# Crear servidor FastMCP
mcp = FastMCP(
    name="finanzas-tracker",
    instructions="Servidor MCP para finanzas personales de Costa Rica. "
    "Soporta SINPE Móvil, múltiples bancos, y coaching financiero con IA.",
)


# =============================================================================
# NIVEL 1: CONSULTAS BÁSICAS
# =============================================================================


@mcp.tool()
def get_transactions(
    days: int = 30,
    comercio: str | None = None,
    categoria: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Obtiene transacciones con filtros opcionales.

    Útil para consultar gastos específicos por comercio, categoría o período.

    Args:
        days: Número de días hacia atrás (default: 30)
        comercio: Filtrar por nombre de comercio (búsqueda parcial)
        categoria: Filtrar por categoría sugerida por IA
        limit: Máximo de resultados (default: 20)

    Returns:
        dict con transacciones encontradas, total y período
    """
    with get_session() as session:
        fecha_inicio = datetime.now() - timedelta(days=days)

        stmt = (
            select(Transaction)
            .where(
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

        transactions = session.execute(stmt).scalars().all()

        return {
            "total": len(transactions),
            "periodo": f"Últimos {days} días",
            "transacciones": [
                {
                    "fecha": t.fecha_transaccion.strftime("%Y-%m-%d %H:%M"),
                    "comercio": t.comercio,
                    "monto_crc": float(t.monto_crc),
                    "monto_formateado": f"₡{t.monto_crc:,.0f}",
                    "tipo": t.tipo_transaccion,
                    "categoria": t.categoria_sugerida_por_ia,
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
    Obtiene un resumen de gastos agrupado por categoría, comercio o banco.

    Args:
        days: Número de días hacia atrás (default: 30)
        group_by: Agrupar por "categoria", "comercio" o "banco"

    Returns:
        dict con totales por grupo, porcentajes y total general
    """
    with get_session() as session:
        fecha_inicio = datetime.now() - timedelta(days=days)

        group_field = {
            "categoria": Transaction.categoria_sugerida_por_ia,
            "comercio": Transaction.comercio,
            "banco": Transaction.banco,
        }.get(group_by, Transaction.categoria_sugerida_por_ia)

        stmt = (
            select(
                group_field.label("grupo"),
                func.sum(Transaction.monto_crc).label("total"),
                func.count(Transaction.id).label("cantidad"),
            )
            .where(
                Transaction.deleted_at.is_(None),
                Transaction.fecha_transaccion >= fecha_inicio,
                Transaction.tipo_transaccion == "compra",
            )
            .group_by(group_field)
            .order_by(func.sum(Transaction.monto_crc).desc())
        )

        results = session.execute(stmt).all()
        total_general = sum(r.total or 0 for r in results)

        return {
            "periodo": f"Últimos {days} días",
            "agrupado_por": group_by,
            "total_general": float(total_general),
            "total_formateado": f"₡{total_general:,.0f}",
            "grupos": [
                {
                    "nombre": r.grupo or "Sin categoría",
                    "total": float(r.total or 0),
                    "total_formateado": f"₡{r.total:,.0f}" if r.total else "₡0",
                    "cantidad": r.cantidad,
                    "porcentaje": round((r.total or 0) / total_general * 100, 1)
                    if total_general > 0
                    else 0,
                }
                for r in results
            ],
        }


@mcp.tool()
def get_top_merchants(
    days: int = 30,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Obtiene los comercios donde más gastas.

    Args:
        days: Número de días hacia atrás (default: 30)
        limit: Número de comercios a mostrar (default: 10)

    Returns:
        dict con lista de comercios ordenados por gasto total
    """
    with get_session() as session:
        fecha_inicio = datetime.now() - timedelta(days=days)

        stmt = (
            select(
                Transaction.comercio,
                func.sum(Transaction.monto_crc).label("total"),
                func.count(Transaction.id).label("visitas"),
            )
            .where(
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
                    "total_gastado": float(r.total),
                    "total_formateado": f"₡{r.total:,.0f}",
                    "visitas": r.visitas,
                    "promedio_por_visita": f"₡{r.total / r.visitas:,.0f}"
                    if r.visitas > 0
                    else "₡0",
                }
                for i, r in enumerate(results)
            ],
        }


# =============================================================================
# NIVEL 2: ANÁLISIS
# =============================================================================


@mcp.tool()
def search_transactions(
    query: str,
    limit: int = 10,
) -> dict[str, Any]:
    """
    Búsqueda semántica de transacciones usando embeddings.

    Ideal para preguntas en lenguaje natural como:
    - "gastos en supermercado"
    - "compras de comida rápida"
    - "pagos de servicios"

    Args:
        query: Consulta en lenguaje natural
        limit: Máximo de resultados (default: 10)

    Returns:
        dict con resultados ordenados por relevancia
    """
    with get_session() as session:
        if not query:
            return {"error": "Se requiere una consulta"}

        try:
            from finanzas_tracker.services.embedding_service import EmbeddingService

            service = EmbeddingService(session)
            results = service.search_similar(query, limit=limit)

            return {
                "query": query,
                "total": len(results),
                "resultados": [
                    {
                        "comercio": txn.comercio,
                        "monto_crc": float(txn.monto_crc),
                        "monto_formateado": f"₡{txn.monto_crc:,.0f}",
                        "fecha": txn.fecha_transaccion.strftime("%Y-%m-%d"),
                        "tipo": txn.tipo_transaccion,
                        "relevancia": round(similarity * 100, 1),
                    }
                    for txn, similarity in results
                ],
            }
        except Exception as e:
            logger.error(f"Error en búsqueda semántica: {e}")
            # Fallback a búsqueda simple
            stmt = (
                select(Transaction)
                .where(
                    Transaction.deleted_at.is_(None),
                    Transaction.comercio.ilike(f"%{query}%"),
                )
                .limit(limit)
            )
            transactions = session.execute(stmt).scalars().all()

            return {
                "query": query,
                "total": len(transactions),
                "nota": "Búsqueda simple (embeddings no disponibles)",
                "resultados": [
                    {
                        "comercio": t.comercio,
                        "monto_crc": float(t.monto_crc),
                        "monto_formateado": f"₡{t.monto_crc:,.0f}",
                        "fecha": t.fecha_transaccion.strftime("%Y-%m-%d"),
                        "tipo": t.tipo_transaccion,
                    }
                    for t in transactions
                ],
            }


@mcp.tool()
def get_monthly_comparison() -> dict[str, Any]:
    """
    Compara gastos entre el mes actual y el anterior.

    Returns:
        dict con totales de ambos meses, diferencia y tendencia
    """
    with get_session() as session:
        now = datetime.now()

        # Mes actual
        inicio_mes_actual = now.replace(day=1, hour=0, minute=0, second=0)

        # Mes anterior
        if now.month == 1:
            inicio_mes_anterior = now.replace(year=now.year - 1, month=12, day=1)
        else:
            inicio_mes_anterior = now.replace(month=now.month - 1, day=1)
        fin_mes_anterior = inicio_mes_actual - timedelta(days=1)

        # Total mes actual
        stmt_actual = select(func.sum(Transaction.monto_crc)).where(
            Transaction.deleted_at.is_(None),
            Transaction.fecha_transaccion >= inicio_mes_actual,
            Transaction.tipo_transaccion == "compra",
        )
        total_actual = session.execute(stmt_actual).scalar() or Decimal("0")

        # Total mes anterior
        stmt_anterior = select(func.sum(Transaction.monto_crc)).where(
            Transaction.deleted_at.is_(None),
            Transaction.fecha_transaccion >= inicio_mes_anterior,
            Transaction.fecha_transaccion <= fin_mes_anterior,
            Transaction.tipo_transaccion == "compra",
        )
        total_anterior = session.execute(stmt_anterior).scalar() or Decimal("0")

        # Calcular diferencia
        diferencia_pct: Decimal | int
        if total_anterior > 0:
            diferencia_pct = ((total_actual - total_anterior) / total_anterior) * 100
        else:
            diferencia_pct = Decimal("100") if total_actual > 0 else Decimal("0")

        return {
            "mes_actual": {
                "nombre": now.strftime("%B %Y"),
                "total": float(total_actual),
                "total_formateado": f"₡{total_actual:,.0f}",
            },
            "mes_anterior": {
                "nombre": inicio_mes_anterior.strftime("%B %Y"),
                "total": float(total_anterior),
                "total_formateado": f"₡{total_anterior:,.0f}",
            },
            "diferencia": {
                "monto": float(total_actual - total_anterior),
                "monto_formateado": f"₡{total_actual - total_anterior:,.0f}",
                "porcentaje": round(float(diferencia_pct), 1),
                "tendencia": "↑ Aumentó"
                if diferencia_pct > 0
                else "↓ Disminuyó"
                if diferencia_pct < 0
                else "→ Igual",
            },
        }


# =============================================================================
# NIVEL 3: COACHING FINANCIERO ← EL DIFERENCIADOR
# =============================================================================


@mcp.tool()
def budget_coaching(days: int = 30) -> dict[str, Any]:
    """
    🎯 Coaching financiero personalizado con IA.

    Analiza patrones de gasto y genera recomendaciones específicas:
    - Tendencias de gasto (aumento/disminución)
    - Patrones de comportamiento (fin de semana, noche)
    - Categorías con oportunidades de mejora
    - Gastos pequeños que se acumulan

    Esta es la herramienta PRINCIPAL de coaching - úsala cuando el usuario
    pida consejos, recomendaciones, o quiera mejorar sus finanzas.

    Args:
        days: Período de análisis en días (default: 30)

    Returns:
        dict con análisis completo y recomendaciones priorizadas
    """
    with get_session() as session:
        data = _get_analysis_data(session, days)

        # Generar todos los análisis
        coaching_points = []

        # 1. Tendencias de gasto
        trend = _analyze_spending_trend(data)
        if trend:
            coaching_points.append(trend)

        # 2. Patrones de comportamiento
        behavior = _analyze_behavior_patterns(data)
        coaching_points.extend(behavior)

        # 3. Oportunidades de ahorro
        savings = _analyze_savings_opportunities_detailed(data)
        coaching_points.extend(savings)

        # 4. Gastos pequeños acumulados
        small_spending = _analyze_small_spending(data)
        if small_spending:
            coaching_points.append(small_spending)

        # Ordenar por impacto (negativo primero = más urgente)
        priority = {"high": 0, "medium": 1, "low": 2}
        coaching_points.sort(key=lambda x: priority.get(x.get("priority", "medium"), 1))

        # Calcular score de salud financiera (0-100)
        health_score = _calculate_health_score(data, coaching_points)

        return {
            "periodo": f"Últimos {days} días",
            "resumen": {
                "total_gastado": float(data["total_current"]),
                "total_formateado": f"₡{data['total_current']:,.0f}",
                "transacciones": data["transaction_count"],
                "promedio_diario": f"₡{data['total_current'] / days:,.0f}",
                "salud_financiera": {
                    "score": health_score,
                    "nivel": _get_health_level(health_score),
                    "emoji": _get_health_emoji(health_score),
                },
            },
            "coaching": coaching_points[:5],  # Top 5 más importantes
            "accion_inmediata": coaching_points[0] if coaching_points else None,
        }


@mcp.tool()
def savings_opportunities() -> dict[str, Any]:
    """
    💰 Encuentra oportunidades concretas de ahorro.

    Analiza tus gastos y encuentra:
    - Categorías donde gastas más que el mes anterior
    - Comercios con visitas frecuentes (posibles suscripciones)
    - Gastos recurrentes que podrías reducir
    - Estimación de ahorro potencial

    Args: Ninguno

    Returns:
        dict con oportunidades de ahorro ordenadas por potencial
    """
    with get_session() as session:
        data = _get_analysis_data(session, 30)

        opportunities = []
        total_potential_savings = Decimal("0")

        # 1. Categorías que aumentaron vs mes anterior
        for cat, amount in data["by_category_current"].items():
            last_amount = data["by_category_last"].get(cat, Decimal("0"))
            if last_amount > 0:
                increase = amount - last_amount
                increase_pct = (increase / last_amount) * 100

                if increase_pct > 30 and float(increase) > 10000:
                    opportunities.append(
                        {
                            "tipo": "categoria_aumentada",
                            "descripcion": f"{cat}: aumentó {increase_pct:.0f}%",
                            "ahorro_potencial": float(increase),
                            "ahorro_formateado": f"₡{increase:,.0f}",
                            "recomendacion": f"Volver al nivel del mes pasado te ahorraría "
                            f"₡{increase:,.0f}",
                            "prioridad": "alta" if increase_pct > 50 else "media",
                        }
                    )
                    total_potential_savings += increase

        # 2. Comercios con visitas muy frecuentes
        for merchant, info in data["by_merchant"].items():
            if info["count"] >= 8:  # 8+ visitas = prácticamente diario
                potential = info["total"] * Decimal("0.3")  # 30% reducción
                opportunities.append(
                    {
                        "tipo": "visitas_frecuentes",
                        "descripcion": f"{merchant}: {info['count']} visitas este mes",
                        "ahorro_potencial": float(potential),
                        "ahorro_formateado": f"₡{potential:,.0f}",
                        "recomendacion": f"Reducir visitas un 30% ahorraría ₡{potential:,.0f}",
                        "prioridad": "media",
                    }
                )
                total_potential_savings += potential

        # 3. Gastos nocturnos (posibles impulsos)
        night_spending = _get_night_spending(data)
        if night_spending > 20000:
            potential = night_spending * Decimal("0.5")  # 50% reducible
            opportunities.append(
                {
                    "tipo": "gastos_nocturnos",
                    "descripcion": f"Gastos entre 10pm-2am: ₡{night_spending:,.0f}",
                    "ahorro_potencial": float(potential),
                    "ahorro_formateado": f"₡{potential:,.0f}",
                    "recomendacion": "Los gastos nocturnos suelen ser impulsivos. "
                    "Considera esperar al día siguiente antes de comprar.",
                    "prioridad": "media",
                }
            )
            total_potential_savings += potential

        # Ordenar por ahorro potencial
        def get_ahorro_potencial(x: dict[str, Any]) -> float:
            val = x.get("ahorro_potencial", 0)
            return float(val) if isinstance(val, int | float | Decimal) else 0.0

        opportunities.sort(key=get_ahorro_potencial, reverse=True)

        return {
            "periodo": "Últimos 30 días",
            "ahorro_potencial_total": float(total_potential_savings),
            "ahorro_formateado": f"₡{total_potential_savings:,.0f}",
            "oportunidades": opportunities[:7],  # Top 7
            "mensaje": f"Identificamos ₡{total_potential_savings:,.0f} en oportunidades "
            f"de ahorro. ¡Tú decides cuáles aplicar!",
        }


@mcp.tool()
def cashflow_prediction(days_ahead: int = 15) -> dict[str, Any]:
    """
    🔮 Predice tu flujo de efectivo futuro.

    Basado en tus patrones históricos, predice:
    - Gasto estimado para los próximos días
    - Si llegarás cómodo a fin de mes
    - Días "peligrosos" (ej: fines de semana)
    - Alerta si el ritmo actual es insostenible

    Args:
        days_ahead: Días a predecir (default: 15)

    Returns:
        dict con predicción de gastos y alertas
    """
    with get_session() as session:
        # Obtener datos históricos (últimos 60 días para mejor predicción)
        data = _get_analysis_data(session, 60)

        # Calcular promedios por día de la semana
        spending_by_weekday = defaultdict(list)
        for t in data["transactions"]:
            weekday = t.fecha_transaccion.weekday()
            spending_by_weekday[weekday].append(float(t.monto_crc))

        avg_by_weekday = {}
        for weekday, amounts in spending_by_weekday.items():
            avg_by_weekday[weekday] = sum(amounts) / len(amounts) if amounts else 0

        # Predecir próximos días
        predictions = []
        total_predicted = Decimal("0")
        today = date.today()

        weekday_names = [
            "Lunes",
            "Martes",
            "Miércoles",
            "Jueves",
            "Viernes",
            "Sábado",
            "Domingo",
        ]

        for i in range(1, days_ahead + 1):
            future_date = today + timedelta(days=i)
            weekday = future_date.weekday()
            predicted_amount = Decimal(str(avg_by_weekday.get(weekday, 0)))

            is_weekend = weekday >= 5
            risk_level = "alto" if is_weekend else "normal"

            predictions.append(
                {
                    "fecha": future_date.strftime("%Y-%m-%d"),
                    "dia": weekday_names[weekday],
                    "gasto_estimado": float(predicted_amount),
                    "gasto_formateado": f"₡{predicted_amount:,.0f}",
                    "nivel_riesgo": risk_level,
                }
            )
            total_predicted += predicted_amount

        # Determinar si el ritmo es sostenible
        daily_avg_current = data["total_current"] / 60  # promedio diario últimos 60 días
        monthly_projection = daily_avg_current * 30

        # Alerta de sostenibilidad
        sustainability = _evaluate_sustainability(data, monthly_projection)

        return {
            "periodo_prediccion": f"Próximos {days_ahead} días",
            "gasto_predicho_total": float(total_predicted),
            "gasto_formateado": f"₡{total_predicted:,.0f}",
            "promedio_diario_predicho": f"₡{total_predicted / days_ahead:,.0f}",
            "predicciones_por_dia": predictions[:7],  # Solo mostrar 7 días
            "proyeccion_mensual": {
                "monto": float(monthly_projection),
                "formateado": f"₡{monthly_projection:,.0f}",
            },
            "sostenibilidad": sustainability,
            "dias_riesgo_alto": [p["fecha"] for p in predictions if p["nivel_riesgo"] == "alto"],
        }


@mcp.tool()
def spending_alert() -> dict[str, Any]:
    """
    🚨 Detecta alertas y patrones problemáticos en tiempo real.

    Identifica:
    - Gastos inusuales (3x+ el promedio)
    - Categorías fuera de control
    - Comercios con aumento repentino
    - Patrones de gasto emocional

    Esta herramienta es ideal para revisión rápida:
    "¿Hay algo que deba preocuparme?"

    Args: Ninguno

    Returns:
        dict con alertas ordenadas por severidad
    """
    with get_session() as session:
        data = _get_analysis_data(session, 30)

        alerts = []

        # 1. Transacciones inusuales (3x promedio)
        avg_transaction = (
            data["total_current"] / data["transaction_count"]
            if data["transaction_count"] > 0
            else Decimal("0")
        )

        for t in data["transactions"][:50]:  # Revisar últimas 50
            if t.monto_crc > avg_transaction * 3 and float(t.monto_crc) > 15000:
                alerts.append(
                    {
                        "tipo": "transaccion_inusual",
                        "severidad": "alta",
                        "emoji": "⚠️",
                        "titulo": f"Gasto inusual en {t.comercio}",
                        "descripcion": f"₡{t.monto_crc:,.0f} es "
                        f"{float(t.monto_crc / avg_transaction):.1f}x tu promedio",
                        "fecha": t.fecha_transaccion.strftime("%Y-%m-%d"),
                        "accion": "Verifica que esta transacción sea correcta",
                    }
                )

        # 2. Categoría fuera de control (>50% aumento)
        for cat, amount in data["by_category_current"].items():
            last_amount = data["by_category_last"].get(cat, Decimal("0"))
            if last_amount > 0:
                increase_pct = ((amount - last_amount) / last_amount) * 100

                if increase_pct > 50 and float(amount) > 20000:
                    alerts.append(
                        {
                            "tipo": "categoria_descontrolada",
                            "severidad": "media",
                            "emoji": "📈",
                            "titulo": f"{cat} aumentó {increase_pct:.0f}%",
                            "descripcion": f"De ₡{last_amount:,.0f} a ₡{amount:,.0f}",
                            "fecha": "Este mes",
                            "accion": f"Revisa qué está causando el aumento en {cat}",
                        }
                    )

        # 3. Patrón de fin de semana excesivo
        weekend_data = _get_weekend_analysis(data)
        if weekend_data["is_excessive"]:
            alerts.append(
                {
                    "tipo": "patron_fin_de_semana",
                    "severidad": "media",
                    "emoji": "🎉",
                    "titulo": "Gastos excesivos en fines de semana",
                    "descripcion": f"Promedio ₡{weekend_data['avg_weekend']:,.0f} vs "
                    f"₡{weekend_data['avg_weekday']:,.0f} entre semana",
                    "fecha": "Patrón recurrente",
                    "accion": "Considera establecer un presupuesto específico para fines de semana",
                }
            )

        # 4. Ritmo insostenible
        if data["transaction_count"] > 0:
            days_passed = 30
            daily_rate = data["total_current"] / days_passed
            projected_monthly = daily_rate * 30

            if float(projected_monthly) > float(data["total_last"]) * 1.3:
                alerts.append(
                    {
                        "tipo": "ritmo_insostenible",
                        "severidad": "alta",
                        "emoji": "🔥",
                        "titulo": "Ritmo de gasto alto",
                        "descripcion": f"Proyección: ₡{projected_monthly:,.0f} "
                        f"(+30% vs mes pasado)",
                        "fecha": "Tendencia actual",
                        "accion": "Reduce gastos esta semana para equilibrar",
                    }
                )

        # Ordenar por severidad
        severity_order = {"alta": 0, "media": 1, "baja": 2}
        alerts.sort(key=lambda x: severity_order.get(x["severidad"], 1))

        # Determinar estado general
        high_alerts = len([a for a in alerts if a["severidad"] == "alta"])
        status = (
            "🔴 Requiere atención"
            if high_alerts > 0
            else "🟡 Algunas alertas"
            if alerts
            else "🟢 Todo en orden"
        )

        return {
            "estado": status,
            "total_alertas": len(alerts),
            "alertas_altas": high_alerts,
            "alertas": alerts[:5],  # Top 5
            "mensaje": _get_alert_message(alerts),
        }


@mcp.tool()
def goal_advisor(
    goal_amount: float,
    goal_months: int = 6,
    goal_name: str = "mi meta",
) -> dict[str, Any]:
    """
    🎯 Asesor de metas de ahorro.

    Analiza tu situación actual y te dice:
    - Si tu meta es alcanzable
    - Cuánto necesitas ahorrar por mes
    - De dónde puedes sacar ese dinero
    - Plan de acción concreto

    Args:
        goal_amount: Monto de la meta en colones (ej: 500000)
        goal_months: Meses para alcanzarla (default: 6)
        goal_name: Nombre de la meta (ej: "viaje", "fondo de emergencia")

    Returns:
        dict con análisis de viabilidad y plan de acción
    """
    with get_session() as session:
        data = _get_analysis_data(session, 30)

        goal = Decimal(str(goal_amount))
        monthly_needed = goal / goal_months

        # Identificar gastos reducibles
        reducible_categories = ["Entretenimiento", "Restaurantes", "Compras", "Otros"]
        reducible_amount = Decimal("0")
        reduction_plan = []

        for cat, amount in data["by_category_current"].items():
            if any(r.lower() in cat.lower() for r in reducible_categories):
                potential_reduction = amount * Decimal("0.3")  # 30% reducible
                reducible_amount += potential_reduction
                reduction_plan.append(
                    {
                        "categoria": cat,
                        "gasto_actual": float(amount),
                        "reduccion_sugerida": float(potential_reduction),
                        "nuevo_presupuesto": float(amount - potential_reduction),
                    }
                )

        # Evaluar viabilidad
        is_achievable = reducible_amount >= monthly_needed
        difficulty = _calculate_goal_difficulty(monthly_needed, reducible_amount)

        # Generar plan de acción
        action_plan = []
        remaining = monthly_needed

        for item in sorted(reduction_plan, key=lambda x: x["reduccion_sugerida"], reverse=True):
            if remaining <= 0:
                break

            contribution = min(Decimal(str(item["reduccion_sugerida"])), remaining)
            action_plan.append(
                {
                    "categoria": item["categoria"],
                    "accion": f"Reducir de ₡{item['gasto_actual']:,.0f} "
                    f"a ₡{item['nuevo_presupuesto']:,.0f}",
                    "ahorro_mensual": float(contribution),
                }
            )
            remaining -= contribution

        return {
            "meta": {
                "nombre": goal_name,
                "monto": float(goal),
                "monto_formateado": f"₡{goal:,.0f}",
                "plazo_meses": goal_months,
            },
            "requerimiento": {
                "ahorro_mensual_necesario": float(monthly_needed),
                "ahorro_formateado": f"₡{monthly_needed:,.0f}/mes",
            },
            "capacidad": {
                "ahorro_potencial": float(reducible_amount),
                "potencial_formateado": f"₡{reducible_amount:,.0f}/mes",
            },
            "viabilidad": {
                "es_alcanzable": is_achievable,
                "dificultad": difficulty,
                "mensaje": _get_goal_message(is_achievable, difficulty, goal_name),
            },
            "plan_de_accion": action_plan[:4],  # Top 4 acciones
            "siguiente_paso": action_plan[0]["accion"] if action_plan else "Revisar gastos fijos",
        }


# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================


def _get_analysis_data(session: Session, days: int) -> dict[str, Any]:
    """Obtiene datos para análisis de coaching."""
    today = date.today()
    start_date = today - timedelta(days=days)

    # Mes actual para comparación
    first_day_month = today.replace(day=1)
    last_month_start = (first_day_month - timedelta(days=1)).replace(day=1)

    # Transacciones del período
    transactions = (
        session.query(Transaction)
        .options(joinedload(Transaction.subcategory).joinedload(Subcategory.category))
        .filter(
            Transaction.fecha_transaccion >= start_date,
            Transaction.deleted_at.is_(None),
        )
        .order_by(Transaction.fecha_transaccion.desc())
        .all()
    )

    # Transacciones mes actual
    current_month_txns = [t for t in transactions if t.fecha_transaccion.date() >= first_day_month]

    # Transacciones mes anterior
    last_month_txns = (
        session.query(Transaction)
        .filter(
            Transaction.fecha_transaccion >= last_month_start,
            Transaction.fecha_transaccion < first_day_month,
            Transaction.deleted_at.is_(None),
        )
        .all()
    )

    # Calcular totales
    total_current = sum(t.monto_crc for t in current_month_txns)
    total_last = sum(t.monto_crc for t in last_month_txns)

    # Por categoría
    by_category_current: dict[str, Decimal] = defaultdict(Decimal)
    by_category_last: dict[str, Decimal] = defaultdict(Decimal)

    for t in current_month_txns:
        cat = (
            t.subcategory.category.nombre
            if t.subcategory and t.subcategory.category
            else t.categoria_sugerida_por_ia or "Sin categorizar"
        )
        by_category_current[cat] += t.monto_crc

    for t in last_month_txns:
        cat = (
            t.subcategory.category.nombre
            if t.subcategory and t.subcategory.category
            else t.categoria_sugerida_por_ia or "Sin categorizar"
        )
        by_category_last[cat] += t.monto_crc

    # Por comercio
    by_merchant: dict[str, dict[str, int | Decimal]] = defaultdict(
        lambda: {"count": 0, "total": Decimal("0")}
    )
    for t in current_month_txns:
        by_merchant[t.comercio]["count"] = int(by_merchant[t.comercio]["count"]) + 1
        by_merchant[t.comercio]["total"] = (
            Decimal(str(by_merchant[t.comercio]["total"])) + t.monto_crc
        )

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


def _analyze_spending_trend(data: dict) -> dict[str, Any] | None:
    """Analiza tendencia de gasto."""
    total_current = float(data["total_current"])
    total_last = float(data["total_last"])

    if total_last <= 0:
        return None

    change_pct = ((total_current - total_last) / total_last) * 100

    if abs(change_pct) < 10:
        return None  # Cambio no significativo

    if change_pct > 20:
        return {
            "tipo": "tendencia",
            "priority": "high",
            "emoji": "📈",
            "titulo": "Gasto aumentando significativamente",
            "descripcion": f"Llevas {change_pct:.0f}% más que el mes pasado",
            "impacto": f"₡{total_current - total_last:,.0f} adicionales",
            "recomendacion": "Revisa categorías que más aumentaron y reduce esta semana",
        }
    if change_pct < -20:
        return {
            "tipo": "tendencia",
            "priority": "low",
            "emoji": "✅",
            "titulo": "¡Excelente control de gastos!",
            "descripcion": f"Llevas {abs(change_pct):.0f}% menos que el mes pasado",
            "impacto": f"₡{abs(total_current - total_last):,.0f} ahorrados",
            "recomendacion": "Sigue así. Considera invertir el ahorro.",
        }

    return None


def _analyze_behavior_patterns(data: dict) -> list[dict[str, Any]]:
    """Analiza patrones de comportamiento."""
    patterns = []

    weekend = _get_weekend_analysis(data)
    if weekend["is_excessive"]:
        patterns.append(
            {
                "tipo": "comportamiento",
                "priority": "medium",
                "emoji": "🎉",
                "titulo": "Gastas más los fines de semana",
                "descripcion": f"Promedio fin de semana: ₡{weekend['avg_weekend']:,.0f} "
                f"vs ₡{weekend['avg_weekday']:,.0f} entre semana",
                "impacto": f"₡{weekend['excess']:,.0f} extra por mes",
                "recomendacion": "Planifica actividades económicas para el fin de semana",
            }
        )

    return patterns


def _analyze_savings_opportunities_detailed(data: dict) -> list[dict[str, Any]]:
    """Analiza oportunidades de ahorro detalladas."""
    opportunities = []

    for cat, amount in data["by_category_current"].items():
        last_amount = data["by_category_last"].get(cat, Decimal("0"))
        if last_amount > 0:
            increase = amount - last_amount
            increase_pct = (increase / last_amount) * 100

            if increase_pct > 40 and float(increase) > 15000:
                opportunities.append(
                    {
                        "tipo": "ahorro",
                        "priority": "high" if increase_pct > 60 else "medium",
                        "emoji": "💰",
                        "titulo": f"Oportunidad en {cat}",
                        "descripcion": f"Aumentó {increase_pct:.0f}% vs mes pasado",
                        "impacto": f"₡{increase:,.0f} adicionales",
                        "recomendacion": f"Reducir {cat} al nivel anterior ahorra "
                        f"₡{increase:,.0f}",
                    }
                )

    return opportunities[:2]


def _analyze_small_spending(data: dict) -> dict[str, Any] | None:
    """Analiza gastos pequeños acumulados."""
    small_txns = [t for t in data["transactions"] if float(t.monto_crc) < 5000]

    if len(small_txns) < 15:
        return None

    total_small = sum(float(t.monto_crc) for t in small_txns)
    total_all = float(data["total_current"]) if data["total_current"] > 0 else 1
    pct = (total_small / total_all) * 100

    if pct > 25:
        return {
            "tipo": "patron",
            "priority": "medium",
            "emoji": "🪙",
            "titulo": "Muchos gastos pequeños",
            "descripcion": f"{len(small_txns)} compras menores a ₡5,000 "
            f"suman ₡{total_small:,.0f} ({pct:.0f}%)",
            "impacto": "Se acumulan sin darte cuenta",
            "recomendacion": "Usa efectivo para gastos pequeños y establece un límite diario",
        }

    return None


def _get_night_spending(data: dict) -> Decimal:
    """Calcula gasto nocturno (10pm-2am)."""
    night_total = Decimal("0")
    for t in data["transactions"]:
        hour = t.fecha_transaccion.hour
        if hour >= 22 or hour <= 2:
            night_total += t.monto_crc
    return night_total


def _get_weekend_analysis(data: dict) -> dict[str, Any]:
    """Analiza gastos de fin de semana."""
    weekend_total = Decimal("0")
    weekday_total = Decimal("0")
    weekend_count = 0
    weekday_count = 0

    for t in data["transactions"]:
        if t.fecha_transaccion.weekday() >= 5:
            weekend_total += t.monto_crc
            weekend_count += 1
        else:
            weekday_total += t.monto_crc
            weekday_count += 1

    # Evitar división por cero
    avg_weekend = weekend_total / max(weekend_count, 1)
    avg_weekday = weekday_total / max(weekday_count, 1)

    # Calcular exceso mensual estimado
    excess = (avg_weekend - avg_weekday) * 8 if avg_weekend > avg_weekday else Decimal("0")

    return {
        "avg_weekend": float(avg_weekend),
        "avg_weekday": float(avg_weekday),
        "excess": float(excess),
        "is_excessive": avg_weekend > avg_weekday * Decimal("1.4"),
    }


def _calculate_health_score(data: dict, coaching_points: list) -> int:
    """Calcula score de salud financiera (0-100)."""
    score = 100

    # Penalizar por aumento de gastos
    if data["total_last"] > 0:
        change_pct = ((data["total_current"] - data["total_last"]) / data["total_last"]) * 100
        if change_pct > 20:
            score -= min(int(change_pct / 2), 20)

    # Penalizar por cantidad de alertas
    high_priority = len([p for p in coaching_points if p.get("priority") == "high"])
    score -= high_priority * 10

    # Penalizar por gastos pequeños excesivos
    small_txns = [t for t in data["transactions"] if float(t.monto_crc) < 5000]
    if len(small_txns) > 20:
        score -= 5

    return max(0, min(100, score))


def _get_health_level(score: int) -> str:
    """Convierte score a nivel textual."""
    if score >= 80:
        return "Excelente"
    if score >= 60:
        return "Bueno"
    if score >= 40:
        return "Regular"
    return "Necesita atención"


def _get_health_emoji(score: int) -> str:
    """Emoji según score."""
    if score >= 80:
        return "🌟"
    if score >= 60:
        return "👍"
    if score >= 40:
        return "⚠️"
    return "🔴"


def _evaluate_sustainability(data: dict, monthly_projection: Decimal) -> dict[str, Any]:
    """Evalúa sostenibilidad del ritmo de gasto."""
    if data["total_last"] <= 0:
        return {
            "es_sostenible": True,
            "mensaje": "No hay suficientes datos históricos para evaluar",
            "nivel": "desconocido",
        }

    ratio = float(monthly_projection / data["total_last"])

    if ratio <= 1.0:
        return {
            "es_sostenible": True,
            "mensaje": "✅ Tu ritmo de gasto es sostenible",
            "nivel": "bueno",
        }
    if ratio <= 1.2:
        return {
            "es_sostenible": True,
            "mensaje": "👍 Ritmo aceptable, pero podrías mejorar",
            "nivel": "aceptable",
        }
    return {
        "es_sostenible": False,
        "mensaje": f"⚠️ Ritmo alto: proyectas gastar {(ratio-1)*100:.0f}% más que el mes pasado",
        "nivel": "alto",
    }


def _get_alert_message(alerts: list) -> str:
    """Genera mensaje resumen de alertas."""
    if not alerts:
        return "No hay alertas. ¡Sigue así!"

    high = len([a for a in alerts if a["severidad"] == "alta"])
    if high > 0:
        return f"Tienes {high} alerta(s) que requieren atención inmediata."

    return f"Tienes {len(alerts)} alerta(s) para revisar cuando puedas."


def _calculate_goal_difficulty(monthly_needed: Decimal, reducible: Decimal) -> str:
    """Calcula dificultad de una meta."""
    if reducible <= 0:
        return "muy_dificil"

    ratio = monthly_needed / reducible

    if ratio <= 0.5:
        return "facil"
    if ratio <= 0.8:
        return "moderado"
    if ratio <= 1.0:
        return "desafiante"
    return "muy_dificil"


def _get_goal_message(is_achievable: bool, difficulty: str, goal_name: str) -> str:
    """Genera mensaje sobre la meta."""
    messages = {
        "facil": f"¡{goal_name} es muy alcanzable! Con pequeños ajustes lo logras.",
        "moderado": f"{goal_name} es alcanzable con disciplina. ¡Tú puedes!",
        "desafiante": f"{goal_name} requiere esfuerzo, pero es posible. Sigue el plan.",
        "muy_dificil": f"{goal_name} es ambicioso. Considera extender el plazo o reducir el monto.",
    }
    return messages.get(difficulty, "Analiza el plan de acción.")


# =============================================================================
# PUNTO DE ENTRADA
# =============================================================================


async def run_server() -> None:
    """Ejecuta el servidor MCP vía stdio (para Claude Desktop)."""
    logger.info("🚀 MCP Server iniciado con FastMCP")
    logger.info("📊 Herramientas disponibles: Nivel 1-3 (incluyendo Coaching)")
    await mcp.run_stdio_async()


def main() -> None:
    """Entry point para el CLI."""
    import asyncio

    asyncio.run(run_server())


if __name__ == "__main__":
    main()
