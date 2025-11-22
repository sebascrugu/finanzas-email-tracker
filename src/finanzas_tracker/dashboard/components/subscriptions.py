"""Componente de dashboard para mostrar suscripciones recurrentes."""

from datetime import date

import streamlit as st

from finanzas_tracker.core.database import get_session
from finanzas_tracker.models.subscription import Subscription
from finanzas_tracker.services.subscription_detector import subscription_detector


def render_subscriptions_widget(profile_id: str) -> None:
    """
    Renderiza un widget mostrando las suscripciones recurrentes detectadas.

    Este widget muestra:
    - Lista de suscripciones activas
    - Próximas fechas de cobro
    - Total mensual aproximado
    - Botón para re-detectar suscripciones

    Args:
        profile_id: ID del perfil activo
    """
    st.subheader("📋 Suscripciones Recurrentes")

    # Obtener suscripciones activas
    with get_session() as session:
        active_subs = (
            session.query(Subscription)
            .filter(
                Subscription.profile_id == profile_id,
                Subscription.is_active == True,  # noqa: E712
                Subscription.deleted_at.is_(None),
            )
            .order_by(Subscription.proxima_fecha_estimada.asc())
            .all()
        )

    if not active_subs:
        st.info(
            "ℹ️ No se han detectado suscripciones recurrentes.\n\n"
            "💡 Tip: Necesitas al menos 2 cobros del mismo servicio para detectar un patrón."
        )

        # Botón para detectar manualmente
        if st.button("🔍 Buscar Suscripciones", use_container_width=True):
            with st.spinner("Analizando transacciones..."):
                stats = subscription_detector.sync_subscriptions_to_db(profile_id)

                if stats["total_detected"] > 0:
                    st.success(
                        f"✅ Detección completada: "
                        f"{stats['created']} nuevas, "
                        f"{stats['updated']} actualizadas"
                    )
                    st.rerun()
                else:
                    st.warning("No se detectaron suscripciones recurrentes.")

        return

    # Calcular total mensual
    total_mensual = sum(
        sub.monto_promedio for sub in active_subs if sub.frecuencia_dias <= 35
    )

    # Mostrar resumen
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Suscripciones Activas",
            len(active_subs),
            delta=None,
        )

    with col2:
        st.metric(
            "Total Mensual",
            f"₡{total_mensual:,.0f}",
            delta=None,
            help="Suma de suscripciones con frecuencia ≤35 días",
        )

    with col3:
        proximas = sum(1 for sub in active_subs if sub.esta_proxima)
        st.metric(
            "Próximas (3 días)",
            proximas,
            delta=None,
            help="Suscripciones que se cobrarán en los próximos 3 días",
        )

    # Mostrar lista de suscripciones
    st.markdown("---")
    st.markdown("### Detalle de Suscripciones")

    for sub in active_subs:
        days_until = sub.dias_hasta_proximo_cobro

        # Determinar emoji y color según proximidad
        if days_until < 0:
            status_emoji = "⚠️"
            status_text = f"Vencida hace {abs(days_until)} días"
            status_color = "red"
        elif days_until == 0:
            status_emoji = "🔔"
            status_text = "Cobro HOY"
            status_color = "orange"
        elif days_until <= 3:
            status_emoji = "🔜"
            status_text = f"En {days_until} días"
            status_color = "orange"
        else:
            status_emoji = "✅"
            status_text = f"En {days_until} días"
            status_color = "green"

        # Mostrar cada suscripción en un contenedor
        with st.container():
            col1, col2, col3 = st.columns([3, 2, 2])

            with col1:
                st.markdown(f"**{status_emoji} {sub.comercio}**")
                if sub.monto_min != sub.monto_max:
                    st.caption(
                        f"₡{sub.monto_promedio:,.0f} "
                        f"(rango: ₡{sub.monto_min:,.0f} - ₡{sub.monto_max:,.0f})"
                    )
                else:
                    st.caption(f"₡{sub.monto_promedio:,.0f}")

            with col2:
                st.markdown(f"**{sub.frecuencia_display}**")
                st.caption(f"Cada {sub.frecuencia_dias} días")

            with col3:
                st.markdown(f":{status_color}[**{status_text}**]")
                st.caption(f"{sub.proxima_fecha_estimada.strftime('%d/%m/%Y')}")

            # Información adicional en expander
            with st.expander("ℹ️ Más información"):
                st.write(f"**Cobros detectados:** {sub.occurrences_count}")
                st.write(f"**Primera vez:** {sub.primera_fecha_cobro.strftime('%d/%m/%Y')}")
                st.write(f"**Última vez:** {sub.ultima_fecha_cobro.strftime('%d/%m/%Y')}")
                st.write(f"**Confianza:** {sub.confidence_score:.0f}%")

                if sub.notas:
                    st.write(f"**Notas:** {sub.notas}")

            st.markdown("---")

    # Botón para re-detectar suscripciones
    st.markdown("### Actualizar Suscripciones")

    if st.button("🔄 Actualizar Suscripciones", use_container_width=True):
        with st.spinner("Re-analizando transacciones..."):
            stats = subscription_detector.sync_subscriptions_to_db(profile_id)

            st.success(
                f"✅ Actualización completada: "
                f"{stats['created']} nuevas, "
                f"{stats['updated']} actualizadas, "
                f"{stats['deactivated']} desactivadas"
            )
            st.rerun()

    # Tips para el usuario
    with st.expander("💡 ¿Cómo funciona la detección de suscripciones?"):
        st.markdown(
            """
            El sistema detecta automáticamente suscripciones recurrentes analizando tus transacciones:

            **Criterios de detección:**
            - Mismo comercio
            - Monto similar (±10% de variación)
            - Frecuencia regular (±5 días de variación)
            - Mínimo 2 cobros detectados

            **Tipos de frecuencia:**
            - **Semanal:** cada ~7 días
            - **Quincenal:** cada ~15 días
            - **Mensual:** cada ~30 días
            - **Personalizado:** otras frecuencias

            **Actualización automática:**
            Las suscripciones se actualizan automáticamente cada vez que procesas
            correos nuevos. No necesitas hacer nada manualmente.

            **Desactivación automática:**
            Si una suscripción no se cobra en 2x su frecuencia normal, se marca
            como inactiva automáticamente.
            """
        )
