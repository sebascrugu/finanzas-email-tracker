"""
Página de Onboarding - Configuración inicial para nuevos usuarios.

Wizard multi-paso que guía al usuario a través de:
1. Subir PDF de estado de cuenta
2. Confirmar cuentas detectadas
3. Confirmar tarjetas detectadas
4. Resumen y próximos pasos
"""

import time

import httpx
import streamlit as st


# Configuración de la página
st.set_page_config(
    page_title="Configuración Inicial | Finanzas Tracker",
    page_icon="🚀",
    layout="wide",
)

# API Base URL
API_URL = "http://localhost:8000/api/v1"

# =============================================================================
# Estado de sesión
# =============================================================================

if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = 1

if "user_id" not in st.session_state:
    st.session_state.user_id = None

if "detected_accounts" not in st.session_state:
    st.session_state.detected_accounts = []

if "detected_cards" not in st.session_state:
    st.session_state.detected_cards = []

if "transactions_count" not in st.session_state:
    st.session_state.transactions_count = 0


# =============================================================================
# Funciones de API
# =============================================================================


def start_onboarding(user_id: str) -> dict | None:
    """Inicia el onboarding para un usuario."""
    try:
        response = httpx.post(
            f"{API_URL}/onboarding/start",
            json={"user_id": user_id},
            timeout=10.0,
        )
        if response.status_code == 201:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None


def upload_pdf(user_id: str, file_content: bytes, banco: str) -> dict | None:
    """Sube y procesa un PDF."""
    try:
        files = {"file": ("estado_cuenta.pdf", file_content, "application/pdf")}
        data = {"banco": banco}
        response = httpx.post(
            f"{API_URL}/onboarding/{user_id}/upload-pdf",
            files=files,
            data=data,
            timeout=60.0,  # PDFs pueden tardar
        )
        if response.status_code == 200:
            return response.json()
        st.error(f"Error: {response.json().get('detail', 'Error desconocido')}")
        return None
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None


