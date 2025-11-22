"""Pagina de Chat con Finanzas - Asistente IA."""

import streamlit as st

st.set_page_config(
    page_title="Chat - Finanzas Tracker",
    page_icon=":speech_balloon:",
    layout="wide",
)

from pathlib import Path
import sys

src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.services.finance_chat import finance_chat_service


logger = get_logger(__name__)


def chat_page() -> None:
    """Pagina principal del chat con finanzas."""
    st.title("Chat con tus Finanzas")
    st.markdown("Preguntame lo que quieras sobre tus finanzas. Por ejemplo:")
    st.markdown("""
    - *Cuanto gaste en comida este mes?*
    - *Cual es mi gasto mas alto?*
    - *Como van mis ahorros?*
    - *En que comercio gasto mas?*
    """)

    # Obtener perfil activo
    with get_session() as session:
        perfil = session.query(Profile).filter(Profile.es_activo.is_(True)).first()

        if not perfil:
            st.warning("No hay un perfil activo. Ve a Setup para configurar tu perfil.")
            return

        st.info(f"Perfil activo: **{perfil.nombre}**")

        # Historial de chat
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = []

        # Mostrar historial
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.chat_message("user").write(msg["content"])
            else:
                st.chat_message("assistant").write(msg["content"])

        # Input del usuario
        user_input = st.chat_input("Escribe tu pregunta aqui...")

        if user_input:
            # Mostrar mensaje del usuario
            st.chat_message("user").write(user_input)
            st.session_state.chat_history.append({"role": "user", "content": user_input})

            # Obtener respuesta
            with st.spinner("Pensando..."):
                response = finance_chat_service.chat(user_input, str(perfil.id))

            # Mostrar respuesta
            st.chat_message("assistant").write(response)
            st.session_state.chat_history.append({"role": "assistant", "content": response})

        # Boton para limpiar historial
        if st.session_state.chat_history:
            if st.button("Limpiar conversacion", type="secondary"):
                st.session_state.chat_history = []
                st.rerun()


if __name__ == "__main__":
    chat_page()
