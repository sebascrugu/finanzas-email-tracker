"""Página de Alertas Inteligentes - Centro de Notificaciones."""

import streamlit as st

st.set_page_config(
    page_title="Alertas - Finanzas Tracker",
    page_icon="🔔",
    layout="wide",
)

from pathlib import Path
import sys
from datetime import datetime

src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.dashboard.helpers import require_profile
from finanzas_tracker.dashboard.styles import apply_custom_styles
from finanzas_tracker.models.alert import Alert
from finanzas_tracker.models.enums import AlertPriority, AlertStatus, AlertType
from finanzas_tracker.services.alert_engine import AlertEngine
from sqlalchemy import select, func

logger = get_logger(__name__)

# Apply custom styles
apply_custom_styles()


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def get_alert_stats(profile_id: str) -> dict:
    """Obtiene estadísticas de alertas para un perfil."""
    with get_session() as session:
        # Total por estado
        stmt = select(
            Alert.status,
            func.count(Alert.id)
        ).where(
            Alert.profile_id == profile_id
        ).group_by(Alert.status)

        results = session.execute(stmt).all()
        stats = {status: count for status, count in results}

        # Total por prioridad (solo pendientes)
        stmt_priority = select(
            Alert.priority,
            func.count(Alert.id)
        ).where(
            Alert.profile_id == profile_id,
            Alert.status == AlertStatus.PENDING
        ).group_by(Alert.priority)

        priority_results = session.execute(stmt_priority).all()
        priority_stats = {priority: count for priority, count in priority_results}

        return {
            "by_status": stats,
            "by_priority": priority_stats,
            "total": sum(stats.values()),
            "pending": stats.get(AlertStatus.PENDING, 0),
            "read": stats.get(AlertStatus.READ, 0),
            "resolved": stats.get(AlertStatus.RESOLVED, 0),
            "dismissed": stats.get(AlertStatus.DISMISSED, 0),
            "critical": priority_stats.get(AlertPriority.CRITICAL, 0),
            "high": priority_stats.get(AlertPriority.HIGH, 0),
            "medium": priority_stats.get(AlertPriority.MEDIUM, 0),
            "low": priority_stats.get(AlertPriority.LOW, 0),
        }


def get_alerts(profile_id: str, status_filter: str = "all", priority_filter: str = "all") -> list[Alert]:
    """Obtiene alertas filtradas para un perfil."""
    with get_session() as session:
        stmt = select(Alert).where(Alert.profile_id == profile_id)

        # Filtro por estado
        if status_filter != "all":
            if status_filter == "active":
                stmt = stmt.where(Alert.status.in_([AlertStatus.PENDING, AlertStatus.READ]))
            else:
                stmt = stmt.where(Alert.status == status_filter)

        # Filtro por prioridad
        if priority_filter != "all":
            stmt = stmt.where(Alert.priority == priority_filter)

        # Ordenar: primero pendientes, luego por prioridad, luego por fecha
        stmt = stmt.order_by(
            Alert.status.desc(),
            Alert.priority.asc(),
            Alert.created_at.desc()
        )

        return list(session.execute(stmt).scalars().all())


