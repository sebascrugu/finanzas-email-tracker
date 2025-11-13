"""
Dashboard de Streamlit para visualizar transacciones bancarias.

Este módulo proporciona una interfaz web interactiva para:
- Visualizar transacciones
- Confirmar/rechazar transacciones
- Ver estadísticas y gráficos
- Exportar reportes
"""

from pathlib import Path
import sys


# Agregar el directorio src al path
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

import streamlit as st

from finanzas_tracker import __version__
from finanzas_tracker.core.logging import get_logger


logger = get_logger(__name__)


def main() -> None:
    """
    Función principal del dashboard de Streamlit.

    Este es un placeholder que será implementado en fases posteriores.
    """
    # Configuración de la página
    st.set_page_config(
        page_title="Finanzas Email Tracker",
        page_icon="💰",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Título principal
    st.title("💰 Finanzas Email Tracker")
    st.caption(f"Versión {__version__}")

    # Sidebar
    st.sidebar.title("Navegación")
    st.sidebar.info("Dashboard en desarrollo")

    # Contenido principal
    st.markdown("""
    ## 🚀 Bienvenido al Finanzas Email Tracker

    Este dashboard te permite:
    - 📊 Visualizar tus transacciones bancarias
    - ✅ Confirmar o rechazar transacciones
    - 📈 Ver estadísticas de gastos
    - 📥 Exportar reportes

    ### 🔧 Estado del Proyecto: En Desarrollo

    El setup inicial está completo. Las siguientes características serán
    implementadas en las próximas fases:

    1. ✅ Configuración del proyecto
    2. ⏳ Extracción de correos
    3. ⏳ Parser de transacciones
    4. ⏳ Categorización con IA
    5. ⏳ Dashboard interactivo

    ### 📚 Primeros Pasos

    1. Configura tu archivo `.env` con tus credenciales
    2. Ejecuta el script de extracción de correos
    3. Visualiza tus transacciones aquí

    """)

    # Tabs de ejemplo
    tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "💳 Transacciones", "⚙️ Configuración"])

    with tab1:
        st.info("Dashboard principal - Próximamente")

    with tab2:
        st.info("Lista de transacciones - Próximamente")

    with tab3:
        st.info("Configuración - Próximamente")

    # Footer
    st.divider()
    st.caption("Desarrollado por Sebastian Cruz | 2025")

    logger.info("Dashboard de Streamlit iniciado")


if __name__ == "__main__":
    main()


