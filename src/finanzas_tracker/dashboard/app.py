"""
App principal de Streamlit - Dashboard de Finanzas.

Esta es la página principal que se muestra al usuario.
"""

import streamlit as st
from datetime import date

# Configurar página
st.set_page_config(
    page_title="Finanzas Email Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Importar después de set_page_config
import sys
from pathlib import Path

# Agregar src al path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session, init_db
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.user import User
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.models.income import Income
from finanzas_tracker.utils.seed_categories import seed_categories

logger = get_logger(__name__)

# Inicializar BD
init_db()

# Seed categorías si no existen
seed_categories()


def check_user_exists() -> User | None:
    """Verifica si existe un usuario activo."""
    with get_session() as session:
        return session.query(User).filter(User.activo == True).first()  # noqa: E712


def main():
    """Función principal del dashboard."""

    # Verificar si hay usuario configurado
    user = check_user_exists()

    if not user:
        st.warning("⚠️ **No hay usuario configurado**")
        st.info("👉 Ve a la página **Setup** en el menú lateral para configurar tu cuenta.")

        st.markdown("---")
        st.markdown("### 🚀 Bienvenido a Finanzas Email Tracker")
        st.markdown("""
        Esta aplicación te ayuda a:
        
        - 📧 **Procesar correos** de notificaciones bancarias automáticamente
        - 💰 **Trackear ingresos** y gastos en tiempo real
        - 📊 **Ver balance mensual** (ingresos vs gastos)
        - 🤖 **Categorización inteligente** con IA (Claude)
        - 🎯 **Gestionar presupuesto** según regla 50/30/20
        
        **¿Empezamos?** 👈 Configura tu cuenta en el menú lateral.
        """)
        return

    # Si hay usuario, mostrar dashboard
    st.title(f"💰 Dashboard - {user.nombre}")

    # Obtener datos del mes actual
    with get_session() as session:
        hoy = date.today()
        primer_dia = date(hoy.year, hoy.month, 1)

        # Próximo mes
        if hoy.month == 12:
            proximo_mes = date(hoy.year + 1, 1, 1)
        else:
            proximo_mes = date(hoy.year, hoy.month + 1, 1)

        # Ingresos del mes
        ingresos = (
            session.query(Income)
            .filter(
                Income.user_email == user.email,
                Income.fecha >= primer_dia,
                Income.fecha < proximo_mes,
                Income.deleted_at.is_(None),
            )
            .all()
        )

        total_ingresos = sum(i.monto_crc for i in ingresos)

        # Gastos del mes
        gastos = (
            session.query(Transaction)
            .filter(
                Transaction.user_email == user.email,
                Transaction.fecha_transaccion >= primer_dia,
                Transaction.fecha_transaccion < proximo_mes,
                Transaction.deleted_at.is_(None),
                Transaction.excluir_de_presupuesto == False,  # noqa: E712
            )
            .all()
        )

        total_gastos = sum(g.monto_crc for g in gastos)
        balance = total_ingresos - total_gastos

        # Transacciones sin revisar
        sin_revisar = (
            session.query(Transaction)
            .filter(
                Transaction.user_email == user.email,
                Transaction.necesita_revision == True,  # noqa: E712
                Transaction.deleted_at.is_(None),
            )
            .count()
        )

    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="💰 Ingresos del Mes",
            value=f"₡{total_ingresos:,.0f}",
            delta=f"{len(ingresos)} registro(s)",
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
            st.markdown(f"**Has gastado el {porcentaje_gastado:.1f}% de tus ingresos**")

            if porcentaje_gastado > 100:
                st.error("⚠️ ¡Estás gastando más de lo que ingresas!")
            elif porcentaje_gastado > 90:
                st.warning("⚠️ ¡Cuidado! Ya gastaste más del 90%")
            elif porcentaje_gastado > 75:
                st.info("💡 Buen control, pero vigila tus gastos")
            else:
                st.success("✅ ¡Excelente control de gastos!")

        with col2:
            disponible = total_ingresos - total_gastos
            st.metric(label="Disponible", value=f"₡{disponible:,.0f}")

    elif total_gastos > 0:
        st.warning("⚠️ Tienes gastos pero no ingresos registrados")
        st.info("💡 Ve a **Ingresos** para registrar tus ingresos del mes")

    else:
        st.info("📭 No hay transacciones para este mes todavía")
        st.markdown("""
        ### 🎯 Próximos pasos:
        
        1. **Ingresos** → Registra tus ingresos (salario, ventas, etc.)
        2. **Procesar Correos** → Procesa tus correos bancarios
        3. **Revisar** → Categoriza tus transacciones
        """)

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
                f"📝 Revisar {sin_revisar} Transacciones", use_container_width=True, type="primary"
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
