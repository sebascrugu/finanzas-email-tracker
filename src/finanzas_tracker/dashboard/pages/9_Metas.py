"""Página de Metas Financieras con AI."""

import streamlit as st

st.set_page_config(
    page_title="Metas Financieras - Finanzas Tracker",
    page_icon="🎯",
    layout="wide",
)

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sys

src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.services.goal_service import goal_service

logger = get_logger(__name__)


def main() -> None:
    """Página principal de metas financieras."""
    st.title("🎯 Metas Financieras")
    st.caption("Alcanza tus objetivos financieros con análisis inteligente")

    with get_session() as session:
        perfil = session.query(Profile).filter(Profile.es_activo.is_(True)).first()

        if not perfil:
            st.warning("⚠️ No hay un perfil activo. Configura uno en Setup.")
            return

        # Tabs principales
        tab1, tab2 = st.tabs(["📊 Mis Metas", "➕ Nueva Meta"])

        with tab1:
            _mostrar_metas(perfil.id)

        with tab2:
            _crear_nueva_meta(perfil.id)


def _mostrar_metas(profile_id: str) -> None:
    """Muestra todas las metas del usuario."""
    goals = goal_service.get_active_goals(profile_id)

    if not goals:
        st.info(
            "👋 ¡Aún no tienes metas! Crea tu primera meta en la pestaña **Nueva Meta**"
        )
        return

    # Métricas generales
    col1, col2, col3, col4 = st.columns(4)

    total_metas = len(goals)
    metas_completadas = sum(1 for g in goals if g.is_completed)
    metas_en_riesgo = sum(1 for g in goals if g.is_at_risk)
    progreso_promedio = sum(g.progress_percentage for g in goals) / total_metas if total_metas > 0 else 0

    with col1:
        st.metric("Total de Metas", total_metas)

    with col2:
        st.metric("Completadas", f"{metas_completadas} 🎉")

    with col3:
        st.metric("En Riesgo", f"{metas_en_riesgo} ⚠️")

    with col4:
        st.metric("Progreso Promedio", f"{progreso_promedio:.1f}%")

    st.markdown("---")

    # Filtros
    col_filter1, col_filter2 = st.columns([2, 1])

    with col_filter1:
        filter_status = st.selectbox(
            "Filtrar por estado",
            ["Todas", "Activas", "Completadas", "En Riesgo", "En Progreso"],
            key="filter_status",
        )

    with col_filter2:
        sort_by = st.selectbox(
            "Ordenar por",
            ["Prioridad", "Progreso", "Fecha Límite", "Nombre"],
            key="sort_by",
        )

    # Aplicar filtros
    filtered_goals = _aplicar_filtros(goals, filter_status, sort_by)

    # Mostrar metas
    for goal in filtered_goals:
        _render_goal_card(goal)


def _aplicar_filtros(goals: list, filter_status: str, sort_by: str) -> list:
    """Aplica filtros y ordenamiento a las metas."""
    # Filtrar
    if filter_status == "Activas":
        goals = [g for g in goals if not g.is_completed]
    elif filter_status == "Completadas":
        goals = [g for g in goals if g.is_completed]
    elif filter_status == "En Riesgo":
        goals = [g for g in goals if g.is_at_risk]
    elif filter_status == "En Progreso":
        goals = [g for g in goals if not g.is_completed and g.progress_percentage > 0]

    # Ordenar
    if sort_by == "Prioridad":
        goals = sorted(goals, key=lambda g: g.priority)
    elif sort_by == "Progreso":
        goals = sorted(goals, key=lambda g: g.progress_percentage, reverse=True)
    elif sort_by == "Fecha Límite":
        goals = sorted(
            goals,
            key=lambda g: g.deadline if g.deadline else date.max,
        )
    elif sort_by == "Nombre":
        goals = sorted(goals, key=lambda g: g.name)

    return goals


