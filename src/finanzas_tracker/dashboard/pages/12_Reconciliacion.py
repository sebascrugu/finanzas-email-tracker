"""Página de Reconciliación de Estados de Cuenta PDF."""

import streamlit as st

st.set_page_config(
    page_title="Reconciliación - Finanzas Tracker",
    page_icon="🔄",
    layout="wide",
)

from pathlib import Path
import sys
from datetime import date, datetime
from io import BytesIO

src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.dashboard.helpers import require_profile
from finanzas_tracker.dashboard.styles import apply_custom_styles
from finanzas_tracker.models.bank_statement import BankStatement
from finanzas_tracker.models.enums import BankName
from finanzas_tracker.services.pdf_reconciliation_service import pdf_reconciliation_service

# Apply custom styles
apply_custom_styles()


def mostrar_resumen_reconciliacion(report):
    """Muestra el resumen general de la reconciliación."""
    summary = report.summary

    # Determinar color según status
    status_colors = {
        "perfect": "success",
        "good": "info",
        "needs_review": "warning",
    }
    status_labels = {
        "perfect": "✅ PERFECTO",
        "good": "👍 BUENO",
        "needs_review": "⚠️ NECESITA REVISIÓN",
    }

    status_color = status_colors.get(summary.status, "warning")
    status_label = status_labels.get(summary.status, "DESCONOCIDO")

    st.markdown(f"""
    <div style="padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border-radius: 10px; margin-bottom: 20px; color: white;">
        <h2 style="margin: 0 0 15px 0; color: white;">📊 Resumen de Reconciliación</h2>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
            <div>
                <div style="font-size: 0.9rem; opacity: 0.9;">Transacciones PDF</div>
                <div style="font-size: 2rem; font-weight: bold;">{summary.total_pdf_transactions}</div>
            </div>
            <div>
                <div style="font-size: 0.9rem; opacity: 0.9;">Transacciones Email</div>
                <div style="font-size: 2rem; font-weight: bold;">{summary.total_email_transactions}</div>
            </div>
            <div>
                <div style="font-size: 0.9rem; opacity: 0.9;">Matched</div>
                <div style="font-size: 2rem; font-weight: bold;">{summary.matched_count} ({summary.match_percentage:.1f}%)</div>
            </div>
            <div>
                <div style="font-size: 0.9rem; opacity: 0.9;">Estado</div>
                <div style="font-size: 1.5rem; font-weight: bold;">{status_label}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Métricas detalladas
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="🎯 Alta Confianza",
            value=summary.matched_high_confidence,
            delta=f"{summary.matched_high_confidence / summary.total_pdf_transactions * 100:.0f}%"
            if summary.total_pdf_transactions > 0
            else "0%",
        )

    with col2:
        st.metric(
            label="⚠️ Faltantes en Emails",
            value=summary.missing_in_emails,
            delta=f"-{summary.missing_in_emails}" if summary.missing_in_emails > 0 else "Perfecto",
            delta_color="inverse",
        )

    with col3:
        st.metric(
            label="❓ Faltantes en PDF",
            value=summary.missing_in_statement,
            delta=f"-{summary.missing_in_statement}" if summary.missing_in_statement > 0 else "Bien",
            delta_color="inverse",
        )

    with col4:
        st.metric(
            label="💰 Discrepancias",
            value=summary.discrepancies,
            delta=f"-{summary.discrepancies}" if summary.discrepancies > 0 else "Sin errores",
            delta_color="inverse",
        )


def mostrar_matched_transactions(matches):
    """Muestra tabla de transacciones matched."""
    if not matches:
        st.info("ℹ️ No hay transacciones matched")
        return

    st.subheader(f"✅ Transacciones Matched ({len(matches)})")

    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        confidence_filter = st.multiselect(
            "Filtrar por confianza",
            ["high", "medium", "low"],
            default=["high", "medium", "low"],
        )

    # Filtrar
    filtered_matches = [m for m in matches if m.match_confidence in confidence_filter]

    # Tabla
    for idx, match in enumerate(filtered_matches):
        pdf_tx = match.pdf_transaction
        email_tx = match.email_transaction

        confidence_emoji = {
            "high": "🟢",
            "medium": "🟡",
            "low": "🔴",
        }

        with st.expander(
            f"{confidence_emoji.get(match.match_confidence, '⚪')} "
            f"{pdf_tx.comercio[:40]} - ₡{pdf_tx.monto:,.2f} "
            f"(Score: {match.match_score:.1f}%)"
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**📄 PDF**")
                st.write(f"Fecha: {pdf_tx.fecha}")
                st.write(f"Comercio: {pdf_tx.comercio}")
                st.write(f"Monto: ₡{pdf_tx.monto:,.2f}")
                st.write(f"Tipo: {pdf_tx.tipo_transaccion.value}")

            with col2:
                st.markdown("**📧 Email**")
                if email_tx:
                    st.write(f"Fecha: {email_tx.fecha_transaccion.date()}")
                    st.write(f"Comercio: {email_tx.comercio}")
                    st.write(f"Monto: ₡{email_tx.monto_crc:,.2f}")
                    st.write(f"Categoría: {email_tx.subcategory.nombre_completo if email_tx.subcategory else 'Sin categoría'}")

            st.caption(f"**Razones del match:** {', '.join(match.match_reasons)}")


def mostrar_missing_in_emails(missing_transactions, profile_id, banco):
    """Muestra transacciones que faltan en emails."""
    if not missing_transactions:
        st.success("✅ No hay transacciones faltantes en emails - ¡Todo en orden!")
        return

    st.subheader(f"⚠️ Transacciones Faltantes en Emails ({len(missing_transactions)})")
    st.warning(
        "Estas transacciones están en el estado de cuenta del banco pero no en tus correos. "
        "Posiblemente no recibiste el email de notificación."
    )

    # Tabla
    for idx, pdf_tx in enumerate(missing_transactions):
        with st.expander(
            f"⚠️ {pdf_tx.comercio[:40]} - ₡{pdf_tx.monto:,.2f} ({pdf_tx.fecha})"
        ):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.write(f"**Fecha:** {pdf_tx.fecha}")
                st.write(f"**Comercio:** {pdf_tx.comercio}")
                st.write(f"**Monto:** ₡{pdf_tx.monto:,.2f} {pdf_tx.moneda.value}")
                st.write(f"**Tipo:** {pdf_tx.tipo_transaccion.value}")
                st.write(f"**Referencia:** {pdf_tx.referencia}")

            with col2:
                if st.button(f"➕ Agregar", key=f"add_{idx}"):
                    # TODO: Implementar agregar transacción
                    st.success("✅ Transacción agregada (implementar)")

    # Botón para agregar todas
    if st.button(f"➕ Agregar todas las {len(missing_transactions)} transacciones"):
        # TODO: Implementar agregar todas
        st.success("✅ Todas las transacciones agregadas (implementar)")


def mostrar_discrepancies(discrepancies):
    """Muestra transacciones con discrepancias."""
    if not discrepancies:
        st.success("✅ No hay discrepancias - ¡Todos los montos coinciden!")
        return

    st.subheader(f"💰 Discrepancias Detectadas ({len(discrepancies)})")
    st.error(
        "Estas transacciones tienen diferencias entre el PDF y los correos. "
        "Revisa manualmente para identificar el problema."
    )

    for idx, match in enumerate(discrepancies):
        pdf_tx = match.pdf_transaction
        email_tx = match.email_transaction

        with st.expander(
            f"💰 {pdf_tx.comercio[:40]} - {match.discrepancy_type or 'Discrepancia'}"
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**📄 PDF**")
                st.write(f"Fecha: {pdf_tx.fecha}")
                st.write(f"Monto: ₡{pdf_tx.monto:,.2f}")

            with col2:
                st.markdown("**📧 Email**")
                if email_tx:
                    st.write(f"Fecha: {email_tx.fecha_transaccion.date()}")
                    st.write(f"Monto: ₡{email_tx.monto_crc:,.2f}")

            st.error(f"**Discrepancia:** {match.discrepancy_details}")


def mostrar_historial_statements(profile_id):
    """Muestra historial de estados de cuenta procesados."""
    st.subheader("📚 Historial de Reconciliaciones")

    with get_session() as session:
        statements = (
            session.query(BankStatement)
            .filter(
                BankStatement.profile_id == profile_id,
                BankStatement.deleted_at.is_(None),
            )
            .order_by(BankStatement.fecha_corte.desc())
            .limit(10)
            .all()
        )

        if not statements:
            st.info("ℹ️ Aún no has procesado ningún estado de cuenta")
            return

        for stmt in statements:
            status_emoji = {
                "perfect": "✅",
                "good": "👍",
                "needs_review": "⚠️",
                "pending": "⏳",
            }

            emoji = status_emoji.get(stmt.reconciliation_status, "❓")

            with st.expander(
                f"{emoji} {stmt.banco.value.upper()} - {stmt.fecha_corte.strftime('%b %Y')} "
                f"({stmt.matched_count}/{stmt.total_transactions_pdf} matched)"
            ):
                col1, col2, col3 = st.columns(3)

                with col1:
                    st.metric("Total PDF", stmt.total_transactions_pdf)
                    st.metric("Matched", stmt.matched_count)

                with col2:
                    st.metric("Faltantes Emails", stmt.missing_in_emails_count)
                    st.metric("Faltantes PDF", stmt.missing_in_statement_count)

                with col3:
                    st.metric("Discrepancias", stmt.discrepancies_count)
                    st.metric("Match %", f"{stmt.match_percentage:.1f}%")

                st.caption(
                    f"Procesado: {stmt.processed_at.strftime('%Y-%m-%d %H:%M') if stmt.processed_at else 'Pendiente'}"
                )


def main() -> None:
    """Página principal de reconciliación."""
    st.title("🔄 Reconciliación de Estados de Cuenta")
    st.markdown(
        "Valida que todas las transacciones del banco estén en tu sistema y detecta correos perdidos."
    )

    perfil_activo = require_profile()
    st.caption(f"Perfil: **{perfil_activo.nombre_completo}**")

    # Tabs
    tab1, tab2 = st.tabs(["📤 Nuevo Estado de Cuenta", "📚 Historial"])

    with tab1:
        st.markdown("---")

        # Upload PDF
        uploaded_file = st.file_uploader(
            "📄 Sube tu estado de cuenta PDF",
            type=["pdf"],
            help="Sube el PDF del estado de cuenta de tu banco (BAC o Popular)",
        )

        if uploaded_file:
            # Configuración
            col1, col2, col3 = st.columns(3)

            with col1:
                banco = st.selectbox(
                    "🏦 Banco",
                    options=[BankName.BAC, BankName.POPULAR],
                    format_func=lambda x: x.value.upper(),
                )

            with col2:
                fecha_corte = st.date_input(
                    "📅 Fecha de corte",
                    value=date.today(),
                    help="Fecha de corte del estado de cuenta (se puede extraer automáticamente del PDF)",
                )

            with col3:
                st.write("")  # Spacing
                st.write("")
                process_button = st.button("🔄 Procesar Estado de Cuenta", type="primary", use_container_width=True)

            if process_button:
                try:
                    # Leer contenido del PDF
                    pdf_content = uploaded_file.read()

                    # Progress bar
                    progress_bar = st.progress(0)
                    status_text = st.empty()

                    # Paso 1: Extrayendo
                    status_text.text("📄 Extrayendo transacciones del PDF con Claude Vision...")
                    progress_bar.progress(25)

                    # Procesar
                    with st.spinner("Procesando estado de cuenta..."):
                        report = pdf_reconciliation_service.process_bank_statement(
                            pdf_content=pdf_content,
                            profile_id=perfil_activo.id,
                            banco=banco,
                            fecha_corte=fecha_corte,
                            pdf_filename=uploaded_file.name,
                        )

                    progress_bar.progress(100)
                    status_text.text("✅ Procesamiento completado!")

                    st.success("✅ Estado de cuenta procesado exitosamente!")

                    # Mostrar resultados
                    st.markdown("---")
                    st.markdown("## 📊 Resultados de la Reconciliación")

                    # Resumen
                    mostrar_resumen_reconciliacion(report)

                    # Tabs para detalles
                    detail_tabs = st.tabs([
                        f"✅ Matched ({len(report.matched_transactions)})",
                        f"⚠️ Faltantes en Emails ({len(report.missing_in_emails)})",
                        f"❓ Faltantes en PDF ({len(report.missing_in_statement)})",
                        f"💰 Discrepancias ({len(report.discrepancies)})",
                    ])

                    with detail_tabs[0]:
                        mostrar_matched_transactions(report.matched_transactions)

                    with detail_tabs[1]:
                        mostrar_missing_in_emails(
                            report.missing_in_emails, perfil_activo.id, banco
                        )

                    with detail_tabs[2]:
                        if report.missing_in_statement:
                            st.warning(
                                f"Hay {len(report.missing_in_statement)} transacciones en emails "
                                "que no aparecen en el estado de cuenta del banco."
                            )
                            # TODO: Mostrar tabla
                        else:
                            st.success("✅ Todas las transacciones en emails están en el PDF")

                    with detail_tabs[3]:
                        mostrar_discrepancies(report.discrepancies)

                except ValueError as e:
                    st.error(f"❌ Error: {str(e)}")
                except Exception as e:
                    st.error(f"❌ Error procesando estado de cuenta: {str(e)}")
                    with st.expander("Ver detalles del error"):
                        st.exception(e)

    with tab2:
        mostrar_historial_statements(perfil_activo.id)


if __name__ == "__main__":
    main()
