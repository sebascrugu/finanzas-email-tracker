"""Componentes de UI para gestión de cuentas financieras."""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session
import streamlit as st

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.account import Account, AccountType
from finanzas_tracker.models.enums import Currency
from finanzas_tracker.models.profile import Profile


logger = get_logger(__name__)


def gestionar_cuentas(session: Session, perfil: Profile) -> None:
    """Gestión de cuentas financieras del perfil activo."""
    st.subheader(f"Cuentas de {perfil.nombre}")

    cuentas = (
        session.query(Account)
        .filter(
            Account.profile_id == perfil.id,
            Account.deleted_at.is_(None),
        )
        .order_by(Account.created_at.desc())
        .all()
    )

    patrimonio_total = Account.calcular_patrimonio_total(session, perfil.id)
    intereses_mensuales = Account.calcular_intereses_mensuales_totales(session, perfil.id)

    # Mostrar resumen
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Cuentas", len(cuentas))
    with col2:
        st.metric("Patrimonio Total", f"₡{patrimonio_total:,.0f}")
    with col3:
        st.metric(
            "Intereses/Mes", f"₡{intereses_mensuales:,.0f}" if intereses_mensuales > 0 else "₡0"
        )

    st.markdown("---")

    col_lista, col_form = st.columns([2, 1])

    with col_lista:
        st.markdown("### Mis Cuentas")
        if cuentas:
            _mostrar_lista_cuentas(session, cuentas)
        else:
            st.info("No tienes cuentas registradas. Agrega tu primera cuenta en el formulario.")

    with col_form:
        st.markdown("### Agregar Cuenta")
        crear_cuenta_form(session, perfil)


def _mostrar_lista_cuentas(session: Session, cuentas: list[Account]) -> None:
    """Muestra la lista de cuentas con opciones de edición."""
    for cuenta in cuentas:
        icono = "✅" if cuenta.activa else "❌"
        with st.expander(
            f"{icono} {cuenta.nombre} - {cuenta.moneda} {cuenta.saldo_actual:,.2f}",
            expanded=False,
        ):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**Tipo:** {cuenta.tipo}")
                if cuenta.banco:
                    st.markdown(f"**Banco:** {cuenta.banco}")
                st.markdown(f"**Saldo:** {cuenta.moneda} {cuenta.saldo_actual:,.2f}")
                st.markdown(f"**En colones:** ₡{cuenta.saldo_crc:,.0f}")

                if cuenta.tasa_interes and cuenta.tasa_interes > 0:
                    st.markdown(
                        f"**Tasa de interes:** {cuenta.tasa_interes}% anual ({cuenta.tipo_interes})"
                    )
                    interes_mensual = cuenta.calcular_interes_mensual()
                    st.markdown(f"**Interes mensual:** ₡{interes_mensual:,.0f}")
                    if cuenta.fecha_vencimiento:
                        st.markdown(f"**Fecha vencimiento:** {cuenta.fecha_vencimiento}")

                if cuenta.descripcion:
                    st.markdown(f"**Descripcion:** {cuenta.descripcion}")

                estado_patrimonio = "Incluida" if cuenta.incluir_en_patrimonio else "Excluida"
                st.markdown(
                    f"**Estado:** {'Activa' if cuenta.activa else 'Inactiva'} | {estado_patrimonio} del patrimonio"
                )

            with col2:
                if st.button("Editar", key=f"edit_acc_{cuenta.id}", use_container_width=True):
                    st.session_state[f"editing_account_{cuenta.id}"] = True
                    st.rerun()

                if cuenta.activa:
                    if st.button(
                        "Desactivar", key=f"deact_acc_{cuenta.id}", use_container_width=True
                    ):
                        cuenta.activa = False
                        session.commit()
                        st.success("Cuenta desactivada")
                        st.rerun()
                elif st.button("Activar", key=f"act_acc_{cuenta.id}", use_container_width=True):
                    cuenta.activa = True
                    session.commit()
                    st.success("Cuenta activada")
                    st.rerun()

            if st.session_state.get(f"editing_account_{cuenta.id}", False):
                st.markdown("---")
                editar_cuenta(session, cuenta)