def render_alert_card(alert: Alert):
    """Renderiza una tarjeta de alerta."""
    # Colores según prioridad
    priority_colors = {
        AlertPriority.CRITICAL: "#ff4444",
        AlertPriority.HIGH: "#ff8800",
        AlertPriority.MEDIUM: "#ffbb33",
        AlertPriority.LOW: "#00C851",
    }

    priority_labels = {
        AlertPriority.CRITICAL: "🔴 CRÍTICA",
        AlertPriority.HIGH: "🟠 ALTA",
        AlertPriority.MEDIUM: "🟡 MEDIA",
        AlertPriority.LOW: "🟢 BAJA",
    }

    status_labels = {
        AlertStatus.PENDING: "⏳ Pendiente",
        AlertStatus.READ: "👁️ Leída",
        AlertStatus.RESOLVED: "✅ Resuelta",
        AlertStatus.DISMISSED: "❌ Descartada",
    }

    color = priority_colors.get(alert.priority, "#666")
    priority_label = priority_labels.get(alert.priority, "DESCONOCIDA")
    status_label = status_labels.get(alert.status, "DESCONOCIDO")

    # Determinar opacidad según estado
    opacity = "1.0" if alert.status == AlertStatus.PENDING else "0.6"

    # Formato de fecha
    created_str = alert.created_at.strftime("%d/%m/%Y %H:%M")

    # HTML de la tarjeta
    st.markdown(f"""
    <div style="
        border-left: 5px solid {color};
        background: white;
        padding: 15px;
        margin-bottom: 15px;
        border-radius: 5px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        opacity: {opacity};
    ">
        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 10px;">
            <div>
                <span style="background: {color}; color: white; padding: 3px 8px; border-radius: 3px; font-size: 0.75rem; font-weight: bold;">
                    {priority_label}
                </span>
                <span style="margin-left: 10px; color: #666; font-size: 0.85rem;">
                    {status_label}
                </span>
            </div>
            <span style="color: #999; font-size: 0.8rem;">{created_str}</span>
        </div>
        <h3 style="margin: 10px 0; color: #333;">{alert.emoji} {alert.title}</h3>
        <p style="margin: 10px 0; color: #666; line-height: 1.5;">{alert.message}</p>
    </div>
    """, unsafe_allow_html=True)

    # Botones de acción
    col1, col2, col3, col4 = st.columns([1, 1, 1, 2])

    with col1:
        if alert.status == AlertStatus.PENDING:
            if st.button("👁️ Marcar Leída", key=f"read_{alert.id}", use_container_width=True):
                with get_session() as session:
                    db_alert = session.get(Alert, alert.id)
                    if db_alert:
                        db_alert.mark_as_read()
                        session.commit()
                        st.rerun()

    with col2:
        if alert.status in [AlertStatus.PENDING, AlertStatus.READ]:
            if st.button("✅ Resolver", key=f"resolve_{alert.id}", use_container_width=True):
                with get_session() as session:
                    db_alert = session.get(Alert, alert.id)
                    if db_alert:
                        db_alert.mark_as_resolved()
                        session.commit()
                        st.success("✅ Alerta resuelta")
                        st.rerun()

    with col3:
        if alert.status in [AlertStatus.PENDING, AlertStatus.READ]:
            if st.button("❌ Descartar", key=f"dismiss_{alert.id}", use_container_width=True):
                with get_session() as session:
                    db_alert = session.get(Alert, alert.id)
                    if db_alert:
                        db_alert.dismiss()
                        session.commit()
                        st.rerun()

    with col4:
        if alert.action_url:
            if st.button(f"→ Ver Detalle", key=f"action_{alert.id}", use_container_width=True):
                st.info(f"🔗 Ir a: {alert.action_url}")

    st.markdown("---")


# ============================================================================
# PÁGINA PRINCIPAL
# ============================================================================

