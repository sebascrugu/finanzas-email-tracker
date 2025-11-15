"""Página de Gestión de Ingresos - Simplificada."""

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


def es_tipo_recurrente(tipo: IncomeType) -> bool:
    """Determina si un tipo de ingreso es típicamente recurrente."""
    tipos_recurrentes = {
        IncomeType.SALARY,
        IncomeType.PENSION,
    }
    return tipo in tipos_recurrentes


def calcular_proximo_ingreso_automatico(tipo: IncomeType, fecha_actual: date) -> date | None:
    """Calcula automáticamente el próximo ingreso esperado según el tipo."""
    if tipo == IncomeType.SALARY:
        # Salario: mensual
        next_month = fecha_actual.month + 1
        year = fecha_actual.year
        if next_month > 12:
            next_month = 1
            year += 1
        try:
            return date(year, next_month, fecha_actual.day)
        except ValueError:
            return date(year, next_month, 28)
    elif tipo == IncomeType.PENSION:
        # Pensión: mensual
        next_month = fecha_actual.month + 1
        year = fecha_actual.year
        if next_month > 12:
            next_month = 1
            year += 1
        try:
            return date(year, next_month, fecha_actual.day)
        except ValueError:
            return date(year, next_month, 28)
    # Otros tipos no son recurrentes
    return None


