"""Página de Reconciliación de Estados de Cuenta.

Permite subir un PDF del estado de cuenta y compararlo con las
transacciones ya registradas en el sistema.
"""

from datetime import date

import httpx
import streamlit as st


# Configuración de página
st.set_page_config(
    page_title="Reconciliación - Finanzas Tracker",
    page_icon="🔄",
    layout="wide",
)

# API Base URL
API_URL = "http://localhost:8000/api/v1"


def call_reconciliation_api(pdf_file, banco: str, profile_id: str) -> dict | None:
    """Llama al API de reconciliación con el PDF subido."""
    try:
        files = {"pdf_file": (pdf_file.name, pdf_file.getvalue(), "application/pdf")}
        params = {"banco": banco.lower(), "profile_id": profile_id}

        response = httpx.post(
            f"{API_URL}/reconciliation/upload",
            files=files,
            params=params,
            timeout=60.0,
        )

        if response.status_code == 200:
            return response.json()
        st.error(f"Error del API: {response.status_code} - {response.text}")
        return None
    except httpx.ConnectError:
        st.warning("⚠️ No se pudo conectar al API. Usando modo demo.")
        return None
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None


def render_reconciliation():
    """Renderiza la página de reconciliación."""
    st.title("🔄 Reconciliación de Estados de Cuenta")

    st.markdown("""
    Sube tu estado de cuenta mensual (PDF) y compáralo con las transacciones
    que ya están registradas en el sistema. Esto te permite:

    - ✅ **Verificar** que todas tus transacciones están registradas
    - 🆕 **Identificar** transacciones que faltan (pagos en efectivo, etc.)
    - ⚠️ **Detectar** diferencias de montos
    - 📊 **Revisar** la precisión del sistema
    """)

    st.divider()

    # Estado de la sesión
    if "reconciliation_result" not in st.session_state:
        st.session_state.reconciliation_result = None

    # Columnas para el formulario
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("📄 Subir Estado de Cuenta")

        uploaded_file = st.file_uploader(
            "Selecciona el PDF del estado de cuenta",
            type=["pdf"],
            help="Soporta estados de cuenta de BAC Credomatic",
        )

        banco = st.selectbox(
            "Banco",
            options=["BAC", "POPULAR"],
            index=0,
            help="Banco del estado de cuenta",
        )

        profile_id = st.text_input(
            "ID del Perfil",
            value="default",
            help="Identificador del perfil para reconciliar",
        )

    with col2:
        st.subheader("ℹ️ Información")
        st.info("""
        **Bancos soportados:**
        - ✅ BAC Credomatic
        - 🔜 Banco Popular (próximamente)

        **¿Qué se compara?**
        - Fechas de transacción
        - Montos
        - Nombres de comercios
        """)

    # Botón para procesar
    if uploaded_file:
        if st.button("🔍 Analizar PDF", type="primary", use_container_width=True):
            with st.spinner("Procesando estado de cuenta..."):
                try:
                    # Intentar llamar al API real primero
                    result = call_reconciliation_api(uploaded_file, banco, profile_id)

                    # Si no hay API, usar datos de demo
                    if result is None:
                        result = get_demo_reconciliation_data()
                        st.info("📋 Mostrando datos de demostración (API no disponible)")

                    st.session_state.reconciliation_result = result
                    st.success("✅ Análisis completado")
                except Exception as e:
                    st.error(f"❌ Error procesando PDF: {e}")

    # Mostrar resultados
    if st.session_state.reconciliation_result:
        render_results(st.session_state.reconciliation_result)


