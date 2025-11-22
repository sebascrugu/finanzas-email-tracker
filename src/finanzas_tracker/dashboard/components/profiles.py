"""Componentes de UI para gestión de perfiles."""

from datetime import date
from decimal import Decimal, InvalidOperation

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.orm import Session
import streamlit as st

from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.enums import BankName, CardType
from finanzas_tracker.models.profile import Profile


logger = get_logger(__name__)


def mostrar_perfiles(session: Session, perfiles: list[Profile]) -> None:
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
                    st.markdown(f"**Descripcion:** {perfil.descripcion}")
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
                        alias_text = f" ({card.alias})" if card.alias else ""
                        st.markdown(f"- ****{card.ultimos_4_digitos} - {banco} {tipo}{alias_text}")

            with col2:
                if st.button("Editar", key=f"edit_{perfil.id}", use_container_width=True):
                    st.session_state[f"editing_{perfil.id}"] = True
                    st.rerun()

                if not perfil.es_activo:
                    if st.button("Activar", key=f"activate_{perfil.id}", use_container_width=True):
                        activar_perfil(session, perfil)
                        st.rerun()
                else:
                    st.success("Activo")

            # Formulario de edición inline
            if st.session_state.get(f"editing_{perfil.id}", False):
                st.markdown("---")
                editar_perfil(session, perfil)


def activar_perfil(session: Session, perfil: Profile) -> None:
    """Activa un perfil y desactiva los demás."""
    perfiles_todos = session.query(Profile).all()
    for p in perfiles_todos:
        p.es_activo = False

    perfil.es_activo = True
    session.commit()
    st.success(f"Perfil '{perfil.nombre}' activado")


def editar_perfil(session: Session, perfil: Profile) -> None:
    """Formulario para editar un perfil."""
    st.subheader(f"Editando: {perfil.nombre}")

    with st.form(f"edit_perfil_{perfil.id}"):
        nuevo_nombre = st.text_input("Nombre:", value=perfil.nombre)
        nueva_desc = st.text_area("Descripcion:", value=perfil.descripcion or "")
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


def crear_perfil_nuevo(session: Session, es_primero: bool = False) -> None:
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
        - Familia (ej: finanzas de tu mama en su email)
        """)

    with st.form("crear_perfil_form"):
        # Sección 1: Información del perfil
        st.markdown("#### 1. Informacion del Perfil")
        col1, col2 = st.columns(2)
        with col1:
            email_outlook = st.text_input(
                "Email de Outlook:",
                placeholder="tu.email@outlook.com",
                help="Email donde recibes los correos bancarios",
            )
            nombre = st.text_input("Nombre del perfil:", placeholder="Personal")
        with col2:
            icono = st.text_input("Icono (emoji):", value=":person:")
            descripcion = st.text_area(
                "Descripcion (opcional):", placeholder="Mis finanzas personales"
            )

        # Sección 2: Presupuesto
        st.markdown("#### 2. Presupuesto Mensual")
        salario_str = st.text_input(
            "Salario/Ingreso NETO mensual (₡):",
            placeholder="280000",
            help="Tu salario mensual neto en colones",
        )

        salario = Decimal(0)
        if salario_str:
            try:
                salario = Decimal(salario_str.replace(",", ""))
                if salario > 0:
                    st.info(f"""
                    **Distribucion 50/30/20 (automatica):**
                    - 50% Necesidades: ₡{(salario * Decimal('0.50')):,.0f}
                    - 30% Gustos: ₡{(salario * Decimal('0.30')):,.0f}
                    - 20% Ahorros: ₡{(salario * Decimal('0.20')):,.0f}
                    """)
            except (ValueError, InvalidOperation):
                st.error("Formato invalido. Usa solo numeros (ej: 280000)")

        # Sección 3: Tarjetas
        st.markdown("#### 3. Tarjetas Bancarias")
        st.info("Agrega al menos una tarjeta para este perfil")

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
            ultimos_4 = st.text_input("Ultimos 4", max_chars=4, key="card_digits")
        with col2:
            tipo_card = st.selectbox("Tipo", options=[e.value for e in CardType], key="card_type")
        with col3:
            banco_card = st.selectbox("Banco", options=[e.value for e in BankName], key="card_bank")
        with col4:
            alias_card = st.text_input("Alias (opcional)", key="card_alias")
        with col5:
            st.write("")
            add_card_btn = st.form_submit_button("Agregar", help="Agregar tarjeta")

        if add_card_btn:
            if not ultimos_4:
                st.error("Debes ingresar los ultimos 4 digitos")
            elif not ultimos_4.isdigit():
                st.error("Los ultimos 4 digitos deben ser solo numeros")
            elif len(ultimos_4) != 4:
                st.error("Debes ingresar exactamente 4 digitos")
            else:
                st.session_state["new_profile_cards"].append(
                    (ultimos_4, tipo_card, banco_card, alias_card)
                )
                st.rerun()

        st.markdown("---")
        crear = st.form_submit_button("Crear Perfil", type="primary", use_container_width=True)

        if crear:
            _crear_perfil(session, email_outlook, nombre, descripcion, icono, salario, es_primero)


def _crear_perfil(
    session: Session,
    email_outlook: str,
    nombre: str,
    descripcion: str,
    icono: str,
    salario: Decimal,
    es_primero: bool,
) -> None:
    """Crea un nuevo perfil con validaciones."""
    # Validaciones
    if not email_outlook:
        st.error("Debes ingresar un email")
        return

    try:
        validate_email(email_outlook, check_deliverability=False)
    except EmailNotValidError as e:
        st.error(f"Email invalido: {e!s}")
        return

    if not nombre:
        st.error("Debes poner un nombre al perfil")
        return

    if salario <= 0:
        st.error("Debes ingresar un salario valido")
        return

    if not st.session_state.get("new_profile_cards"):
        st.error("Debes agregar al menos una tarjeta")
        return

    try:
        # 1. Crear perfil
        nuevo_perfil = Profile(
            email_outlook=email_outlook,
            nombre=nombre,
            descripcion=descripcion if descripcion else None,
            icono=icono,
            es_activo=True,
            activo=True,
        )
        session.add(nuevo_perfil)
        session.flush()

        # Desactivar otros perfiles si no es el primero
        if not es_primero:
            otros_perfiles = session.query(Profile).filter(Profile.id != nuevo_perfil.id).all()
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
            st.info("Ahora ve a **Transacciones** para procesar tus correos")

        st.rerun()

    except Exception as e:
        session.rollback()
        st.error(f"Error: {e}")
        logger.error(f"Error creando perfil: {e}")
