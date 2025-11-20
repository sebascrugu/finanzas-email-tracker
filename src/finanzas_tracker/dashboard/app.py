"""
App principal de Streamlit - Dashboard de Finanzas Simplificado.

Esta es la página principal que se muestra al usuario.
"""

import calendar
from datetime import date

import streamlit as st


# Configurar página
st.set_page_config(
    page_title="Dashboard - Finanzas Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "Finanzas Email Tracker - Sistema automatizado de rastreo financiero",
    },
)

# CSS personalizado para mejorar el diseño
st.markdown(
    """
    <style>
    /* Mejoras generales */
    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    /* Cards con sombra y bordes redondeados */
    div[data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
    }

    div[data-testid="stMetricDelta"] {
        font-size: 0.9rem;
    }

    /* Mejorar botones */
    .stButton>button {
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s ease;
    }

    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    /* Barras de progreso más bonitas */
    .stProgress > div > div > div > div {
        background-image: linear-gradient(to right, #00c853, #64dd17);
    }

    /* Sidebar más bonito */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
    }

    /* Métricas con mejor espaciado */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
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
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.utils.seed_categories import seed_categories


logger = get_logger(__name__)

# Inicializar BD
init_db()

# Seed categorías si no existen
seed_categories()


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


def mostrar_selector_perfiles(perfil_actual: Profile):
    """Muestra selector de perfiles en el sidebar."""
    with get_session() as session:
        perfiles = (
            session.query(Profile)
            .options(
                joinedload(Profile.budgets),
                joinedload(Profile.cards),
            )
            .filter(
                Profile.activo == True,  # noqa: E712
            )
            .all()
        )

        # Forzar carga de relaciones
        for p in perfiles:
            _ = p.budgets
            _ = p.cards
            _ = p.bancos_asociados

        st.sidebar.markdown(f"## {perfil_actual.nombre_completo}")

        # Mostrar info del perfil
        presupuesto = next((b for b in perfil_actual.budgets if b.fecha_fin is None), None)
        if presupuesto:
            st.sidebar.metric(" Presupuesto", f"₡{presupuesto.salario_mensual:,.0f}/mes")

        tarjetas_activas = [c for c in perfil_actual.cards if c.activa]
        st.sidebar.metric(" Tarjetas", len(tarjetas_activas))

        bancos = perfil_actual.bancos_asociados
        if bancos:
            st.sidebar.markdown(f"** Bancos:** {', '.join([b.upper() for b in bancos])}")

        # Selector solo si hay múltiples perfiles
        if len(perfiles) > 1:
            st.sidebar.markdown("---")
            st.sidebar.markdown("###  Cambiar Perfil")

            perfil_nombres = [p.nombre_completo for p in perfiles]
            perfil_ids = [p.id for p in perfiles]

            idx_actual = 0
            try:
                idx_actual = perfil_ids.index(perfil_actual.id)
            except ValueError:
                pass

            seleccion = st.sidebar.selectbox(
                "Seleccionar:",
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

    # Perfil activo: mostrar selector si hay múltiples
    mostrar_selector_perfiles(perfil_activo)

    # Header del dashboard con diseño mejorado
    hoy = date.today()
    mes_nombre = calendar.month_name[hoy.month]

    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(
            f"""
            <div style='margin-bottom: 1rem;'>
                <h1 style='margin: 0; color: #1f1f1f; font-size: 2.5rem;'>
                    💰 Dashboard Financiero
                </h1>
                <p style='margin: 0.5rem 0 0 0; color: #666; font-size: 1.1rem;'>
                    Bienvenido, <strong>{perfil_activo.nombre_completo}</strong> 👋
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col2:
        st.metric(
            label="📅 Período Actual",
            value=f"{mes_nombre} {hoy.year}",
            delta=f"Día {hoy.day}",
        )

    st.markdown("---")

    # Obtener datos del mes actual del perfil activo
    with get_session() as session:
        primer_dia = date(hoy.year, hoy.month, 1)
        if hoy.month == 12:
            proximo_mes = date(hoy.year + 1, 1, 1)
        else:
            proximo_mes = date(hoy.year, hoy.month + 1, 1)

        # Ingresos del perfil
        ingresos = (
            session.query(Income)
            .filter(
                Income.profile_id == perfil_activo.id,
                Income.fecha >= primer_dia,
                Income.fecha < proximo_mes,
                Income.deleted_at.is_(None),
            )
            .all()
        )
        total_ingresos = sum(i.monto_crc for i in ingresos)

        # Gastos del perfil (que cuentan en presupuesto)
        gastos = (
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
        total_gastos = sum(g.monto_crc for g in gastos)

        # Transacciones sin revisar del perfil
        sin_revisar = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == perfil_activo.id,
                Transaction.necesita_revision == True,  # noqa: E712
                Transaction.deleted_at.is_(None),
            )
            .count()
        )

        balance = total_ingresos - total_gastos

        # Calcular porcentaje gastado
        porcentaje_gastado = (total_gastos / total_ingresos * 100) if total_ingresos > 0 else 0

    # Métricas principales con diseño mejorado
    st.markdown("### 📊 Resumen Financiero del Mes")
    st.markdown("")  # Espacio

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="💵 Ingresos Totales",
            value=f"₡{total_ingresos:,.0f}",
            delta=f"+{len(ingresos)} registro(s)" if len(ingresos) > 0 else "Sin ingresos",
            delta_color="normal",
        )

    with col2:
        delta_gastos = f"-{len(gastos)} transacción(es)" if len(gastos) > 0 else "Sin gastos"
        st.metric(
            label="🛒 Gastos del Mes",
            value=f"₡{total_gastos:,.0f}",
            delta=delta_gastos,
            delta_color="inverse" if len(gastos) > 0 else "off",
        )

    with col3:
        delta_color = "normal" if balance >= 0 else "inverse"
        delta_text = f"+₡{balance:,.0f}" if balance >= 0 else f"₡{balance:,.0f}"
        st.metric(
            label="💰 Balance Neto",
            value=f"₡{balance:,.0f}",
            delta=delta_text,
            delta_color=delta_color,
        )

    with col4:
        if sin_revisar > 0:
            st.metric(
                label="⚠️ Pendientes de Revisar",
                value=sin_revisar,
                delta="Requieren atención",
                delta_color="inverse",
            )
        else:
            st.metric(
                label="✅ Transacciones",
                value="Todo OK",
                delta="Nada que revisar",
                delta_color="normal",
            )

    st.markdown("---")

    # Progreso de gastos con diseño mejorado
    if total_ingresos > 0:
        porcentaje_gastado = (total_gastos / total_ingresos) * 100

        st.markdown("### 📊 Progreso de Gastos del Mes")
        st.markdown("")  # Espacio

        # Barra de progreso con color dinámico
        progress_value = min(porcentaje_gastado / 100, 1.0)
        st.progress(progress_value)

        # Espacio
        st.markdown("")

        # Análisis de gastos con mejor diseño
        col1, col2, col3 = st.columns([2, 1, 1])

        with col1:
            # Mensaje contextual según el nivel de gasto
            if porcentaje_gastado > 100:
                st.error(
                    f"### 🚨 ¡Atención!\n"
                    f"Gastaste **{porcentaje_gastado:.1f}%** de tus ingresos. "
                    f"Estás excediendo tu presupuesto por **₡{abs(balance):,.0f}**"
                )
            elif porcentaje_gastado > 90:
                st.warning(
                    f"### ⚠️ Cuidado\n"
                    f"Has gastado **{porcentaje_gastado:.1f}%** de tus ingresos. "
                    f"Te quedan solo **₡{balance:,.0f}** para el resto del mes."
                )
            elif porcentaje_gastado > 75:
                st.info(
                    f"### 📌 Buen ritmo\n"
                    f"Llevas gastado **{porcentaje_gastado:.1f}%** de tus ingresos. "
                    f"Controla tus gastos para mantener el balance positivo."
                )
            else:
                st.success(
                    f"### ✅ ¡Excelente!\n"
                    f"Solo has gastado **{porcentaje_gastado:.1f}%** de tus ingresos. "
                    f"Tienes un excelente control financiero."
                )

        with col2:
            st.metric(
                label="📈 Porcentaje Gastado",
                value=f"{porcentaje_gastado:.1f}%",
                delta=f"{100 - porcentaje_gastado:.1f}% disponible",
                delta_color="normal" if porcentaje_gastado <= 90 else "inverse",
            )

        with col3:
            st.metric(
                label="💵 Balance Restante",
                value=f"₡{balance:,.0f}",
                delta="Positivo" if balance >= 0 else "Negativo",
                delta_color="normal" if balance >= 0 else "inverse",
            )
    else:
        st.info(
            "💡 **Tip:** Agrega tus ingresos mensuales para ver el progreso de gastos y obtener "
            "análisis detallados de tu situación financiera. Ve a la página **📥 Ingresos** para comenzar."
        )

    st.markdown("---")

    # Acciones rápidas con mejor diseño
    st.markdown("### ⚡ Acciones Rápidas")
    st.markdown(
        "<p style='color: #666; margin-bottom: 1rem;'>"
        "Accesos directos a las funciones más utilizadas"
        "</p>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("💰 Agregar Ingreso", use_container_width=True, help="Registra un nuevo ingreso"):
            st.switch_page("pages/2__Ingresos.py")

    with col2:
        if st.button(
            "📊 Balance Detallado",
            use_container_width=True,
            help="Ver análisis completo de ingresos y gastos",
        ):
            st.switch_page("pages/3__Balance.py")

    with col3:
        if sin_revisar > 0:
            if st.button(
                f"⚠️ Revisar {sin_revisar} Transacciones",
                use_container_width=True,
                type="primary",
                help=f"Hay {sin_revisar} transacciones pendientes de revisión",
            ):
                st.switch_page("pages/4__Transacciones.py")
        else:
            if st.button(
                "✅ Ver Transacciones",
                use_container_width=True,
                help="Ver todas tus transacciones",
            ):
                st.switch_page("pages/4__Transacciones.py")

    with col4:
        if st.button(
            "📧 Procesar Correos",
            use_container_width=True,
            help="Importar nuevas transacciones desde tus correos bancarios",
        ):
            st.switch_page("pages/4__Transacciones.py")


if __name__ == "__main__":
    main()