def editar_cuenta(session: Session, cuenta: Account) -> None:
    """Formulario para editar una cuenta existente."""
    st.markdown("**Editar Cuenta**")

    with st.form(f"edit_cuenta_{cuenta.id}"):
        nombre = st.text_input("Nombre:", value=cuenta.nombre)
        tipo = st.selectbox(
            "Tipo:",
            options=[e.value for e in AccountType],
            index=[e.value for e in AccountType].index(cuenta.tipo),
        )
        banco = st.text_input("Banco:", value=cuenta.banco or "")

        col1, col2 = st.columns(2)
        with col1:
            saldo = st.number_input(
                "Saldo:",
                min_value=0.0,
                value=float(cuenta.saldo_actual),
                step=1000.0,
                format="%.2f",
            )
        with col2:
            moneda = st.selectbox(
                "Moneda:",
                options=[e.value for e in Currency],
                index=[e.value for e in Currency].index(cuenta.moneda),
            )

        # Campos de interes para cuentas con rendimiento
        tasa = None
        tipo_interes = cuenta.tipo_interes or "simple"
        fecha_vencimiento = cuenta.fecha_vencimiento
        plazo_meses = cuenta.plazo_meses

        if tipo in ["savings", "cdp", "investment"]:
            st.markdown("**Configuracion de Intereses**")
            col1, col2 = st.columns(2)
            with col1:
                tasa = st.number_input(
                    "Tasa anual (%):",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(cuenta.tasa_interes) if cuenta.tasa_interes else 0.0,
                    step=0.01,
                    format="%.2f",
                )
            with col2:
                tipo_interes = st.selectbox(
                    "Tipo:",
                    options=["simple", "compuesto"],
                    index=0 if cuenta.tipo_interes == "simple" else 1,
                )

            if tipo == "cdp":
                col1, col2 = st.columns(2)
                with col1:
                    fecha_vencimiento = st.date_input(
                        "Vencimiento:",
                        value=cuenta.fecha_vencimiento or date.today(),
                    )
                with col2:
                    plazo_meses = st.number_input(
                        "Plazo (meses):",
                        min_value=1,
                        value=cuenta.plazo_meses or 1,
                    )

        descripcion = st.text_area("Descripcion:", value=cuenta.descripcion or "")
        incluir_patrimonio = st.checkbox(
            "Incluir en patrimonio total", value=cuenta.incluir_en_patrimonio
        )

        col1, col2 = st.columns(2)
        with col1:
            guardar = st.form_submit_button("Guardar", type="primary", use_container_width=True)
        with col2:
            cancelar = st.form_submit_button("Cancelar", use_container_width=True)

        if guardar:
            _guardar_cuenta_editada(
                session,
                cuenta,
                nombre,
                tipo,
                banco,
                saldo,
                moneda,
                descripcion,
                incluir_patrimonio,
                tasa,
                tipo_interes,
                fecha_vencimiento,
                plazo_meses,
            )

        if cancelar:
            st.session_state[f"editing_account_{cuenta.id}"] = False
            st.rerun()


def _guardar_cuenta_editada(
    session: Session,
    cuenta: Account,
    nombre: str,
    tipo: str,
    banco: str,
    saldo: float,
    moneda: str,
    descripcion: str,
    incluir_patrimonio: bool,
    tasa: float | None,
    tipo_interes: str,
    fecha_vencimiento: date | None,
    plazo_meses: int | None,
) -> None:
    """Guarda los cambios en una cuenta."""
    cuenta.nombre = nombre
    cuenta.tipo = tipo
    cuenta.banco = banco if banco else None
    cuenta.saldo_actual = Decimal(str(saldo))
    cuenta.moneda = moneda
    cuenta.descripcion = descripcion if descripcion else None
    cuenta.incluir_en_patrimonio = incluir_patrimonio

    if tipo in ["savings", "cdp", "investment"]:
        cuenta.tasa_interes = Decimal(str(tasa)) if tasa and tasa > 0 else None
        cuenta.tipo_interes = tipo_interes
        if tipo == "cdp":
            cuenta.fecha_vencimiento = fecha_vencimiento
            cuenta.plazo_meses = plazo_meses
    else:
        cuenta.tasa_interes = None
        cuenta.tipo_interes = None
        cuenta.fecha_vencimiento = None
        cuenta.plazo_meses = None

    session.commit()
    st.session_state[f"editing_account_{cuenta.id}"] = False
    st.success("Cuenta actualizada")
    st.rerun()