def _render_goal_card(goal) -> None:
    """Renderiza una card de meta con diseño atractivo."""
    # Color según estado de salud
    health_colors = {
        "excellent": "🟢",
        "good": "🟡",
        "warning": "🟠",
        "critical": "🔴",
    }

    health_emoji = health_colors.get(goal.health_status, "⚪")

    with st.container(border=True):
        # Header
        col_header1, col_header2 = st.columns([0.8, 0.2])

        with col_header1:
            st.markdown(f"### {goal.display_name}")
            if goal.category:
                st.caption(f"Categoría: {goal.category}")

        with col_header2:
            st.markdown(f"### {health_emoji}")
            st.caption(goal.health_status.upper())

        # Progress bar
        progress_pct = min(goal.progress_percentage, 100.0)
        st.progress(progress_pct / 100.0)

        # Métricas
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Objetivo",
                f"₡{goal.target_amount:,.0f}",
            )

        with col2:
            st.metric(
                "Ahorrado",
                f"₡{goal.current_amount:,.0f}",
                f"{progress_pct:.1f}%",
            )

        with col3:
            st.metric(
                "Faltante",
                f"₡{goal.amount_remaining:,.0f}",
            )

        with col4:
            if goal.deadline:
                days_left = goal.days_remaining or 0
                st.metric(
                    "Días Restantes",
                    days_left,
                    "¡Ya venció!" if goal.is_overdue else None,
                    delta_color="inverse",
                )
            else:
                st.metric("Días Restantes", "Sin límite")

        # Información adicional
        if goal.required_monthly_savings:
            st.info(
                f"💡 **Ahorro mensual requerido:** ₡{goal.required_monthly_savings:,.0f}"
            )

        # Probabilidad de éxito (si está calculada)
        if goal.success_probability is not None:
            prob_pct = float(goal.success_probability)
            prob_color = "green" if prob_pct >= 70 else "orange" if prob_pct >= 50 else "red"

            col_prob1, col_prob2 = st.columns([0.7, 0.3])

            with col_prob1:
                st.markdown(
                    f"**Probabilidad de éxito:** :{prob_color}[{prob_pct:.1f}%]"
                )

            with col_prob2:
                if st.button(
                    "🔄 Recalcular",
                    key=f"recalc_{goal.id}",
                    help="Recalcular probabilidad con datos actuales",
                ):
                    with st.spinner("Calculando..."):
                        new_prob = goal_service.calculate_success_probability(goal.id)
                        st.success(f"Nueva probabilidad: {new_prob:.1f}%")
                        st.rerun()

        # Alertas
        if goal.is_at_risk:
            st.warning(
                "⚠️ **Esta meta está en riesgo.** Vas atrasado según el tiempo transcurrido."
            )

        if goal.is_overdue and not goal.is_completed:
            st.error(
                "🔴 **Meta vencida.** La fecha límite ya pasó y aún no has alcanzado el objetivo."
            )

        # Recomendaciones AI
        if goal.ai_recommendations:
            with st.expander("🤖 **Recomendaciones de IA**", expanded=False):
                st.markdown(goal.ai_recommendations)
                st.caption(
                    f"Última actualización: {goal.last_ai_analysis_at.strftime('%Y-%m-%d %H:%M') if goal.last_ai_analysis_at else 'N/A'}"
                )

        # Acciones
        st.markdown("---")
        col_act1, col_act2, col_act3, col_act4 = st.columns(4)

        with col_act1:
            if st.button("💰 Agregar Contribución", key=f"contribute_{goal.id}"):
                _mostrar_form_contribucion(goal)

        with col_act2:
            if st.button("🤖 Generar Recomendaciones AI", key=f"ai_{goal.id}"):
                with st.spinner("Analizando con Claude..."):
                    try:
                        recommendations = goal_service.generate_ai_recommendations(
                            goal.id
                        )
                        st.success("✅ Recomendaciones generadas!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al generar recomendaciones: {e}")

        with col_act3:
            if st.button("📊 Calcular Probabilidad", key=f"prob_{goal.id}"):
                with st.spinner("Calculando..."):
                    try:
                        prob = goal_service.calculate_success_probability(goal.id)
                        st.success(f"Probabilidad de éxito: {prob:.1f}%")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al calcular probabilidad: {e}")

        with col_act4:
            if st.button("📜 Ver Historial", key=f"history_{goal.id}"):
                _mostrar_historial(goal)


def _mostrar_form_contribucion(goal) -> None:
    """Muestra formulario para agregar contribución."""
    with st.form(key=f"form_contribute_{goal.id}"):
        st.markdown(f"### Agregar Contribución a: {goal.name}")

        amount = st.number_input(
            "Monto a contribuir (₡)",
            min_value=0.0,
            step=1000.0,
            value=10000.0,
            format="%.0f",
        )

        note = st.text_area("Nota (opcional)", placeholder="Ej: Ahorro de este mes")

        submit = st.form_submit_button("💾 Guardar Contribución")

        if submit:
            if amount <= 0:
                st.error("El monto debe ser mayor a 0")
            else:
                try:
                    goal_service.add_contribution(
                        goal.id,
                        Decimal(str(amount)),
                        note if note else None,
                    )
                    st.success(f"✅ Contribución de ₡{amount:,.0f} agregada!")
                    st.balloons()  # Celebración 🎉
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al agregar contribución: {e}")


def _mostrar_historial(goal) -> None:
    """Muestra el historial de hitos de una meta."""
    summary = goal_service.get_goal_summary(goal.id)
    milestones = summary.get("milestones", [])

    if not milestones:
        st.info("Aún no hay actividad en esta meta")
        return

    st.markdown(f"### 📜 Historial: {goal.name}")

    for milestone in milestones:
        icon_map = {
            "achievement": "🏆",
            "progress": "🎯",
            "contribution": "💰",
            "alert": "⚠️",
        }

        icon = icon_map.get(milestone["type"], "📌")

        with st.container(border=True):
            col_m1, col_m2 = st.columns([0.1, 0.9])

            with col_m1:
                st.markdown(f"### {icon}")

            with col_m2:
                st.markdown(f"**{milestone['title']}**")
                st.caption(milestone["description"])
                st.caption(f"📅 {milestone['date'][:10]}")


