"""
Página de Gestión de Merchants.

Permite ver, editar y gestionar los comercios normalizados y sus variantes.
"""

import streamlit as st


# Configurar página
st.set_page_config(
    page_title="Merchants - Finanzas Tracker",
    page_icon="🏪",
    layout="wide",
)

# Imports después de configuración
from pathlib import Path
import sys


# Agregar src al path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.dashboard.helpers import mostrar_sidebar_simple
from finanzas_tracker.models.merchant import Merchant, MerchantVariant
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction


logger = get_logger(__name__)


def main() -> None:
    """Página principal de gestión de merchants."""

    # Obtener perfil activo
    with get_session() as session:
        perfil_activo = (
            session.query(Profile)
            .filter(
                Profile.es_activo == True,
                Profile.activo == True,
            )
            .first()
        )

        if not perfil_activo:
            st.warning("⚠️ Necesitas crear un perfil primero")
            if st.button("Ir a Setup"):
                st.switch_page("pages/1__Setup.py")
            return

    # Sidebar
    mostrar_sidebar_simple(perfil_activo)

    # Header
    st.markdown("# 🏪 Gestión de Merchants")
    st.markdown("Merchants normalizados: 'SUBWAY MOMENTUM' + 'SUBWAY AMERICA FREE ZO' = **Subway**")
    st.markdown("---")

    # Tabs
    tab_lista, tab_stats = st.tabs(["📋 Lista de Merchants", "📊 Estadísticas"])

    # ========================================================================
    # TAB 1: LISTA DE MERCHANTS
    # ========================================================================
    with tab_lista, get_session() as session:
        # Obtener todos los merchants
        merchants = (
            session.query(Merchant)
            .filter(Merchant.deleted_at.is_(None))
            .order_by(Merchant.nombre_normalizado)
            .all()
        )

        if not merchants:
            st.info(
                "📭 **No hay merchants aún.**\n\n"
                "Los merchants se crean automáticamente al procesar correos bancarios."
            )
            return

        st.markdown(f"**Total de merchants:** {len(merchants)}")

        # Búsqueda
        buscar = st.text_input("🔍 Buscar merchant", placeholder="Ej: Subway, Walmart...")

        merchants_filtrados = merchants
        if buscar:
            buscar_lower = buscar.lower()
            merchants_filtrados = [
                m for m in merchants if buscar_lower in m.nombre_normalizado.lower()
            ]

        st.markdown("---")

        # Mostrar merchants
        for merchant in merchants_filtrados:
            # Obtener variantes
            variantes = (
                session.query(MerchantVariant)
                .filter(
                    MerchantVariant.merchant_id == merchant.id,
                    MerchantVariant.deleted_at.is_(None),
                )
                .all()
            )

            # Calcular total gastado
            total_gastado = merchant.calcular_total_gastado(session, perfil_activo.id)

            # Card del merchant
            with st.expander(
                f"**{merchant.nombre_normalizado}** "
                f"({len(variantes)} {'variante' if len(variantes) == 1 else 'variantes'}) "
                f"- ₡{total_gastado:,.0f} gastado"
            ):
                col1, col2 = st.columns([2, 1])

                with col1:
                    # Info del merchant
                    st.markdown(f"**📍 Nombre Normalizado:** {merchant.nombre_normalizado}")

                    if merchant.categoria_principal:
                        st.markdown(f"**🏷️ Categoría:** {merchant.categoria_principal}")
                    if merchant.tipo_negocio:
                        st.markdown(f"**💼 Tipo:** {merchant.tipo_negocio}")
                    if merchant.que_vende:
                        st.markdown(f"**🛒 Vende:** {merchant.que_vende}")

                    # Formulario para editar (simple)
                    with st.form(f"edit_{merchant.id}"):
                        st.markdown("**Editar información:**")

                        col_a, col_b = st.columns(2)

                        with col_a:
                            nueva_categoria = st.text_input(
                                "Categoría Principal",
                                value=merchant.categoria_principal or "",
                                key=f"cat_{merchant.id}",
                            )

                        with col_b:
                            nuevo_tipo = st.selectbox(
                                "Tipo de Negocio",
                                options=[
                                    "food_service",
                                    "retail",
                                    "entertainment",
                                    "services",
                                    "transportation",
                                    "health",
                                    "other",
                                ],
                                index=(
                                    [
                                        "food_service",
                                        "retail",
                                        "entertainment",
                                        "services",
                                        "transportation",
                                        "health",
                                        "other",
                                    ].index(merchant.tipo_negocio)
                                    if merchant.tipo_negocio
                                    else 6
                                ),
                                key=f"tipo_{merchant.id}",
                            )

                        nueva_desc = st.text_area(
                            "Qué Vende",
                            value=merchant.que_vende or "",
                            key=f"desc_{merchant.id}",
                            height=60,
                        )

                        if st.form_submit_button("💾 Guardar Cambios"):
                            try:
                                merchant_db = session.query(Merchant).get(merchant.id)
                                merchant_db.categoria_principal = nueva_categoria or None
                                merchant_db.tipo_negocio = nuevo_tipo
                                merchant_db.que_vende = nueva_desc or None
                                session.commit()

                                st.success("✅ Merchant actualizado")
                                st.rerun()

                            except Exception as e:
                                st.error(f"Error: {e}")
                                logger.error(f"Error actualizando merchant: {e}")

                with col2:
                    # Métricas
                    st.metric("Total Gastado", f"₡{total_gastado:,.0f}")
                    st.metric("Variantes", len(variantes))

                    # Contar transacciones
                    num_transacciones = (
                        session.query(Transaction)
                        .filter(
                            Transaction.merchant_id == merchant.id,
                            Transaction.profile_id == perfil_activo.id,
                            Transaction.deleted_at.is_(None),
                        )
                        .count()
                    )
                    st.metric("Transacciones", num_transacciones)

                # Mostrar variantes
                if variantes:
                    st.markdown("---")
                    st.markdown("**Variantes detectadas:**")

                    for variante in variantes:
                        ubicacion = []
                        if variante.ciudad:
                            ubicacion.append(variante.ciudad)
                        if variante.pais:
                            ubicacion.append(variante.pais)

                        ubicacion_str = ", ".join(ubicacion) if ubicacion else "Sin ubicación"

                        st.markdown(
                            f"- `{variante.nombre_raw}` → {ubicacion_str} "
                            f"(confianza: {variante.confianza_match}%)"
                        )

    # ========================================================================
    # TAB 2: ESTADÍSTICAS
    # ========================================================================
    with tab_stats, get_session() as session:
        merchants = session.query(Merchant).filter(Merchant.deleted_at.is_(None)).all()

        if not merchants:
            st.info("No hay merchants para mostrar estadísticas.")
            return

        # Calcular top merchants por gasto
        merchant_gastos = []
        for merchant in merchants:
            total_gastado = merchant.calcular_total_gastado(session, perfil_activo.id)
            if total_gastado > 0:
                merchant_gastos.append((merchant, total_gastado))

        merchant_gastos.sort(key=lambda x: x[1], reverse=True)

        # Top 10
        st.markdown("### 🏆 Top 10 Merchants por Gasto Total")

        if not merchant_gastos:
            st.info("No hay gastos en merchants aún.")
            return

        col1, col2 = st.columns([2, 1])

        with col1:
            # Tabla
            for i, (merchant, total) in enumerate(merchant_gastos[:10], 1):
                col_a, col_b, col_c = st.columns([1, 4, 2])

                with col_a:
                    # Ranking
                    if i == 1:
                        st.markdown("🥇")
                    elif i == 2:
                        st.markdown("🥈")
                    elif i == 3:
                        st.markdown("🥉")
                    else:
                        st.markdown(f"**#{i}**")

                with col_b:
                    st.markdown(f"**{merchant.nombre_normalizado}**")
                    if merchant.categoria_principal:
                        st.caption(merchant.categoria_principal)

                with col_c:
                    st.markdown(f"₡{total:,.0f}")

                st.markdown("---")

        with col2:
            # Métricas generales
            st.markdown("### 📈 Resumen General")

            total_merchants_con_gasto = len(merchant_gastos)
            total_gastado_general = sum(g[1] for g in merchant_gastos)

            st.metric("Merchants Usados", total_merchants_con_gasto)
            st.metric("Gasto Total", f"₡{total_gastado_general:,.0f}")

            if total_merchants_con_gasto > 0:
                promedio = total_gastado_general / total_merchants_con_gasto
                st.metric("Promedio por Merchant", f"₡{promedio:,.0f}")

            # Top por categoría
            st.markdown("---")
            st.markdown("**Top por Categoría:**")

            categorias = {}
            for merchant, total in merchant_gastos:
                cat = merchant.categoria_principal or "Sin categoría"
                categorias[cat] = categorias.get(cat, 0) + total

            top_categorias = sorted(categorias.items(), key=lambda x: x[1], reverse=True)[:5]

            for cat, total in top_categorias:
                st.markdown(f"**{cat}:** ₡{total:,.0f}")


if __name__ == "__main__":
    main()
