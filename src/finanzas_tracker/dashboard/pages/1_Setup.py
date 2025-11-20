"""Página de Setup y Gestión de Perfiles SIMPLIFICADA."""

from datetime import date
from decimal import Decimal, InvalidOperation

from email_validator import EmailNotValidError, validate_email
import streamlit as st


st.set_page_config(
    page_title="Setup - Finanzas Tracker",
    page_icon=":gear:",
    layout="wide",
)

from pathlib import Path
import sys


src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.account import Account, AccountType
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.enums import BankName, CardType, Currency
from finanzas_tracker.models.profile import Profile


logger = get_logger(__name__)


def setup_page():
    """Página principal de setup y gestión de perfiles."""
    st.title("Setup y Gestión de Perfiles")

    with get_session() as session:
        # Verificar si existen perfiles
        perfiles = session.query(Profile).filter(Profile.activo == True).all()  # noqa: E712

        if not perfiles:
            # Primera vez: crear primer perfil
            st.info("¡Bienvenido! Vamos a crear tu primer perfil.")
            crear_perfil_nuevo(session, es_primero=True)
        else:
            # Ya hay perfiles: gestionar
            gestionar_perfiles(session, perfiles)


def gestionar_perfiles(session, perfiles: list[Profile]):
    """Gestión de perfiles existentes."""
    st.success(f"Tienes **{len(perfiles)}** perfil(es) configurado(s)")

    tab1, tab2, tab3 = st.tabs(["Mis Perfiles", "Mis Cuentas", "Crear Perfil"])

    with tab1:
        mostrar_perfiles(session, perfiles)

    with tab2:
        # Obtener perfil activo
        perfil_activo = next((p for p in perfiles if p.es_activo), None)
        if perfil_activo:
            gestionar_cuentas(session, perfil_activo)
        else:
            st.warning("No hay un perfil activo. Por favor activa un perfil primero.")

    with tab3:
        crear_perfil_nuevo(session, es_primero=False)


def mostrar_perfiles(session, perfiles: list[Profile]):
    """Muestra lista de perfiles con opciones de edición."""
    st.subheader(f"Tus Perfiles ({len(perfiles)})")

    for perfil in perfiles:
        with st.expander(
            f"{perfil.nombre_completo} {'ACTIVO' if perfil.es_activo else ''}",
            expanded=perfil.es_activo,
        ):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown(f"**Email Outlook:** {perfil.email_outlook}")
                st.markdown(f"**Nombre:** {perfil.nombre}")
                if perfil.descripcion:
                    st.markdown(f"**Descripción:** {perfil.descripcion}")
                st.markdown(f"**Icono:** {perfil.icono}")

                # Mostrar tarjetas del perfil
                tarjetas = [c for c in perfil.cards if c.activa]
                if tarjetas:
                    st.markdown(f"**Tarjetas ({len(tarjetas)}):**")
                    for card in tarjetas:
                        banco = (
                            card.banco.value.upper()
                            if hasattr(card.banco, "value")
                            else card.banco.upper()
                        )
                        tipo = (
                            card.tipo.value.capitalize()
                            if hasattr(card.tipo, "value")
                            else card.tipo.capitalize()
                        )
                        st.markdown(f"  - {banco} ****{card.ultimos_4_digitos} ({tipo})")
                else:
                    st.warning("Sin tarjetas configuradas")

                # Mostrar presupuesto
                presupuesto = next((b for b in perfil.budgets if b.fecha_fin is None), None)
                if presupuesto:
                    st.markdown(f"**Presupuesto:** ₡{presupuesto.salario_mensual:,.0f}")
                    st.markdown(f"  - 50% Necesidades: ₡{presupuesto.monto_necesidades:,.0f}")
                    st.markdown(f"  - 30% Gustos: ₡{presupuesto.monto_gustos:,.0f}")
                    st.markdown(f"  - 20% Ahorros: ₡{presupuesto.monto_ahorros:,.0f}")
                else:
                    st.warning("Sin presupuesto configurado")

            with col2:
                if not perfil.es_activo:
                    if st.button(
                        "Activar", key=f"activar_{perfil.id}", use_container_width=True
                    ):
                        activar_perfil(session, perfil)
                        st.rerun()

                if st.button("Editar", key=f"editar_{perfil.id}", use_container_width=True):
                    st.session_state[f"editing_{perfil.id}"] = True
                    st.rerun()

            # Modo edición
            if st.session_state.get(f"editing_{perfil.id}", False):
                st.markdown("---")
                editar_perfil(session, perfil)


