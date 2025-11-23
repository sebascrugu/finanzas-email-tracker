"""Página de Reportes Mensuales con IA."""

import streamlit as st

st.set_page_config(
    page_title="Reportes - Finanzas Tracker",
    page_icon="📊",
    layout="wide",
)

from datetime import date, datetime
from pathlib import Path
import sys

src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.services.monthly_report_service import monthly_report_service

logger = get_logger(__name__)


def main() -> None:
    """Página principal de reportes mensuales."""
    st.title("📊 Reportes Mensuales")
    st.caption("Análisis inteligente de tus finanzas generado por IA")

    with get_session() as session:
        perfil = session.query(Profile).filter(Profile.es_activo.is_(True)).first()

        if not perfil:
            st.warning("⚠️ No hay un perfil activo. Configura uno en Setup.")
            return

        # Selector de mes
        col_select1, col_select2, col_select3 = st.columns([2, 1, 1])

        with col_select1:
            st.info(f"📌 Generando reportes para: **{perfil.nombre}**")

        with col_select2:
            # Año actual por defecto
            current_year = datetime.now().year
            selected_year = st.selectbox(
                "Año",
                range(current_year, current_year - 3, -1),
                index=0,
            )

        with col_select3:
            # Mes actual por defecto
            current_month = datetime.now().month
            months_es = [
                "Enero", "Febrero", "Marzo", "Abril",
                "Mayo", "Junio", "Julio", "Agosto",
                "Septiembre", "Octubre", "Noviembre", "Diciembre"
            ]

            selected_month_name = st.selectbox(
                "Mes",
                months_es,
                index=current_month - 1,
            )

            selected_month = months_es.index(selected_month_name) + 1

        # Botón para generar reporte
        if st.button("🤖 Generar Reporte con IA", use_container_width=True, type="primary"):
            with st.spinner("Analizando tus finanzas con Claude AI... Esto puede tomar 10-15 segundos."):
                try:
                    report = monthly_report_service.generate_monthly_report(
                        profile_id=perfil.id,
                        year=selected_year,
                        month=selected_month,
                    )

                    # Guardar en session state
                    st.session_state.current_report = report
                    st.success("✅ ¡Reporte generado exitosamente!")
                    st.rerun()

                except Exception as e:
                    st.error(f"❌ Error al generar reporte: {e}")
                    logger.error(f"Error generating report: {e}", exc_info=True)

        st.markdown("---")

        # Mostrar reporte si existe
        if "current_report" in st.session_state and st.session_state.current_report:
            _render_report(st.session_state.current_report)
        else:
            st.info(
                "👆 Seleccioná un mes y presioná **Generar Reporte** para ver el análisis "
                "completo generado por Inteligencia Artificial."
            )

            # Ejemplo de lo que se genera
            with st.expander("💡 ¿Qué incluye el reporte?", expanded=True):
                st.markdown(
                    """
                    ### Claude AI analiza y genera:

                    1. **📋 Resumen Ejecutivo**
                       - Visión general del mes en lenguaje natural
                       - Aspecto más importante (logros o áreas de mejora)
                       - Mensaje motivador personalizado

                    2. **🔍 Análisis Detallado**
                       - Tendencias de gasto identificadas
                       - Comparación con mes anterior
                       - Patrones en categorías y comercios
                       - Observaciones sobre comportamiento financiero

                    3. **💡 Insights Clave**
                       - Hallazgos específicos y accionables
                       - 4-6 puntos concretos y relevantes
                       - Datos que quizás no notaste

                    4. **✅ Recomendaciones**
                       - 3-5 acciones priorizadas por impacto
                       - Consejos específicos y realistas
                       - Enfocadas en mejorar próximo mes

                    5. **🔮 Proyección Próximo Mes**
                       - Predicción basada en tendencias actuales
                       - Áreas de oportunidad
                       - Meta sugerida

                    ### 📊 Plus: Datos Numéricos Completos
                    - Ingresos vs Gastos
                    - Top categorías y comercios
                    - Progreso de metas de ahorro
                    - Balance y tendencias
                    """
                )


def _render_report(report: dict) -> None:
    """Renderiza el reporte mensual completo."""
    # Header del reporte
    st.markdown(f"# 📊 Reporte: {report['month_name']}")
    st.caption(f"Generado el {datetime.fromisoformat(report['generated_at']).strftime('%d/%m/%Y %H:%M')}")

    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "💰 Ingresos",
            f"₡{report['data']['income']['total']:,.0f}",
        )

    with col2:
        st.metric(
            "💸 Gastos",
            f"₡{report['data']['expenses']['total']:,.0f}",
        )

    with col3:
        balance_data = report['data']['balance']
        st.metric(
            "📊 Balance",
            f"₡{balance_data['amount']:,.0f}",
            f"{balance_data['percentage']:.1f}%",
            delta_color="normal" if balance_data['amount'] > 0 else "inverse",
        )

    with col4:
        comparison = report['data']['comparison']
        st.metric(
            "📈 vs Mes Anterior",
            f"{comparison['change_percentage']:+.1f}%",
            f"₡{comparison['change_amount']:+,.0f}",
            delta_color="inverse",
        )

    st.markdown("---")

    # Tabs para organizar el contenido
    tab1, tab2, tab3, tab4 = st.tabs([
        "📋 Resumen Ejecutivo",
        "🔍 Análisis Detallado",
        "📊 Datos Numéricos",
        "💾 Exportar"
    ])

    with tab1:
        _render_executive_summary(report)

    with tab2:
        _render_detailed_analysis(report)

    with tab3:
        _render_numerical_data(report)

    with tab4:
        _render_export_options(report)


