"""Componente de dashboard para mostrar estado del detector de anomalías."""

import streamlit as st

from finanzas_tracker.services.anomaly_helpers import (
    get_anomaly_detector_status,
    retrain_anomaly_detector,
)


def render_anomaly_status_widget(profile_id: str) -> None:
    """
    Renderiza un widget mostrando el estado del detector de anomalías.

    Este widget muestra:
    - Si el modelo está activo o no
    - Cuántas transacciones hay disponibles
    - Botón para re-entrenar manualmente (si aplica)

    Args:
        profile_id: ID del perfil activo
    """
    st.subheader("🤖 Detector de Anomalías (ML)")

    # Obtener estado
    status = get_anomaly_detector_status(profile_id)

    # Mostrar estado con color
    if status["is_active"]:
        st.success(status["message"])
    elif status["can_train"]:
        st.warning(status["message"])
    else:
        st.info(status["message"])

    # Mostrar detalles
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Transacciones",
            f"{status['transactions_count']}/{status['min_required']}",
            delta=None,
        )

    with col2:
        st.metric(
            "Estado",
            "Activo" if status["is_active"] else "Inactivo",
            delta=None,
        )

    with col3:
        if status["model_exists"]:
            st.metric("Modelo", "✅ Entrenado", delta=None)
        else:
            st.metric("Modelo", "❌ No disponible", delta=None)

    # Botón de re-entrenamiento (solo si puede entrenar)
    if status["can_train"]:
        st.markdown("---")

        col1, col2, col3 = st.columns([1, 2, 1])

        with col2:
            if st.button(
                "🔄 Re-entrenar Modelo",
                help="Re-entrena el modelo con tus datos más recientes. Esto mejora la detección de anomalías.",
                use_container_width=True,
            ):
                with st.spinner("Entrenando modelo de ML..."):
                    result = retrain_anomaly_detector(profile_id)

                if result["success"]:
                    st.success(result["message"])
                    st.balloons()
                    st.rerun()  # Recargar para actualizar estado
                else:
                    st.error(result["message"])

    # Info adicional colapsable
    with st.expander("ℹ️ ¿Qué es la Detección de Anomalías?"):  # noqa: RUF001
        st.markdown(
            """
            La **Detección de Anomalías** usa Machine Learning para identificar transacciones inusuales
            basándose en tus patrones de gasto normales.

            **¿Qué detecta?**
            - ✅ Montos inusualmente altos o bajos
            - ✅ Compras en horarios raros (ej: 3am)
            - ✅ Transacciones internacionales inesperadas
            - ✅ Gastos en categorías nuevas
            - ✅ Patrones diferentes a tu historial

            **¿Cómo funciona?**
            1. El modelo aprende de tus últimos 6 meses de transacciones
            2. Identifica qué es "normal" para vos
            3. Detecta automáticamente cuando algo es diferente

            **Casos de uso:**
            - 🔒 **Seguridad**: Detectar posible fraude
            - 💡 **Conciencia**: Alertas cuando gastás fuera de lo normal
            - 📊 **Control**: Identificar gastos grandes inesperados

            **Privacidad:**
            - ⚡ Todo el procesamiento es 100% local
            - 🔐 Tus datos nunca salen de tu computadora
            - 🎯 El modelo aprende SOLO de tus patrones
            """
        )


# Ejemplo de uso en una página de dashboard
def example_usage() -> None:
    """Ejemplo de cómo usar este componente."""
    st.title("Dashboard Financiero")

    # Suponiendo que tenés el profile_id en session_state
    if "current_profile_id" in st.session_state:
        profile_id = st.session_state["current_profile_id"]

        # Renderizar el widget
        render_anomaly_status_widget(profile_id)

    else:
        st.warning("Selecciona un perfil primero")


if __name__ == "__main__":
    # Para testing
    example_usage()
