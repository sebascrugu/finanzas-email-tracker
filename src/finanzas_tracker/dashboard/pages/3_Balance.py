"""Página de Balance Mensual."""

from datetime import date

import streamlit as st


st.set_page_config(
    page_title="Balance - Finanzas Tracker",
    page_icon="",
    layout="wide",
)

from pathlib import Path
import sys


src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.dashboard.helpers import require_profile
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.transaction import Transaction


logger = get_logger(__name__)


def main():
    st.title(" Balance Mensual")

    perfil_activo = require_profile()
    st.caption(f" Perfil: **{perfil_activo.nombre_completo}**")

    # Selector de mes
    col1, col2 = st.columns([1, 3])

    with col1:
        mes_actual = date.today()
        mes_seleccionado = st.date_input(" Seleccionar Fecha", value=mes_actual)

    # Calcular rango del mes
    primer_dia = date(mes_seleccionado.year, mes_seleccionado.month, 1)

    if mes_seleccionado.month == 12:
        proximo_mes = date(mes_seleccionado.year + 1, 1, 1)
    else:
        proximo_mes = date(mes_seleccionado.year, mes_seleccionado.month + 1, 1)

    # Obtener datos
    with get_session() as session:
        # Ingresos
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

        # Gastos
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
        balance = total_ingresos - total_gastos

    # Mostrar balance
    st.markdown(f"### Balance de {mes_seleccionado.strftime('%B %Y').upper()}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label=" Ingresos",
            value=f"₡{total_ingresos:,.0f}",
            delta=f"{len(ingresos)} registro(s)",
        )

    with col2:
        st.metric(
            label=" Gastos", value=f"₡{total_gastos:,.0f}", delta=f"{len(gastos)} transacción(es)"
        )

    with col3:
        delta_color = "normal" if balance >= 0 else "inverse"
        st.metric(
            label=" Balance",
            value=f"₡{balance:,.0f}",
            delta="Positivo" if balance >= 0 else "Negativo",
            delta_color=delta_color,
        )

    st.markdown("---")

    # Progreso
    if total_ingresos > 0:
        porcentaje_gastado = (total_gastos / total_ingresos) * 100

        st.subheader(" Progreso de Gastos")

        st.progress(min(porcentaje_gastado / 100, 1.0))

        st.markdown(f"**Has gastado el {porcentaje_gastado:.1f}% de tus ingresos**")

        if porcentaje_gastado > 100:
            st.error(" ¡Estás gastando más de lo que ingresas!")
        elif porcentaje_gastado > 90:
            st.warning(" ¡Cuidado! Ya gastaste más del 90%")
        elif porcentaje_gastado > 75:
            st.info(" Buen control, pero vigila tus gastos")
        else:
            st.success(" ¡Excelente control de gastos!")

        st.markdown("---")

        # Detalles
        col1, col2 = st.columns(2)

        with col1:
            st.subheader(" Ingresos Detallados")

            if ingresos:
                for ing in ingresos:
                    st.markdown(
                        f"- **{ing.tipo.value}**: {ing.monto_display} ({ing.fecha.strftime('%d/%m')})"
                    )
            else:
                st.info("Sin ingresos este mes")

        with col2:
            st.subheader(" Gastos Detallados")

            if gastos:
                # Agrupar por categoría
                por_categoria = {}
                for gasto in gastos:
                    cat = gasto.categoria_sugerida_por_ia or "Sin categoría"
                    if cat not in por_categoria:
                        por_categoria[cat] = 0
                    por_categoria[cat] += float(gasto.monto_crc)

                # Ordenar por monto
                for cat, monto in sorted(por_categoria.items(), key=lambda x: x[1], reverse=True):
                    porcentaje = (monto / float(total_gastos)) * 100
                    st.markdown(f"- **{cat}**: ₡{monto:,.0f} ({porcentaje:.1f}%)")
            else:
                st.info("Sin gastos este mes")

    elif total_gastos > 0:
        st.warning(" Tienes gastos pero no ingresos registrados")
        st.info(" Ve a **Ingresos** para registrar tus ingresos del mes")

    else:
        st.info(" No hay transacciones para este mes")


if __name__ == "__main__":
    main()
