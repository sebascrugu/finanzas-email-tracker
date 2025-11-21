"""Componentes de UI para gestión de ingresos."""

__all__ = [
    "es_tipo_recurrente",
    "calcular_proximo_ingreso",
    "formulario_agregar_ingreso",
    "listar_ingresos",
]

from datetime import date
from decimal import Decimal

import streamlit as st

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.enums import Currency, IncomeType, RecurrenceFrequency
from finanzas_tracker.models.income import Income
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.services.exchange_rate import ExchangeRateService


logger = get_logger(__name__)

TIPOS_RECURRENTES = {IncomeType.SALARY, IncomeType.PENSION}

OPCIONES_TIPO_INGRESO = [
    (IncomeType.SALARY, "Salario"),
    (IncomeType.PENSION, "Pension"),
    (IncomeType.FREELANCE, "Freelance/Proyecto"),
    (IncomeType.SALE, "Venta"),
    (IncomeType.INVESTMENT_RETURN, "Rendimiento Inversion"),
    (IncomeType.GIFT, "Regalo/Ayuda"),
    (IncomeType.OTHER, "Otro"),
]

TIPOS_ESPECIALES = {
    "ninguno": "Ninguno (ingreso normal)",
    "dinero_ajeno": "Dinero de otra persona",
    "intermediaria": "Intermediaria (paso plata)",
    "transferencia_propia": "Transferencia entre mis cuentas",
    "ajuste_inicial": "Ajuste de saldo inicial",
}


def es_tipo_recurrente(tipo: IncomeType) -> bool:
    """Determina si un tipo de ingreso es tipicamente recurrente."""
    return tipo in TIPOS_RECURRENTES


def calcular_proximo_ingreso(tipo: IncomeType, fecha_actual: date) -> date | None:
    """Calcula automaticamente el proximo ingreso esperado segun el tipo."""
    if tipo not in TIPOS_RECURRENTES:
        return None

    next_month = fecha_actual.month + 1
    year = fecha_actual.year
    if next_month > 12:
        next_month = 1
        year += 1

    try:
        return date(year, next_month, fecha_actual.day)
    except ValueError:
        return date(year, next_month, 28)


def formulario_agregar_ingreso(perfil: Profile) -> None:
    """Renderiza formulario para agregar un nuevo ingreso."""
    st.subheader("Registrar Nuevo Ingreso")

    with st.form("add_income_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            tipo_seleccionado = st.selectbox(
                "Tipo de Ingreso",
                options=OPCIONES_TIPO_INGRESO,
                format_func=lambda x: x[1],
                help="El tipo determina si es recurrente automaticamente",
            )
            tipo_income = tipo_seleccionado[0]

            descripcion = st.text_input(
                "Descripcion",
                placeholder="ej: Salario Nov 2025, Venta PS5",
                help="Descripcion breve del ingreso",
            )

            monto = st.number_input(
                "Monto",
                min_value=0.0,
                value=0.0,
                step=1000.0,
                format="%.2f",
            )

        with col2:
            moneda = st.selectbox("Moneda", options=["CRC", "USD"], index=0)
            fecha_ingreso = st.date_input(
                "Fecha del Ingreso",
                value=date.today(),
                max_value=date.today(),
            )

            es_recurrente = es_tipo_recurrente(tipo_income)
            if es_recurrente:
                st.info("Ingreso recurrente (se calculara el proximo)")
                proximo_auto = calcular_proximo_ingreso(tipo_income, fecha_ingreso)
                if proximo_auto:
                    st.caption(f"Proximo: {proximo_auto.strftime('%d/%m/%Y')}")
            else:
                st.info("Ingreso unico")

        # Campos adicionales
        st.markdown("---")
        st.markdown("### Contexto y Desglose _(opcional)_")

        contexto = st.text_area(
            "Contexto",
            placeholder="Ej: Mi mama me paso 10K para comprar dona",
            height=80,
        )

        col1, col2 = st.columns(2)
        with col1:
            es_dinero_ajeno = st.checkbox("Es dinero de otra persona")
            excluir_presupuesto = st.checkbox("Excluir de presupuesto mensual")

        with col2:
            tipo_especial = st.selectbox(
                "Tipo especial",
                options=list(TIPOS_ESPECIALES.keys()),
                format_func=lambda x: TIPOS_ESPECIALES[x],
            )

        # Desglose si es dinero ajeno
        monto_usado = 0.0
        if es_dinero_ajeno:
            st.markdown("---")
            st.markdown("#### Desglose del Dinero")
            col1, col2, col3 = st.columns(3)

            with col1:
                monto_usado = st.number_input(
                    "Monto usado",
                    min_value=0.0,
                    max_value=float(monto) if monto > 0 else 999999999.0,
                    value=0.0,
                    step=100.0,
                    format="%.2f",
                )

            with col2:
                if monto > 0:
                    monto_sobrante_calc = monto - monto_usado
                    st.metric("Monto sobrante", f"{monto_sobrante_calc:,.2f}")

            with col3:
                if monto > 0 and monto_usado > 0:
                    porcentaje_usado = (monto_usado / monto) * 100
                    st.metric("% Usado", f"{porcentaje_usado:.1f}%")

        # Submit
        st.markdown("---")
        submitted = st.form_submit_button(
            "Guardar Ingreso", type="primary", use_container_width=True
        )

        if submitted:
            _procesar_formulario_ingreso(
                perfil=perfil,
                tipo_income=tipo_income,
                descripcion=descripcion,
                monto=monto,
                moneda=moneda,
                fecha_ingreso=fecha_ingreso,
                es_recurrente=es_recurrente,
                contexto=contexto,
                es_dinero_ajeno=es_dinero_ajeno,
                excluir_presupuesto=excluir_presupuesto,
                tipo_especial=tipo_especial,
                monto_usado=monto_usado,
            )


