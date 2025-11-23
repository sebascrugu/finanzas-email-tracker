"""Componente de dashboard para mostrar alertas inteligentes."""


import streamlit as st

from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.alert import Alert, AlertSeverity, AlertStatus, AlertType
from finanzas_tracker.services.alert_service import alert_service


def render_alerts_widget(profile_id: str) -> None:
    """
    Renderiza un widget mostrando alertas inteligentes del usuario.

    Este widget muestra:
    - Alertas pendientes y recientes
    - Filtrado por severidad y tipo
    - Acciones: marcar como leída, descartar
    - Resumen de alertas

    Args:
        profile_id: ID del perfil activo
    """
    st.subheader("🔔 Alertas Inteligentes")

    # Obtener todas las alertas (no solo pendientes)
    with get_session() as session:
        all_alerts = (
            session.query(Alert)
            .filter(Alert.profile_id == profile_id)
            .order_by(Alert.created_at.desc())
            .limit(50)  # Últimas 50 alertas
            .all()
        )

        # Separar por estado
        pending_alerts = [a for a in all_alerts if a.status == AlertStatus.PENDING]
        read_alerts = [a for a in all_alerts if a.status == AlertStatus.READ]

    # Resumen
    col1, col2, col3 = st.columns(3)

    with col1:
        critical_count = sum(
            1 for a in pending_alerts if a.severity == AlertSeverity.CRITICAL
        )
        st.metric(
            "🚨 Críticas",
            critical_count,
            delta=None,
            help="Alertas que requieren atención inmediata",
        )

    with col2:
        warning_count = sum(
            1 for a in pending_alerts if a.severity == AlertSeverity.WARNING
        )
        st.metric(
            "⚠️ Advertencias",
            warning_count,
            delta=None,
            help="Alertas importantes pero no urgentes",
        )

    with col3:
        st.metric(
            "📬 Pendientes",
            len(pending_alerts),
            delta=None,
            help="Total de alertas sin revisar",
        )

    # Tabs para separar alertas
    tab1, tab2 = st.tabs(["📬 Pendientes", "✅ Revisadas"])

    with tab1:
        if not pending_alerts:
            st.success("🎉 ¡Todo al día! No tienes alertas pendientes.")
            st.info(
                "💡 Tip: Las alertas se generan automáticamente cuando:\n"
                "- Se detecta una anomalía en tus transacciones\n"
                "- Una suscripción está próxima a vencerse\n"
                "- Excedes tu presupuesto mensual\n"
                "- Hay un gasto inusualmente alto en una categoría"
            )
        else:
            _render_alert_list(pending_alerts, profile_id, show_actions=True)

    with tab2:
        if not read_alerts:
            st.info("No hay alertas revisadas recientes.")
        else:
            _render_alert_list(read_alerts, profile_id, show_actions=False)

    # Tips para el usuario
    with st.expander("💡 ¿Cómo funcionan las alertas inteligentes?"):
        st.markdown(
            """
            El sistema genera alertas automáticamente para ayudarte a controlar tus finanzas:

            **Tipos de alertas:**

            🚨 **Anomalía Detectada**
            - Transacción inusual según tus patrones de gasto
            - Ejemplo: "⚠️ Gasto inusual detectado: ₡85,000 en Amazon"

            📅 **Suscripción Próxima**
            - Notificación 3 días antes de un cobro recurrente
            - Te ayuda a anticipar gastos mensuales

            💰 **Presupuesto Excedido**
            - Alerta cuando superas el umbral de tu presupuesto
            - Configurable (por defecto: 85% del presupuesto)

            📈 **Gasto Alto en Categoría**
            - Detecta gastos 3x superiores al promedio
            - Compara con tus últimos 3 meses

            📊 **Comparación Mensual**
            - Compara tus gastos vs mes anterior
            - Ejemplo: "📈 Este mes gastaste 40% más en Uber Eats"

            🌍 **Compra Internacional**
            - Notifica sobre transacciones fuera del país
            - Útil para detectar fraudes

            💳 **Cierre de Tarjeta** (próximamente)
            - Alertas antes del cierre de tu ciclo de tarjeta
            - Ejemplo: "Tu tarjeta X5678 cierra en 3 días (saldo: ₡120,000)"

            🎯 **Meta de Ahorro** (próximamente)
            - Progreso hacia tus metas de ahorro
            - Ejemplo: "Estás a ₡50,000 de tu meta de ahorro"

            **Configuración:**
            Puedes activar/desactivar tipos de alertas desde tu perfil.

            **Actualización automática:**
            Las alertas se generan automáticamente al procesar correos.
            No necesitas hacer nada manualmente.
            """
        )