def _crear_nueva_meta(profile_id: str) -> None:
    """Formulario para crear una nueva meta."""
    st.markdown("### ➕ Crear Nueva Meta Financiera")

    with st.form(key="form_new_goal", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input(
                "Nombre de la Meta *",
                placeholder="Ej: Mundial 2026, Vacaciones, Fondo de Emergencia",
                help="Dale un nombre motivador a tu meta",
            )

            target_amount = st.number_input(
                "Monto Objetivo (₡) *",
                min_value=0.0,
                step=10000.0,
                value=100000.0,
                format="%.0f",
                help="¿Cuánto necesitas ahorrar?",
            )

            deadline = st.date_input(
                "Fecha Límite",
                value=date.today() + timedelta(days=365),
                min_value=date.today(),
                help="¿Para cuándo necesitas alcanzar esta meta?",
            )

        with col2:
            # Selector de icono
            icon_options = {
                "⚽ Deportes": "⚽",
                "✈️ Viajes": "✈️",
                "🏠 Casa/Hogar": "🏠",
                "🚗 Auto/Transporte": "🚗",
                "💍 Boda": "💍",
                "🎓 Educación": "🎓",
                "💼 Negocio": "💼",
                "🎮 Entretenimiento": "🎮",
                "🏥 Salud": "🏥",
                "💰 Ahorro General": "💰",
                "🎯 Otro": "🎯",
            }

            icon_label = st.selectbox("Icono de la Meta", list(icon_options.keys()))
            icon = icon_options[icon_label]

            category_options = [
                "Vacaciones",
                "Emergencia",
                "Compra Mayor",
                "Inversión",
                "Educación",
                "Salud",
                "Evento Especial",
                "Otro",
            ]

            category = st.selectbox("Categoría", category_options)

            priority = st.selectbox(
                "Prioridad",
                [1, 2, 3],
                format_func=lambda x: {1: "🔴 Alta", 2: "🟡 Media", 3: "🟢 Baja"}[x],
                help="¿Qué tan importante es esta meta?",
            )

        current_amount = st.number_input(
            "Monto Inicial Ahorrado (₡)",
            min_value=0.0,
            step=1000.0,
            value=0.0,
            format="%.0f",
            help="¿Ya tienes algo ahorrado para esta meta?",
        )

        description = st.text_area(
            "Descripción (opcional)",
            placeholder="¿Por qué es importante esta meta para ti?",
            help="Una descripción motivadora te ayudará a mantener el enfoque",
        )

        # Configuración avanzada
        with st.expander("⚙️ Configuración Avanzada", expanded=False):
            savings_type = st.selectbox(
                "Tipo de Ahorro",
                ["manual", "monthly_target", "automatic"],
                format_func=lambda x: {
                    "manual": "Manual - Contribuyo cuando puedo",
                    "monthly_target": "Meta Mensual - Contribución fija mensual",
                    "automatic": "Automático - Descuento automático",
                }[x],
            )

            monthly_target = None
            if savings_type == "monthly_target":
                monthly_target = st.number_input(
                    "Meta de Contribución Mensual (₡)",
                    min_value=0.0,
                    step=1000.0,
                    value=10000.0,
                    format="%.0f",
                )

        submit = st.form_submit_button("🎯 Crear Meta", use_container_width=True)

        if submit:
            if not name:
                st.error("❌ El nombre de la meta es requerido")
            elif target_amount <= 0:
                st.error("❌ El monto objetivo debe ser mayor a 0")
            else:
                try:
                    goal = goal_service.create_goal(
                        profile_id=profile_id,
                        name=name,
                        target_amount=Decimal(str(target_amount)),
                        deadline=deadline,
                        category=category,
                        icon=icon,
                        priority=priority,
                        savings_type=savings_type,
                        monthly_contribution_target=(
                            Decimal(str(monthly_target)) if monthly_target else None
                        ),
                        current_amount=Decimal(str(current_amount)),
                        description=description if description else None,
                    )

                    st.success(f"✅ Meta '{name}' creada exitosamente!")
                    st.balloons()

                    # Calcular probabilidad inicial
                    with st.spinner("Calculando probabilidad de éxito..."):
                        prob = goal_service.calculate_success_probability(goal.id)
                        st.info(f"📊 Probabilidad de éxito: {prob:.1f}%")

                    # Generar recomendaciones iniciales
                    with st.spinner("Generando recomendaciones con IA..."):
                        try:
                            recommendations = goal_service.generate_ai_recommendations(
                                goal.id
                            )
                            st.markdown("### 🤖 Recomendaciones Iniciales")
                            st.markdown(recommendations)
                        except Exception as e:
                            logger.warning(f"No se pudieron generar recomendaciones: {e}")

                    st.info(
                        "👈 Ve a la pestaña **Mis Metas** para ver tu nueva meta y empezar a contribuir"
                    )

                except Exception as e:
                    st.error(f"❌ Error al crear la meta: {e}")
                    logger.error(f"Error creating goal: {e}", exc_info=True)


if __name__ == "__main__":
    main()