def main():
    st.title("💰 Gestión de Ingresos")

    perfil_activo = require_profile()
    st.caption(f"📊 Perfil: **{perfil_activo.nombre_completo}**")

    # Tabs
    tab1, tab2 = st.tabs(["➕ Agregar Ingreso", "📋 Mis Ingresos"])

    # TAB 1: AGREGAR INGRESO
    with tab1:
        st.subheader("Registrar Nuevo Ingreso")

        with st.form("add_income_form", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                tipo_seleccionado = st.selectbox(
                    "💼 Tipo de Ingreso",
                    options=[
                        (IncomeType.SALARY, "💼 Salario"),
                        (IncomeType.PENSION, "👴 Pensión"),
                        (IncomeType.FREELANCE, "💻 Freelance/Proyecto"),
                        (IncomeType.SALE, "🛍️ Venta"),
                        (IncomeType.INVESTMENT_RETURN, "📈 Rendimiento Inversión"),
                        (IncomeType.GIFT, "🎁 Regalo/Ayuda"),
                        (IncomeType.OTHER, "📦 Otro"),
                    ],
                    format_func=lambda x: x[1],
                    help="El tipo determina si es recurrente automáticamente",
                )

                descripcion = st.text_input(
                    "📝 Descripción",
                    placeholder="ej: Salario Nov 2025, Venta PS5, Proyecto Web App",
                    help="Descripción breve del ingreso",
                )

                monto = st.number_input(
                    "💵 Monto",
                    min_value=0.0,
                    value=0.0,
                    step=1000.0,
                    format="%.2f",
                    help="Monto del ingreso",
                )

            with col2:
                moneda = st.selectbox("💱 Moneda", options=["CRC", "USD"], index=0)

                fecha_ingreso = st.date_input(
                    "📅 Fecha del Ingreso",
                    value=date.today(),
                    max_value=date.today(),
                    help="Fecha en que recibiste el ingreso",
                )

                # Mostrar info automática si es recurrente
                tipo_income = tipo_seleccionado[0]
                es_recurrente = es_tipo_recurrente(tipo_income)

                if es_recurrente:
                    st.info("🔄 **Ingreso recurrente** (se calculará automáticamente el próximo)")
                    proximo_auto = calcular_proximo_ingreso_automatico(tipo_income, fecha_ingreso)
                    if proximo_auto:
                        st.caption(
                            f"📅 Próximo ingreso esperado: {proximo_auto.strftime('%d/%m/%Y')}"
                        )
                else:
                    st.info("1️⃣ **Ingreso único** (no recurrente)")

            # Botón de submit
            submitted = st.form_submit_button(
                "✅ Guardar Ingreso", type="primary", use_container_width=True
            )

            if submitted:
                if not descripcion or not descripcion.strip():
                    st.error("❌ La descripción es requerida")
                elif monto <= 0:
                    st.error("❌ El monto debe ser mayor a 0")
                else:
                    try:
                        # Convertir a CRC si es USD
                        monto_crc = Decimal(str(monto))
                        tipo_cambio = None

                        if moneda == "USD":
                            with st.spinner("💱 Obteniendo tipo de cambio..."):
                                exchange_service = ExchangeRateService()
                                tipo_cambio = exchange_service.get_rate(fecha_ingreso)
                                monto_crc = Decimal(str(monto)) * Decimal(str(tipo_cambio))
                                st.success(
                                    f"💱 Tipo de cambio: ₡{tipo_cambio:.2f} → **₡{monto_crc:,.2f}**"
                                )

                        # Calcular próximo ingreso automáticamente
                        proximo = calcular_proximo_ingreso_automatico(tipo_income, fecha_ingreso)
                        frecuencia = RecurrenceFrequency.MONTHLY if es_recurrente else None

                        # Guardar en BD
                        with get_session() as session:
                            nuevo_ingreso = Income(
                                profile_id=perfil_activo.id,
                                tipo=tipo_income,
                                descripcion=descripcion.strip(),
                                monto_original=Decimal(str(monto)),
                                moneda_original=Currency(moneda),
                                monto_crc=monto_crc,
                                tipo_cambio_usado=Decimal(str(tipo_cambio))
                                if tipo_cambio
                                else None,
                                fecha=fecha_ingreso,
                                es_recurrente=es_recurrente,
                                frecuencia=frecuencia,
                                proximo_ingreso_esperado=proximo,
                            )
                            session.add(nuevo_ingreso)
                            session.commit()

                            st.success("✅ ¡Ingreso registrado exitosamente!")
                            st.balloons()

                            if es_recurrente and proximo:
                                st.info(
                                    f"🔄 Próximo ingreso esperado: **{proximo.strftime('%d/%m/%Y')}**"
                                )

                            # El form se limpia automáticamente con clear_on_submit=True

                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                        logger.error(f"Error guardando ingreso: {e}")

    # TAB 2: MIS INGRESOS
    with tab2:
        st.subheader("📋 Lista de Ingresos")

        with get_session() as session:
            ingresos = (
                session.query(Income)
                .filter(Income.profile_id == perfil_activo.id, Income.deleted_at.is_(None))
                .order_by(Income.fecha.desc())
                .all()
            )

            if not ingresos:
                st.info("📭 No tienes ingresos registrados todavía")
                st.markdown("""
                **💡 Tip:** Los ingresos recurrentes (Salario, Pensión) se calculan automáticamente.
                Solo necesitas registrarlos una vez.
                """)
            else:
                # Resumen rápido
                total_mes = sum(
                    i.monto_crc
                    for i in ingresos
                    if i.fecha.month == date.today().month and i.fecha.year == date.today().year
                )
                total_general = sum(i.monto_crc for i in ingresos)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 Total General", f"₡{total_general:,.0f}")
                with col2:
                    st.metric("📅 Este Mes", f"₡{total_mes:,.0f}")
                with col3:
                    st.metric("📝 Total Ingresos", len(ingresos))

                st.markdown("---")

                # Agrupar por tipo
                st.markdown("### 📊 Por Tipo de Ingreso")

                tipos_agrupados = {}
                for ingreso in ingresos:
                    tipo_nombre = ingreso.tipo.value
                    if tipo_nombre not in tipos_agrupados:
                        tipos_agrupados[tipo_nombre] = []
                    tipos_agrupados[tipo_nombre].append(ingreso)

                for tipo_nombre, ingresos_tipo in sorted(tipos_agrupados.items()):
                    total_tipo = sum(i.monto_crc for i in ingresos_tipo)
                    icono = "🔁" if any(i.es_recurrente for i in ingresos_tipo) else "1️⃣"

                    with st.expander(
                        f"{icono} **{tipo_nombre.upper()}** - ₡{total_tipo:,.0f} ({len(ingresos_tipo)} ingreso(s))",
                        expanded=False,
                    ):
                        for ingreso in sorted(ingresos_tipo, key=lambda x: x.fecha, reverse=True):
                            col1, col2, col3 = st.columns([3, 2, 1])

                            with col1:
                                st.markdown(f"**{ingreso.descripcion}**")
                                st.caption(f"📅 {ingreso.fecha.strftime('%d/%m/%Y')}")

                            with col2:
                                st.markdown(f"**{ingreso.monto_display}**")
                                if ingreso.moneda_original == Currency.USD:
                                    st.caption(f"Original: ${ingreso.monto_original:,.2f} USD")

                            with col3:
                                if ingreso.es_recurrente:
                                    st.markdown("🔄 **Recurrente**")
                                    if ingreso.proximo_ingreso_esperado:
                                        st.caption(
                                            f"Próximo: {ingreso.proximo_ingreso_esperado.strftime('%d/%m/%Y')}"
                                        )
                                else:
                                    st.markdown("1️⃣ **Único**")

                            if ingreso != ingresos_tipo[-1]:
                                st.markdown("---")


if __name__ == "__main__":
    main()