def crear_cuenta_form(session: Session, perfil: Profile) -> None:
    """Formulario para crear una nueva cuenta."""
    with st.form("crear_cuenta_form"):
        nombre = st.text_input(
            "Nombre:",
            placeholder="Cuenta Vista Popular 6%",
            help="Nombre descriptivo de la cuenta",
        )

        tipo = st.selectbox(
            "Tipo:",
            options=[e.value for e in AccountType],
            format_func=lambda x: {
                "checking": "Cuenta Corriente",
                "savings": "Cuenta de Ahorros",
                "investment": "Inversion",
                "cdp": "CDP (Certificado de Deposito)",
                "cash": "Efectivo",
            }.get(x, x),
        )

        banco = st.text_input(
            "Banco:",
            placeholder="Banco Popular",
            help="Nombre del banco o institucion financiera",
        )

        col1, col2 = st.columns(2)
        with col1:
            saldo = st.number_input(
                "Saldo actual:",
                min_value=0.0,
                value=0.0,
                step=1000.0,
                format="%.2f",
            )
        with col2:
            moneda = st.selectbox("Moneda:", options=[e.value for e in Currency], index=0)

        # Campos de interes
        tasa = None
        tipo_interes = "simple"
        fecha_vencimiento = None
        plazo_meses = None

        if tipo in ["savings", "cdp", "investment"]:
            st.markdown("**Configuracion de Intereses** _(opcional)_")
            col1, col2 = st.columns(2)
            with col1:
                tasa = st.number_input(
                    "Tasa anual (%):",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                )
            with col2:
                tipo_interes = st.selectbox("Tipo:", options=["simple", "compuesto"], index=0)

            if tipo == "cdp":
                col1, col2 = st.columns(2)
                with col1:
                    fecha_vencimiento = st.date_input("Fecha vencimiento:", value=date.today())
                with col2:
                    plazo_meses = st.number_input("Plazo (meses):", min_value=1, value=1, step=1)

        descripcion = st.text_area("Descripcion:", placeholder="Notas adicionales")
        incluir_patrimonio = st.checkbox("Incluir en calculo de patrimonio total", value=True)

        crear = st.form_submit_button("Crear Cuenta", type="primary", use_container_width=True)

        if crear:
            _crear_cuenta(
                session,
                perfil,
                nombre,
                tipo,
                banco,
                saldo,
                moneda,
                descripcion,
                incluir_patrimonio,
                tasa,
                tipo_interes,
                fecha_vencimiento,
                plazo_meses,
            )


def _crear_cuenta(
    session: Session,
    perfil: Profile,
    nombre: str,
    tipo: str,
    banco: str,
    saldo: float,
    moneda: str,
    descripcion: str,
    incluir_patrimonio: bool,
    tasa: float | None,
    tipo_interes: str,
    fecha_vencimiento: date | None,
    plazo_meses: int | None,
) -> None:
    """Crea una nueva cuenta."""
    if not nombre:
        st.error("El nombre es obligatorio")
        return

    if saldo < 0:
        st.error("El saldo no puede ser negativo")
        return

    try:
        nueva_cuenta = Account(
            profile_id=perfil.id,
            nombre=nombre,
            tipo=tipo,
            banco=banco if banco else None,
            saldo_actual=Decimal(str(saldo)),
            moneda=moneda,
            descripcion=descripcion if descripcion else None,
            tasa_interes=Decimal(str(tasa)) if tasa and tasa > 0 else None,
            tipo_interes=tipo_interes if tasa and tasa > 0 else None,
            fecha_vencimiento=fecha_vencimiento if tipo == "cdp" else None,
            plazo_meses=plazo_meses if tipo == "cdp" else None,
            activa=True,
            incluir_en_patrimonio=incluir_patrimonio,
        )

        session.add(nueva_cuenta)
        session.commit()
        st.success(f"Cuenta '{nombre}' creada exitosamente!")
        st.rerun()

    except Exception as e:
        session.rollback()
        st.error(f"Error al crear la cuenta: {e}")
        logger.error(f"Error creando cuenta: {e}")