def _procesar_formulario_ingreso(
    perfil: Profile,
    tipo_income: IncomeType,
    descripcion: str,
    monto: float,
    moneda: str,
    fecha_ingreso: date,
    es_recurrente: bool,
    contexto: str,
    es_dinero_ajeno: bool,
    excluir_presupuesto: bool,
    tipo_especial: str,
    monto_usado: float,
) -> None:
    """Procesa y guarda el formulario de ingreso."""
    # Validaciones
    if not descripcion or not descripcion.strip():
        st.error("La descripcion es requerida")
        return
    if monto <= 0:
        st.error("El monto debe ser mayor a 0")
        return
    if es_dinero_ajeno and monto_usado > monto:
        st.error("El monto usado no puede ser mayor al monto total")
        return

    try:
        monto_crc = Decimal(str(monto))
        tipo_cambio = None

        if moneda == "USD":
            with st.spinner("Obteniendo tipo de cambio..."):
                exchange_service = ExchangeRateService()
                tipo_cambio = exchange_service.get_rate(fecha_ingreso)
                monto_crc = Decimal(str(monto)) * Decimal(str(tipo_cambio))
                st.success(f"Tipo de cambio: {tipo_cambio:.2f}")

        proximo = calcular_proximo_ingreso(tipo_income, fecha_ingreso)
        frecuencia = RecurrenceFrequency.MONTHLY if es_recurrente else None

        # Calcular desglose
        monto_usado_decimal = None
        monto_sobrante_decimal = None
        if es_dinero_ajeno:
            monto_usado_decimal = Decimal(str(monto_usado)) if monto_usado > 0 else Decimal("0")
            monto_sobrante_decimal = monto_crc - monto_usado_decimal
            if moneda == "USD" and tipo_cambio:
                monto_usado_decimal = monto_usado_decimal * Decimal(str(tipo_cambio))

        tipo_especial_value = tipo_especial if tipo_especial != "ninguno" else None

        with get_session() as session:
            nuevo_ingreso = Income(
                profile_id=perfil.id,
                tipo=tipo_income,
                descripcion=descripcion.strip(),
                monto_original=Decimal(str(monto)),
                moneda_original=Currency(moneda),
                monto_crc=monto_crc,
                tipo_cambio_usado=Decimal(str(tipo_cambio)) if tipo_cambio else None,
                fecha=fecha_ingreso,
                es_recurrente=es_recurrente,
                frecuencia=frecuencia,
                proximo_ingreso_esperado=proximo,
                contexto=contexto.strip() if contexto and contexto.strip() else None,
                tipo_especial=tipo_especial_value,
                excluir_de_presupuesto=excluir_presupuesto,
                es_dinero_ajeno=es_dinero_ajeno,
                requiere_desglose=es_dinero_ajeno,
                monto_usado=monto_usado_decimal,
                monto_sobrante=monto_sobrante_decimal,
            )
            session.add(nuevo_ingreso)
            session.commit()

            st.success("Ingreso registrado exitosamente!")
            if es_dinero_ajeno and monto_sobrante_decimal:
                st.info(f"Desglose: Usaste {monto_usado_decimal:,.0f}, te quedaste {monto_sobrante_decimal:,.0f}")
            if es_recurrente and proximo:
                st.info(f"Proximo ingreso esperado: {proximo.strftime('%d/%m/%Y')}")
            st.balloons()

    except (ValueError, TypeError) as e:
        st.error(f"Error de datos: {e}")
        logger.error(f"Error en formulario ingreso: {type(e).__name__}: {e}")
    except Exception as e:
        st.error(f"Error guardando ingreso: {e}")
        logger.error(f"Error guardando ingreso: {type(e).__name__}: {e}")


