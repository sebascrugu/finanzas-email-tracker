"""Página de Preguntas Pendientes SINPE.

Permite al usuario responder preguntas sobre transacciones SINPE
que no tienen descripción clara (beneficiario desconocido, descripción
genérica, etc.)
"""

from decimal import Decimal

import streamlit as st

from finanzas_tracker.core.database import SessionLocal
from finanzas_tracker.models import (
    Category,
    PendingQuestion,
    Profile,
    Subcategory,
    Transaction,
)
from finanzas_tracker.models.enums import QuestionStatus
from finanzas_tracker.services.sinpe_reconciliation_service import (
    SinpeReconciliationService,
)


# Configuración de página
st.set_page_config(
    page_title="SINPE Pendientes - Finanzas Tracker",
    page_icon="❓",
    layout="wide",
)


def get_active_profile_id() -> str | None:
    """Obtiene el profile_id activo de la sesión o el primero activo."""
    if "profile_id" in st.session_state and st.session_state.profile_id:
        return st.session_state.profile_id
    
    db = SessionLocal()
    try:
        profile = db.query(Profile).filter(Profile.activo == True).first()
        if profile:
            st.session_state.profile_id = str(profile.id)
            return str(profile.id)
        return None
    finally:
        db.close()


def get_pending_questions(profile_id: str, limit: int = 20) -> list[PendingQuestion]:
    """Obtiene las preguntas pendientes para un perfil."""
    db = SessionLocal()
    try:
        questions = (
            db.query(PendingQuestion)
            .filter(
                PendingQuestion.profile_id == profile_id,
                PendingQuestion.status == QuestionStatus.PENDIENTE,
                PendingQuestion.deleted_at.is_(None),
            )
            .order_by(
                PendingQuestion.prioridad,
                PendingQuestion.monto_relacionado.desc(),
            )
            .limit(limit)
            .all()
        )
        # Detach from session
        for q in questions:
            db.expunge(q)
        return questions
    finally:
        db.close()


def get_transaction_for_question(question: PendingQuestion) -> Transaction | None:
    """Obtiene la transacción asociada a una pregunta."""
    if not question.transaction_id:
        return None
    
    db = SessionLocal()
    try:
        txn = db.query(Transaction).filter(
            Transaction.id == question.transaction_id
        ).first()
        if txn:
            db.expunge(txn)
        return txn
    finally:
        db.close()


def get_categories_for_profile(profile_id: str) -> list[tuple[str, str, str]]:
    """Obtiene categorías y subcategorías para el formulario.
    
    Returns:
        List of (subcategory_id, category_name, subcategory_name)
    """
    db = SessionLocal()
    try:
        results = []
        categories = (
            db.query(Category)
            .filter(Category.profile_id == profile_id, Category.deleted_at.is_(None))
            .all()
        )
        for cat in categories:
            subcats = (
                db.query(Subcategory)
                .filter(
                    Subcategory.category_id == cat.id,
                    Subcategory.deleted_at.is_(None),
                )
                .all()
            )
            for subcat in subcats:
                results.append((str(subcat.id), cat.nombre, subcat.nombre))
        return results
    finally:
        db.close()


def get_reconciliation_stats(profile_id: str) -> dict:
    """Obtiene estadísticas de reconciliación."""
    db = SessionLocal()
    try:
        service = SinpeReconciliationService(db)
        return service.obtener_resumen(profile_id)
    finally:
        db.close()


def process_answer(question_id: str, comercio: str, subcategory_id: str | None, notas: str | None) -> bool:
    """Procesa la respuesta del usuario."""
    db = SessionLocal()
    try:
        service = SinpeReconciliationService(db)
        
        # Obtener la pregunta
        question = db.query(PendingQuestion).filter(
            PendingQuestion.id == question_id
        ).first()
        
        if not question or not question.transaction_id:
            return False
        
        # Actualizar la transacción
        txn = db.query(Transaction).filter(
            Transaction.id == question.transaction_id
        ).first()
        
        if txn:
            txn.comercio = comercio
            txn.beneficiario = comercio
            txn.necesita_reconciliacion_sinpe = False
            if subcategory_id:
                txn.subcategory_id = subcategory_id
                txn.categoria_confirmada_usuario = True
            if notas:
                txn.notas = notas
        
        # Marcar pregunta como respondida
        question.status = QuestionStatus.RESPONDIDA
        question.respuesta = f"Comercio: {comercio}"
        
        db.commit()
        return True
    except Exception as e:
        db.rollback()
        st.error(f"Error procesando respuesta: {e}")
        return False
    finally:
        db.close()


def render_stats_header(stats: dict) -> None:
    """Renderiza el header con estadísticas."""
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Pendientes",
            stats.get("necesitan_reconciliacion", 0),
            delta=None,
            help="Transacciones SINPE que necesitan clarificación",
        )
    
    with col2:
        st.metric(
            "Reconciliadas",
            stats.get("ya_reconciliadas", 0),
            delta=None,
            help="Transacciones ya clarificadas",
        )
    
    with col3:
        monto = stats.get("monto_pendiente", Decimal("0"))
        st.metric(
            "Monto Pendiente",
            f"₡{monto:,.0f}",
            delta=None,
            help="Suma de transacciones pendientes",
        )
    
    with col4:
        pct = stats.get("porcentaje_reconciliado", 0)
        st.metric(
            "% Completado",
            f"{pct:.1f}%",
            delta=None,
            help="Porcentaje de transferencias reconciliadas",
        )


