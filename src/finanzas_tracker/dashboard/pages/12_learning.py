"""Dashboard de Sistema de Aprendizaje (ML/AI).

Visualiza el estado y métricas del sistema de aprendizaje inteligente:
- Patrones aprendidos
- Estadísticas de precisión
- Embeddings y similarity
- Patrones globales crowdsourced
"""

import logging
from datetime import UTC, datetime, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import func, select

from finanzas_tracker.core.database import SessionLocal
from finanzas_tracker.dashboard.helpers import (
    get_current_profile,
    require_profile,
)
from finanzas_tracker.models.category import Subcategory
from finanzas_tracker.models.smart_learning import (
    GlobalPattern,
    LearningEvent,
    LearningEventType,
    PatternType,
    TransactionPattern,
    UserLearningProfile,
)
from finanzas_tracker.services.smart_learning_service import SmartLearningService

st.set_page_config(
    page_title="Finanzas CR - Aprendizaje AI",
    page_icon="🧠",
    layout="wide",
)

logger = logging.getLogger(__name__)


def main() -> None:
    """Página principal del dashboard de ML."""
    st.title("🧠 Sistema de Aprendizaje Inteligente")
    st.markdown("""
    Este dashboard muestra cómo el sistema aprende de tus transacciones 
    para auto-categorizar futuros gastos.
    """)
    
    profile = require_profile()
    if not profile:
        return
    
    db = SessionLocal()
    
    try:
        # Obtener servicio y estadísticas
        learning_service = SmartLearningService(db)
        stats = learning_service.get_learning_stats(profile.id)
        
        # Mostrar métricas principales
        render_main_metrics(stats)
        
        st.divider()
        
        # Tabs para diferentes secciones
        tab1, tab2, tab3, tab4 = st.tabs([
            "📚 Mis Patrones",
            "📈 Estadísticas",
            "🌍 Patrones Globales",
            "📋 Historial"
        ])
        
        with tab1:
            render_user_patterns(db, profile.id)
        
        with tab2:
            render_statistics(db, profile.id, stats)
        
        with tab3:
            render_global_patterns(db)
        
        with tab4:
            render_learning_history(db, profile.id)
        
    finally:
        db.close()


