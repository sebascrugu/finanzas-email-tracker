"""Página de Setup/Onboarding para configurar el usuario."""

import streamlit as st
from decimal import Decimal
from datetime import date

st.set_page_config(
    page_title="Setup - Finanzas Tracker",
    page_icon="⚙️",
    layout="wide",
)

import sys
from pathlib import Path

src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.user import User
from finanzas_tracker.models.budget import Budget
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.enums import CardType, BankName

logger = get_logger(__name__)


def check_user_exists() -> User | None:
    """Verifica si existe un usuario activo."""
    with get_session() as session:
        return session.query(User).filter(User.activo == True).first()  # noqa: E712


def main():
    st.title("⚙️ Configuración de Usuario")

    # Verificar si ya existe usuario
    existing_user = check_user_exists()

    if existing_user:
        st.success(f"✅ Usuario configurado: **{existing_user.nombre}** ({existing_user.email})")

        st.markdown("---")
        st.info(
            "💡 **Ya tienes un usuario configurado.** Para cambiar la configuración, puedes ir a **Configuración** en el menú."
        )

        if st.button("🏠 Ir al Dashboard"):
            st.switch_page("app.py")

        return

    # Formulario de setup
    st.markdown("""
    ### 👋 ¡Bienvenido!
    
    Vamos a configurar tu cuenta paso a paso. Solo tomará unos minutos.
    """)

    st.markdown("---")

    with st.form("setup_form"):
        st.subheader("📋 Información Personal")

        email = st.text_input(
            "📧 Email (Outlook/Hotmail)",
            placeholder="tu.email@outlook.com",
            help="El email de tu cuenta de Outlook que recibe las notificaciones bancarias",
        )

        nombre = st.text_input("👤 Nombre Completo", placeholder="Juan Pérez")

        st.markdown("---")
        st.subheader("💰 Presupuesto Mensual")

        st.info("""
        **Salario NETO:** Es tu salario después de deducciones (lo que realmente recibes).
        
        La regla 50/30/20 se calculará automáticamente:
        - **50% Necesidades** (transporte, trabajo, servicios)
        - **30% Gustos** (entretenimiento, comida, shopping)
        - **20% Ahorros** (ahorro regular, metas)
        """)

        salario = st.number_input(
            "💵 Salario Mensual NETO (en colones)",
            min_value=0,
            value=280000,
            step=10000,
            format="%d",
            help="Tu ingreso mensual neto (después de deducciones)",
        )

        # Mostrar distribución
        if salario > 0:
            col1, col2, col3 = st.columns(3)

            necesidades = salario * 0.50
            gustos = salario * 0.30
            ahorros = salario * 0.20

            with col1:
                st.metric("🏠 Necesidades (50%)", f"₡{necesidades:,.0f}")
            with col2:
                st.metric("🎉 Gustos (30%)", f"₡{gustos:,.0f}")
            with col3:
                st.metric("💎 Ahorros (20%)", f"₡{ahorros:,.0f}")

        st.markdown("---")
        st.subheader("💳 Tarjetas Bancarias")

        st.info("""
        Registra tus tarjetas para que el sistema pueda detectar automáticamente
        si una transacción es de débito o crédito.
        
        **No te preocupes:** Solo guardamos los últimos 4 dígitos por seguridad.
        """)

        # Tarjeta 1
        with st.expander("➕ Agregar Tarjeta 1", expanded=True):
            card1_digits = st.text_input(
                "Últimos 4 dígitos", key="card1_digits", max_chars=4, placeholder="6380"
            )

            card1_type = st.selectbox(
                "Tipo de Tarjeta", options=["debito", "credito"], key="card1_type"
            )

            card1_bank = st.selectbox(
                "Banco",
                options=["bac", "popular"],
                key="card1_bank",
                format_func=lambda x: "BAC Credomatic" if x == "bac" else "Banco Popular",
            )

            card1_alias = st.text_input(
                "Alias (opcional)", key="card1_alias", placeholder="ej: Tarjeta Principal"
            )

            if card1_type == "credito":
                card1_limit = st.number_input(
                    "Límite de Crédito (opcional)",
                    min_value=0,
                    value=0,
                    step=50000,
                    key="card1_limit",
                    format="%d",
                )
            else:
                card1_limit = None

        # Tarjeta 2 (opcional)
        with st.expander("➕ Agregar Tarjeta 2 (Opcional)"):
            card2_digits = st.text_input(
                "Últimos 4 dígitos", key="card2_digits", max_chars=4, placeholder="3640"
            )

            if card2_digits:
                card2_type = st.selectbox(
                    "Tipo de Tarjeta", options=["debito", "credito"], key="card2_type"
                )

                card2_bank = st.selectbox(
                    "Banco",
                    options=["bac", "popular"],
                    key="card2_bank",
                    format_func=lambda x: "BAC Credomatic" if x == "bac" else "Banco Popular",
                )

                card2_alias = st.text_input(
                    "Alias (opcional)", key="card2_alias", placeholder="ej: Tarjeta Secundaria"
                )

                if card2_type == "credito":
                    card2_limit = st.number_input(
                        "Límite de Crédito (opcional)",
                        min_value=0,
                        value=0,
                        step=50000,
                        key="card2_limit",
                        format="%d",
                    )
                else:
                    card2_limit = None

        st.markdown("---")

        submitted = st.form_submit_button("✅ Guardar Configuración", use_container_width=True)

        if submitted:
            # Validaciones
            if not email or not nombre:
                st.error("❌ Por favor completa todos los campos requeridos")
                return

            if salario <= 0:
                st.error("❌ El salario debe ser mayor a 0")
                return

            if not card1_digits or len(card1_digits) != 4:
                st.error("❌ Debes registrar al menos una tarjeta con 4 dígitos")
                return

            try:
                with get_session() as session:
                    # Crear usuario
                    nuevo_usuario = User(email=email, nombre=nombre, activo=True)
                    session.add(nuevo_usuario)
                    session.flush()

                    # Crear presupuesto (regla 50/30/20)
                    presupuesto = Budget(
                        user_email=email,
                        salario_mensual=Decimal(str(salario)),
                        fecha_inicio=date.today(),
                        porcentaje_necesidades=Decimal("50.00"),
                        porcentaje_gustos=Decimal("30.00"),
                        porcentaje_ahorros=Decimal("20.00"),
                    )
                    session.add(presupuesto)

                    # Crear tarjeta 1
                    tarjeta1 = Card(
                        user_email=email,
                        ultimos_4_digitos=card1_digits,
                        tipo=CardType.CREDIT if card1_type == "credito" else CardType.DEBIT,
                        banco=BankName.BAC if card1_bank == "bac" else BankName.POPULAR,
                        alias=card1_alias or None,
                        limite_credito=Decimal(str(card1_limit))
                        if card1_limit and card1_limit > 0
                        else None,
                        activa=True,
                    )
                    session.add(tarjeta1)

                    # Crear tarjeta 2 si existe
                    if card2_digits and len(card2_digits) == 4:
                        tarjeta2 = Card(
                            user_email=email,
                            ultimos_4_digitos=card2_digits,
                            tipo=CardType.CREDIT if card2_type == "credito" else CardType.DEBIT,
                            banco=BankName.BAC if card2_bank == "bac" else BankName.POPULAR,
                            alias=card2_alias or None,
                            limite_credito=Decimal(str(card2_limit))
                            if card2_limit and card2_limit > 0
                            else None,
                            activa=True,
                        )
                        session.add(tarjeta2)

                    session.commit()

                    st.success("🎉 ¡Configuración guardada exitosamente!")
                    st.balloons()

                    st.info("✅ **¡Todo listo!** Recarga la página para ver el dashboard.")
                    st.info("💡 Usa el menú lateral para navegar.")

            except Exception as e:
                st.error(f"❌ Error al guardar: {e}")
                logger.error(f"Error en setup: {e}")


if __name__ == "__main__":
    main()