def activar_perfil(session, perfil: Profile):
    """Activa un perfil (desactiva los demás)."""
    # Desactivar todos los perfiles
    perfiles_todos = session.query(Profile).all()
    for p in perfiles_todos:
        p.es_activo = False

    # Activar el seleccionado
    perfil.es_activo = True
    session.commit()
    st.success(f"Perfil '{perfil.nombre}' activado")


def gestionar_cuentas(session, perfil: Profile):
    """Gestión de cuentas financieras del perfil activo."""
    st.subheader(f"💰 Cuentas de {perfil.nombre}")

    # Obtener cuentas activas del perfil
    cuentas = (
        session.query(Account)
        .filter(
            Account.profile_id == perfil.id,
            Account.deleted_at.is_(None),
        )
        .order_by(Account.created_at.desc())
        .all()
    )

    # Calcular patrimonio total
    patrimonio_total = Account.calcular_patrimonio_total(session, perfil.id)
    intereses_mensuales = Account.calcular_intereses_mensuales_totales(session, perfil.id)

    # Mostrar resumen
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Cuentas", len(cuentas))
    with col2:
        st.metric("Patrimonio Total", f"₡{patrimonio_total:,.0f}")
    with col3:
        if intereses_mensuales > 0:
            st.metric("Intereses/Mes", f"₡{intereses_mensuales:,.0f}")
        else:
            st.metric("Intereses/Mes", "₡0")

    st.markdown("---")

    # Dividir en dos columnas: lista de cuentas y formulario
    col_lista, col_form = st.columns([2, 1])

    with col_lista:
        st.markdown("### Mis Cuentas")

        if cuentas:
            for cuenta in cuentas:
                with st.expander(
                    f"{'✅' if cuenta.activa else '❌'} {cuenta.nombre} - "
                    f"{cuenta.moneda} {cuenta.saldo_actual:,.2f}",
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
                            st.markdown(f"**Tasa de interés:** {cuenta.tasa_interes}% anual ({cuenta.tipo_interes})")
                            interes_mensual = cuenta.calcular_interes_mensual()
                            st.markdown(f"**Interés mensual:** ₡{interes_mensual:,.0f}")

                            if cuenta.fecha_vencimiento:
                                st.markdown(f"**Fecha vencimiento:** {cuenta.fecha_vencimiento}")

                        if cuenta.descripcion:
                            st.markdown(f"**Descripción:** {cuenta.descripcion}")

                        st.markdown(
                            f"**Estado:** {'Activa' if cuenta.activa else 'Inactiva'} | "
                            f"{'Incluida' if cuenta.incluir_en_patrimonio else 'Excluida'} del patrimonio"
                        )

                    with col2:
                        if st.button("Editar", key=f"edit_acc_{cuenta.id}", use_container_width=True):
                            st.session_state[f"editing_account_{cuenta.id}"] = True
                            st.rerun()

                        if cuenta.activa:
                            if st.button("Desactivar", key=f"deact_acc_{cuenta.id}", use_container_width=True):
                                cuenta.activa = False
                                session.commit()
                                st.success("Cuenta desactivada")
                                st.rerun()
                        else:
                            if st.button("Activar", key=f"act_acc_{cuenta.id}", use_container_width=True):
                                cuenta.activa = True
                                session.commit()
                                st.success("Cuenta activada")
                                st.rerun()

                    # Formulario de edición
                    if st.session_state.get(f"editing_account_{cuenta.id}", False):
                        st.markdown("---")
                        editar_cuenta(session, cuenta)
        else:
            st.info("No tienes cuentas registradas. Agrega tu primera cuenta en el formulario →")

    with col_form:
        st.markdown("### Agregar Cuenta")
        crear_cuenta_form(session, perfil)


def editar_cuenta(session, cuenta: Account):
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

        # Campos de interés (solo para savings, cdp, investment)
        if tipo in ["savings", "cdp", "investment"]:
            st.markdown("**Configuración de Intereses**")
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

        descripcion = st.text_area("Descripción:", value=cuenta.descripcion or "")

        incluir_patrimonio = st.checkbox(
            "Incluir en patrimonio total",
            value=cuenta.incluir_en_patrimonio,
        )

        col1, col2 = st.columns(2)
        with col1:
            guardar = st.form_submit_button("Guardar", type="primary", use_container_width=True)
        with col2:
            cancelar = st.form_submit_button("Cancelar", use_container_width=True)

        if guardar:
            cuenta.nombre = nombre
            cuenta.tipo = tipo
            cuenta.banco = banco if banco else None
            cuenta.saldo_actual = Decimal(str(saldo))
            cuenta.moneda = moneda
            cuenta.descripcion = descripcion if descripcion else None
            cuenta.incluir_en_patrimonio = incluir_patrimonio

            if tipo in ["savings", "cdp", "investment"]:
                cuenta.tasa_interes = Decimal(str(tasa)) if tasa > 0 else None
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

        if cancelar:
            st.session_state[f"editing_account_{cuenta.id}"] = False
            st.rerun()


def crear_cuenta_form(session, perfil: Profile):
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
                "investment": "Inversión",
                "cdp": "CDP (Certificado de Depósito)",
                "cash": "Efectivo",
            }[x],
        )

        banco = st.text_input(
            "Banco:",
            placeholder="Banco Popular",
            help="Nombre del banco o institución financiera",
        )

        col1, col2 = st.columns(2)
        with col1:
            saldo = st.number_input(
                "Saldo actual:",
                min_value=0.0,
                value=0.0,
                step=1000.0,
                format="%.2f",
                help="Saldo actual en la moneda seleccionada",
            )
        with col2:
            moneda = st.selectbox(
                "Moneda:",
                options=[e.value for e in Currency],
                index=0,  # CRC por defecto
            )

        # Campos de interés (solo para savings, cdp, investment)
        tasa = None
        tipo_interes = "simple"
        fecha_vencimiento = None
        plazo_meses = None

        if tipo in ["savings", "cdp", "investment"]:
            st.markdown("**Configuración de Intereses** _(opcional)_")
            col1, col2 = st.columns(2)
            with col1:
                tasa = st.number_input(
                    "Tasa anual (%):",
                    min_value=0.0,
                    max_value=100.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    help="Ejemplo: 6.00 para 6% anual",
                )
            with col2:
                tipo_interes = st.selectbox(
                    "Tipo:",
                    options=["simple", "compuesto"],
                    index=0,
                )

            if tipo == "cdp":
                col1, col2 = st.columns(2)
                with col1:
                    fecha_vencimiento = st.date_input(
                        "Fecha vencimiento:",
                        value=date.today(),
                    )
                with col2:
                    plazo_meses = st.number_input(
                        "Plazo (meses):",
                        min_value=1,
                        value=1,
                        step=1,
                    )

        descripcion = st.text_area(
            "Descripción:",
            placeholder="Notas adicionales sobre esta cuenta",
            help="Opcional",
        )

        incluir_patrimonio = st.checkbox(
            "Incluir en cálculo de patrimonio total",
            value=True,
            help="Desmarca si no quieres que esta cuenta se incluya en tu patrimonio total",
        )

        crear = st.form_submit_button("Crear Cuenta", type="primary", use_container_width=True)

        if crear:
            # Validaciones
            if not nombre:
                st.error("El nombre es obligatorio")
                return

            if saldo < 0:
                st.error("El saldo no puede ser negativo")
                return

            try:
                # Crear cuenta
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

                st.success(f"✅ Cuenta '{nombre}' creada exitosamente!")
                st.rerun()

            except Exception as e:
                session.rollback()
                st.error(f"Error al crear la cuenta: {e}")
                logger.error(f"Error creando cuenta: {e}")