def render_question_card(
    question: PendingQuestion,
    transaction: Transaction | None,
    categories: list[tuple[str, str, str]],
    index: int,
) -> None:
    """Renderiza una tarjeta de pregunta con formulario."""
    # Determinar prioridad para el color del borde
    prioridad = question.prioridad if isinstance(question.prioridad, str) else question.prioridad.value
    
    # Color basado en monto
    if question.monto_relacionado and question.monto_relacionado > 50000:
        border_color = "#ff6b6b"  # Rojo para montos altos
    elif question.monto_relacionado and question.monto_relacionado > 10000:
        border_color = "#ffd93d"  # Amarillo para montos medios
    else:
        border_color = "#6bcb77"  # Verde para montos bajos
    
    with st.container():
        st.markdown(
            f"""
            <div style="
                border-left: 4px solid {border_color};
                padding: 10px 15px;
                margin-bottom: 10px;
                background-color: #f8f9fa;
                border-radius: 5px;
            ">
                <strong>₡{question.monto_relacionado:,.0f}</strong> 
                | Prioridad: {prioridad.upper()}
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Mostrar info de transacción si existe
        if transaction:
            col_info1, col_info2, col_info3 = st.columns(3)
            with col_info1:
                st.text(f"📅 {transaction.fecha_transaccion.strftime('%d/%m/%Y')}")
            with col_info2:
                st.text(f"🏪 Actual: {transaction.comercio or 'Sin comercio'}")
            with col_info3:
                st.text(f"📝 {transaction.notas or 'Sin notas'}")
        
        st.markdown(f"**❓ {question.pregunta}**")
        
        # Formulario de respuesta
        with st.form(key=f"form_{question.id}"):
            col1, col2 = st.columns(2)
            
            with col1:
                comercio_nuevo = st.text_input(
                    "¿A quién/dónde fue este pago?",
                    placeholder="Ej: Alquiler, Papá, Electricidad...",
                    key=f"comercio_{question.id}",
                )
            
            with col2:
                # Preparar opciones de categoría
                cat_options = ["(Sin categoría)"] + [
                    f"{cat} > {subcat}" for (_, cat, subcat) in categories
                ]
                cat_values = [None] + [subcat_id for (subcat_id, _, _) in categories]
                
                selected_cat = st.selectbox(
                    "Categoría (opcional)",
                    options=cat_options,
                    index=0,
                    key=f"cat_{question.id}",
                )
                
                # Obtener el subcategory_id correspondiente
                selected_idx = cat_options.index(selected_cat)
                subcategory_id = cat_values[selected_idx] if selected_idx > 0 else None
            
            notas = st.text_input(
                "Notas adicionales (opcional)",
                placeholder="Ej: Mes de noviembre, regalo cumpleaños...",
                key=f"notas_{question.id}",
            )
            
            submitted = st.form_submit_button(
                "✅ Guardar Respuesta",
                use_container_width=True,
                type="primary",
            )
            
            if submitted:
                if not comercio_nuevo.strip():
                    st.error("Debes indicar a quién o dónde fue el pago")
                else:
                    success = process_answer(
                        str(question.id),
                        comercio_nuevo.strip(),
                        subcategory_id,
                        notas.strip() if notas else None,
                    )
                    if success:
                        st.success("✅ Respuesta guardada!")
                        st.rerun()
        
        st.divider()


def render_sinpe_questions():
    """Renderiza la página principal de preguntas SINPE."""
    st.title("❓ Preguntas Pendientes SINPE")
    
    st.markdown("""
    Estas son transacciones SINPE que no tienen descripción clara.
    Responde cada pregunta para que el sistema pueda categorizar correctamente.
    """)
    
    # Obtener perfil activo
    profile_id = get_active_profile_id()
    
    if not profile_id:
        st.error("No hay un perfil activo. Ve a Configuración primero.")
        return
    
    st.divider()
    
    # Estadísticas
    stats = get_reconciliation_stats(profile_id)
    render_stats_header(stats)
    
    st.divider()
    
    # Botón para detectar nuevas transacciones ambiguas
    col_actions1, col_actions2, _ = st.columns([1, 1, 2])
    
    with col_actions1:
        if st.button("🔍 Buscar Nuevas", help="Analiza transacciones y crea nuevas preguntas"):
            with st.spinner("Analizando transacciones..."):
                db = SessionLocal()
                try:
                    service = SinpeReconciliationService(db)
                    
                    # Primero detectar transacciones ambiguas
                    marcadas = service.detectar_transacciones_ambiguas(profile_id)
                    
                    # Luego crear preguntas
                    creadas = service.analizar_transacciones_pendientes(profile_id)
                    
                    st.success(f"✅ Marcadas {marcadas} transacciones. Creadas {creadas} preguntas nuevas.")
                    st.rerun()
                finally:
                    db.close()
    
    with col_actions2:
        if st.button("🔄 Refrescar", help="Actualiza la lista de preguntas"):
            st.rerun()
    
    st.divider()
    
    # Obtener preguntas pendientes
    questions = get_pending_questions(profile_id, limit=20)
    categories = get_categories_for_profile(profile_id)
    
    if not questions:
        st.success("🎉 ¡No hay preguntas pendientes! Todas tus transacciones SINPE están claras.")
        
        # Mostrar resumen
        if stats.get("total_transferencias", 0) > 0:
            st.info(f"""
            **Resumen de Transferencias:**
            - Total: {stats.get('total_transferencias', 0)}
            - Reconciliadas: {stats.get('ya_reconciliadas', 0)}
            - Porcentaje: {stats.get('porcentaje_reconciliado', 0):.1f}%
            """)
        return
    
    st.subheader(f"📋 {len(questions)} Preguntas Pendientes")
    
    # Renderizar cada pregunta
    for i, question in enumerate(questions):
        transaction = get_transaction_for_question(question)
        render_question_card(question, transaction, categories, i)


# Ejecutar la página
if __name__ == "__main__":
    render_sinpe_questions()
else:
    render_sinpe_questions()
