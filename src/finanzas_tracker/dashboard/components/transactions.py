"""Componentes de UI para revision de transacciones."""

__all__ = [
    "procesar_correos_bancarios",
    "revisar_transacciones",
    "mostrar_estado_vacio",
]

import streamlit as st

from finanzas_tracker.core.database import get_session
from finanzas_tracker.core.logging import get_logger
from finanzas_tracker.models.card import Card
from finanzas_tracker.models.category import Subcategory
from finanzas_tracker.models.enums import TransactionType
from finanzas_tracker.models.profile import Profile
from finanzas_tracker.models.transaction import Transaction


logger = get_logger(__name__)

# Tipos comunes para simplificar el UI
# El usuario puede escribir lo que quiera en el campo tipo_especial,
# pero estos son los más comunes para facilitar la selección
TIPOS_GASTO_COMUNES = {
    "normal": "Normal",
    "dinero_ajeno": "Dinero ajeno (no cuenta en presupuesto)",
    "intermediaria": "Intermediaria (no cuenta en presupuesto)",
    "transferencia_propia": "Transferencia propia (no cuenta en presupuesto)",
    "otro": "Otro (describir en contexto)",
}


def _es_transferencia_o_sinpe(transaction: Transaction) -> bool:
    """Determina si una transaccion es transferencia o SINPE."""
    return transaction.tipo_transaccion in [TransactionType.TRANSFER, TransactionType.SINPE]


def _buscar_patron_historico(comercio: str, profile_id: str) -> dict | None:
    """Busca patrones en transacciones anteriores del mismo comercio."""
    with get_session() as session:
        transacciones_anteriores = (
            session.query(Transaction)
            .filter(
                Transaction.profile_id == profile_id,
                Transaction.comercio == comercio,
                Transaction.tipo_especial.isnot(None),
            )
            .order_by(Transaction.fecha_transaccion.desc())
            .limit(3)
            .all()
        )

        if not transacciones_anteriores:
            return None

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


def mostrar_estado_vacio(perfil: Profile) -> None:
    """Muestra UI cuando no hay transacciones pendientes."""
    st.success("Excelente! No hay transacciones pendientes de revision")
    st.info("Todas tus transacciones estan categorizadas")

    st.markdown("---")
    st.subheader("Procesar Nuevos Correos")
    st.markdown("Recibiste nuevas transacciones? Presiona el boton para buscar y procesar.")

    if st.button("Procesar Correos Bancarios", type="primary", use_container_width=True):
        procesar_correos_bancarios(perfil)


def procesar_correos_bancarios(perfil: Profile) -> None:
    """Procesa correos bancarios para el perfil."""
    with st.spinner("Buscando correos bancarios..."):
        try:
            from finanzas_tracker.services.email_fetcher import EmailFetcher
            from finanzas_tracker.services.transaction_processor import TransactionProcessor

            # Obtener bancos del perfil
            with get_session() as card_session:
                user_cards = (
                    card_session.query(Card)
                    .filter(Card.profile_id == perfil.id, Card.activa.is_(True))
                    .all()
                )

                if not user_cards:
                    st.error("No tienes tarjetas registradas")
                    st.info("Ve a la pagina de Setup para agregar tus tarjetas")
                    return

                user_banks = list({card.banco for card in user_cards})
                bank_names = [bank.value if hasattr(bank, "value") else bank for bank in user_banks]

            st.info(
                f"Conectando con Outlook... (bancos: {', '.join([b.upper() for b in bank_names])})"
            )

            fetcher = EmailFetcher()
            emails = fetcher.fetch_all_emails(days_back=30)

            processor = TransactionProcessor()
            filtered_emails = [
                email for email in emails if processor._identify_bank(email) in bank_names
            ]

            if not filtered_emails:
                st.warning("No se encontraron correos bancarios nuevos")
                return

            st.info(f"{len(filtered_emails)} correo(s) encontrado(s). Procesando...")

            stats = processor.process_emails(filtered_emails, perfil.id)

            _mostrar_resultados_procesamiento(stats)

        except (ConnectionError, TimeoutError) as e:
            st.error(f"Error de conexion: {e}")
            logger.error(f"Error de conexion procesando correos: {e}")
        except Exception as e:
            st.error(f"Error al procesar correos: {e}")
            logger.error(f"Error en procesamiento: {type(e).__name__}: {e}")


