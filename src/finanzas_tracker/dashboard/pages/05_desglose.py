"""
Página de Desglose de Ingresos.

Permite vincular ingresos (especialmente "dinero ajeno") con los gastos específicos
donde se usó ese dinero. Resuelve el caso de uso "mamá me dio ₡20K para comprar carne".
"""

from datetime import timedelta
from decimal import Decimal

import streamlit as st


# Configurar página
st.set_page_config(
    page_title="Desglose - Finanzas Tracker",
    page_icon="💸",
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
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.income_split import IncomeSplit
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction


logger = get_logger(__name__)


def main() -> None:
    """Página principal de desglose de ingresos."""

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
    st.markdown("# 💸 Desglose de Ingresos")
    st.markdown(
        "Vincula ingresos con sus gastos específicos. Ideal para dinero que te dieron para algo específico."
    )
    st.markdown("---")

    # Tabs: Pendientes | Completados
    tab_pendientes, tab_completados = st.tabs(["📋 Pendientes de Desglose", "✅ Completados"])

    # ========================================================================
    # TAB 1: PENDIENTES DE DESGLOSE
    # ========================================================================
    with tab_pendientes:
        with get_session() as session:
            # Buscar ingresos que requieren desglose y aún no están completos
            ingresos_pendientes = (
                session.query(Income)
                .filter(
                    Income.profile_id == perfil_activo.id,
                    Income.requiere_desglose == True,
                    Income.es_dinero_ajeno == True,
                    Income.deleted_at.is_(None),
                )
                .order_by(Income.fecha.desc())
                .all()
            )

            if not ingresos_pendientes:
                st.info(
                    "✅ **¡Todo al día!** No tienes ingresos pendientes de desglosar.\n\n"
                    "Los ingresos marcados como 'dinero ajeno' aparecerán aquí automáticamente."
                )
            else:
                st.markdown(
                    f"**Encontramos {len(ingresos_pendientes)} ingresos que necesitan desglose:**"
                )
                st.markdown("---")

                for ingreso in ingresos_pendientes:
                    # Obtener splits existentes
                    splits_existentes = (
                        session.query(IncomeSplit)
                        .filter(
                            IncomeSplit.income_id == ingreso.id, IncomeSplit.deleted_at.is_(None)
                        )
                        .all()
                    )

                    monto_ya_asignado = sum(split.monto_asignado for split in splits_existentes)
                    monto_restante = ingreso.monto_crc - monto_ya_asignado

                    # Card del ingreso
                    with st.expander(
                        f"💰 **{ingreso.descripcion}** - ₡{ingreso.monto_crc:,.0f} "
                        f"({ingreso.fecha.strftime('%d/%m/%Y')})",
                        expanded=len(splits_existentes) == 0,
                    ):
                        # Info del ingreso
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Monto Total", f"₡{ingreso.monto_crc:,.0f}")
                        with col2:
                            st.metric("Monto Usado", f"₡{ingreso.monto_usado or 0:,.0f}")
                        with col3:
                            st.metric(
                                "Te Quedaste", f"₡{ingreso.monto_sobrante or 0:,.0f}", delta="✅"
                            )

                        if ingreso.contexto:
                            st.info(f"💬 **Contexto:** {ingreso.contexto}")

                        # Splits existentes
                        if splits_existentes:
                            st.markdown("**Gastos ya vinculados:**")
                            for split in splits_existentes:
                                tx = split.transaction
                                st.markdown(
                                    f"- **{tx.comercio}** - ₡{split.monto_asignado:,.0f} "
                                    f"({tx.fecha_transaccion.strftime('%d/%m/%Y')})"
                                )

                            st.markdown(f"**Monto restante por asignar:** ₡{monto_restante:,.0f}")

                        # Buscar transacciones candidatas (misma fecha ±5 días)
                        fecha_inicio = ingreso.fecha - timedelta(days=5)
                        fecha_fin = ingreso.fecha + timedelta(days=5)

                        transacciones_candidatas = (
                            session.query(Transaction)
                            .filter(
                                Transaction.profile_id == perfil_activo.id,
                                Transaction.fecha_transaccion >= fecha_inicio,
                                Transaction.fecha_transaccion <= fecha_fin,
                                Transaction.deleted_at.is_(None),
                            )
                            .order_by(Transaction.fecha_transaccion.desc())
                            .all()
                        )

                        # Filtrar las que ya están asignadas a este ingreso
                        tx_ids_asignadas = {split.transaction_id for split in splits_existentes}
                        transacciones_disponibles = [
                            tx for tx in transacciones_candidatas if tx.id not in tx_ids_asignadas
                        ]

                        if not transacciones_disponibles:
                            st.warning("No hay transacciones cercanas a esta fecha para vincular.")
                        else:
                            st.markdown("---")
                            st.markdown(
                                f"**Vincular con transacciones cercanas** (±5 días de {ingreso.fecha.strftime('%d/%m/%Y')}):"
                            )

                            # Formulario para vincular
                            with st.form(f"vincular_{ingreso.id}"):
                                # Dropdown de transacciones
                                opciones_tx = {
                                    f"{tx.comercio} - ₡{tx.monto_crc:,.0f} ({tx.fecha_transaccion.strftime('%d/%m/%Y')})": tx.id
                                    for tx in transacciones_disponibles
                                }

                                if opciones_tx:
                                    tx_seleccionada_display = st.selectbox(
                                        "Selecciona la transacción",
                                        options=list(opciones_tx.keys()),
                                        key=f"tx_select_{ingreso.id}",
                                    )

                                    tx_seleccionada_id = opciones_tx[tx_seleccionada_display]

                                    # Obtener transacción para mostrar monto sugerido
                                    tx_obj = next(
                                        tx
                                        for tx in transacciones_disponibles
                                        if tx.id == tx_seleccionada_id
                                    )

                                    # Input de monto (con sugerencia del monto de la transacción)
                                    monto_asignar = st.number_input(
                                        "Monto a asignar",
                                        min_value=0.0,
                                        max_value=float(monto_restante),
                                        value=min(float(tx_obj.monto_crc), float(monto_restante)),
                                        step=100.0,
                                        key=f"monto_{ingreso.id}",
                                        help=f"Máximo: ₡{monto_restante:,.0f} (lo que queda del ingreso)",
                                    )

                                    proposito = st.text_input(
                                        "Propósito (opcional)",
                                        placeholder="Ej: Dona para mamá, Chuletas",
                                        key=f"proposito_{ingreso.id}",
                                    )

                                    col1, col2 = st.columns([1, 3])
                                    with col1:
                                        vincular_btn = st.form_submit_button(
                                            "🔗 Vincular", type="primary"
                                        )

                                    if vincular_btn:
                                        try:
                                            nuevo_split = IncomeSplit(
                                                income_id=ingreso.id,
                                                transaction_id=tx_seleccionada_id,
                                                monto_asignado=Decimal(str(monto_asignar)),
                                                proposito=proposito.strip() if proposito else None,
                                                confianza_match=Decimal("100.0"),
                                                sugerido_por_ai=False,
                                            )

                                            session.add(nuevo_split)
                                            session.commit()

                                            st.success(
                                                f"✅ Vinculado! {tx_obj.comercio} con ₡{monto_asignar:,.0f}"
                                            )
                                            st.rerun()

                                        except Exception as e:
                                            st.error(f"Error: {e}")
                                            logger.error(f"Error vinculando split: {e}")
                                else:
                                    st.info("No hay transacciones disponibles para vincular")

    # ========================================================================
    # TAB 2: COMPLETADOS
    # ========================================================================
    with tab_completados, get_session() as session:
        # Buscar todos los splits
        todos_splits = (
            session.query(IncomeSplit)
            .join(Income)
            .filter(Income.profile_id == perfil_activo.id, IncomeSplit.deleted_at.is_(None))
            .order_by(Income.fecha.desc())
            .all()
        )

        if not todos_splits:
            st.info("Aún no tienes desgloses completados.")
        else:
            # Agrupar por ingreso
            splits_por_ingreso = {}
            for split in todos_splits:
                ingreso_id = split.income_id
                if ingreso_id not in splits_por_ingreso:
                    splits_por_ingreso[ingreso_id] = []
                splits_por_ingreso[ingreso_id].append(split)

            st.markdown(f"**Mostrando {len(splits_por_ingreso)} ingresos desglosados:**")
            st.markdown("---")

            for ingreso_id, splits in splits_por_ingreso.items():
                ingreso = splits[0].income  # Todos los splits tienen el mismo income

                with st.expander(
                    f"💰 **{ingreso.descripcion}** - ₡{ingreso.monto_crc:,.0f} "
                    f"({ingreso.fecha.strftime('%d/%m/%Y')})"
                ):
                    total_asignado = sum(split.monto_asignado for split in splits)

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Monto Total", f"₡{ingreso.monto_crc:,.0f}")
                    with col2:
                        st.metric("Total Asignado", f"₡{total_asignado:,.0f}")
                    with col3:
                        diferencia = ingreso.monto_crc - total_asignado
                        st.metric("Sin Asignar", f"₡{diferencia:,.0f}")

                    st.markdown("**Desglose:**")
                    for split in splits:
                        tx = split.transaction
                        col_a, col_b, col_c = st.columns([2, 2, 1])

                        with col_a:
                            st.markdown(f"**{tx.comercio}**")
                            if split.proposito:
                                st.caption(split.proposito)

                        with col_b:
                            st.markdown(f"₡{split.monto_asignado:,.0f}")
                            st.caption(tx.fecha_transaccion.strftime("%d/%m/%Y"))

                        with col_c:
                            # Botón para eliminar split
                            if st.button("🗑️", key=f"delete_{split.id}", help="Desvincular"):
                                try:
                                    session.delete(split)
                                    session.commit()
                                    st.success("Desvinculado")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Error: {e}")


if __name__ == "__main__":
    main()