def _render_alert_list(alerts: list[Alert], profile_id: str, show_actions: bool) -> None:
    """
    Renderiza una lista de alertas.

    Args:
        alerts: Lista de alertas a renderizar
        profile_id: ID del perfil activo
        show_actions: Si se muestran botones de acción
    """
    for alert in alerts:
        # Determinar icono y color según severidad
        if alert.severity == AlertSeverity.CRITICAL:
            severity_emoji = "🚨"
            severity_color = "red"
        elif alert.severity == AlertSeverity.WARNING:
            severity_emoji = "⚠️"
            severity_color = "orange"
        else:
            severity_emoji = "ℹ️"  # noqa: RUF001
            severity_color = "blue"

        # Determinar emoji según tipo de alerta
        type_emoji = _get_alert_type_emoji(alert.alert_type)

        # Contenedor para cada alerta
        with st.container():
            # Encabezado con badge de severidad
            col1, col2 = st.columns([4, 1])

            with col1:
                st.markdown(
                    f"### {type_emoji} {alert.title}",
                    help=f"Severidad: {alert.severity.value}",
                )

            with col2:
                st.markdown(
                    f":{severity_color}[**{severity_emoji} {alert.severity.value.upper()}**]"
                )

            # Mensaje de la alerta
            st.markdown(alert.message)

            # Metadata
            col1, col2, col3 = st.columns(3)

            with col1:
                st.caption(f"📅 {alert.created_at.strftime('%d/%m/%Y %H:%M')}")

            with col2:
                st.caption(f"🔖 {_get_alert_type_name(alert.alert_type)}")

            with col3:
                if alert.read_at:
                    st.caption(f"✅ Leída: {alert.read_at.strftime('%d/%m/%Y %H:%M')}")

            # Botones de acción (solo para alertas pendientes)
            if show_actions:
                col1, col2 = st.columns(2)

                with col1:
                    if st.button(
                        "✅ Marcar como leída",
                        key=f"read_{alert.id}",
                        use_container_width=True,
                    ):
                        alert_service.mark_alert_as_read(alert.id)
                        st.success("Alerta marcada como leída")
                        st.rerun()

                with col2:
                    if st.button(
                        "🗑️ Descartar",
                        key=f"dismiss_{alert.id}",
                        use_container_width=True,
                    ):
                        alert_service.dismiss_alert(alert.id)
                        st.success("Alerta descartada")
                        st.rerun()

            st.markdown("---")


def _get_alert_type_emoji(alert_type: AlertType) -> str:
    """Retorna el emoji correspondiente a un tipo de alerta."""
    emoji_map = {
        AlertType.ANOMALY_DETECTED: "⚠️",
        AlertType.SUBSCRIPTION_DUE: "📅",
        AlertType.BUDGET_EXCEEDED: "💰",
        AlertType.CATEGORY_SPIKE: "📈",
        AlertType.MULTIPLE_PURCHASES: "🔁",
        AlertType.HIGH_SPENDING_DAY: "💸",
        AlertType.UNUSUAL_TIME: "🕐",
        AlertType.INTERNATIONAL_PURCHASE: "🌍",
        AlertType.CREDIT_CARD_CLOSING: "💳",
        AlertType.MONTHLY_COMPARISON: "📊",
        AlertType.SAVINGS_GOAL_PROGRESS: "🎯",
        AlertType.MONTHLY_SPENDING_FORECAST: "📊",
        AlertType.BUDGET_FORECAST_WARNING: "⚠️",
        AlertType.CATEGORY_TREND_ALERT: "📈",
    }
    return emoji_map.get(alert_type, "🔔")


def _get_alert_type_name(alert_type: AlertType) -> str:
    """Retorna el nombre legible de un tipo de alerta."""
    name_map = {
        AlertType.ANOMALY_DETECTED: "Anomalía",
        AlertType.SUBSCRIPTION_DUE: "Suscripción",
        AlertType.BUDGET_EXCEEDED: "Presupuesto",
        AlertType.CATEGORY_SPIKE: "Gasto Alto",
        AlertType.MULTIPLE_PURCHASES: "Compras múltiples",
        AlertType.HIGH_SPENDING_DAY: "Día de alto gasto",
        AlertType.UNUSUAL_TIME: "Horario inusual",
        AlertType.INTERNATIONAL_PURCHASE: "Compra internacional",
        AlertType.CREDIT_CARD_CLOSING: "Cierre de tarjeta",
        AlertType.MONTHLY_COMPARISON: "Comparación mensual",
        AlertType.SAVINGS_GOAL_PROGRESS: "Meta de ahorro",
        AlertType.MONTHLY_SPENDING_FORECAST: "Predicción de Gasto",
        AlertType.BUDGET_FORECAST_WARNING: "Advertencia de Presupuesto",
        AlertType.CATEGORY_TREND_ALERT: "Tendencia de Categoría",
    }
    return name_map.get(alert_type, alert_type.value)
