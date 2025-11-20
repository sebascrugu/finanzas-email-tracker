"""Página de Gestión de Ingresos - Simplificada."""

from datetime import date
from decimal import Decimal

import streamlit as st


st.set_page_config(
    page_title="Ingresos - Finanzas Tracker",
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
from finanzas_tracker.models.enums import (
    Currency,
    IncomeType,
    RecurrenceFrequency,
    SpecialTransactionType,
)
from finanzas_tracker.models.income import Income
from finanzas_tracker.services.exchange_rate import ExchangeRateService


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
    st.title(" Gestión de Ingresos")

    perfil_activo = require_profile()
    st.caption(f" Perfil: **{perfil_activo.nombre_completo}**")

    # Tabs
    tab1, tab2 = st.tabs([" Agregar Ingreso", " Mis Ingresos"])

    # TAB 1: AGREGAR INGRESO
    with tab1:
        st.subheader("Registrar Nuevo Ingreso")

        with st.form("add_income_form", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                tipo_seleccionado = st.selectbox(
                    "💰 Tipo de Ingreso",
                    options=[
                        (IncomeType.SALARY, "💼 Salario"),
                        (IncomeType.PENSION, "👴 Pensión"),
                        (IncomeType.FREELANCE, "💻 Freelance/Proyecto"),
                        (IncomeType.SALE, "🏷️ Venta"),
                        (IncomeType.INVESTMENT_RETURN, "📈 Rendimiento Inversión"),
                        (IncomeType.GIFT, "🎁 Regalo/Ayuda"),
                        (IncomeType.OTHER, "📋 Otro"),
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
                    st.info("🔁 **Ingreso recurrente** (se calculará automáticamente el próximo)")
                    proximo_auto = calcular_proximo_ingreso_automatico(tipo_income, fecha_ingreso)
                    if proximo_auto:
                        st.caption(
                            f"📆 Próximo ingreso esperado: {proximo_auto.strftime('%d/%m/%Y')}"
                        )
                else:
                    st.info("📌 **Ingreso único** (no recurrente)")

            # NUEVOS CAMPOS - Contexto y desglose
            st.markdown("---")
            st.markdown("### 🔍 Contexto y Desglose _(opcional)_")

            contexto = st.text_area(
                "💬 Contexto",
                placeholder="Ej: Mi mamá me pasó ₡10K para comprar dona y chuletas, gasté ₡5.5K",
                help="Explica el contexto de este ingreso si es dinero de otra persona o tiene un propósito específico",
                height=80,
            )

            col1, col2 = st.columns(2)

            with col1:
                es_dinero_ajeno = st.checkbox(
                    "💸 Es dinero de otra persona",
                    help="Marca si este dinero es de alguien más (ej: mamá te pasó para comprar algo)",
                )

                excluir_presupuesto = st.checkbox(
                    "🚫 Excluir de presupuesto mensual",
                    help="No se contará en el presupuesto 50/30/20 (ej: ajuste inicial, transferencia propia)",
                )

            with col2:
                tipo_especial = st.selectbox(
                    "🏷️ Tipo especial",
                    options=["ninguno", "dinero_ajeno", "intermediaria", "transferencia_propia", "ajuste_inicial"],
                    format_func=lambda x: {
                        "ninguno": "Ninguno (ingreso normal)",
                        "dinero_ajeno": "💸 Dinero de otra persona",
                        "intermediaria": "🔄 Intermediaria (paso plata)",
                        "transferencia_propia": "🔁 Transferencia entre mis cuentas",
                        "ajuste_inicial": "⚖️ Ajuste de saldo inicial",
                    }[x],
                    help="Clasificación especial de este ingreso",
                )

            # Si es dinero ajeno, mostrar campos de desglose
            if es_dinero_ajeno:
                st.markdown("---")
                st.markdown("#### 💰 Desglose del Dinero")
                st.info(
                    "Si usaste solo una parte del dinero, especifica cuánto usaste. "
                    "El resto se considerará como dinero que te quedaste."
                )

                col1, col2, col3 = st.columns(3)

                with col1:
                    monto_usado = st.number_input(
                        "Monto usado",
                        min_value=0.0,
                        max_value=float(monto) if monto > 0 else 999999999.0,
                        value=0.0,
                        step=100.0,
                        format="%.2f",
                        help="Cuánto dinero de este ingreso realmente usaste/gastaste",
                    )

                with col2:
                    if monto > 0:
                        monto_sobrante_calc = monto - monto_usado
                        st.metric(
                            "Monto sobrante",
                            f"₡{monto_sobrante_calc:,.2f}" if moneda == "CRC" else f"${monto_sobrante_calc:,.2f}",
                            delta="Lo que te quedaste",
                            delta_color="normal",
                        )
                    else:
                        st.caption("_Ingresa el monto total primero_")

                with col3:
                    if monto > 0 and monto_usado > 0:
                        porcentaje_usado = (monto_usado / monto) * 100
                        st.metric(
                            "% Usado",
                            f"{porcentaje_usado:.1f}%",
                            delta=f"{100 - porcentaje_usado:.1f}% sobró",
                        )

            # Botón de submit
            st.markdown("---")
            submitted = st.form_submit_button(
                "💾 Guardar Ingreso", type="primary", use_container_width=True
            )

            if submitted:
                if not descripcion or not descripcion.strip():
                    st.error("❌ La descripción es requerida")
                elif monto <= 0:
                    st.error("❌ El monto debe ser mayor a 0")
                elif es_dinero_ajeno and monto_usado > monto:
                    st.error("❌ El monto usado no puede ser mayor al monto total")
                else:
                    try:
                        # Convertir a CRC si es USD
                        monto_crc = Decimal(str(monto))
                        tipo_cambio = None

                        if moneda == "USD":
                            with st.spinner("⏳ Obteniendo tipo de cambio..."):
                                exchange_service = ExchangeRateService()
                                tipo_cambio = exchange_service.get_rate(fecha_ingreso)
                                monto_crc = Decimal(str(monto)) * Decimal(str(tipo_cambio))
                                st.success(
                                    f"✅ Tipo de cambio: ₡{tipo_cambio:.2f} → **₡{monto_crc:,.2f}**"
                                )

                        # Calcular próximo ingreso automáticamente
                        proximo = calcular_proximo_ingreso_automatico(tipo_income, fecha_ingreso)
                        frecuencia = RecurrenceFrequency.MONTHLY if es_recurrente else None

                        # Calcular montos de desglose si es dinero ajeno
                        monto_usado_decimal = None
                        monto_sobrante_decimal = None
                        if es_dinero_ajeno:
                            monto_usado_decimal = Decimal(str(monto_usado)) if monto_usado > 0 else Decimal("0")
                            monto_sobrante_decimal = monto_crc - monto_usado_decimal
                            # Convertir a CRC si era USD
                            if moneda == "USD" and tipo_cambio:
                                monto_usado_decimal = monto_usado_decimal * Decimal(str(tipo_cambio))

                        # Determinar tipo especial
                        tipo_especial_value = tipo_especial if tipo_especial != "ninguno" else None

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
                                # NUEVOS CAMPOS
                                contexto=contexto.strip() if contexto and contexto.strip() else None,
                                tipo_especial=tipo_especial_value,
                                excluir_de_presupuesto=excluir_presupuesto,
                                es_dinero_ajeno=es_dinero_ajeno,
                                requiere_desglose=es_dinero_ajeno,  # Si es dinero ajeno, puede requerir desglose
                                monto_usado=monto_usado_decimal,
                                monto_sobrante=monto_sobrante_decimal,
                            )
                            session.add(nuevo_ingreso)
                            session.commit()

                            st.success("✅ ¡Ingreso registrado exitosamente!")

                            # Mostrar resumen si es dinero ajeno
                            if es_dinero_ajeno and monto_sobrante_decimal:
                                st.info(
                                    f"💰 **Desglose:** De ₡{monto_crc:,.0f}, usaste ₡{monto_usado_decimal:,.0f} y "
                                    f"te quedaste con ₡{monto_sobrante_decimal:,.0f}"
                                )

                            if es_recurrente and proximo:
                                st.info(
                                    f"🔁 Próximo ingreso esperado: **{proximo.strftime('%d/%m/%Y')}**"
                                )

                            st.balloons()

                            # El form se limpia automáticamente con clear_on_submit=True

                    except Exception as e:
                        st.error(f"❌ Error: {e}")
                        logger.error(f"Error guardando ingreso: {e}")

    # TAB 2: MIS INGRESOS
    with tab2:
        st.subheader(" Lista de Ingresos")

        with get_session() as session:
            ingresos = (
                session.query(Income)
                .filter(Income.profile_id == perfil_activo.id, Income.deleted_at.is_(None))
                .order_by(Income.fecha.desc())
                .all()
            )

            if not ingresos:
                st.info(" No tienes ingresos registrados todavía")
                st.markdown("""
                ** Tip:** Los ingresos recurrentes (Salario, Pensión) se calculan automáticamente.
                Solo necesitas registrarlos una vez.
                """)
            else:
                # Resumen rápido (usando calcular_monto_patrimonio para considerar desgloses)
                total_mes = sum(
                    i.calcular_monto_patrimonio()
                    for i in ingresos
                    if i.fecha.month == date.today().month and i.fecha.year == date.today().year
                )
                total_general = sum(i.calcular_monto_patrimonio() for i in ingresos)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric(" Total General", f"₡{total_general:,.0f}")
                with col2:
                    st.metric(" Este Mes", f"₡{total_mes:,.0f}")
                with col3:
                    st.metric(" Total Ingresos", len(ingresos))

                st.markdown("---")

                # Agrupar por tipo
                st.markdown("###  Por Tipo de Ingreso")

                tipos_agrupados = {}
                for ingreso in ingresos:
                    tipo_nombre = ingreso.tipo.value
                    if tipo_nombre not in tipos_agrupados:
                        tipos_agrupados[tipo_nombre] = []
                    tipos_agrupados[tipo_nombre].append(ingreso)

                for tipo_nombre, ingresos_tipo in sorted(tipos_agrupados.items()):
                    total_tipo = sum(i.calcular_monto_patrimonio() for i in ingresos_tipo)
                    icono = "🔁" if any(i.es_recurrente for i in ingresos_tipo) else ""

                    with st.expander(
                        f"{icono} **{tipo_nombre.upper()}** - ₡{total_tipo:,.0f} ({len(ingresos_tipo)} ingreso(s))",
                        expanded=False,
                    ):
                        for ingreso in sorted(ingresos_tipo, key=lambda x: x.fecha, reverse=True):
                            col1, col2, col3 = st.columns([3, 2, 1])

                            with col1:
                                # Título con badges si es especial
                                titulo = f"**{ingreso.descripcion}**"
                                if ingreso.es_dinero_ajeno:
                                    titulo += " 💸"
                                if ingreso.excluir_de_presupuesto:
                                    titulo += " 🚫"
                                st.markdown(titulo)
                                st.caption(f"📅 {ingreso.fecha.strftime('%d/%m/%Y')}")

                                # Mostrar contexto si existe
                                if ingreso.contexto:
                                    st.caption(f"💬 _{ingreso.contexto[:80]}..._" if len(ingreso.contexto) > 80 else f"💬 _{ingreso.contexto}_")

                            with col2:
                                # Mostrar monto con desglose si es dinero ajeno
                                if ingreso.es_dinero_ajeno and ingreso.monto_sobrante is not None:
                                    st.markdown(f"**₡{ingreso.monto_crc:,.0f}** _total_")
                                    st.caption(f"💰 Te quedaste: ₡{ingreso.monto_sobrante:,.0f}")
                                    if ingreso.monto_usado:
                                        st.caption(f"📤 Usaste: ₡{ingreso.monto_usado:,.0f}")
                                else:
                                    st.markdown(f"**{ingreso.monto_display}**")
                                    if ingreso.moneda_original == Currency.USD:
                                        st.caption(f"Original: ${ingreso.monto_original:,.2f} USD")

                            with col3:
                                if ingreso.es_recurrente:
                                    st.markdown("🔁 **Recurrente**")
                                    if ingreso.proximo_ingreso_esperado:
                                        st.caption(
                                            f"Próximo: {ingreso.proximo_ingreso_esperado.strftime('%d/%m/%Y')}"
                                        )
                                else:
                                    st.markdown("📌 **Único**")

                                # Mostrar tipo especial si existe
                                if ingreso.tipo_especial:
                                    especial_map = {
                                        "dinero_ajeno": "💸 Ajeno",
                                        "intermediaria": "🔄 Intermediaria",
                                        "transferencia_propia": "🔁 Transferencia",
                                        "ajuste_inicial": "⚖️ Ajuste",
                                    }
                                    st.caption(especial_map.get(ingreso.tipo_especial, ingreso.tipo_especial))

                            if ingreso != ingresos_tipo[-1]:
                                st.markdown("---")


if __name__ == "__main__":
    main()
