"""
Página de Patrimonio - Net Worth, Activos y Proyecciones.

Muestra:
- Net Worth total y evolución
- Desglose: Cuentas, Inversiones, Metas
- Deudas (tarjetas de crédito)
- Suscripciones detectadas
- Gastos proyectados próximos
- Evolución histórica
"""

import streamlit as st
from decimal import Decimal
import httpx
from datetime import date, datetime, timedelta
import pandas as pd

# Configuración de la página
st.set_page_config(
    page_title="Patrimonio | Finanzas Tracker",
    page_icon="💰",
    layout="wide",
)

# API Base URL
API_URL = "http://localhost:8000/api/v1"

# =============================================================================
# Funciones de API
# =============================================================================


def get_patrimony_summary(profile_id: str) -> dict | None:
    """Obtiene el resumen de patrimonio."""
    try:
        response = httpx.get(
            f"{API_URL}/patrimony/summary",
            headers={"X-Profile-Id": profile_id},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None


def get_accounts(profile_id: str) -> list:
    """Obtiene las cuentas."""
    try:
        response = httpx.get(
            f"{API_URL}/patrimony/accounts",
            headers={"X-Profile-Id": profile_id},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def get_investments(profile_id: str) -> list:
    """Obtiene las inversiones."""
    try:
        response = httpx.get(
            f"{API_URL}/patrimony/investments",
            headers={"X-Profile-Id": profile_id},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def get_goals(profile_id: str) -> list:
    """Obtiene las metas."""
    try:
        response = httpx.get(
            f"{API_URL}/patrimony/goals",
            headers={"X-Profile-Id": profile_id},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def get_credit_cards(profile_id: str) -> list:
    """Obtiene tarjetas de crédito con deudas."""
    try:
        response = httpx.get(
            f"{API_URL}/cards",
            headers={"X-Profile-Id": profile_id},
            params={"tipo": "credito"},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def get_card_alerts(profile_id: str) -> list:
    """Obtiene alertas de tarjetas."""
    try:
        response = httpx.get(
            f"{API_URL}/cards/alerts/upcoming",
            headers={"X-Profile-Id": profile_id},
            params={"dias": 7},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def get_subscriptions(profile_id: str) -> list:
    """Obtiene suscripciones detectadas."""
    try:
        response = httpx.get(
            f"{API_URL}/subscriptions",
            headers={"X-Profile-Id": profile_id},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def get_predicted_expenses(profile_id: str, dias: int = 30) -> list:
    """Obtiene gastos proyectados."""
    try:
        response = httpx.get(
            f"{API_URL}/expenses/predicted",
            headers={"X-Profile-Id": profile_id},
            params={"dias": dias},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


def get_patrimony_history(profile_id: str, meses: int = 6) -> list:
    """Obtiene historial de patrimonio."""
    try:
        response = httpx.get(
            f"{API_URL}/patrimony/history",
            headers={"X-Profile-Id": profile_id},
            params={"meses": meses},
            timeout=10.0,
        )
        if response.status_code == 200:
            return response.json()
        return []
    except Exception:
        return []


# =============================================================================
# Componentes UI
# =============================================================================


def render_net_worth_card(summary: dict):
    """Renderiza la tarjeta principal de Net Worth."""
    net_worth = summary.get("net_worth_crc", 0)
    accounts_total = summary.get("cuentas_total", 0)
    investments_total = summary.get("inversiones_total", 0)
    debts_total = summary.get("deudas_total", 0)

    # Net Worth principal
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 1rem;
        color: white;
        text-align: center;
        margin-bottom: 1rem;
    ">
        <h2 style="margin: 0; font-size: 1rem; opacity: 0.9;">💰 TU PATRIMONIO NETO</h2>
        <h1 style="margin: 0.5rem 0; font-size: 3rem;">₡{net_worth:,.0f}</h1>
        <p style="margin: 0; opacity: 0.8;">Actualizado hoy</p>
    </div>
    """, unsafe_allow_html=True)

    # Desglose
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "🏦 Cuentas",
            f"₡{accounts_total:,.0f}",
            help="Total en cuentas bancarias",
        )

    with col2:
        st.metric(
            "📈 Inversiones",
            f"₡{investments_total:,.0f}",
            help="CDPs, fondos, ahorros a plazo",
        )

    with col3:
        st.metric(
            "💳 Deudas",
            f"-₡{debts_total:,.0f}",
            delta=f"-₡{debts_total:,.0f}" if debts_total > 0 else None,
            delta_color="inverse",
            help="Saldo de tarjetas de crédito",
        )


def render_accounts_section(accounts: list):
    """Renderiza la sección de cuentas."""
    st.subheader("🏦 Cuentas Bancarias")

    if not accounts:
        st.info("No tenés cuentas registradas. Agregá una en Configuración.")
        return

    for acc in accounts:
        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            banco = acc.get("banco", "").upper()
            tipo = acc.get("tipo", "corriente").capitalize()
            numero = acc.get("numero_cuenta", "****")
            st.markdown(f"**{acc.get('nombre', 'Cuenta')}**")
            st.caption(f"{banco} · {tipo} · ***{numero}")

        with col2:
            saldo = acc.get("saldo", 0)
            moneda = acc.get("moneda", "CRC")
            simbolo = "₡" if moneda == "CRC" else "$"
            st.markdown(f"### {simbolo}{saldo:,.0f}")

        with col3:
            if acc.get("es_cuenta_principal"):
                st.markdown("⭐ Principal")

        st.divider()


def render_investments_section(investments: list):
    """Renderiza la sección de inversiones."""
    st.subheader("📈 Inversiones")

    if not investments:
        st.info("No tenés inversiones registradas. ¿Tenés un CDP o ahorro a plazo?")
        return

    for inv in investments:
        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])

        with col1:
            st.markdown(f"**{inv.get('nombre', 'Inversión')}**")
            tipo = inv.get("tipo", "otro").replace("_", " ").title()
            institucion = inv.get("institucion", "")
            st.caption(f"{tipo} · {institucion}")

        with col2:
            monto = inv.get("monto_principal", 0)
            st.markdown(f"### ₡{monto:,.0f}")

        with col3:
            tasa = inv.get("tasa_interes_anual", 0)
            st.metric("Tasa", f"{tasa}%")

        with col4:
            rendimiento = inv.get("rendimiento_acumulado", 0)
            st.metric(
                "Rendimiento",
                f"₡{rendimiento:,.0f}",
                delta=f"+₡{rendimiento:,.0f}" if rendimiento > 0 else None,
            )

        # Fecha de vencimiento si aplica
        vencimiento = inv.get("fecha_vencimiento")
        if vencimiento:
            dias = inv.get("dias_para_vencimiento", 0)
            if dias and dias > 0:
                st.caption(f"⏰ Vence en {dias} días ({vencimiento})")

        st.divider()


def render_goals_section(goals: list):
    """Renderiza la sección de metas."""
    st.subheader("🎯 Metas de Ahorro")

    if not goals:
        st.info("No tenés metas definidas. ¿Para qué querés ahorrar?")
        if st.button("➕ Crear primera meta"):
            st.session_state.show_goal_form = True
        return

    for goal in goals:
        nombre = goal.get("nombre", "Meta")
        objetivo = goal.get("monto_objetivo", 0)
        actual = goal.get("monto_actual", 0)
        porcentaje = goal.get("porcentaje_completado", 0)
        prioridad = goal.get("prioridad", "media")

        # Color según prioridad
        color = "#28a745" if prioridad == "alta" else "#ffc107" if prioridad == "media" else "#6c757d"

        col1, col2 = st.columns([3, 1])

        with col1:
            st.markdown(f"**{nombre}**")
            st.progress(min(porcentaje / 100, 1.0))
            st.caption(f"₡{actual:,.0f} de ₡{objetivo:,.0f} ({porcentaje:.0f}%)")

        with col2:
            faltante = objetivo - actual
            if faltante > 0:
                st.metric("Falta", f"₡{faltante:,.0f}")
            else:
                st.success("✅ ¡Completada!")

        st.divider()


def render_subscriptions_section(subscriptions: list):
    """Renderiza la sección de suscripciones detectadas."""
    st.subheader("🔄 Suscripciones Detectadas")

    if not subscriptions:
        st.info("No se detectaron suscripciones activas. Las detectaré cuando proceses más transacciones.")
        return

    # Calcular total mensual
    total_mensual = sum(s.get("monto_promedio", 0) for s in subscriptions)

    st.metric(
        "Gasto mensual en suscripciones",
        f"₡{total_mensual:,.0f}",
        help="Suma de todas las suscripciones detectadas",
    )

    st.divider()

    for sub in subscriptions:
        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            comercio = sub.get("comercio", "Servicio")
            st.markdown(f"**{comercio}**")
            frecuencia = sub.get("frecuencia", "mensual")
            confianza = sub.get("confianza", 0)
            st.caption(f"📅 {frecuencia.capitalize()} · {confianza}% confianza")

        with col2:
            monto = sub.get("monto_promedio", 0)
            st.markdown(f"### ₡{monto:,.0f}")

        with col3:
            ultimo = sub.get("ultimo_cobro", "")
            if ultimo:
                st.caption(f"Último: {ultimo}")

        st.divider()


def render_predicted_expenses_section(expenses: list):
    """Renderiza la sección de gastos proyectados."""
    st.subheader("📅 Gastos Próximos (30 días)")

    if not expenses:
        st.info("No hay gastos proyectados para los próximos 30 días.")
        return

    # Separar por nivel de alerta
    urgentes = [e for e in expenses if e.get("nivel_alerta") == "urgent"]
    warnings = [e for e in expenses if e.get("nivel_alerta") == "warning"]
    info = [e for e in expenses if e.get("nivel_alerta") == "info"]

    # Mostrar urgentes primero
    if urgentes:
        st.error(f"⚠️ {len(urgentes)} gastos urgentes (≤2 días)")
        for expense in urgentes:
            _render_expense_item(expense, "🔴")

    if warnings:
        st.warning(f"⏰ {len(warnings)} gastos próximos (≤5 días)")
        for expense in warnings:
            _render_expense_item(expense, "🟡")

    # Info en expander
    if info:
        with st.expander(f"📋 Ver {len(info)} gastos adicionales"):
            for expense in info:
                _render_expense_item(expense, "🟢")

    # Resumen
    total = sum(e.get("monto_estimado", 0) for e in expenses)
    st.divider()
    st.metric(
        "Total proyectado (30 días)",
        f"₡{total:,.0f}",
        help="Suma de todos los gastos predecidos",
    )


def _render_expense_item(expense: dict, emoji: str):
    """Renderiza un item de gasto proyectado."""
    col1, col2, col3 = st.columns([3, 2, 1])

    with col1:
        comercio = expense.get("comercio", "Gasto")
        tipo = expense.get("tipo", "otro")
        tipo_emoji = {
            "subscription": "📺",
            "utility": "💡",
            "loan": "🏦",
            "rent": "🏠",
            "insurance": "🛡️",
        }.get(tipo, "📌")
        st.markdown(f"{emoji} **{comercio}**")
        st.caption(f"{tipo_emoji} {tipo.capitalize()}")

    with col2:
        monto = expense.get("monto_estimado", 0)
        st.markdown(f"### ₡{monto:,.0f}")

    with col3:
        dias = expense.get("dias_restantes", 0)
        fecha = expense.get("fecha_estimada", "")
        if dias == 0:
            st.error("HOY")
        elif dias == 1:
            st.warning("MAÑANA")
        else:
            st.caption(f"En {dias} días")
            st.caption(fecha)


def render_patrimony_history(history: list):
    """Renderiza la evolución histórica del patrimonio."""
    st.subheader("📈 Evolución del Patrimonio")

    if not history or len(history) < 2:
        st.info("Se necesitan al menos 2 registros para mostrar la evolución.")
        return

    # Crear DataFrame
    df = pd.DataFrame(history)
    df["fecha"] = pd.to_datetime(df["fecha"])
    df = df.sort_values("fecha")

    # Gráfico de área
    st.area_chart(
        df.set_index("fecha")[["net_worth"]],
        use_container_width=True,
    )

    # Cambio total
    primer_valor = df.iloc[0]["net_worth"]
    ultimo_valor = df.iloc[-1]["net_worth"]
    cambio = ultimo_valor - primer_valor
    cambio_pct = (cambio / primer_valor * 100) if primer_valor else 0

    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "Cambio absoluto",
            f"₡{cambio:,.0f}",
            delta=f"{cambio_pct:+.1f}%",
        )
    with col2:
        st.metric(
            "Último valor",
            f"₡{ultimo_valor:,.0f}",
        )


def render_debts_section(cards: list, alerts: list):
    """Renderiza la sección de deudas (tarjetas de crédito)."""
    st.subheader("💳 Deudas de Tarjetas")

    # Alertas urgentes primero
    if alerts:
        for alert in alerts:
            dias = alert.get("dias_restantes", 0)
            monto = alert.get("monto_pendiente", 0)
            nombre = alert.get("card_nombre", "Tarjeta")

            if dias <= 1:
                st.error(f"""
                ⚠️ **{nombre}** vence {"HOY" if dias == 0 else "MAÑANA"}!
                
                Total a pagar: **₡{monto:,.0f}**
                """)
            elif dias <= 3:
                st.warning(f"""
                ⏰ **{nombre}** vence en {dias} días
                
                Total: ₡{monto:,.0f} | Mínimo: ₡{alert.get('pago_minimo', 0):,.0f}
                """)

    if not cards:
        st.success("🎉 ¡No tenés deudas de tarjetas!")
        return

    for card in cards:
        col1, col2, col3 = st.columns([3, 2, 1])

        with col1:
            nombre = card.get("nombre_display", "Tarjeta")
            st.markdown(f"**{nombre}**")

            fecha_pago = card.get("proximo_pago", {}).get("fecha", "")
            if fecha_pago:
                st.caption(f"Pago: {fecha_pago}")

        with col2:
            deuda = card.get("deuda_total", 0)
            limite = card.get("limite", 0)
            if limite:
                porcentaje = (deuda / limite) * 100
                st.markdown(f"### ₡{deuda:,.0f}")
                st.caption(f"de ₡{limite:,.0f} ({porcentaje:.0f}% usado)")
            else:
                st.markdown(f"### ₡{deuda:,.0f}")

        with col3:
            disponible = card.get("disponible", 0)
            if disponible:
                st.metric("Disponible", f"₡{disponible:,.0f}")

        st.divider()


# =============================================================================
# Main
# =============================================================================


def main():
    """Renderiza la página de patrimonio."""
    st.title("💰 Tu Patrimonio")

    # Obtener profile_id de session state
    profile_id = st.session_state.get("profile_id")

    if not profile_id:
        st.warning("Seleccioná un perfil para ver tu patrimonio.")
        # Para demo, usar un ID fijo
        profile_id = "demo-profile"
        st.info("Usando perfil de demostración...")

    # Tabs para organizar
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📊 Resumen",
        "🏦 Cuentas",
        "📈 Inversiones",
        "🎯 Metas",
        "🔄 Suscripciones",
        "📅 Proyecciones",
    ])

    with tab1:
        # Obtener datos
        summary = get_patrimony_summary(profile_id)
        cards = get_credit_cards(profile_id)
        alerts = get_card_alerts(profile_id)

        if summary:
            render_net_worth_card(summary)
        else:
            st.info("No hay datos de patrimonio. Comenzá agregando tus cuentas.")

        # Evolución histórica
        history = get_patrimony_history(profile_id)
        if history:
            render_patrimony_history(history)

        # Deudas
        render_debts_section(cards, alerts)

    with tab2:
        accounts = get_accounts(profile_id)
        render_accounts_section(accounts)

        # Botón para agregar
        if st.button("➕ Agregar Cuenta", key="add_account"):
            st.session_state.show_account_form = True

    with tab3:
        investments = get_investments(profile_id)
        render_investments_section(investments)

        # Botón para agregar
        if st.button("➕ Agregar Inversión", key="add_investment"):
            st.session_state.show_investment_form = True

    with tab4:
        goals = get_goals(profile_id)
        render_goals_section(goals)

    with tab5:
        subscriptions = get_subscriptions(profile_id)
        render_subscriptions_section(subscriptions)

    with tab6:
        expenses = get_predicted_expenses(profile_id, dias=30)
        render_predicted_expenses_section(expenses)

        # Flujo de caja
        if expenses:
            st.divider()
            st.subheader("💸 Flujo de Caja Proyectado")
            st.info("""
            Este gráfico mostrará cómo afectarán los gastos proyectados a tu saldo.
            Conectá tus cuentas bancarias para ver esta proyección.
            """)

    # Sidebar con acciones rápidas
    with st.sidebar:
        st.header("⚡ Acciones Rápidas")

        if st.button("🔄 Actualizar Datos", use_container_width=True):
            st.rerun()

        if st.button("📄 Subir Estado de Cuenta", use_container_width=True):
            st.switch_page("pages/00_onboarding.py")

        st.divider()

        # Resumen rápido de alertas
        predicted = get_predicted_expenses(profile_id, dias=7)
        urgentes = [e for e in predicted if e.get("nivel_alerta") == "urgent"]
        if urgentes:
            st.error(f"⚠️ {len(urgentes)} gastos urgentes esta semana")

        st.divider()

        st.caption("💡 **Tip del día**")
        st.info("""
        El fondo de emergencia ideal es de 
        **3-6 meses de gastos**.
        
        Basado en tus gastos promedio, 
        necesitarías ₡2,400,000.
        """)


if __name__ == "__main__":
    main()
