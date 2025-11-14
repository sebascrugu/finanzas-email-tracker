"""Página de Revisión y Categorización de Transacciones con Detección de Patrones."""

import streamlit as st

st.set_page_config(
    page_title="Transacciones - Finanzas Tracker",
    page_icon="📝",
    layout="wide",
)

import sys
from pathlib import Path

src_path = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(src_path))

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.user import User
from finanzas_tracker.models.transaction import Transaction
from finanzas_tracker.models.category import Subcategory
from finanzas_tracker.models.enums import TransactionType, SpecialTransactionType

logger = get_logger(__name__)


def check_user_exists() -> User | None:
    """Verifica si existe un usuario activo."""
    with get_session() as session:
        return session.query(User).filter(User.activo == True).first()  # noqa: E712


def es_transferencia_o_sinpe(transaction: Transaction) -> bool:
    """Determina si una transacción es transferencia o SINPE."""
    return transaction.tipo_transaccion in [
        TransactionType.TRANSFER,
        TransactionType.SINPE,
    ]


def buscar_patron_historico(comercio: str, user_email: str) -> dict | None:
    """Busca patrones en transacciones anteriores del mismo comercio."""
    with get_session() as session:
        transacciones_anteriores = (
            session.query(Transaction)
            .filter(
                Transaction.user_email == user_email,
                Transaction.comercio == comercio,
                Transaction.tipo_especial.isnot(None),
            )
            .order_by(Transaction.fecha_transaccion.desc())
            .limit(3)
            .all()
        )

        if not transacciones_anteriores:
            return None

        # Si todas tienen el mismo tipo especial, es un patrón
        tipos = [tx.tipo_especial for tx in transacciones_anteriores]
        if len(set(tipos)) == 1:
            tx_ref = transacciones_anteriores[0]
            return {
                "tipo_especial": tx_ref.tipo_especial,
                "relacionada_con": tx_ref.relacionada_con,
                "excluir_presupuesto": tx_ref.excluir_de_presupuesto,
                "frecuencia": len(transacciones_anteriores),
            }

        return None