def _mostrar_resultados_procesamiento(stats: dict) -> None:
    """Muestra resultados del procesamiento de correos."""
    st.success("Proceso completado!")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Correos procesados", stats.get("total", 0))
    with col2:
        st.metric("Nuevas", stats.get("procesados", 0))
    with col3:
        st.metric("Auto-categorizadas", stats.get("categorizadas_automaticamente", 0))
    with col4:
        st.metric("Duplicadas", stats.get("duplicados", 0))

    st.markdown("---")
    st.markdown("### Detalles")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**BAC Credomatic:** {stats.get('bac', 0)}")
        st.markdown(f"**Banco Popular:** {stats.get('popular', 0)}")
    with col2:
        st.markdown(f"**USD convertidas:** {stats.get('usd_convertidos', 0)}")
        st.markdown(f"**Errores:** {stats.get('errores', 0)}")

    if stats.get("necesitan_revision", 0) > 0:
        st.warning(f"{stats['necesitan_revision']} transaccion(es) necesitan tu revision")
        st.info("Recarga la pagina para verlas")
    elif stats.get("procesados", 0) > 0:
        st.success("Todas las transacciones fueron categorizadas automaticamente")

    if st.button("Recargar Pagina"):
        st.rerun()


def revisar_transacciones(perfil: Profile, transacciones: list[Transaction]) -> None:
    """UI para revisar y categorizar transacciones pendientes."""
    st.info(f"Tienes **{len(transacciones)}** transaccion(es) para revisar")

    # Obtener subcategorias agrupadas
    with get_session() as session:
        subcategorias = session.query(Subcategory).all()
        por_categoria: dict[str, list[Subcategory]] = {}
        for subcat in subcategorias:
            cat_nombre = subcat.category.nombre
            if cat_nombre not in por_categoria:
                por_categoria[cat_nombre] = []
            por_categoria[cat_nombre].append(subcat)

    st.markdown("---")

    for i, tx in enumerate(transacciones, 1):
        _renderizar_transaccion(tx, i, len(transacciones), por_categoria, perfil)


def _renderizar_transaccion(
    tx: Transaction,
    indice: int,
    total: int,
    por_categoria: dict[str, list[Subcategory]],
    perfil: Profile,
) -> None:
    """Renderiza una transaccion individual para revision."""
    with st.container():
        st.subheader(f"Transaccion {indice}/{total}")

        # Info basica
        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(f"**Comercio:** {tx.comercio}")
            st.markdown(f"**Monto:** {tx.monto_display}")

        with col2:
            st.markdown(f"**Fecha:** {tx.fecha_transaccion.strftime('%d/%m/%Y %H:%M')}")
            banco_display = (
                tx.banco.value.upper() if hasattr(tx.banco, "value") else str(tx.banco).upper()
            )
            st.markdown(f"**Banco:** {banco_display}")

        with col3:
            tipo_display = (
                tx.tipo_transaccion.value
                if hasattr(tx.tipo_transaccion, "value")
                else tx.tipo_transaccion
            )
            st.markdown(f"**Tipo:** {tipo_display}")
            if tx.card:
                st.markdown(f"**Tarjeta:** {tx.card.nombre_display}")

        # Sugerencia IA
        if tx.categoria_sugerida_por_ia:
            confianza = (
                f" ({tx.confianza_categoria}%)"
                if hasattr(tx, "confianza_categoria") and tx.confianza_categoria
                else ""
            )
            st.info(f"**IA sugiere:** {tx.categoria_sugerida_por_ia}{confianza}")

        # Botones de categoria
        st.markdown("#### Selecciona la Categoria")
        categoria_seleccionada = _mostrar_botones_categoria(tx, por_categoria)

        # Boton aceptar sugerencia IA
        if tx.categoria_sugerida_por_ia:
            if st.button(
                "Aceptar Sugerencia IA",
                key=f"tx_{tx.id}_accept_ia",
                use_container_width=True,
                type="primary",
            ):
                _aceptar_sugerencia_ia(tx)

        # Formulario contexto si selecciono categoria
        if categoria_seleccionada:
            _mostrar_formulario_contexto(tx, categoria_seleccionada, perfil)

        st.markdown("---")


def _mostrar_botones_categoria(
    tx: Transaction, por_categoria: dict[str, list[Subcategory]]
) -> Subcategory | None:
    """Muestra botones de categoria y retorna la seleccionada."""
    col1, col2, col3 = st.columns(3)
    categoria_seleccionada = None

    with col1:
        st.markdown("**Necesidades**")
        if "Necesidades" in por_categoria:
            for subcat in por_categoria["Necesidades"]:
                if st.button(
                    f"{subcat.icono} {subcat.nombre}",
                    key=f"tx_{tx.id}_cat_{subcat.id}",
                    use_container_width=True,
                ):
                    categoria_seleccionada = subcat

    with col2:
        st.markdown("**Gustos**")
        if "Gustos" in por_categoria:
            for subcat in por_categoria["Gustos"]:
                if st.button(
                    f"{subcat.icono} {subcat.nombre}",
                    key=f"tx_{tx.id}_cat_{subcat.id}",
                    use_container_width=True,
                ):
                    categoria_seleccionada = subcat

    with col3:
        st.markdown("**Ahorros**")
        if "Ahorros" in por_categoria:
            for subcat in por_categoria["Ahorros"]:
                if st.button(
                    f"{subcat.icono} {subcat.nombre}",
                    key=f"tx_{tx.id}_cat_{subcat.id}",
                    use_container_width=True,
                ):
                    categoria_seleccionada = subcat

    return categoria_seleccionada