def main():
    """Página principal de alertas."""
    # Require authentication
    profile = require_profile()

    # Header
    st.title("🔔 Centro de Alertas")
    st.markdown("Tus notificaciones inteligentes sobre eventos importantes")

    # Obtener estadísticas
    stats = get_alert_stats(profile.id)

    # Métricas principales
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="📊 Total Alertas",
            value=stats["total"],
            help="Total de alertas generadas"
        )

    with col2:
        st.metric(
            label="⏳ Pendientes",
            value=stats["pending"],
            delta=f"+{stats['pending']}" if stats['pending'] > 0 else "Todo al día",
            delta_color="inverse",
            help="Alertas que requieren tu atención"
        )

    with col3:
        st.metric(
            label="🔴 Críticas",
            value=stats["critical"],
            delta="¡Actúa ya!" if stats["critical"] > 0 else "Ninguna",
            delta_color="inverse",
            help="Alertas que requieren acción inmediata"
        )

    with col4:
        st.metric(
            label="✅ Resueltas",
            value=stats["resolved"],
            help="Alertas que ya atendiste"
        )

    with col5:
        st.metric(
            label="👁️ Leídas",
            value=stats["read"],
            help="Alertas que viste pero no resolviste"
        )

    st.markdown("---")

    # Filtros y acciones
    col_filter1, col_filter2, col_action = st.columns([1, 1, 2])

    with col_filter1:
        status_filter = st.selectbox(
            "🔍 Filtrar por Estado",
            ["all", "active", AlertStatus.PENDING, AlertStatus.READ, AlertStatus.RESOLVED, AlertStatus.DISMISSED],
            format_func=lambda x: {
                "all": "Todas",
                "active": "Activas (Pendientes + Leídas)",
                AlertStatus.PENDING: "⏳ Pendientes",
                AlertStatus.READ: "👁️ Leídas",
                AlertStatus.RESOLVED: "✅ Resueltas",
                AlertStatus.DISMISSED: "❌ Descartadas",
            }[x]
        )

    with col_filter2:
        priority_filter = st.selectbox(
            "⚡ Filtrar por Prioridad",
            ["all", AlertPriority.CRITICAL, AlertPriority.HIGH, AlertPriority.MEDIUM, AlertPriority.LOW],
            format_func=lambda x: {
                "all": "Todas",
                AlertPriority.CRITICAL: "🔴 Críticas",
                AlertPriority.HIGH: "🟠 Altas",
                AlertPriority.MEDIUM: "🟡 Medias",
                AlertPriority.LOW: "🟢 Bajas",
            }[x]
        )

    with col_action:
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🔄 Evaluar Nuevas Alertas", use_container_width=True, type="primary"):
                with st.spinner("Evaluando reglas de alertas..."):
                    try:
                        with get_session() as session:
                            engine = AlertEngine(session)
                            new_alerts = engine.evaluate_all_alerts(profile.id)

                            if new_alerts:
                                # Persistir alertas
                                for alert in new_alerts:
                                    engine.create_alert(alert)

                                st.success(f"✅ {len(new_alerts)} nueva(s) alerta(s) generada(s)!")
                                st.rerun()
                            else:
                                st.info("ℹ️ No hay nuevas alertas. ¡Todo bien!")

                    except Exception as e:
                        st.error(f"❌ Error al evaluar alertas: {e}")
                        logger.error(f"Error evaluating alerts: {e}", exc_info=True)

        with col_btn2:
            if st.button("✅ Marcar Todas Leídas", use_container_width=True):
                with get_session() as session:
                    stmt = select(Alert).where(
                        Alert.profile_id == profile.id,
                        Alert.status == AlertStatus.PENDING
                    )
                    pending_alerts = session.execute(stmt).scalars().all()

                    for alert in pending_alerts:
                        alert.mark_as_read()

                    session.commit()
                    st.success(f"✅ {len(pending_alerts)} alertas marcadas como leídas")
                    st.rerun()

    st.markdown("---")

    # Lista de alertas
    alerts = get_alerts(profile.id, status_filter, priority_filter)

    if alerts:
        st.markdown(f"### 📋 {len(alerts)} Alerta(s)")

        # Agrupar por prioridad si no hay filtro de prioridad
        if priority_filter == "all":
            # Críticas
            critical_alerts = [a for a in alerts if a.priority == AlertPriority.CRITICAL]
            if critical_alerts:
                st.markdown("#### 🔴 Alertas Críticas")
                for alert in critical_alerts:
                    render_alert_card(alert)

            # Altas
            high_alerts = [a for a in alerts if a.priority == AlertPriority.HIGH]
            if high_alerts:
                st.markdown("#### 🟠 Alertas Altas")
                for alert in high_alerts:
                    render_alert_card(alert)

            # Medias
            medium_alerts = [a for a in alerts if a.priority == AlertPriority.MEDIUM]
            if medium_alerts:
                st.markdown("#### 🟡 Alertas Medias")
                for alert in medium_alerts:
                    render_alert_card(alert)

            # Bajas
            low_alerts = [a for a in alerts if a.priority == AlertPriority.LOW]
            if low_alerts:
                st.markdown("#### 🟢 Alertas Bajas")
                for alert in low_alerts:
                    render_alert_card(alert)
        else:
            # Sin agrupar
            for alert in alerts:
                render_alert_card(alert)

    else:
        st.info("ℹ️ No hay alertas que mostrar con los filtros seleccionados.")

        if status_filter == "all" and priority_filter == "all":
            st.markdown("""
            ### 🎉 ¡Todo limpio!

            No tienes alertas todavía. El sistema las generará automáticamente cuando:
            - Se acerque una fecha de pago
            - Excedas un presupuesto
            - Detecte transacciones duplicadas
            - Y más...

            Presiona **"Evaluar Nuevas Alertas"** para generar alertas ahora.
            """)


if __name__ == "__main__":
    main()
