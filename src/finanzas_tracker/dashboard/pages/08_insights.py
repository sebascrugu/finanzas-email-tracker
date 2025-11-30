"""Pagina de Insights Financieros Automaticos."""

import streamlit as st


st.set_page_config(
    page_title="Insights - Finanzas Tracker",
    page_icon=":bulb:",
    layout="wide",
)

from pathlib import Path
import sys


src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.services.insights import InsightType, insights_service


logger = get_logger(__name__)


def insights_page() -> None:
    """Pagina principal de insights financieros."""
    st.title("Insights Financieros")
    st.caption("Analisis automatico de tus patrones de gasto")

    with get_session() as session:
        perfil = session.query(Profile).filter(Profile.es_activo.is_(True)).first()

        if not perfil:
            st.warning("No hay un perfil activo. Configura uno en Setup.")
            return

        st.info(f"Analizando finanzas de **{perfil.nombre}**")

        with st.spinner("Generando insights..."):
            insights = insights_service.generate_insights(str(perfil.id))

        if not insights:
            st.success("No hay insights destacables este mes. Tus finanzas van bien!")
            return

        _mostrar_insights(insights)


def _mostrar_insights(insights: list) -> None:
    """Muestra los insights en cards."""
    # Agrupar por impacto
    negativos = [i for i in insights if i.impact == "negative"]
    neutrales = [i for i in insights if i.impact == "neutral"]
    positivos = [i for i in insights if i.impact == "positive"]

    if negativos:
        st.subheader("Atencion Requerida", divider="red")
        for insight in negativos:
            _render_insight_card(insight, "error")

    if neutrales:
        st.subheader("Para Tu Informacion", divider="orange")
        for insight in neutrales:
            _render_insight_card(insight, "warning")

    if positivos:
        st.subheader("Buen Trabajo!", divider="green")
        for insight in positivos:
            _render_insight_card(insight, "success")


def _render_insight_card(insight, status: str) -> None:
    """Renderiza una card de insight."""
    icon = _get_icon(insight.type)

    with st.container(border=True):
        col1, col2 = st.columns([0.1, 0.9])

        with col1:
            st.markdown(f"### {icon}")

        with col2:
            st.markdown(f"**{insight.title}**")
            st.write(insight.description)

            if insight.recommendation:
                st.caption(f"Recomendacion: {insight.recommendation}")

            if insight.value:
                if insight.type in [InsightType.SPENDING_INCREASE, InsightType.SPENDING_DECREASE]:
                    st.metric("Cambio", f"{insight.value:.0f}%")
                elif insight.type in [
                    InsightType.UNUSUAL_TRANSACTION,
                    InsightType.RECURRING_EXPENSE,
                ]:
                    st.metric("Monto", f"₡{insight.value:,.0f}")


def _get_icon(insight_type: InsightType) -> str:
    """Retorna el icono para un tipo de insight."""
    icons = {
        InsightType.SPENDING_INCREASE: "📈",
        InsightType.SPENDING_DECREASE: "📉",
        InsightType.UNUSUAL_TRANSACTION: "⚠️",
        InsightType.TOP_CATEGORY: "🏷️",
        InsightType.SAVINGS_OPPORTUNITY: "💰",
        InsightType.RECURRING_EXPENSE: "🔄",
    }
    return icons.get(insight_type, "💡")


if __name__ == "__main__":
    insights_page()
