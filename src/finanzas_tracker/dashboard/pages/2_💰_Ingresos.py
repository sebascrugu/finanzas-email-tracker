"""Página de Gestión de Ingresos."""

import streamlit as st
from decimal import Decimal
from datetime import date, timedelta

st.set_page_config(
    page_title="Ingresos - Finanzas Tracker",
    page_icon="💰",
    layout="wide",
)

import sys
from pathlib import Path

src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.enums import IncomeType, Currency, RecurrenceFrequency
from finanzas_tracker.services.exchange_rate import ExchangeRateService
from finanzas_tracker.dashboard.helpers import require_profile

logger = get_logger(__name__)


def calcular_proximo_ingreso(fecha_actual: date, frecuencia: RecurrenceFrequency) -> date:
    """Calcula la próxima fecha de ingreso según frecuencia."""
    if frecuencia == RecurrenceFrequency.WEEKLY:
        return fecha_actual + timedelta(weeks=1)
    elif frecuencia == RecurrenceFrequency.BIWEEKLY:
        return fecha_actual + timedelta(weeks=2)
    elif frecuencia == RecurrenceFrequency.MONTHLY:
        next_month = fecha_actual.month + 1
        year = fecha_actual.year
        if next_month > 12:
            next_month = 1
            year += 1
        try:
            return date(year, next_month, fecha_actual.day)
        except ValueError:
            return date(year, next_month, 28)
    elif frecuencia == RecurrenceFrequency.QUARTERLY:
        months = fecha_actual.month + 3
        year = fecha_actual.year + (months - 1) // 12
        month = ((months - 1) % 12) + 1
        try:
            return date(year, month, fecha_actual.day)
        except ValueError:
            return date(year, month, 28)
    elif frecuencia == RecurrenceFrequency.ANNUAL:
        try:
            return date(fecha_actual.year + 1, fecha_actual.month, fecha_actual.day)
        except ValueError:
            return date(fecha_actual.year + 1, fecha_actual.month, 28)
    else:
        return fecha_actual