def _render_executive_summary(report: dict) -> None:
    """Renderiza el resumen ejecutivo."""
    st.markdown("## 📋 Resumen Ejecutivo")
    st.markdown("*Generado por Claude AI*")

    st.markdown(report["executive_summary"])

    st.markdown("---")

    # Insights clave en cards
    st.markdown("### 💡 Insights Clave")

    for insight in report["insights"]:
        with st.container(border=True):
            st.markdown(insight)

    st.markdown("---")

    # Recomendaciones
    st.markdown("### ✅ Recomendaciones para el Próximo Mes")

    for i, rec in enumerate(report["recommendations"], 1):
        st.markdown(f"**{i}.** {rec}")

    st.markdown("---")

    # Proyección
    st.markdown("### 🔮 Proyección para el Próximo Mes")
    st.info(report["next_month_projection"])


def _render_detailed_analysis(report: dict) -> None:
    """Renderiza el análisis detallado."""
    st.markdown("## 🔍 Análisis Detallado")
    st.markdown("*Generado por Claude AI*")

    st.markdown(report["detailed_analysis"])

    st.markdown("---")

    # Comparación visual
    st.markdown("### 📈 Comparación con Mes Anterior")

    comparison = report['data']['comparison']

    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Gastos Mes Anterior",
            f"₡{comparison['previous_month_spending']:,.0f}",
        )

    with col2:
        st.metric(
            "Gastos Este Mes",
            f"₡{report['data']['expenses']['total']:,.0f}",
            f"{comparison['change_percentage']:+.1f}%",
            delta_color="inverse",
        )

    # Tendencia
    trend_emoji = {
        "up": "📈 Aumentó",
        "down": "📉 Disminuyó",
        "stable": "➡️ Se mantuvo estable",
    }

    trend = comparison['trend']
    st.info(f"**Tendencia**: {trend_emoji.get(trend, trend)}")


def _render_numerical_data(report: dict) -> None:
    """Renderiza los datos numéricos completos."""
    st.markdown("## 📊 Datos Numéricos Detallados")

    # Sección de gastos
    st.markdown("### 💸 Desglose de Gastos")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Top 5 Categorías")
        for cat in report['data']['expenses']['top_categories']:
            percentage = (cat['amount'] / report['data']['expenses']['total']) * 100
            st.markdown(
                f"**{cat['name']}**: ₡{cat['amount']:,.0f} "
                f"({percentage:.1f}%) - {cat['count']} transacciones"
            )

    with col2:
        st.markdown("#### Top 5 Comercios")
        for merchant in report['data']['expenses']['top_merchants']:
            percentage = (merchant['amount'] / report['data']['expenses']['total']) * 100
            st.markdown(
                f"**{merchant['name']}**: ₡{merchant['amount']:,.0f} "
                f"({percentage:.1f}%) - {merchant['count']} compras"
            )

    st.markdown("---")

    # Sección de ingresos
    st.markdown("### 💰 Desglose de Ingresos")

    for income in report['data']['income']['sources']:
        st.markdown(f"- **{income['nombre']}**: ₡{income['monto']:,.0f}")

    st.markdown("---")

    # Sección de metas
    st.markdown("### 🎯 Estado de Metas de Ahorro")

    savings = report['data']['savings']

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total de Metas", savings['total_goals'])

    with col2:
        st.metric("Progreso Promedio", f"{savings['avg_progress']:.1f}%")

    with col3:
        st.metric("Completadas Este Mes", savings['completed_this_month'], "🎉")

    with col4:
        st.metric("En Riesgo", savings['at_risk'], "⚠️")


def _render_export_options(report: dict) -> None:
    """Renderiza opciones de exportación."""
    st.markdown("## 💾 Exportar Reporte")

    st.info(
        "Exportá tu reporte para guardarlo, compartirlo o incluirlo en presentaciones."
    )

    # Opción 1: Markdown
    st.markdown("### 📝 Formato Markdown")

    markdown_report = f"""# Reporte Financiero Mensual
## {report['month_name']}

---

## 📋 Resumen Ejecutivo

{report['executive_summary']}

---

## 🔍 Análisis Detallado

{report['detailed_analysis']}

---

## 💡 Insights Clave

{chr(10).join(f"- {insight}" for insight in report['insights'])}

---

## ✅ Recomendaciones

{chr(10).join(f"{i}. {rec}" for i, rec in enumerate(report['recommendations'], 1))}

---

## 🔮 Proyección Próximo Mes

{report['next_month_projection']}

---

## 📊 Datos Numéricos

**Ingresos**: ₡{report['data']['income']['total']:,.0f}
**Gastos**: ₡{report['data']['expenses']['total']:,.0f}
**Balance**: ₡{report['data']['balance']['amount']:,.0f} ({report['data']['balance']['percentage']:.1f}%)

**Top Categorías**:
{chr(10).join(f"- {cat['name']}: ₡{cat['amount']:,.0f}" for cat in report['data']['expenses']['top_categories'])}

---

*Generado por Finanzas Tracker con Claude AI*
*{datetime.fromisoformat(report['generated_at']).strftime('%d/%m/%Y %H:%M')}*
"""

    st.download_button(
        label="📥 Descargar Markdown (.md)",
        data=markdown_report,
        file_name=f"reporte_{report['year']}_{report['month']:02d}.md",
        mime="text/markdown",
    )

    # Opción 2: JSON (para desarrolladores)
    st.markdown("### 🔧 Formato JSON")

    import json
    json_report = json.dumps(report, indent=2, ensure_ascii=False)

    st.download_button(
        label="📥 Descargar JSON (.json)",
        data=json_report,
        file_name=f"reporte_{report['year']}_{report['month']:02d}.json",
        mime="application/json",
    )

    # Preview del JSON
    with st.expander("👁️ Preview JSON"):
        st.json(report)


if __name__ == "__main__":
    main()
