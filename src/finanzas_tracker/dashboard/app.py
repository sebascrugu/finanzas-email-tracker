"""
App principal de Streamlit - Dashboard de Finanzas Simplificado.

Esta es la página principal que se muestra al usuario.
"""

import calendar
from datetime import date, timedelta
from collections import defaultdict

import streamlit as st
import pandas as pd


# Configurar página
st.set_page_config(
    page_title="Dashboard - Finanzas Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "Finanzas Email Tracker - Sistema automatizado de rastreo financiero",
    },
)

# CSS personalizado - Solo estilos específicos del diseño
# El tema base se configura en .streamlit/config.toml
st.markdown(
    """
    <style>
    /* Layout y espaciado */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }

    /* Hero metric - Card destacada con gradiente */
    .hero-metric {
        text-align: center;
        padding: 2.5rem 1rem;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 16px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 20px rgba(102, 126, 234, 0.25);
    }

    .hero-metric h1 {
        color: white;
        font-size: 3.5rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -1px;
    }

    .hero-metric p {
        color: rgba(255, 255, 255, 0.95);
        font-size: 1.1rem;
        margin: 0.5rem 0 0 0;
        font-weight: 400;
    }

    /* Metric cards - Diseño mejorado */
    div[data-testid="metric-container"] {
        border-radius: 12px;
        padding: 1.25rem 1rem;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
        transition: all 0.2s ease;
    }

    div[data-testid="metric-container"]:hover {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        transform: translateY(-2px);
    }

    div[data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.75rem;
        font-weight: 700;
    }

    /* Botones con mejor interacción */
    .stButton>button {
        border-radius: 10px;
        font-weight: 600;
        padding: 0.6rem 1.2rem;
        transition: all 0.2s ease;
        font-size: 0.9rem;
    }

    .stButton>button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.12);
    }

    /* Barras de progreso con gradiente */
    .stProgress > div > div > div > div {
        background: linear-gradient(90deg, #10b981 0%, #059669 100%);
        border-radius: 10px;
    }

    /* Headers con mejor jerarquía */
    .main h3 {
        font-size: 1.25rem;
        margin-top: 2rem;
        margin-bottom: 1rem;
        font-weight: 700;
    }

    /* Dividers sutiles */
    .main hr {
        margin: 2rem 0;
        border: none;
        border-top: 1px solid rgba(0, 0, 0, 0.1);
    }

    /* Charts con bordes redondeados */
    .element-container iframe {
        border-radius: 12px;
    }

    /* Alerts con bordes redondeados */
    .stAlert {
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Importar después de set_page_config
from pathlib import Path
import sys


# Agregar src al path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from sqlalchemy.orm import joinedload

from finanzas_tracker.core.database import get_session, init_db
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.account import Account
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.utils.seed_categories import seed_categories
from finanzas_tracker.utils.seed_merchants import seed_merchants


logger = get_logger(__name__)

# Inicializar BD
init_db()

# Seed categorías si no existen
seed_categories()

# Seed merchants si no existen
seed_merchants()


def get_active_profile() -> Profile | None:
    """Obtiene el perfil activo con todas sus relaciones cargadas."""
    with get_session() as session:
        perfil = (
            session.query(Profile)
            .options(
                joinedload(Profile.budgets),
                joinedload(Profile.cards),
            )
            .filter(
                Profile.es_activo == True,  # noqa: E712
                Profile.activo == True,  # noqa: E712
            )
            .first()
        )

        if perfil:
            # Forzar la carga de relaciones antes de cerrar la sesión
            _ = perfil.budgets
            _ = perfil.cards
            _ = perfil.bancos_asociados

        return perfil


def mostrar_sidebar_simple(perfil_actual: Profile):
    """Muestra sidebar minimalista - solo selector si hay múltiples perfiles."""
    with get_session() as session:
        perfiles = (
            session.query(Profile)
            .filter(Profile.activo == True)  # noqa: E712
            .all()
        )

        # Selector solo si hay múltiples perfiles
        if len(perfiles) > 1:
            st.sidebar.markdown("**Cambiar Perfil**")

            perfil_nombres = [f"{p.icono} {p.nombre}" for p in perfiles]
            perfil_ids = [p.id for p in perfiles]

            idx_actual = 0
            try:
                idx_actual = perfil_ids.index(perfil_actual.id)
            except ValueError:
                pass

            seleccion = st.sidebar.selectbox(
                "Perfil:",
                options=range(len(perfiles)),
                format_func=lambda i: perfil_nombres[i],
                index=idx_actual,
                key="selector_perfil",
                label_visibility="collapsed",
            )

            # Si cambió el perfil, actualizar
            if perfil_ids[seleccion] != perfil_actual.id:
                nuevo_perfil = session.query(Profile).get(perfil_ids[seleccion])
                if nuevo_perfil:
                    # Desactivar todos los perfiles
                    for p in perfiles:
                        p.es_activo = False
                    # Activar el nuevo
                    nuevo_perfil.es_activo = True
                    session.commit()
                    st.rerun()


def main():
    """Función principal del dashboard."""

    # Verificar perfil activo
    perfil_activo = get_active_profile()

    if not perfil_activo:
        # Página principal sin perfil - DISEÑO MEJORADO
        st.markdown(
            """
            <div style='text-align: center; padding: 3rem 0 2rem 0;'>
                <h1 style='font-size: 3.5rem; margin-bottom: 0.5rem; color: #1f1f1f;'>💰</h1>
                <h1 style='font-size: 2.5rem; margin-bottom: 0.5rem; color: #1f1f1f;'>
                    ¡Bienvenido a Finanzas Tracker!
                </h1>
                <p style='font-size: 1.2rem; color: #666; margin-top: 1rem;'>
                    Tu asistente inteligente para el control financiero personal
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown(
                """
                ### 🎯 ¿Qué hace esto?

                Rastrea **automáticamente** tus finanzas desde tus correos bancarios:

                - 📧 Lee correos de Outlook
                - 🤖 Categoriza con IA (Claude Haiku 4.5)
                - 👥 Múltiples perfiles (Personal, Negocio, etc.)
                - 💰 Presupuesto 50/30/20 automático
                - 💱 Convierte USD→CRC con tipos históricos
                - 📊 Dashboard interactivo con métricas en tiempo real
                """
            )

        with col2:
            st.markdown(
                """
                ### 🚀 Empecemos en 3 pasos:

                **1️⃣ Crea tu perfil**
                - Nombre, email y salario mensual

                **2️⃣ Agrega tus tarjetas**
                - BAC, Popular, u otros bancos

                **3️⃣ Procesa correos**
                - Importa y categoriza transacciones automáticamente

                ⏱️ **Tiempo estimado:** 2 minutos
                """
            )

        st.markdown("---")

        # Botón grande y centrado con mejor diseño
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button(
                "🚀 Crear Mi Primer Perfil",
                type="primary",
                use_container_width=True,
            ):
                st.switch_page("pages/1__Setup.py")
            st.markdown(
                "<p style='text-align: center; color: #888; margin-top: 1rem; font-size: 0.9rem;'>"
                "Es rápido, fácil y completamente gratis"
                "</p>",
                unsafe_allow_html=True,
            )

        return

    # Obtener fecha actual
    hoy = date.today()
    mes_nombre = calendar.month_name[hoy.month]

    # Recolectar datos del mes para sidebar y dashboard
    with get_session() as session:
        primer_dia = date(hoy.year, hoy.month, 1)
        if hoy.month == 12:
            proximo_mes = date(hoy.year + 1, 1, 1)
        else:
            proximo_mes = date(hoy.year, hoy.month + 1, 1)

        # PATRIMONIO TOTAL - Cuentas + Movimientos
        # 1. Saldo en cuentas (ahorros, CDPs, inversiones, efectivo)
        patrimonio_cuentas = Account.calcular_patrimonio_total(session, perfil_activo.id)

        # 2. Movimientos históricos (ingresos - gastos desde que usas la app)
        # IMPORTANTE: Usar calcular_monto_patrimonio() para considerar desgloses y exclusiones
        total_ingresos_historicos = (
            session.query(Income)
            .filter(
                Income.profile_id == perfil_activo.id,
                Income.deleted_at.is_(None),
            )
            .all()
        )
        patrimonio_ingresos = sum(i.calcular_monto_patrimonio() for i in total_ingresos_historicos)

        total_gastos_historicos = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == perfil_activo.id,
                Transaction.deleted_at.is_(None),
            )
            .all()
        )
        patrimonio_gastos = sum(g.calcular_monto_patrimonio() for g in total_gastos_historicos)
        movimientos_netos = patrimonio_ingresos - patrimonio_gastos

        # PATRIMONIO REAL = Cuentas + Movimientos
        patrimonio_total = patrimonio_cuentas + movimientos_netos

        # Intereses proyectados
        intereses_mensuales = Account.calcular_intereses_mensuales_totales(
            session, perfil_activo.id
        )

        # DATOS DEL MES ACTUAL
        ingresos_mes = (
            session.query(Income)
            .filter(
                Income.profile_id == perfil_activo.id,
                Income.fecha >= primer_dia,
                Income.fecha < proximo_mes,
                Income.deleted_at.is_(None),
            )
            .all()
        )
        total_ingresos_mes = sum(i.monto_crc for i in ingresos_mes)

        gastos_mes = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == perfil_activo.id,
                Transaction.fecha_transaccion >= primer_dia,
                Transaction.fecha_transaccion < proximo_mes,
                Transaction.deleted_at.is_(None),
                Transaction.excluir_de_presupuesto == False,  # noqa: E712
            )
            .all()
        )
        total_gastos_mes = sum(g.monto_crc for g in gastos_mes)
        balance_mes = total_ingresos_mes - total_gastos_mes

        # Transacciones sin revisar
        sin_revisar = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == perfil_activo.id,
                Transaction.necesita_revision == True,  # noqa: E712
                Transaction.deleted_at.is_(None),
            )
            .count()
        )

        # Gastos por día del mes (para gráfico)
        gastos_por_dia = defaultdict(float)
        for gasto in gastos_mes:
            dia = gasto.fecha_transaccion.day
            gastos_por_dia[dia] += gasto.monto_crc

        # Gastos por categoría (top 5)
        gastos_por_categoria = defaultdict(float)
        for gasto in gastos_mes:
            if gasto.categoria:
                gastos_por_categoria[gasto.categoria.nombre] += gasto.monto_crc

    # Mostrar sidebar simple (solo perfil)
    mostrar_sidebar_simple(perfil_activo)

    # Header minimalista
    st.markdown(
        f"""
        <div style='margin-bottom: 1.5rem;'>
            <p style='margin: 0; color: #6b7280; font-size: 0.95rem; font-weight: 500;'>
                {mes_nombre} {hoy.year} • Día {hoy.day}
            </p>
            <h1 style='margin: 0.25rem 0 0 0; color: #111827; font-size: 2rem; font-weight: 700;'>
                Hola, {perfil_activo.nombre} 👋
            </h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # HERO METRIC - Patrimonio Total (estilo Revolut/N26)
    cambio_mes = balance_mes
    cambio_text = f"+₡{cambio_mes:,.0f}" if cambio_mes >= 0 else f"₡{cambio_mes:,.0f}"

    st.markdown(
        f"""
        <div class="hero-metric">
            <p style='margin: 0 0 0.5rem 0; font-size: 0.9rem; text-transform: uppercase;
                      letter-spacing: 1px; opacity: 0.9;'>
                Patrimonio Total
            </p>
            <h1>₡{patrimonio_total:,.0f}</h1>
            <p>{cambio_text} este mes</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # PROYECCIONES DE INTERESES (si hay cuentas con interés)
    if intereses_mensuales > 0:
        st.markdown("### 💰 Proyección de Ganancias por Intereses")
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                label="Este Mes",
                value=f"₡{intereses_mensuales:,.0f}",
                delta="Intereses ganados",
                delta_color="normal",
            )

        with col2:
            intereses_3meses = intereses_mensuales * 3
            st.metric(
                label="3 Meses",
                value=f"₡{intereses_3meses:,.0f}",
                delta=f"₡{intereses_mensuales:,.0f}/mes",
            )

        with col3:
            intereses_6meses = intereses_mensuales * 6
            st.metric(
                label="6 Meses",
                value=f"₡{intereses_6meses:,.0f}",
                delta=f"₡{intereses_mensuales:,.0f}/mes",
            )

        with col4:
            intereses_anuales = intereses_mensuales * 12
            st.metric(
                label="1 Año",
                value=f"₡{intereses_anuales:,.0f}",
                delta=f"₡{intereses_mensuales:,.0f}/mes",
            )

        st.markdown("---")

    # MÉTRICAS DEL MES - Grid de 4 columnas
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="💵 Ingresos",
            value=f"₡{total_ingresos_mes:,.0f}",
            delta=f"{len(ingresos_mes)} ingresos" if len(ingresos_mes) > 0 else "Sin ingresos",
        )

    with col2:
        st.metric(
            label="💸 Gastos",
            value=f"₡{total_gastos_mes:,.0f}",
            delta=f"{len(gastos_mes)} transacciones" if len(gastos_mes) > 0 else "Sin gastos",
            delta_color="inverse" if total_gastos_mes > 0 else "off",
        )

    with col3:
        porcentaje_ahorro = (
            (balance_mes / total_ingresos_mes * 100) if total_ingresos_mes > 0 else 0
        )
        st.metric(
            label="📈 Tasa Ahorro",
            value=f"{porcentaje_ahorro:.1f}%",
            delta="Positivo" if balance_mes >= 0 else "Negativo",
            delta_color="normal" if balance_mes >= 0 else "inverse",
        )

    with col4:
        if sin_revisar > 0:
            st.metric(
                label="⚠️ Sin Revisar",
                value=sin_revisar,
                delta="Requieren revisión",
                delta_color="inverse",
            )
        else:
            st.metric(
                label="✅ Transacciones",
                value="Al día",
                delta="Todo revisado",
                delta_color="normal",
            )

    # Barra de progreso de gastos (visual importante)
    if total_ingresos_mes > 0:
        porcentaje_gastado = (total_gastos_mes / total_ingresos_mes) * 100

        st.markdown("---")
        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"**Progreso de Gastos: {porcentaje_gastado:.1f}%**")
            st.progress(min(porcentaje_gastado / 100, 1.0))

            # Mensaje contextual
            if porcentaje_gastado > 100:
                st.caption(f"🚨 Excediste el presupuesto por ₡{abs(balance_mes):,.0f}")
            elif porcentaje_gastado > 90:
                st.caption(f"⚠️ Cerca del límite - Te quedan ₡{balance_mes:,.0f}")
            elif porcentaje_gastado > 75:
                st.caption(f"📊 Buen ritmo - Disponible: ₡{balance_mes:,.0f}")
            else:
                st.caption(f"✅ Excelente control - Ahorro: ₡{balance_mes:,.0f}")

        with col2:
            st.metric(
                "Balance Mes",
                f"₡{balance_mes:,.0f}",
                delta=f"{100 - porcentaje_gastado:.0f}% disponible" if balance_mes >= 0 else "Déficit",
                delta_color="normal" if balance_mes >= 0 else "inverse",
            )

    # GRÁFICOS Y ANÁLISIS
    if total_gastos_mes > 0:
        st.markdown("---")
        st.markdown("### 📈 Análisis de Gastos")

        # Tres columnas para los gráficos
        col1, col2, col3 = st.columns(3)

        with col1:
            # Gráfico de gastos diarios
            st.markdown("**💸 Gastos Diarios**")
            dias_del_mes = list(range(1, hoy.day + 1))
            montos_por_dia = [gastos_por_dia.get(dia, 0) for dia in dias_del_mes]

            df_dias = pd.DataFrame({"Día": dias_del_mes, "Monto": montos_por_dia})
            st.line_chart(df_dias.set_index("Día"), height=200)

        with col2:
            # Gráfico de gastos acumulados
            st.markdown("**📊 Acumulado del Mes**")
            gastos_acumulados = []
            acumulado = 0
            for dia in dias_del_mes:
                acumulado += gastos_por_dia.get(dia, 0)
                gastos_acumulados.append(acumulado)

            df_acumulado = pd.DataFrame(
                {"Día": dias_del_mes, "Acumulado": gastos_acumulados}
            )
            st.area_chart(df_acumulado.set_index("Día"), height=200)

        with col3:
            # Gráfico de top categorías
            st.markdown("**🏷️ Top Categorías**")
            if gastos_por_categoria:
                top_categorias = sorted(
                    gastos_por_categoria.items(), key=lambda x: x[1], reverse=True
                )[:5]

                df_cats = pd.DataFrame(
                    {
                        "Categoría": [cat[0] for cat in top_categorias],
                        "Monto": [cat[1] for cat in top_categorias],
                    }
                )
                st.bar_chart(df_cats.set_index("Categoría"), height=200)
            else:
                st.info("Sin categorías")

        # Alerta contextual si hay pendientes
        if sin_revisar > 0:
            st.markdown("---")
            st.warning(
                f"⚠️ **Tienes {sin_revisar} transacciones sin revisar.** "
                f"Revísalas para mantener tu presupuesto actualizado."
            )
    else:
        st.info(
            "💡 **Comienza agregando transacciones** para ver análisis detallados "
            "de tus gastos y patrones de consumo."
        )


if __name__ == "__main__":
    main()