def editar_perfil(session, perfil: Profile):
    """Formulario para editar un perfil."""
    st.subheader(f"Editando: {perfil.nombre}")

    with st.form(f"edit_perfil_{perfil.id}"):
        nuevo_nombre = st.text_input("Nombre:", value=perfil.nombre)
        nueva_desc = st.text_area("Descripción:", value=perfil.descripcion or "")
        nuevo_icono = st.text_input("Icono (emoji):", value=perfil.icono or ":person:")

        col1, col2 = st.columns(2)
        with col1:
            guardar = st.form_submit_button("Guardar", type="primary", use_container_width=True)
        with col2:
            cancelar = st.form_submit_button("Cancelar", use_container_width=True)

        if guardar:
            perfil.nombre = nuevo_nombre
            perfil.descripcion = nueva_desc if nueva_desc else None
            perfil.icono = nuevo_icono
            session.commit()
            st.session_state[f"editing_{perfil.id}"] = False
            st.success("Perfil actualizado")
            st.rerun()

        if cancelar:
            st.session_state[f"editing_{perfil.id}"] = False
            st.rerun()


def crear_perfil_nuevo(session, es_primero: bool = False):
    """Formulario para crear un nuevo perfil."""
    if es_primero:
        st.subheader("Crea Tu Primer Perfil")
        st.markdown("""
        Un perfil agrupa:
        - Tu email de Outlook (donde recibes correos bancarios)
        - Tus tarjetas bancarias
        - Tu presupuesto mensual
        - Tus transacciones e ingresos
        
        **Ejemplo:** Si tienes finanzas personales y de negocio, puedes crear dos perfiles separados.
        """)
    else:
        st.subheader("Crear Nuevo Perfil")
        st.markdown("""
        Crea un nuevo perfil para separar diferentes contextos financieros:
        - Personal
        - Negocio
        - Familia (ej: finanzas de tu mamá en su email)
        """)

    with st.form("crear_perfil_form"):
        st.markdown("#### 1. Información del Perfil")
        col1, col2 = st.columns(2)
        with col1:
            email_outlook = st.text_input(
                "Email de Outlook:",
                placeholder="tu.email@outlook.com",
                help="Email donde recibes los correos bancarios",
            )
            nombre = st.text_input(
                "Nombre del perfil:", placeholder="Personal", help="Ej: Personal, Negocio, Mamá"
            )
        with col2:
            icono = st.text_input(
                "Icono (emoji):", value=":person:", help="Un emoji que represente este perfil"
            )
            descripcion = st.text_area(
                "Descripción (opcional):", placeholder="Mis finanzas personales"
            )

        st.markdown("#### 2. Presupuesto Mensual")
        salario_str = st.text_input(
            "Salario/Ingreso NETO mensual (₡):",
            placeholder="280000",
            help="Tu salario mensual neto en colones (después de impuestos)",
        )

        salario = Decimal(0)
        if salario_str:
            try:
                salario = Decimal(salario_str.replace(",", ""))
                if salario > 0:
                    st.info(
                        f"""
                    **Distribución 50/30/20 (automática):**
                    - 50% Necesidades: ₡{(salario * Decimal('0.50')):,.0f}
                    - 30% Gustos: ₡{(salario * Decimal('0.30')):,.0f}
                    - 20% Ahorros: ₡{(salario * Decimal('0.20')):,.0f}
                    """
                    )
            except (ValueError, InvalidOperation):
                st.error("Formato inválido. Usa solo números (ej: 280000)")

        st.markdown("#### 3. Tarjetas Bancarias")
        st.info("Agrega al menos una tarjeta para este perfil")

        # Lista de tarjetas a agregar
        if "new_profile_cards" not in st.session_state:
            st.session_state["new_profile_cards"] = []

        # Mostrar tarjetas agregadas
        if st.session_state["new_profile_cards"]:
            st.markdown("**Tarjetas a agregar:**")
            for i, card_data in enumerate(st.session_state["new_profile_cards"]):
                col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 2, 0.5])
                with col1:
                    st.write(f"****{card_data[0]}")
                with col2:
                    st.write(card_data[1].capitalize())
                with col3:
                    st.write(card_data[2].upper())
                with col4:
                    st.write(card_data[3] if card_data[3] else "N/A")
                with col5:
                    if st.form_submit_button("Eliminar", key=f"del_card_{i}"):
                        st.session_state["new_profile_cards"].pop(i)
                        st.rerun()

        # Formulario para agregar tarjeta
        col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 2, 1])
        with col1:
            ultimos_4 = st.text_input("Últimos 4", max_chars=4, key="card_digits")
        with col2:
            tipo_card = st.selectbox("Tipo", options=[e.value for e in CardType], key="card_type")
        with col3:
            banco_card = st.selectbox("Banco", options=[e.value for e in BankName], key="card_bank")
        with col4:
            alias_card = st.text_input("Alias (opcional)", key="card_alias")
        with col5:
            st.write("")  # Spacing
            add_card_btn = st.form_submit_button("Agregar", help="Agregar tarjeta")

        if add_card_btn:
            # Validar que los últimos 4 dígitos sean exactamente 4 números
            if not ultimos_4:
                st.error("Debes ingresar los últimos 4 dígitos")
            elif not ultimos_4.isdigit():
                st.error("Los últimos 4 dígitos deben ser solo números")
            elif len(ultimos_4) != 4:
                st.error("Debes ingresar exactamente 4 dígitos")
            else:
                st.session_state["new_profile_cards"].append(
                    (ultimos_4, tipo_card, banco_card, alias_card)
                )
                st.rerun()

        st.markdown("---")
        crear = st.form_submit_button("Crear Perfil", type="primary", use_container_width=True)

        if crear:
            # Validaciones
            if not email_outlook:
                st.error("Debes ingresar un email")
                return

            # Validar formato de email
            try:
                validate_email(email_outlook, check_deliverability=False)
            except EmailNotValidError as e:
                st.error(f"Email inválido: {e!s}")
                return
            if not nombre:
                st.error("Debes poner un nombre al perfil")
                return
            if salario <= 0:
                st.error("Debes ingresar un salario válido")
                return
            if not st.session_state["new_profile_cards"]:
                st.error("Debes agregar al menos una tarjeta")
                return

            try:
                # 1. Crear perfil
                nuevo_perfil = Profile(
                    email_outlook=email_outlook,
                    nombre=nombre,
                    descripcion=descripcion if descripcion else None,
                    icono=icono,
                    es_activo=True,  # Siempre activo al crear
                    activo=True,
                )
                session.add(nuevo_perfil)
                session.flush()

                # Desactivar otros perfiles si no es el primero
                if not es_primero:
                    otros_perfiles = (
                        session.query(Profile).filter(Profile.id != nuevo_perfil.id).all()
                    )
                    for p in otros_perfiles:
                        p.es_activo = False

                # 2. Crear presupuesto
                nuevo_presupuesto = Budget(
                    profile_id=nuevo_perfil.id,
                    salario_mensual=salario,
                    fecha_inicio=date.today(),
                    porcentaje_necesidades=Decimal("50.00"),
                    porcentaje_gustos=Decimal("30.00"),
                    porcentaje_ahorros=Decimal("20.00"),
                )
                session.add(nuevo_presupuesto)

                # 3. Crear tarjetas
                for card_data in st.session_state["new_profile_cards"]:
                    nueva_tarjeta = Card(
                        profile_id=nuevo_perfil.id,
                        ultimos_4_digitos=card_data[0],
                        tipo=CardType(card_data[1]),
                        banco=BankName(card_data[2]),
                        alias=card_data[3] if card_data[3] else None,
                        activa=True,
                    )
                    session.add(nueva_tarjeta)

                session.commit()

                # Limpiar estado
                st.session_state["new_profile_cards"] = []

                st.success(f"Perfil '{nombre}' creado exitosamente!")
                st.balloons()

                if es_primero:
                    st.info(
                        "¡Perfecto! Ahora ve a **Transacciones** para procesar tus correos"
                    )

                st.rerun()

            except Exception as e:
                session.rollback()
                st.error(f"Error: {e}")
                logger.error(f"Error creando perfil: {e}")


if __name__ == "__main__":
    setup_page()