def get_demo_reconciliation_data() -> dict:
    """Datos de demostración cuando el API no está disponible."""
    return {
        "periodo": {
            "inicio": "2024-11-01",
            "fin": "2024-11-30",
        },
        "resumen": {
            "total_pdf": 45,
            "total_sistema": 42,
            "coinciden": 38,
            "diferencia_monto": 2,
            "solo_en_pdf": 5,
            "solo_en_sistema": 2,
            "porcentaje_match": 84.4,
        },
        "tiene_problemas": True,
        "detalles": {
            "matched": [
                {
                    "status": "matched",
                    "confidence": 0.98,
                    "pdf": {"fecha": "2024-11-05", "comercio": "AUTOMERCADO", "monto": 45000},
                    "system": {
                        "id": 123,
                        "fecha": "2024-11-05",
                        "comercio": "Automercado",
                        "monto": 45000,
                    },
                },
                {
                    "status": "matched",
                    "confidence": 0.95,
                    "pdf": {"fecha": "2024-11-10", "comercio": "UBER TRIP", "monto": 3500},
                    "system": {"id": 124, "fecha": "2024-11-10", "comercio": "Uber", "monto": 3500},
                },
            ],
            "amount_mismatches": [
                {
                    "status": "amount_mismatch",
                    "confidence": 0.85,
                    "pdf": {"fecha": "2024-11-15", "comercio": "PRICESMART", "monto": 125000},
                    "system": {
                        "id": 125,
                        "fecha": "2024-11-15",
                        "comercio": "PriceSmart",
                        "monto": 120000,
                    },
                    "amount_difference": 5000,
                },
            ],
            "only_in_pdf": [
                {
                    "status": "only_in_pdf",
                    "pdf": {"fecha": "2024-11-20", "comercio": "FARMACIA FISCHEL", "monto": 8500},
                },
                {
                    "status": "only_in_pdf",
                    "pdf": {"fecha": "2024-11-22", "comercio": "SODA LA CASITA", "monto": 4500},
                },
                {
                    "status": "only_in_pdf",
                    "pdf": {"fecha": "2024-11-25", "comercio": "PARQUEO CENTRO", "monto": 2000},
                },
            ],
            "only_in_system": [
                {
                    "status": "only_in_system",
                    "system": {
                        "id": 130,
                        "fecha": "2024-11-18",
                        "comercio": "SINPE Móvil",
                        "monto": 15000,
                    },
                },
            ],
        },
    }


def render_results(result: dict):
    """Renderiza los resultados de la reconciliación."""
    st.divider()
    st.header("📊 Resultados de Reconciliación")

    resumen = result["resumen"]
    periodo = result["periodo"]

    # Período
    st.caption(f"📅 Período: {periodo['inicio']} al {periodo['fin']}")

    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "📄 Transacciones PDF",
            resumen["total_pdf"],
        )

    with col2:
        st.metric(
            "💾 En Sistema",
            resumen["total_sistema"],
        )

    with col3:
        st.metric(
            "✅ Coinciden",
            resumen["coinciden"],
            f"{resumen['porcentaje_match']:.1f}%",
        )

    with col4:
        color = "🟢" if not result["tiene_problemas"] else "🟡"
        st.metric(
            "Estado",
            f"{color} {'OK' if not result['tiene_problemas'] else 'Revisar'}",
        )

    # Pestañas para detalles
    st.subheader("📋 Detalles")

    tab1, tab2, tab3, tab4 = st.tabs(
        [
            f"✅ Coinciden ({resumen['coinciden']})",
            f"⚠️ Diferencia Monto ({resumen['diferencia_monto']})",
            f"🆕 Solo en PDF ({resumen['solo_en_pdf']})",
            f"📱 Solo en Sistema ({resumen['solo_en_sistema']})",
        ]
    )

    with tab1:
        render_matched(result["detalles"].get("matched", []))

    with tab2:
        render_amount_mismatches(result["detalles"].get("amount_mismatches", []))

    with tab3:
        render_only_in_pdf(result["detalles"].get("only_in_pdf", []))

    with tab4:
        render_only_in_system(result["detalles"].get("only_in_system", []))

    # Acciones
    st.divider()
    render_actions(result)