def main():
    st.title("💰 Gestión de Ingresos")

    perfil_activo = require_profile()
    st.caption(f"📊 Perfil: **{perfil_activo.nombre_completo}**")

    # Tabs
    tab1, tab2 = st.tabs(["➕ Agregar Ingreso", "📋 Mis Ingresos"])

    # TAB 1: AGREGAR INGRESO
    with tab1:
        st.subheader("Registrar Nuevo Ingreso")

        with st.form("add_income_form"):
            col1, col2 = st.columns(2)

            with col1:
                tipo = st.selectbox(
                    "💼 Tipo de Ingreso",
                    options=[
                        ("salary", "💼 Salario"),
                        ("pension", "👴 Pensión"),
                        ("freelance", "💻 Freelance"),
                        ("sale", "🛍️ Venta"),
                        ("investment_return", "📈 Rendimiento Inversión"),
                        ("gift", "🎁 Regalo/Ayuda"),
                        ("other", "📦 Otro"),
                    ],
                    format_func=lambda x: x[1],
                )

                descripcion = st.text_input(
                    "📝 Descripción",
                    placeholder="ej: Salario Nov 2025, Venta PS5",
                    help="Descripción breve del ingreso",
                )

                monto = st.number_input(
                    "💵 Monto", min_value=0.0, value=0.0, step=1000.0, format="%.2f"
                )

                moneda = st.selectbox("💱 Moneda", options=["CRC", "USD"], index=0)

            with col2:
                fecha_ingreso = st.date_input(
                    "📅 Fecha del Ingreso", value=date.today(), max_value=date.today()
                )

                es_recurrente = st.checkbox(
                    "🔁 Es un ingreso recurrente",
                    help="Marca si este ingreso se repite regularmente (ej: salario)",
                )

                if es_recurrente:
                    frecuencia = st.selectbox(
                        "📆 Frecuencia",
                        options=[
                            (RecurrenceFrequency.WEEKLY, "📅 Semanal"),
                            (RecurrenceFrequency.BIWEEKLY, "📆 Quincenal"),
                            (RecurrenceFrequency.MONTHLY, "🗓️ Mensual"),
                            (RecurrenceFrequency.QUARTERLY, "📊 Trimestral"),
                            (RecurrenceFrequency.ANNUAL, "📈 Anual"),
                        ],
                        format_func=lambda x: x[1],
                    )
                else:
                    frecuencia = None

            submitted = st.form_submit_button("✅ Guardar Ingreso", use_container_width=True)

            if submitted:
                if not descripcion:
                    st.error("❌ La descripción es requerida")
                elif monto <= 0:
                    st.error("❌ El monto debe ser mayor a 0")
                else:
                    try:
                        # Convertir a CRC si es USD
                        if moneda == "USD":
                            with st.spinner("Obteniendo tipo de cambio..."):
                                exchange_service = ExchangeRateService()
                                tipo_cambio = exchange_service.get_rate(fecha_ingreso)
                                monto_crc = Decimal(str(monto)) * Decimal(str(tipo_cambio))
                                st.info(
                                    f"💱 Tipo de cambio: ₡{tipo_cambio:.2f} → ₡{monto_crc:,.2f}"
                                )
                        else:
                            monto_crc = Decimal(str(monto))
                            tipo_cambio = None

                        # Calcular próximo ingreso si es recurrente
                        proximo = None
                        if es_recurrente and frecuencia:
                            proximo = calcular_proximo_ingreso(fecha_ingreso, frecuencia[0])

                        # Guardar en BD
                        with get_session() as session:
                            nuevo_ingreso = Income(
                                profile_id=perfil_activo.id,
                                tipo=IncomeType(tipo[0]),
                                descripcion=descripcion,
                                monto_original=Decimal(str(monto)),
                                moneda_original=Currency(moneda),
                                monto_crc=monto_crc,
                                tipo_cambio_usado=Decimal(str(tipo_cambio))
                                if tipo_cambio
                                else None,
                                fecha=fecha_ingreso,
                                es_recurrente=es_recurrente,
                                frecuencia=frecuencia[0] if frecuencia else None,
                                proximo_ingreso_esperado=proximo,
                            )
                            session.add(nuevo_ingreso)
                            session.commit()

                            st.success("✅ ¡Ingreso registrado exitosamente!")
                            st.balloons()

                            if es_recurrente and proximo:
                                st.info(
                                    f"🔄 Próximo ingreso esperado: {proximo.strftime('%d/%m/%Y')}"
                                )

                            # Limpiar form
                            st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                        logger.error(f"Error guardando ingreso: {e}")

    # TAB 2: MIS INGRESOS
    with tab2:
        st.subheader("Lista de Ingresos Registrados")

        with get_session() as session:
            ingresos = (
                session.query(Income)
                .filter(Income.profile_id == perfil_activo.id, Income.deleted_at.is_(None))
                .order_by(Income.fecha.desc())
                .all()
            )

            if not ingresos:
                st.info("📭 No tienes ingresos registrados todavía")
            else:
                st.success(f"📊 Tienes **{len(ingresos)}** ingreso(s) registrado(s)")

                for ingreso in ingresos:
                    recurrente_icon = "🔁" if ingreso.es_recurrente else "1️⃣"

                    with st.expander(
                        f"{recurrente_icon} {ingreso.tipo.value.upper()} - {ingreso.monto_display} ({ingreso.fecha.strftime('%d/%m/%Y')})"
                    ):
                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown(f"**Descripción:** {ingreso.descripcion}")
                            st.markdown(f"**Fecha:** {ingreso.fecha.strftime('%d/%m/%Y')}")
                            st.markdown(f"**Monto:** {ingreso.monto_display}")

                        with col2:
                            if ingreso.es_recurrente:
                                st.markdown(
                                    f"**Recurrente:** Sí ({ingreso.frecuencia.value if ingreso.frecuencia else 'N/A'})"
                                )
                                if ingreso.proximo_ingreso_esperado:
                                    st.markdown(
                                        f"**Próximo:** {ingreso.proximo_ingreso_esperado.strftime('%d/%m/%Y')}"
                                    )
                            else:
                                st.markdown("**Recurrente:** No")


if __name__ == "__main__":
    main()