def render_main_metrics(stats: dict) -> None:
    """Renderiza métricas principales."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="🎯 Precisión",
            value=f"{stats.get('accuracy_rate', 0):.1f}%",
            help="Porcentaje de sugerencias correctas"
        )
    
    with col2:
        st.metric(
            label="📚 Patrones Aprendidos",
            value=stats.get("total_patterns", 0),
            delta=f"+{stats.get('patterns_with_embeddings', 0)} con embeddings"
        )
    
    with col3:
        st.metric(
            label="✅ Confirmaciones (30d)",
            value=stats.get("confirmations_30d", 0),
        )
    
    with col4:
        st.metric(
            label="🔧 Correcciones (30d)",
            value=stats.get("corrections_30d", 0),
        )


def render_user_patterns(db, profile_id: str) -> None:
    """Muestra los patrones aprendidos del usuario."""
    st.subheader("📚 Patrones que he aprendido de ti")
    
    # Obtener patrones
    patterns = (
        db.query(TransactionPattern)
        .filter(
            TransactionPattern.profile_id == profile_id,
            TransactionPattern.deleted_at.is_(None),
        )
        .order_by(TransactionPattern.times_matched.desc())
        .limit(50)
        .all()
    )
    
    if not patterns:
        st.info("Aún no he aprendido patrones de tus transacciones. ¡Categoriza algunas transacciones para comenzar!")
        return
    
    # Convertir a DataFrame
    data = []
    for p in patterns:
        subcat = db.get(Subcategory, p.subcategory_id)
        data.append({
            "Patrón": p.user_label or p.pattern_text[:30],
            "Tipo": p.pattern_type.value if p.pattern_type else "N/A",
            "Categoría": subcat.nombre if subcat else "N/A",
            "Veces Usado": p.times_matched,
            "Confianza": f"{float(p.confidence) * 100:.0f}%",
            "Recurrente": "✅" if p.is_recurring else "",
            "Monto Promedio": f"₡{float(p.avg_amount or 0):,.0f}",
            "Última Vez": p.last_seen_at.strftime("%Y-%m-%d") if p.last_seen_at else "N/A",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Gráfico de patrones por tipo
    st.subheader("📊 Distribución de Patrones")
    
    type_counts = {}
    for p in patterns:
        t = p.pattern_type.value if p.pattern_type else "otro"
        type_counts[t] = type_counts.get(t, 0) + 1
    
    fig = px.pie(
        values=list(type_counts.values()),
        names=list(type_counts.keys()),
        title="Patrones por Tipo",
        color_discrete_sequence=px.colors.qualitative.Set3,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_statistics(db, profile_id: str, stats: dict) -> None:
    """Muestra estadísticas detalladas."""
    st.subheader("📈 Estadísticas de Aprendizaje")
    
    # Gráfico de progreso de precisión
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎯 Evolución de Precisión")
        
        # Obtener eventos de los últimos 30 días agrupados por día
        since = datetime.now(UTC) - timedelta(days=30)
        
        daily_events = (
            db.query(
                func.date(LearningEvent.created_at).label("day"),
                LearningEvent.event_type,
                func.count(LearningEvent.id).label("count"),
            )
            .filter(
                LearningEvent.profile_id == profile_id,
                LearningEvent.created_at >= since,
            )
            .group_by(func.date(LearningEvent.created_at), LearningEvent.event_type)
            .all()
        )
        
        if daily_events:
            # Procesar para gráfico
            days_data: dict = {}
            for day, event_type, count in daily_events:
                if day not in days_data:
                    days_data[day] = {"confirmations": 0, "corrections": 0}
                if event_type == LearningEventType.CONFIRMATION:
                    days_data[day]["confirmations"] = count
                elif event_type == LearningEventType.CORRECTION:
                    days_data[day]["corrections"] = count
            
            df_events = pd.DataFrame([
                {
                    "Día": day,
                    "Confirmaciones": data["confirmations"],
                    "Correcciones": data["corrections"],
                }
                for day, data in sorted(days_data.items())
            ])
            
            fig = px.line(
                df_events,
                x="Día",
                y=["Confirmaciones", "Correcciones"],
                title="Actividad Diaria",
                color_discrete_sequence=["#00CC00", "#FF6666"],
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay suficientes datos para mostrar evolución")
    
    with col2:
        st.markdown("### 📊 Distribución de Confianza")
        
        # Obtener distribución de confianza de patrones
        patterns = (
            db.query(TransactionPattern.confidence)
            .filter(
                TransactionPattern.profile_id == profile_id,
                TransactionPattern.deleted_at.is_(None),
            )
            .all()
        )
        
        if patterns:
            confidence_values = [float(p.confidence) for p in patterns]
            
            fig = go.Figure()
            fig.add_trace(go.Histogram(
                x=confidence_values,
                nbinsx=10,
                name="Patrones",
                marker_color="#3366FF",
            ))
            fig.update_layout(
                title="Distribución de Confianza",
                xaxis_title="Confianza",
                yaxis_title="Cantidad de Patrones",
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay patrones para analizar")
    
    # Resumen de patrones recurrentes
    st.markdown("### 🔄 Patrones Recurrentes Detectados")
    
    recurring = (
        db.query(TransactionPattern)
        .filter(
            TransactionPattern.profile_id == profile_id,
            TransactionPattern.is_recurring == True,  # noqa: E712
            TransactionPattern.deleted_at.is_(None),
        )
        .order_by(TransactionPattern.times_matched.desc())
        .limit(10)
        .all()
    )
    
    if recurring:
        for p in recurring:
            subcat = db.get(Subcategory, p.subcategory_id)
            freq = p.recurring_frequency or "mensual"
            day = p.recurring_day or "?"
            
            st.markdown(
                f"- **{p.user_label or p.pattern_text[:30]}** → "
                f"{subcat.nombre if subcat else 'N/A'} "
                f"(cada {freq}, día ~{day})"
            )
    else:
        st.info("Aún no he detectado patrones recurrentes")


def render_global_patterns(db) -> None:
    """Muestra patrones globales de Costa Rica."""
    st.subheader("🌍 Patrones Globales de Costa Rica")
    st.markdown("""
    Estos patrones son aprendidos de **todos los usuarios** de Finanzas Tracker en Costa Rica.
    Cuando varios usuarios categorizan igual algo, se vuelve un patrón global.
    """)
    
    # Obtener patrones globales aprobados
    global_patterns = (
        db.query(GlobalPattern)
        .filter(GlobalPattern.is_approved == True)  # noqa: E712
        .order_by(GlobalPattern.user_count.desc())
        .limit(20)
        .all()
    )
    
    if not global_patterns:
        st.info("Aún no hay suficientes datos para patrones globales. ¡Ayuda categorizando tus transacciones!")
        return
    
    # Tabla de patrones globales
    data = []
    for gp in global_patterns:
        subcat = db.get(Subcategory, gp.primary_subcategory_id)
        data.append({
            "Patrón": gp.pattern_text[:40],
            "Categoría": subcat.nombre if subcat else "N/A",
            "Usuarios": gp.user_count,
            "Confianza": f"{float(gp.confidence) * 100:.0f}%",
            "Auto-aprobado": "✅" if gp.is_auto_approved else "👤",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Estadísticas globales
    st.markdown("### 📊 Estadísticas Globales")
    
    col1, col2, col3 = st.columns(3)
    
    total_global = db.query(func.count(GlobalPattern.id)).scalar()
    approved_global = db.query(func.count(GlobalPattern.id)).filter(
        GlobalPattern.is_approved == True  # noqa: E712
    ).scalar()
    auto_approved = db.query(func.count(GlobalPattern.id)).filter(
        GlobalPattern.is_auto_approved == True  # noqa: E712
    ).scalar()
    
    with col1:
        st.metric("Total Patrones", total_global or 0)
    with col2:
        st.metric("Aprobados", approved_global or 0)
    with col3:
        st.metric("Auto-aprobados", auto_approved or 0)


def render_learning_history(db, profile_id: str) -> None:
    """Muestra historial de eventos de aprendizaje."""
    st.subheader("📋 Historial de Aprendizaje")
    
    # Obtener últimos eventos
    events = (
        db.query(LearningEvent)
        .filter(LearningEvent.profile_id == profile_id)
        .order_by(LearningEvent.created_at.desc())
        .limit(50)
        .all()
    )
    
    if not events:
        st.info("No hay eventos de aprendizaje registrados")
        return
    
    # Tabla de eventos
    data = []
    for e in events:
        event_icons = {
            LearningEventType.CATEGORIZATION: "📝",
            LearningEventType.CONFIRMATION: "✅",
            LearningEventType.CORRECTION: "🔧",
            LearningEventType.REJECTION: "❌",
            LearningEventType.ALIAS_CREATED: "🏷️",
            LearningEventType.PATTERN_MERGED: "🔄",
        }
        
        icon = event_icons.get(e.event_type, "📌")
        
        # Obtener nombre de subcategoría
        new_cat = ""
        if e.new_subcategory_id:
            subcat = db.get(Subcategory, e.new_subcategory_id)
            new_cat = subcat.nombre if subcat else ""
        
        data.append({
            "Fecha": e.created_at.strftime("%Y-%m-%d %H:%M"),
            "Tipo": f"{icon} {e.event_type.value}",
            "Texto": (e.input_text or "")[:30],
            "Categoría": new_cat,
            "Alias": e.user_label or "",
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Botón para exportar
    st.download_button(
        label="📥 Exportar Historial (CSV)",
        data=df.to_csv(index=False),
        file_name=f"learning_history_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