def main():
    st.title("📝 Revisión de Transacciones")

    user = check_user_exists()

    if not user:
        st.warning("⚠️ No hay usuario configurado")
        st.info("👉 Ve a **Setup** para configurar tu cuenta primero.")
        return

    # Obtener transacciones pendientes
    with get_session() as session:
        transacciones = (
            session.query(Transaction)
            .filter(
                Transaction.user_email == user.email,
                Transaction.necesita_revision == True,  # noqa: E712
                Transaction.deleted_at.is_(None),
            )
            .order_by(Transaction.fecha_transaccion.desc())
            .all()
        )

        if not transacciones:
            st.success("✅ ¡Excelente! No hay transacciones pendientes de revisión")
            st.info("💡 Todas tus transacciones están categorizadas")

            st.markdown("---")

            # Botón para procesar más correos
            st.subheader("📧 Procesar Nuevos Correos")
            st.markdown("""
            ¿Recibiste nuevas transacciones en tu correo? 
            Presiona el botón para buscar y procesar automáticamente.
            """)

            if st.button("📧 Procesar Correos Bancarios", type="primary", use_container_width=True):
                with st.spinner("🔍 Buscando correos bancarios..."):
                    try:
                        # Importar servicios necesarios
                        from finanzas_tracker.services.email_fetcher import EmailFetcher
                        from finanzas_tracker.services.transaction_processor import (
                            TransactionProcessor,
                        )
                        from finanzas_tracker.models.card import Card
                        from finanzas_tracker.models.enums import BankName

                        # 0. Obtener bancos del usuario (de sus tarjetas)
                        with get_session() as card_session:
                            user_cards = (
                                card_session.query(Card)
                                .filter(Card.user_email == user.email, Card.activa == True)  # noqa: E712
                                .all()
                            )

                            if not user_cards:
                                st.error("❌ No tienes tarjetas registradas")
                                st.info("💡 Ve a la página de Setup para agregar tus tarjetas")
                                return

                            # Obtener bancos únicos
                            user_banks = list(set(card.banco for card in user_cards))
                            bank_names = [
                                bank.value if hasattr(bank, "value") else bank
                                for bank in user_banks
                            ]

                        # 1. Obtener correos (solo de los bancos del usuario)
                        st.info(
                            f"📧 Conectando con Outlook... (bancos: {', '.join([b.upper() for b in bank_names])})"
                        )
                        fetcher = EmailFetcher()
                        emails = fetcher.fetch_all_emails(days_back=30)  # Últimos 30 días

                        # Filtrar correos solo de los bancos del usuario
                        processor = TransactionProcessor()
                        filtered_emails = []
                        for email in emails:
                            banco = processor._identify_bank(email)
                            if banco and banco in bank_names:
                                filtered_emails.append(email)

                        emails = filtered_emails

                        if not emails:
                            st.warning("⚠️ No se encontraron correos bancarios nuevos")
                            st.info(
                                "💡 Verifica que tengas correos de transacciones en tu bandeja de entrada"
                            )
                            return

                        st.info(
                            f"📬 {len(emails)} correo(s) de tus bancos encontrado(s). Procesando..."
                        )

                        # 2. Procesar transacciones
                        stats = processor.process_emails(emails, user.email)

                        # Mostrar resultados
                        st.success(f"✅ ¡Proceso completado!")

                        col1, col2, col3, col4 = st.columns(4)

                        with col1:
                            st.metric("📧 Correos procesados", stats.get("total", 0))

                        with col2:
                            st.metric("✅ Nuevas", stats.get("procesados", 0))

                        with col3:
                            st.metric(
                                "🤖 Auto-categorizadas",
                                stats.get("categorizadas_automaticamente", 0),
                            )

                        with col4:
                            st.metric("🔄 Duplicadas", stats.get("duplicados", 0))

                        # Detalles adicionales
                        st.markdown("---")
                        st.markdown("### 📊 Detalles")

                        col1, col2 = st.columns(2)

                        with col1:
                            st.markdown(f"**🏦 BAC Credomatic:** {stats.get('bac', 0)}")
                            st.markdown(f"**🏦 Banco Popular:** {stats.get('popular', 0)}")

                        with col2:
                            st.markdown(
                                f"**💱 USD convertidas:** {stats.get('usd_convertidos', 0)}"
                            )
                            st.markdown(f"**❌ Errores:** {stats.get('errores', 0)}")

                        st.markdown("---")

                        if stats.get("necesitan_revision", 0) > 0:
                            st.warning(
                                f"📝 {stats['necesitan_revision']} transacción(es) necesitan tu revisión"
                            )
                            st.info("💡 Recarga la página para verlas y categorizarlas")
                        elif stats.get("procesados", 0) > 0:
                            st.success(
                                "🎉 Todas las transacciones fueron categorizadas automáticamente"
                            )
                        else:
                            st.info(
                                "ℹ️ No se guardaron nuevas transacciones (posiblemente todas son duplicadas)"
                            )

                        # Botón para recargar
                        if st.button("🔄 Recargar Página"):
                            st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error al procesar correos: {e}")
                        logger.error(f"Error en procesamiento: {e}", exc_info=True)
                        st.info(
                            "💡 Verifica que tu configuración de Outlook esté correcta en el archivo .env"
                        )

            return

        st.info(f"📊 Tienes **{len(transacciones)}** transacción(es) para revisar")

        # Obtener subcategorías
        subcategorias = session.query(Subcategory).all()

        # Agrupar por categoría
        por_categoria = {}
        for subcat in subcategorias:
            cat_nombre = subcat.category.nombre
            if cat_nombre not in por_categoria:
                por_categoria[cat_nombre] = []
            por_categoria[cat_nombre].append(subcat)

    st.markdown("---")

    # Revisar cada transacción
    for i, tx in enumerate(transacciones, 1):
        with st.container():
            st.subheader(f"📝 Transacción {i}/{len(transacciones)}")

            # Info de la transacción
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown(f"**🏪 Comercio:** {tx.comercio}")
                st.markdown(f"**💰 Monto:** {tx.monto_display}")

            with col2:
                st.markdown(f"**📅 Fecha:** {tx.fecha_transaccion.strftime('%d/%m/%Y %H:%M')}")
                banco_display = (
                    tx.banco.value.upper() if hasattr(tx.banco, "value") else tx.banco.upper()
                )
                st.markdown(f"**🏦 Banco:** {banco_display}")

            with col3:
                tipo_display = (
                    tx.tipo_transaccion.value
                    if hasattr(tx.tipo_transaccion, "value")
                    else tx.tipo_transaccion
                )
                st.markdown(f"**🔖 Tipo:** {tipo_display}")
                if tx.card:
                    st.markdown(f"**💳 Tarjeta:** {tx.card.nombre_display}")

            # Sugerencia de IA
            if tx.categoria_sugerida_por_ia:
                confianza = (
                    f" ({tx.confianza_categoria}%)" if hasattr(tx, "confianza_categoria") else ""
                )
                st.info(f"🤖 **IA sugiere:** {tx.categoria_sugerida_por_ia}{confianza}")

            # PASO 1: CATEGORIZACIÓN
            st.markdown("#### 1️⃣ Selecciona la Categoría")

            # Mostrar categorías por grupo
            col1, col2, col3 = st.columns(3)

            categoria_seleccionada = None

            with col1:
                st.markdown("**💰 Necesidades**")
                if "Necesidades" in por_categoria:
                    for subcat in por_categoria["Necesidades"]:
                        if st.button(
                            f"{subcat.icono} {subcat.nombre}",
                            key=f"tx_{tx.id}_cat_{subcat.id}",
                            use_container_width=True,
                        ):
                            categoria_seleccionada = subcat

            with col2:
                st.markdown("**🎮 Gustos**")
                if "Gustos" in por_categoria:
                    for subcat in por_categoria["Gustos"]:
                        if st.button(
                            f"{subcat.icono} {subcat.nombre}",
                            key=f"tx_{tx.id}_cat_{subcat.id}",
                            use_container_width=True,
                        ):
                            categoria_seleccionada = subcat

            with col3:
                st.markdown("**💎 Ahorros**")
                if "Ahorros" in por_categoria:
                    for subcat in por_categoria["Ahorros"]:
                        if st.button(
                            f"{subcat.icono} {subcat.nombre}",
                            key=f"tx_{tx.id}_cat_{subcat.id}",
                            use_container_width=True,
                        ):
                            categoria_seleccionada = subcat

            # Botón para aceptar sugerencia de IA
            if tx.categoria_sugerida_por_ia:
                if st.button(
                    "✅ Aceptar Sugerencia IA",
                    key=f"tx_{tx.id}_accept_ia",
                    use_container_width=True,
                    type="primary",
                ):
                    # Buscar subcategoría por nombre
                    if "/" in tx.categoria_sugerida_por_ia:
                        _, subcat_name = tx.categoria_sugerida_por_ia.split("/", 1)
                    else:
                        subcat_name = tx.categoria_sugerida_por_ia

                    with get_session() as session:
                        subcat = (
                            session.query(Subcategory)
                            .filter(Subcategory.nombre == subcat_name.strip())
                            .first()
                        )

                        if subcat:
                            tx.subcategory_id = subcat.id
                            tx.necesita_revision = False

                            # Guardar
                            tx_db = session.query(Transaction).get(tx.id)
                            tx_db.subcategory_id = subcat.id
                            tx_db.necesita_revision = False
                            session.commit()

                            st.success(f"✅ Categorizada como: {tx.categoria_sugerida_por_ia}")
                            st.rerun()

            # Si seleccionó categoría, proceder con tipo especial (si aplica)
            if categoria_seleccionada:
                with get_session() as session:
                    tx_db = session.query(Transaction).get(tx.id)
                    tx_db.subcategory_id = categoria_seleccionada.id
                    tx_db.categoria_sugerida_por_ia = categoria_seleccionada.nombre_completo
                    tx_db.necesita_revision = False

                    # PASO 2: Solo para transferencias/SINPEs, preguntar tipo especial
                    if es_transferencia_o_sinpe(tx_db):
                        st.markdown("---")
                        st.markdown("#### 2️⃣ Tipo de Transferencia/SINPE")

                        # Buscar patrón histórico
                        patron = buscar_patron_historico(tx.comercio, user.email)

                        if patron:
                            st.info(
                                f"🔍 **Patrón detectado:** Últimas {patron['frecuencia']} veces marcaste "
                                f"'{tx.comercio}' de forma especial"
                            )

                        tipo_nombres = {
                            "normal": "💵 Normal (tu gasto regular - SÍ cuenta en presupuesto)",
                            "intermediaria": "🔄 Intermediaria (dinero que solo pasas - NO cuenta)",
                            "compartida": "🤝 Compartida (tu parte - SÍ cuenta)",
                            "ayuda_familiar": "👪 Ayuda familiar (SÍ cuenta)",
                            "prestamo_dado": "💸 Préstamo dado (SÍ cuenta)",
                        }

                        col1, col2 = st.columns(2)

                        with col1:
                            if st.button(
                                tipo_nombres["normal"],
                                key=f"tx_{tx.id}_tipo_normal",
                                use_container_width=True,
                                type="primary" if not patron else "secondary",
                            ):
                                tx_db.tipo_especial = None
                                tx_db.excluir_de_presupuesto = False
                                tx_db.relacionada_con = None
                                session.commit()
                                st.success("✅ Categorizada como gasto normal")
                                st.rerun()

                            if st.button(
                                tipo_nombres["compartida"],
                                key=f"tx_{tx.id}_tipo_compartida",
                                use_container_width=True,
                            ):
                                tx_db.tipo_especial = SpecialTransactionType.SHARED
                                tx_db.excluir_de_presupuesto = False
                                session.commit()
                                st.success("✅ Marcada como gasto compartido")
                                st.rerun()

                            if st.button(
                                tipo_nombres["prestamo_dado"],
                                key=f"tx_{tx.id}_tipo_prestamo",
                                use_container_width=True,
                            ):
                                tx_db.tipo_especial = SpecialTransactionType.LOAN_GIVEN
                                tx_db.excluir_de_presupuesto = False
                                session.commit()
                                st.success("✅ Marcada como préstamo dado")
                                st.rerun()

                        with col2:
                            if st.button(
                                tipo_nombres["intermediaria"],
                                key=f"tx_{tx.id}_tipo_intermediaria",
                                use_container_width=True,
                            ):
                                tx_db.tipo_especial = SpecialTransactionType.INTERMEDIATE
                                tx_db.excluir_de_presupuesto = True
                                session.commit()
                                st.warning("⚠️ Esta transacción NO contará en tu presupuesto")
                                st.rerun()

                            if st.button(
                                tipo_nombres["ayuda_familiar"],
                                key=f"tx_{tx.id}_tipo_familia",
                                use_container_width=True,
                            ):
                                tx_db.tipo_especial = SpecialTransactionType.FAMILY_SUPPORT
                                tx_db.excluir_de_presupuesto = False
                                session.commit()
                                st.success("✅ Marcada como ayuda familiar")
                                st.rerun()

                    else:
                        # No es transferencia, guardar directamente
                        session.commit()
                        st.success(
                            f"✅ Categorizada como: {categoria_seleccionada.nombre_completo}"
                        )
                        st.rerun()

            st.markdown("---")


if __name__ == "__main__":
    main()