def _aceptar_sugerencia_ia(tx: Transaction) -> None:
    """Acepta la sugerencia de IA para una transaccion."""
    if "/" in tx.categoria_sugerida_por_ia:
        _, subcat_name = tx.categoria_sugerida_por_ia.split("/", 1)
    else:
        subcat_name = tx.categoria_sugerida_por_ia

    with get_session() as session:
        subcat = (
            session.query(Subcategory).filter(Subcategory.nombre == subcat_name.strip()).first()
        )
        if subcat:
            tx_db = session.query(Transaction).get(tx.id)
            tx_db.subcategory_id = subcat.id
            tx_db.necesita_revision = False
            session.commit()
            st.success(f"Categorizada como: {tx.categoria_sugerida_por_ia}")
            st.rerun()


def _mostrar_formulario_contexto(tx: Transaction, categoria: Subcategory, perfil: Profile) -> None:
    """Muestra formulario para agregar contexto a la transaccion."""
    st.markdown("---")
    st.markdown("#### Informacion Adicional _(opcional)_")

    with st.form(f"tx_{tx.id}_context_form"):
        contexto = st.text_area(
            "Contexto",
            placeholder="Ej: Compre con plata de mama, Gasto intermediario...",
            height=80,
            key=f"contexto_{tx.id}",
        )

        st.markdown("**Tipo de Gasto (opcional)**")

        patron = _buscar_patron_historico(tx.comercio, perfil.id)
        if patron:
            st.info(
                f"Patron detectado: Ultimas {patron['frecuencia']} veces marcaste '{tx.comercio}' de forma especial"
            )

        tipo_especial = st.selectbox(
            "Tipo:",
            options=list(TIPOS_GASTO_COMUNES.keys()),
            format_func=lambda x: TIPOS_GASTO_COMUNES[x],
            index=0,
            key=f"tipo_{tx.id}",
            help="Si es 'Otro', describe en el campo Contexto arriba",
        )

        # Auto-marcar "excluir" si es dinero ajeno, intermediaria o transferencia
        excluir_presupuesto = st.checkbox(
            "Excluir de presupuesto mensual",
            value=tipo_especial in ["dinero_ajeno", "intermediaria", "transferencia_propia"],
            key=f"excluir_{tx.id}",
            help="Marca esto si NO quieres que cuente para tu presupuesto mensual",
        )

        col1, col2 = st.columns(2)
        with col1:
            guardar_btn = st.form_submit_button("Guardar", type="primary", use_container_width=True)
        with col2:
            saltar_btn = st.form_submit_button("Saltar (sin contexto)", use_container_width=True)

        if guardar_btn:
            _guardar_transaccion_con_contexto(
                tx, categoria, contexto, tipo_especial, excluir_presupuesto
            )

        if saltar_btn:
            _guardar_transaccion_simple(tx, categoria)


def _guardar_transaccion_con_contexto(
    tx: Transaction,
    categoria: Subcategory,
    contexto: str,
    tipo_especial: str,
    excluir_presupuesto: bool,
) -> None:
    """Guarda transaccion con contexto y tipo especial."""
    try:
        with get_session() as session:
            tx_db = session.query(Transaction).get(tx.id)
            tx_db.subcategory_id = categoria.id
            tx_db.categoria_sugerida_por_ia = categoria.nombre_completo
            tx_db.necesita_revision = False
            tx_db.contexto = contexto.strip() if contexto and contexto.strip() else None
            tx_db.tipo_especial = tipo_especial if tipo_especial != "normal" else None
            tx_db.excluir_de_presupuesto = excluir_presupuesto
            session.commit()

            msg = f"Categorizada como: {categoria.nombre_completo}"
            if tipo_especial != "normal":
                msg += f" (tipo: {tipo_especial})"
            st.success(msg)

            if excluir_presupuesto:
                st.warning("Esta transaccion NO contara en tu presupuesto")

            st.rerun()
    except Exception as e:
        st.error(f"Error guardando transaccion: {e}")
        logger.error(f"Error guardando transaccion: {type(e).__name__}: {e}")


def _guardar_transaccion_simple(tx: Transaction, categoria: Subcategory) -> None:
    """Guarda transaccion sin contexto adicional."""
    try:
        with get_session() as session:
            tx_db = session.query(Transaction).get(tx.id)
            tx_db.subcategory_id = categoria.id
            tx_db.categoria_sugerida_por_ia = categoria.nombre_completo
            tx_db.necesita_revision = False
            session.commit()

            st.success(f"Categorizada como: {categoria.nombre_completo}")
            st.rerun()
    except Exception as e:
        st.error(f"Error guardando transaccion: {e}")
        logger.error(f"Error guardando transaccion: {type(e).__name__}: {e}")