def listar_ingresos(perfil: Profile) -> None:
    """Renderiza la lista de ingresos del perfil."""
    st.subheader("Lista de Ingresos")

    with get_session() as session:
        ingresos = (
            session.query(Income)
            .filter(Income.profile_id == perfil.id, Income.deleted_at.is_(None))
            .order_by(Income.fecha.desc())
            .all()
        )

        if not ingresos:
            st.info("No tienes ingresos registrados todavia")
            st.markdown("**Tip:** Los ingresos recurrentes se calculan automaticamente.")
            return

        _mostrar_resumen_ingresos(ingresos)
        st.markdown("---")
        _mostrar_ingresos_por_tipo(ingresos)


def _mostrar_resumen_ingresos(ingresos: list[Income]) -> None:
    """Muestra metricas resumen de ingresos."""
    hoy = date.today()
    total_mes = sum(
        i.calcular_monto_patrimonio()
        for i in ingresos
        if i.fecha.month == hoy.month and i.fecha.year == hoy.year
    )
    total_general = sum(i.calcular_monto_patrimonio() for i in ingresos)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total General", f"{total_general:,.0f}")
    with col2:
        st.metric("Este Mes", f"{total_mes:,.0f}")
    with col3:
        st.metric("Total Ingresos", len(ingresos))


def _mostrar_ingresos_por_tipo(ingresos: list[Income]) -> None:
    """Muestra ingresos agrupados por tipo."""
    st.markdown("### Por Tipo de Ingreso")

    tipos_agrupados: dict[str, list[Income]] = {}
    for ingreso in ingresos:
        tipo_nombre = ingreso.tipo.value
        if tipo_nombre not in tipos_agrupados:
            tipos_agrupados[tipo_nombre] = []
        tipos_agrupados[tipo_nombre].append(ingreso)

    for tipo_nombre, ingresos_tipo in sorted(tipos_agrupados.items()):
        total_tipo = sum(i.calcular_monto_patrimonio() for i in ingresos_tipo)
        icono = "recurrente" if any(i.es_recurrente for i in ingresos_tipo) else ""

        with st.expander(
            f"{icono} **{tipo_nombre.upper()}** - {total_tipo:,.0f} ({len(ingresos_tipo)} ingreso(s))",
            expanded=False,
        ):
            for ingreso in sorted(ingresos_tipo, key=lambda x: x.fecha, reverse=True):
                _renderizar_ingreso(ingreso)
                if ingreso != ingresos_tipo[-1]:
                    st.markdown("---")


def _renderizar_ingreso(ingreso: Income) -> None:
    """Renderiza un ingreso individual."""
    col1, col2, col3 = st.columns([3, 2, 1])

    with col1:
        titulo = f"**{ingreso.descripcion}**"
        if ingreso.es_dinero_ajeno:
            titulo += " (ajeno)"
        if ingreso.excluir_de_presupuesto:
            titulo += " (excluido)"
        st.markdown(titulo)
        st.caption(f"{ingreso.fecha.strftime('%d/%m/%Y')}")
        if ingreso.contexto:
            ctx = ingreso.contexto[:80] + "..." if len(ingreso.contexto) > 80 else ingreso.contexto
            st.caption(f"_{ctx}_")

    with col2:
        if ingreso.es_dinero_ajeno and ingreso.monto_sobrante is not None:
            st.markdown(f"**{ingreso.monto_crc:,.0f}** _total_")
            st.caption(f"Te quedaste: {ingreso.monto_sobrante:,.0f}")
            if ingreso.monto_usado:
                st.caption(f"Usaste: {ingreso.monto_usado:,.0f}")
        else:
            st.markdown(f"**{ingreso.monto_display}**")
            if ingreso.moneda_original == Currency.USD:
                st.caption(f"Original: ${ingreso.monto_original:,.2f} USD")

    with col3:
        if ingreso.es_recurrente:
            st.markdown("**Recurrente**")
            if ingreso.proximo_ingreso_esperado:
                st.caption(f"Proximo: {ingreso.proximo_ingreso_esperado.strftime('%d/%m/%Y')}")
        else:
            st.markdown("**Unico**")

        if ingreso.tipo_especial:
            especial_map = {
                "dinero_ajeno": "Ajeno",
                "intermediaria": "Intermediaria",
                "transferencia_propia": "Transferencia",
                "ajuste_inicial": "Ajuste",
            }
            st.caption(especial_map.get(ingreso.tipo_especial, ingreso.tipo_especial))