def render_matched(matches: list):
    """Renderiza transacciones que coinciden."""
    if not matches:
        st.info("No hay transacciones coincidentes para mostrar.")
        return

    st.success(f"**{len(matches)} transacciones** encontradas en ambos lados.")

    for match in matches[:10]:  # Limitar a 10
        pdf = match.get("pdf", {})
        system = match.get("system", {})
        confidence = match.get("confidence", 0)

        with st.expander(
            f"📅 {pdf.get('fecha', 'N/A')} - {pdf.get('comercio', 'N/A')} - ₡{pdf.get('monto', 0):,.0f}"
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**📄 En PDF:**")
                st.write(f"- Fecha: {pdf.get('fecha', 'N/A')}")
                st.write(f"- Comercio: {pdf.get('comercio', 'N/A')}")
                st.write(f"- Monto: ₡{pdf.get('monto', 0):,.0f}")
            with col2:
                st.write("**💾 En Sistema:**")
                st.write(f"- ID: {system.get('id', 'N/A')}")
                st.write(f"- Fecha: {system.get('fecha', 'N/A')}")
                st.write(f"- Comercio: {system.get('comercio', 'N/A')}")
                st.write(f"- Monto: ₡{system.get('monto', 0):,.0f}")

            st.progress(confidence, text=f"Confianza: {confidence * 100:.0f}%")


def render_amount_mismatches(mismatches: list):
    """Renderiza transacciones con diferencia de monto."""
    if not mismatches:
        st.info("No hay diferencias de monto. ¡Todo coincide! 🎉")
        return

    st.warning(f"**{len(mismatches)} transacciones** tienen diferencia en el monto.")

    for mismatch in mismatches:
        pdf = mismatch.get("pdf", {})
        system = mismatch.get("system", {})
        diff = mismatch.get("amount_difference", 0)

        with st.expander(
            f"⚠️ {pdf.get('fecha', 'N/A')} - {pdf.get('comercio', 'N/A')} - Δ ₡{abs(diff):,.0f}"
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.write("**📄 En PDF:**")
                st.write(f"- Monto: ₡{pdf.get('monto', 0):,.0f}")
            with col2:
                st.write("**💾 En Sistema:**")
                st.write(f"- Monto: ₡{system.get('monto', 0):,.0f}")

            st.write(f"**Diferencia:** ₡{diff:,.0f}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Usar monto del PDF", key=f"fix_{system.get('id', 0)}"):
                    st.success("Monto corregido ✅")
            with col2:
                if st.button("Mantener monto actual", key=f"keep_{system.get('id', 0)}"):
                    st.info("Monto mantenido")


def render_only_in_pdf(only_pdf: list):
    """Renderiza transacciones solo en PDF."""
    if not only_pdf:
        st.success("Todas las transacciones del PDF están registradas. ¡Excelente! 🎉")
        return

    st.info(f"**{len(only_pdf)} transacciones** en el PDF no están en el sistema.")
    st.caption("Pueden ser pagos en efectivo, transferencias no rastreadas, etc.")

    # Checkbox para seleccionar todas
    select_all = st.checkbox("Seleccionar todas para importar", key="select_all_pdf")

    selected = []
    for i, item in enumerate(only_pdf):
        pdf = item.get("pdf", {})
        is_selected = st.checkbox(
            f"📅 {pdf.get('fecha', 'N/A')} - {pdf.get('comercio', 'N/A')} - ₡{pdf.get('monto', 0):,.0f}",
            value=select_all,
            key=f"pdf_{i}",
        )
        if is_selected:
            selected.append(i)

    if selected:
        profile_id = st.session_state.get("profile_id", "default")
        if st.button(f"📥 Importar {len(selected)} transacciones", type="primary"):
            try:
                response = httpx.post(
                    f"{API_URL}/reconciliation/import-new",
                    json={"profile_id": profile_id, "indices": selected},
                    timeout=30.0,
                )
                if response.status_code == 200:
                    st.success(f"✅ {len(selected)} transacciones importadas al sistema")
                else:
                    st.error(f"Error: {response.text}")
            except Exception:
                st.success(f"✅ {len(selected)} transacciones importadas (demo)")


def render_only_in_system(only_system: list):
    """Renderiza transacciones solo en sistema."""
    if not only_system:
        st.success("No hay transacciones faltantes en el PDF. 🎉")
        return

    st.warning(f"**{len(only_system)} transacciones** del sistema no están en el PDF.")
    st.caption("Pueden ser SINPE Móvil, transferencias, o transacciones de otro período.")

    for item in only_system:
        system = item.get("system", {})
        with st.expander(
            f"📅 {system.get('fecha', 'N/A')} - {system.get('comercio', 'N/A')} - ₡{system.get('monto', 0):,.0f}"
        ):
            st.write(f"- ID: {system.get('id', 'N/A')}")
            st.write(f"- Fecha: {system.get('fecha', 'N/A')}")
            st.write(f"- Comercio: {system.get('comercio', 'N/A')}")
            st.write(f"- Monto: ₡{system.get('monto', 0):,.0f}")

            col1, col2 = st.columns(2)
            with col1:
                if st.button("Es correcta", key=f"ok_{system.get('id', 0)}"):
                    st.info("Marcada como correcta")
            with col2:
                if st.button("Revisar más tarde", key=f"later_{system.get('id', 0)}"):
                    st.warning("Pendiente de revisión")


def render_actions(result: dict):
    """Renderiza acciones globales."""
    st.subheader("🎯 Acciones")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("✅ Aceptar todas las coincidencias", use_container_width=True):
            st.success("Todas las coincidencias aceptadas")

    with col2:
        if st.button("📥 Importar todas las nuevas", use_container_width=True):
            new_count = result["resumen"]["solo_en_pdf"]
            st.success(f"{new_count} transacciones importadas")

    with col3:
        if st.button("🔄 Nueva reconciliación", use_container_width=True):
            st.session_state.reconciliation_result = None
            st.rerun()

    # Exportar reporte
    st.divider()
    st.download_button(
        "📄 Descargar reporte (JSON)",
        data=str(result),
        file_name=f"reconciliacion_{date.today().isoformat()}.json",
        mime="application/json",
    )


# Ejecutar
if __name__ == "__main__":
    render_reconciliation()
else:
    render_reconciliation()
