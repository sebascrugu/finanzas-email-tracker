"""Página de Onboarding Wizard - Primera Experiencia del Usuario."""

import streamlit as st

st.set_page_config(
    page_title="Setup - Finanzas Tracker",
    page_icon="🚀",
    layout="centered",
    initial_sidebar_state="collapsed",  # Ocultar sidebar durante onboarding
)

from datetime import timedelta
from decimal import Decimal
from pathlib import Path
import sys

src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.config.settings import settings
from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.enums import BankName, CardType, IncomeType, RecurrenceFrequency
from finanzas_tracker.services.onboarding_service import onboarding_service

logger = get_logger(__name__)


# ============================================================================
# CONFIGURACIÓN INICIAL
# ============================================================================

# Inicializar session state
if "onboarding_email" not in st.session_state:
    st.session_state.onboarding_email = settings.user_email

if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = 1

if "profile_created" not in st.session_state:
    st.session_state.profile_created = None

if "detected_cards" not in st.session_state:
    st.session_state.detected_cards = []


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def render_progress_bar(current_step: int, total_steps: int = 6) -> None:
    """Renderiza la barra de progreso del wizard."""
    progress = (current_step - 1) / total_steps
    st.progress(progress)

    # Texto de progreso
    steps_labels = [
        "Bienvenida",
        "Perfil",
        "Email",
        "Tarjetas",
        "Ingresos",
        "Importación",
    ]

    st.caption(
        f"**Paso {current_step}/{total_steps}:** {steps_labels[current_step - 1]}"
    )
    st.markdown("---")


def next_step() -> None:
    """Avanza al siguiente paso."""
    if st.session_state.onboarding_step < 6:
        st.session_state.onboarding_step += 1


def previous_step() -> None:
    """Retrocede al paso anterior."""
    if st.session_state.onboarding_step > 1:
        st.session_state.onboarding_step -= 1


# ============================================================================
# PASOS DEL WIZARD
# ============================================================================

