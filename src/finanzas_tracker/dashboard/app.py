"""
App principal de Streamlit - Dashboard de Finanzas Simplificado.

Esta es la página principal que se muestra al usuario.
"""

import streamlit as st
from datetime import date

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

# Importar después de set_page_config
import sys
from pathlib import Path

# Agregar src al path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session, init_db
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.models.income import Income
from finanzas_tracker.utils.seed_categories import seed_categories

logger = get_logger(__name__)

# Inicializar BD
init_db()

# Seed categorías si no existen
seed_categories()


def get_active_profile() -> Profile | None:
    """Obtiene el perfil activo."""
    with get_session() as session:
        return (
            session.query(Profile)
            .filter(
                Profile.es_activo == True,  # noqa: E712
                Profile.activo == True,  # noqa: E712
            )
            .first()
        )


def mostrar_selector_perfiles(perfil_actual: Profile):
    """Muestra selector de perfiles en el sidebar."""
    with get_session() as session:
        perfiles = (
            session.query(Profile)
            .filter(
                Profile.activo == True,  # noqa: E712
            )
            .all()
        )

        st.sidebar.markdown(f"## {perfil_actual.nombre_completo}")

        # Mostrar info del perfil
        presupuesto = next((b for b in perfil_actual.budgets if b.fecha_fin is None), None)
        if presupuesto:
            st.sidebar.metric("💰 Presupuesto", f"₡{presupuesto.salario_mensual:,.0f}/mes")

        tarjetas_activas = [c for c in perfil_actual.cards if c.activa]
        st.sidebar.metric("💳 Tarjetas", len(tarjetas_activas))

        bancos = perfil_actual.bancos_asociados
        if bancos:
            st.sidebar.markdown(f"**🏦 Bancos:** {', '.join([b.upper() for b in bancos])}")

        # Selector solo si hay múltiples perfiles
        if len(perfiles) > 1:
            st.sidebar.markdown("---")
            st.sidebar.markdown("### 🔄 Cambiar Perfil")

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
        # Página principal sin perfil - DISEÑO LIMPIO
        st.markdown(
            """
            <div style='text-align: center; padding: 2rem 0;'>
                <h1 style='font-size: 3rem; margin-bottom: 1rem;'>👋</h1>
                <h1>¡Bienvenido a Finanzas Tracker!</h1>
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
                - 💰 Múltiples perfiles (Personal, Negocio, etc.)
                - 📊 Presupuesto 50/30/20 automático
                - 💱 Convierte USD→CRC con tipos históricos
                """
            )

        with col2:
            st.markdown(
                """
                ### 🚀 Empecemos en 3 pasos:
                
                1️⃣ **Crea tu perfil** (nombre, email, salario)
                
                2️⃣ **Agrega tus tarjetas** (BAC, Popular, etc.)
                
                3️⃣ **Procesa correos** y categoriza transacciones
                
                ⏱️ **Tiempo estimado:** 2 minutos
                """
            )

        st.markdown("---")

        # Botón grande y centrado
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button(
                "🎉 Crear Mi Primer Perfil",
                type="primary",
                use_container_width=True,
            ):
                st.switch_page("pages/1_⚙️_Setup.py")

        return

    # Perfil activo: mostrar selector si hay múltiples
    mostrar_selector_perfiles(perfil_activo)

    # Dashboard principal
    st.title(f"🏠 Dashboard - {perfil_activo.nombre_completo}")

    # Obtener datos del mes actual del perfil activo
    with get_session() as session:
        hoy = date.today()
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

    # Métricas principales
    st.subheader("📊 Resumen del Mes")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="💰 Ingresos",
            value=f"₡{total_ingresos:,.0f}",
            delta=f"{len(ingresos)} ingreso(s)",
        )

    with col2:
        st.metric(
            label="💸 Gastos del Mes",
            value=f"₡{total_gastos:,.0f}",
            delta=f"{len(gastos)} transacción(es)",
        )

    with col3:
        delta_color = "normal" if balance >= 0 else "inverse"
        st.metric(
            label="📊 Balance",
            value=f"₡{balance:,.0f}",
            delta="Positivo" if balance >= 0 else "Negativo",
            delta_color=delta_color,
        )

    with col4:
        st.metric(label="📝 Sin Revisar", value=sin_revisar, delta="transacciones")

    st.markdown("---")

    # Progreso de gastos
    if total_ingresos > 0:
        porcentaje_gastado = (total_gastos / total_ingresos) * 100

        st.subheader("📈 Progreso de Gastos del Mes")

        # Barra de progreso
        st.progress(min(porcentaje_gastado / 100, 1.0))

        # Mensaje según porcentaje
        col1, col2 = st.columns([2, 1])

        with col1:
            if porcentaje_gastado > 100:
                st.error(f"⚠️ ¡Gastaste **{porcentaje_gastado:.1f}%** de tus ingresos!")
                st.warning("Estás gastando más de lo que ingresas")
            elif porcentaje_gastado > 90:
                st.warning(f"⚠️ Gastaste **{porcentaje_gastado:.1f}%** de tus ingresos")
                st.info("Cuidado, ya casi llegas al límite")
            elif porcentaje_gastado > 75:
                st.info(f"💡 Gastaste **{porcentaje_gastado:.1f}%** de tus ingresos")
                st.success("Vas bien, pero controla tus gastos")
            else:
                st.success(f"✅ Gastaste **{porcentaje_gastado:.1f}%** de tus ingresos")
                st.success("¡Excelente control de gastos!")

        with col2:
            st.metric(
                label="% Gastado",
                value=f"{porcentaje_gastado:.1f}%",
                delta=f"₡{balance:,.0f} restante",
            )
    else:
        st.info(
            "💡 Agrega tus ingresos mensuales para ver el progreso de gastos (ve a la página **Ingresos**)"
        )

    st.markdown("---")

    # Acciones rápidas
    st.subheader("⚡ Acciones Rápidas")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        if st.button("➕ Agregar Ingreso", use_container_width=True):
            st.switch_page("pages/2_💰_Ingresos.py")

    with col2:
        if st.button("📊 Ver Balance Detallado", use_container_width=True):
            st.switch_page("pages/3_📊_Balance.py")

    with col3:
        if sin_revisar > 0:
            if st.button(
                f"📝 Revisar {sin_revisar} Transacciones",
                use_container_width=True,
                type="primary",
            ):
                st.switch_page("pages/4_📝_Transacciones.py")
        else:
            if st.button("📝 Ver Transacciones", use_container_width=True):
                st.switch_page("pages/4_📝_Transacciones.py")

    with col4:
        if st.button("📧 Procesar Correos", use_container_width=True):
            st.switch_page("pages/4_📝_Transacciones.py")


if __name__ == "__main__":
    main()