def confirm_accounts(user_id: str, profile_id: str, accounts: list) -> dict | None:
    """Confirma las cuentas."""
    try:
        response = httpx.post(
            f"{API_URL}/onboarding/{user_id}/confirm-accounts",
            json={"profile_id": profile_id, "accounts": accounts},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def confirm_cards(user_id: str, profile_id: str, cards: list) -> dict | None:
    """Confirma las tarjetas."""
    try:
        response = httpx.post(
            f"{API_URL}/onboarding/{user_id}/confirm-cards",
            json={"profile_id": profile_id, "cards": cards},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


def complete_onboarding(user_id: str) -> dict | None:
    """Completa el onboarding."""
    try:
        response = httpx.post(
            f"{API_URL}/onboarding/{user_id}/complete",
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Error: {e}")
        return None


# =============================================================================
# Componentes UI
# =============================================================================


def render_progress_bar():
    """Muestra la barra de progreso del wizard."""
    steps = ["📄 PDF", "🏦 Cuentas", "💳 Tarjetas", "✅ Listo"]
    current = st.session_state.onboarding_step

    cols = st.columns(len(steps))
    for i, (col, step) in enumerate(zip(cols, steps, strict=False)):
        with col:
            if i + 1 < current:
                st.success(step)
            elif i + 1 == current:
                st.info(f"**{step}**")
            else:
                st.text(step)


def render_step_1():
    """Paso 1: Subir PDF."""
    st.header("📄 Subí tu estado de cuenta")
    st.write("""
    Para comenzar, necesitamos tu estado de cuenta del mes anterior.
    Esto nos permite detectar automáticamente tus cuentas y tarjetas.
    """)

    col1, col2 = st.columns([2, 1])

    with col1:
        banco = st.selectbox(
            "¿De qué banco es el estado de cuenta?",
            options=["bac", "popular"],
            format_func=lambda x: "BAC Credomatic" if x == "bac" else "Banco Popular",
        )

        uploaded_file = st.file_uploader(
            "Seleccioná el PDF",
            type=["pdf"],
            help="El estado de cuenta que recibís por email cada mes",
        )

        if uploaded_file:
            if st.button("📤 Procesar PDF", type="primary", use_container_width=True):
                with st.spinner("Analizando tu estado de cuenta..."):
                    # Simular usuario si no existe
                    if not st.session_state.user_id:
                        st.session_state.user_id = "demo-user-123"
                        start_onboarding(st.session_state.user_id)

                    result = upload_pdf(
                        st.session_state.user_id,
                        uploaded_file.read(),
                        banco,
                    )

                    if result and result.get("success"):
                        st.session_state.detected_accounts = result.get("detected_accounts", [])
                        st.session_state.detected_cards = result.get("detected_cards", [])
                        st.session_state.transactions_count = result.get("transactions_count", 0)

                        st.success(f"""
                        ✅ **PDF procesado exitosamente**
                        - {len(st.session_state.detected_accounts)} cuentas detectadas
                        - {len(st.session_state.detected_cards)} tarjetas detectadas
                        - {st.session_state.transactions_count} transacciones encontradas
                        """)

                        time.sleep(1)
                        st.session_state.onboarding_step = 2
                        st.rerun()

    with col2:
        st.info("""
        💡 **¿Dónde encuentro el PDF?**
        
        BAC te envía un email mensual con asunto:
        "Estado de Cuenta" o similar.
        
        El PDF está adjunto en ese correo.
        """)

    # Opción de saltar
    st.divider()
    if st.button("⏭️ No tengo el PDF, continuar sin él"):
        if not st.session_state.user_id:
            st.session_state.user_id = "demo-user-123"
            start_onboarding(st.session_state.user_id)
        st.session_state.onboarding_step = 2
        st.rerun()


def render_step_2():
    """Paso 2: Confirmar cuentas."""
    st.header("🏦 Confirmá tus cuentas")

    accounts = st.session_state.detected_accounts

    if not accounts:
        st.warning("No detectamos cuentas automáticamente. Agregá una manualmente:")
        accounts = []

    st.write("Revisá que la información esté correcta:")

    confirmed_accounts = []

    for i, acc in enumerate(accounts):
        with st.expander(f"Cuenta ***{acc.get('numero_cuenta', '????')}", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                nombre = st.text_input(
                    "Nombre de la cuenta",
                    value=acc.get("nombre_sugerido", f"Cuenta {i+1}"),
                    key=f"acc_nombre_{i}",
                )
                tipo = st.selectbox(
                    "Tipo",
                    options=["corriente", "ahorro", "planilla"],
                    index=0 if acc.get("tipo") == "corriente" else 1,
                    key=f"acc_tipo_{i}",
                )

            with col2:
                saldo = st.number_input(
                    "Saldo actual (₡)",
                    value=float(acc.get("saldo", 0)),
                    min_value=0.0,
                    step=1000.0,
                    key=f"acc_saldo_{i}",
                )
                moneda = st.selectbox(
                    "Moneda",
                    options=["CRC", "USD"],
                    key=f"acc_moneda_{i}",
                )

            es_principal = st.checkbox(
                "Es mi cuenta principal",
                value=i == 0,
                key=f"acc_principal_{i}",
            )

            confirmed_accounts.append(
                {
                    "numero_cuenta": acc.get("numero_cuenta", "0000"),
                    "nombre": nombre,
                    "tipo": tipo,
                    "banco": acc.get("banco", "bac"),
                    "saldo": saldo,
                    "moneda": moneda,
                    "es_principal": es_principal,
                }
            )

    # Agregar cuenta manual
    st.divider()
    if st.button("➕ Agregar otra cuenta"):
        st.session_state.detected_accounts.append(
            {
                "numero_cuenta": "",
                "tipo": "corriente",
                "banco": "bac",
                "saldo": 0,
                "nombre_sugerido": f"Cuenta {len(accounts) + 1}",
            }
        )
        st.rerun()

    # Navegación
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Volver"):
            st.session_state.onboarding_step = 1
            st.rerun()

    with col2:
        if st.button("Continuar ➡️", type="primary"):
            # Guardar cuentas en session state para después
            st.session_state.confirmed_accounts = confirmed_accounts
            st.session_state.onboarding_step = 3
            st.rerun()


def render_step_3():
    """Paso 3: Confirmar tarjetas."""
    st.header("💳 Confirmá tus tarjetas")

    cards = st.session_state.detected_cards

    if not cards:
        st.warning("No detectamos tarjetas. Agregá una manualmente si tenés:")

    st.write("Es importante indicar si son de **crédito** o **débito**:")

    confirmed_cards = []

    for i, card in enumerate(cards):
        with st.expander(f"Tarjeta ***{card.get('ultimos_4_digitos', '????')}", expanded=True):
            col1, col2 = st.columns(2)

            with col1:
                tipo = st.selectbox(
                    "Tipo de tarjeta",
                    options=["credito", "debito"],
                    index=0 if card.get("tipo_sugerido") == "credito" else 1,
                    format_func=lambda x: "💳 Crédito" if x == "credito" else "🏧 Débito",
                    key=f"card_tipo_{i}",
                )
                marca = st.text_input(
                    "Marca",
                    value=card.get("marca") or "",
                    placeholder="VISA, Mastercard...",
                    key=f"card_marca_{i}",
                )

            with col2:
                ultimos_4 = st.text_input(
                    "Últimos 4 dígitos",
                    value=card.get("ultimos_4_digitos", ""),
                    max_chars=4,
                    key=f"card_digitos_{i}",
                )
                banco = st.selectbox(
                    "Banco",
                    options=["bac", "popular"],
                    format_func=lambda x: "BAC" if x == "bac" else "Popular",
                    key=f"card_banco_{i}",
                )

            # Solo mostrar campos de crédito si es crédito
            if tipo == "credito":
                st.markdown("**Información de crédito:**")
                col3, col4, col5 = st.columns(3)

                with col3:
                    limite = st.number_input(
                        "Límite de crédito (₡)",
                        value=float(card.get("limite_credito") or 2000000),
                        min_value=0.0,
                        step=100000.0,
                        key=f"card_limite_{i}",
                    )

                with col4:
                    fecha_corte = st.number_input(
                        "Día de corte (1-31)",
                        value=card.get("fecha_corte") or 15,
                        min_value=1,
                        max_value=31,
                        key=f"card_corte_{i}",
                    )

                with col5:
                    fecha_pago = st.number_input(
                        "Día de pago (1-31)",
                        value=card.get("fecha_pago") or 28,
                        min_value=1,
                        max_value=31,
                        key=f"card_pago_{i}",
                    )

                saldo = st.number_input(
                    "Saldo actual de la tarjeta (₡)",
                    value=float(card.get("saldo_actual") or 0),
                    min_value=0.0,
                    step=1000.0,
                    key=f"card_saldo_{i}",
                )
            else:
                limite = None
                fecha_corte = None
                fecha_pago = None
                saldo = 0

            confirmed_cards.append(
                {
                    "ultimos_4_digitos": ultimos_4,
                    "tipo": tipo,
                    "banco": banco,
                    "marca": marca or None,
                    "limite_credito": limite,
                    "fecha_corte": fecha_corte,
                    "fecha_pago": fecha_pago,
                    "saldo_actual": saldo,
                    "tasa_interes": 52.0,  # Default BAC
                }
            )

    # Agregar tarjeta manual
    st.divider()
    if st.button("➕ Agregar otra tarjeta"):
        st.session_state.detected_cards.append(
            {
                "ultimos_4_digitos": "",
                "tipo_sugerido": "credito",
                "banco": "bac",
            }
        )
        st.rerun()

    # Navegación
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⬅️ Volver"):
            st.session_state.onboarding_step = 2
            st.rerun()

    with col2:
        if st.button("Finalizar ✅", type="primary"):
            st.session_state.confirmed_cards = confirmed_cards
            st.session_state.onboarding_step = 4
            st.rerun()


def render_step_4():
    """Paso 4: Resumen y completar."""
    st.header("🎉 ¡Configuración completa!")

    st.balloons()

    # Resumen
    accounts = getattr(st.session_state, "confirmed_accounts", [])
    cards = getattr(st.session_state, "confirmed_cards", [])
    credit_cards = [c for c in cards if c.get("tipo") == "credito"]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("🏦 Cuentas", len(accounts))

    with col2:
        st.metric("💳 Tarjetas", len(cards))

    with col3:
        st.metric("📊 Transacciones", st.session_state.transactions_count)

    st.divider()

    # Próximos pasos
    st.subheader("📋 Próximos pasos recomendados:")

    st.markdown("""
    1. **📧 Conectar tu email** - Para sincronización automática de transacciones
    2. **📊 Configurar presupuesto** - Define tus límites mensuales (50/30/20)
    3. **🎯 Crear una meta** - ¿Para qué querés ahorrar?
    """)

    if credit_cards:
        st.info(f"""
        💳 **Tenés {len(credit_cards)} tarjeta(s) de crédito**
        
        Revisá las fechas de corte y pago en la sección de Tarjetas.
        Te avisaremos cuando se acerque el vencimiento.
        """)

    st.divider()

    if st.button("🚀 Ir al Dashboard", type="primary", use_container_width=True):
        st.switch_page("pages/03_balance.py")


# =============================================================================
# Main
# =============================================================================


def main():
    """Renderiza la página de onboarding."""
    st.title("🚀 Configuración Inicial")
    st.write("Vamos a configurar tu tracker de finanzas en 3 simples pasos.")

    st.divider()

    # Barra de progreso
    render_progress_bar()

    st.divider()

    # Renderizar paso actual
    step = st.session_state.onboarding_step

    if step == 1:
        render_step_1()
    elif step == 2:
        render_step_2()
    elif step == 3:
        render_step_3()
    elif step == 4:
        render_step_4()

    # Debug info (oculto por defecto)
    with st.expander("🔧 Debug", expanded=False):
        st.json(
            {
                "step": st.session_state.onboarding_step,
                "user_id": st.session_state.user_id,
                "accounts": len(st.session_state.detected_accounts),
                "cards": len(st.session_state.detected_cards),
            }
        )


if __name__ == "__main__":
    main()