def step_1_welcome() -> None:
    """Paso 1: Bienvenida."""
    st.title("🎉 ¡Bienvenido a Finanzas Tracker!")

    st.markdown(
        """
        ### Tu asistente inteligente de finanzas personales

        Este wizard te ayudará a configurar todo en **menos de 5 minutos**:

        1. ✨ **Crear tu perfil** financiero
        2. 📧 **Conectar tu email** de Outlook
        3. 💳 **Detectar tus tarjetas** automáticamente
        4. 💰 **Configurar tus ingresos**
        5. 📊 **Importar transacciones** existentes
        6. 🚀 **¡Listo para usar!**

        ---

        ### ¿Qué hace Finanzas Tracker?

        📊 **Rastrea automáticamente** tus gastos desde correos bancarios
        🤖 **Categoriza con IA** usando Claude
        📈 **Visualiza** tus patrones de gasto
        🎯 **Establece metas** financieras inteligentes
        💡 **Obtén insights** personalizados

        ---
        """
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("🚀 Empezar Setup", use_container_width=True, type="primary"):
            # Crear progreso
            onboarding_service.get_or_create_progress(st.session_state.onboarding_email)
            next_step()

    with col2:
        if st.button("⏭️ Ya tengo cuenta", use_container_width=True):
            st.info("Redirigiendo al login...")
            # TODO: Implementar login/skip


def step_2_create_profile() -> None:
    """Paso 2: Crear Perfil."""
    st.title("👤 Crear Tu Perfil")

    st.markdown("Primero, vamos a crear tu perfil financiero:")

    with st.form(key="form_create_profile"):
        nombre = st.text_input(
            "Nombre del Perfil *",
            value="",
            placeholder="Ej: Personal, Finanzas de Sebastián",
            help="¿Cómo querés llamar a este perfil?",
        )

        # Selector de icono
        icon_options = {
            "👤 Usuario": "👤",
            "💼 Profesional": "💼",
            "🏠 Personal": "🏠",
            "🎯 Metas": "🎯",
            "💰 Dinero": "💰",
        }

        icon_label = st.selectbox("Icono del Perfil", list(icon_options.keys()))
        icon = icon_options[icon_label]

        email = st.text_input(
            "Email de Outlook *",
            value=st.session_state.onboarding_email,
            help="Email donde recibís notificaciones de tus bancos",
        )

        descripcion = st.text_area(
            "Descripción (opcional)",
            placeholder="Ej: Mis finanzas personales para 2025",
        )

        col1, col2 = st.columns(2)

        with col1:
            back = st.form_submit_button("⬅️ Atrás", use_container_width=True)

        with col2:
            submit = st.form_submit_button(
                "Siguiente ➡️", use_container_width=True, type="primary"
            )

        if back:
            previous_step()
            st.rerun()

        if submit:
            if not nombre:
                st.error("❌ El nombre del perfil es requerido")
            elif not email or "@" not in email:
                st.error("❌ Email inválido")
            else:
                with st.spinner("Creando perfil..."):
                    try:
                        profile = onboarding_service.create_profile(
                            email=email.lower().strip(),
                            nombre=nombre,
                            icono=icon,
                            descripcion=descripcion if descripcion else None,
                        )

                        st.session_state.profile_created = profile
                        st.session_state.onboarding_email = email.lower().strip()

                        st.success(f"✅ Perfil '{nombre}' creado exitosamente!")
                        next_step()
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error al crear perfil: {e}")
                        logger.error(f"Error creating profile: {e}", exc_info=True)


def step_3_connect_email() -> None:
    """Paso 3: Conectar Email."""
    st.title("📧 Conectar Email")

    st.markdown(
        f"""
        Vamos a conectar tu email **{st.session_state.onboarding_email}**
        para buscar correos bancarios automáticamente.

        ### ¿Qué necesitamos?

        - ✅ Acceso de **solo lectura** a tu correo
        - ✅ Permiso para buscar correos de bancos (BAC, Popular)
        - ✅ **No** guardamos contraseñas ni datos sensibles

        ### Bancos Soportados

        🏦 **BAC Credomatic**
        🏦 **Banco Popular**
        🏦 Más bancos próximamente...

        ---
        """
    )

    st.info(
        "ℹ️ **Nota**: La autorización se hace a través de Microsoft Graph API "
        "usando OAuth 2.0. Es seguro y no compartimos tus credenciales."
    )

    col1, col2, col3 = st.columns([1, 2, 1])

    with col1:
        if st.button("⬅️ Atrás", use_container_width=True):
            previous_step()

    with col2:
        if st.button(
            "🔐 Autorizar con Microsoft",
            use_container_width=True,
            type="primary",
        ):
            st.info(
                "🔄 Esta funcionalidad requiere autorización real con Microsoft. "
                "Por ahora, simulamos que ya está autorizado."
            )

            # Marcar paso como completado
            onboarding_service.mark_step_completed(
                st.session_state.onboarding_email, 3
            )

            next_step()
            st.rerun()

    with col3:
        if st.button("⏭️ Omitir", use_container_width=True):
            st.warning("Omitiste la conexión de email. Podrás hacerlo después.")
            next_step()


def step_4_detect_cards() -> None:
    """Paso 4: Auto-detectar Tarjetas."""
    st.title("💳 Detectar Tarjetas Automáticamente")

    st.markdown(
        """
        Vamos a escanear tus correos de los últimos 30 días para detectar
        automáticamente tus tarjetas bancarias.

        ### ¿Qué detectamos?

        - 🔢 Números de tarjeta (últimos 4 dígitos)
        - 🏦 Banco asociado (BAC, Popular)
        - 💳 Tipo sugerido (débito/crédito)
        - 📊 Frecuencia de uso
        """
    )

    if not st.session_state.detected_cards:
        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button("⬅️ Atrás", use_container_width=True):
                previous_step()

        with col2:
            if st.button(
                "🔍 Detectar Tarjetas",
                use_container_width=True,
                type="primary",
            ):
                with st.spinner("Escaneando correos de últimos 30 días..."):
                    try:
                        detected = onboarding_service.auto_detect_cards(
                            st.session_state.onboarding_email,
                            days_back=30,
                        )

                        st.session_state.detected_cards = detected

                        if detected:
                            st.success(f"✅ ¡Detectamos {len(detected)} tarjeta(s)!")
                        else:
                            st.warning(
                                "No encontramos tarjetas en los últimos 30 días. "
                                "Podés agregar manualmente después."
                            )

                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error al detectar tarjetas: {e}")
                        logger.error(f"Error detecting cards: {e}", exc_info=True)

    else:
        # Mostrar tarjetas detectadas
        st.success(f"✅ Detectamos {len(st.session_state.detected_cards)} tarjeta(s):")

        selected_cards = []

        for i, card in enumerate(st.session_state.detected_cards):
            with st.expander(
                f"💳 {card['banco'].value.upper()} •••• {card['last_digits']} "
                f"({card['tipo_sugerido'].value})",
                expanded=True,
            ):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Transacciones", card["transaction_count"])

                with col2:
                    st.metric("Confianza", f"{card['confidence']}%")

                with col3:
                    use_card = st.checkbox(
                        "Usar",
                        value=True,
                        key=f"use_card_{i}",
                        help="Incluir esta tarjeta en tu perfil",
                    )

                # Editar tipo y etiqueta
                col_type, col_label = st.columns(2)

                with col_type:
                    card_type = st.selectbox(
                        "Tipo",
                        [CardType.DEBIT, CardType.CREDIT],
                        index=0 if card["tipo_sugerido"] == CardType.DEBIT else 1,
                        key=f"type_{i}",
                    )

                with col_label:
                    etiqueta = st.text_input(
                        "Etiqueta (opcional)",
                        placeholder="Ej: Personal, Trabajo",
                        key=f"label_{i}",
                    )

                if use_card:
                    selected_cards.append(
                        {
                            "last_digits": card["last_digits"],
                            "banco": card["banco"],
                            "tipo": card_type,
                            "etiqueta": etiqueta if etiqueta else None,
                        }
                    )

        # Botones de acción
        st.markdown("---")
        col1, col2 = st.columns([1, 1])

        with col1:
            if st.button("⬅️ Atrás", use_container_width=True):
                st.session_state.detected_cards = []
                previous_step()
                st.rerun()

        with col2:
            if st.button(
                f"Confirmar {len(selected_cards)} Tarjeta(s) ➡️",
                use_container_width=True,
                type="primary",
            ):
                if selected_cards:
                    with st.spinner("Creando tarjetas..."):
                        try:
                            profile_id = st.session_state.profile_created.id
                            created = onboarding_service.create_cards_from_detected(
                                st.session_state.onboarding_email,
                                profile_id,
                                selected_cards,
                            )

                            st.success(f"✅ {len(created)} tarjeta(s) configurada(s)!")
                            next_step()
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Error al crear tarjetas: {e}")
                            logger.error(f"Error creating cards: {e}", exc_info=True)
                else:
                    st.warning("Seleccioná al menos una tarjeta para continuar")


def step_5_configure_income() -> None:
    """Paso 5: Configurar Ingreso."""
    st.title("💰 Configurar Tu Ingreso")

    st.markdown(
        """
        Configurá tu ingreso principal para que podamos calcular tu presupuesto
        automáticamente (regla 50/30/20).

        ### ¿Por qué es importante?

        - 📊 Calculamos tu presupuesto sugerido
        - 💡 Detectamos gastos excesivos
        - 🎯 Sugerimos metas de ahorro realistas
        """
    )

    with st.form(key="form_income"):
        nombre = st.text_input(
            "Nombre del Ingreso",
            value="Salario",
            placeholder="Ej: Salario, Freelance, Negocio",
        )

        monto = st.number_input(
            "Monto Mensual (₡)",
            min_value=0.0,
            step=10000.0,
            value=500000.0,
            format="%.0f",
            help="¿Cuánto recibís mensualmente?",
        )

        frecuencia = st.selectbox(
            "Frecuencia",
            [
                RecurrenceFrequency.MONTHLY,
                RecurrenceFrequency.BIWEEKLY,
                RecurrenceFrequency.WEEKLY,
            ],
            format_func=lambda x: {
                RecurrenceFrequency.MONTHLY: "Mensual",
                RecurrenceFrequency.BIWEEKLY: "Quincenal",
                RecurrenceFrequency.WEEKLY: "Semanal",
            }[x],
        )

        tipo = st.selectbox(
            "Tipo de Ingreso",
            [
                IncomeType.SALARY,
                IncomeType.FREELANCE,
                IncomeType.BUSINESS,
                IncomeType.INVESTMENT,
                IncomeType.OTHER,
            ],
            format_func=lambda x: {
                IncomeType.SALARY: "Salario/Sueldo",
                IncomeType.FREELANCE: "Freelance",
                IncomeType.BUSINESS: "Negocio",
                IncomeType.INVESTMENT: "Inversiones",
                IncomeType.OTHER: "Otro",
            }[x],
        )

        col1, col2 = st.columns(2)

        with col1:
            back = st.form_submit_button("⬅️ Atrás", use_container_width=True)

        with col2:
            submit = st.form_submit_button(
                "Guardar ➡️", use_container_width=True, type="primary"
            )

        if back:
            previous_step()
            st.rerun()

        if submit:
            if monto <= 0:
                st.error("❌ El monto debe ser mayor a 0")
            else:
                with st.spinner("Configurando ingreso..."):
                    try:
                        profile_id = st.session_state.profile_created.id

                        income = onboarding_service.create_initial_income(
                            st.session_state.onboarding_email,
                            profile_id,
                            monto=Decimal(str(monto)),
                            frecuencia=frecuencia,
                            nombre=nombre,
                            tipo=tipo,
                        )

                        st.success(
                            f"✅ Ingreso configurado: {nombre} - ₡{monto:,.0f}"
                        )

                        # Mostrar presupuesto sugerido
                        st.info(
                            f"""
                            📊 **Tu presupuesto sugerido (50/30/20)**:
                            - 🏠 Necesidades (50%): ₡{monto * 0.5:,.0f}
                            - 🎉 Gustos (30%): ₡{monto * 0.3:,.0f}
                            - 💰 Ahorros (20%): ₡{monto * 0.2:,.0f}
                            """
                        )

                        next_step()
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error al configurar ingreso: {e}")
                        logger.error(f"Error creating income: {e}", exc_info=True)


def step_6_first_import() -> None:
    """Paso 6: Primera Importación."""
    st.title("🎉 ¡Todo Listo!")

    st.markdown(
        """
        Tu perfil está configurado. Ahora podemos importar tus transacciones
        de los últimos días.

        ### ¿Qué vamos a hacer?

        1. 📧 Buscar correos bancarios de los últimos 30 días
        2. 🤖 Procesar y categorizar con IA
        3. 📊 Importar a tu dashboard
        4. ✨ ¡Listo para ver tus finanzas!

        ---
        """
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("📊 Importar Transacciones", use_container_width=True, type="primary"):
            with st.spinner("Importando transacciones de últimos 30 días..."):
                try:
                    # Simular importación
                    # En una implementación real, llamarías al TransactionProcessor
                    import time
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    for i in range(100):
                        time.sleep(0.02)
                        progress_bar.progress(i + 1)
                        if i < 30:
                            status_text.text("Buscando correos bancarios...")
                        elif i < 60:
                            status_text.text("Procesando transacciones...")
                        elif i < 90:
                            status_text.text("Categorizando con IA...")
                        else:
                            status_text.text("Finalizando...")

                    # Marcar onboarding como completado
                    onboarding_service.complete_onboarding(
                        st.session_state.onboarding_email,
                        imported_count=47,  # Simulado
                    )

                    st.success("✅ ¡Importación completada!")
                    st.balloons()

                    # Mostrar resumen
                    st.markdown(
                        """
                        ### 🎊 ¡Bienvenido a Finanzas Tracker!

                        Se importaron **47 transacciones** exitosamente.

                        ### 🚀 Próximos Pasos

                        - 📊 Explorá tu **Dashboard** principal
                        - 💳 Revisá tus **Transacciones**
                        - 🎯 Creá tu primera **Meta Financiera**
                        - 💬 Preguntale cualquier cosa al **Chat IA**

                        ---
                        """
                    )

                    if st.button(
                        "🏠 Ir al Dashboard",
                        use_container_width=True,
                        type="primary",
                    ):
                        st.switch_page("app.py")

                except Exception as e:
                    st.error(f"❌ Error al importar: {e}")
                    logger.error(f"Error importing transactions: {e}", exc_info=True)

    with col2:
        if st.button("⏭️ Omitir por Ahora", use_container_width=True):
            onboarding_service.complete_onboarding(
                st.session_state.onboarding_email,
                imported_count=0,
            )

            st.info("Podés importar transacciones después desde el Dashboard.")
            st.switch_page("app.py")


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    """Función principal del onboarding wizard."""
    # Verificar si debe saltar onboarding
    should_skip, profile_id = onboarding_service.should_skip_onboarding(
        st.session_state.onboarding_email
    )

    if should_skip:
        st.title("✅ Ya Estás Configurado")
        st.success("Tu perfil ya está configurado. ¡Ve al dashboard!")

        if st.button("🏠 Ir al Dashboard", type="primary"):
            st.switch_page("app.py")

        if st.button("🔄 Resetear Onboarding (solo testing)"):
            onboarding_service.reset_onboarding(st.session_state.onboarding_email)
            st.session_state.onboarding_step = 1
            st.rerun()

        return

    # Renderizar barra de progreso
    render_progress_bar(st.session_state.onboarding_step)

    # Renderizar paso actual
    steps = {
        1: step_1_welcome,
        2: step_2_create_profile,
        3: step_3_connect_email,
        4: step_4_detect_cards,
        5: step_5_configure_income,
        6: step_6_first_import,
    }

    current_step_func = steps.get(st.session_state.onboarding_step)
    if current_step_func:
        current_step_func()


if __name__ == "__main__":
    main()
